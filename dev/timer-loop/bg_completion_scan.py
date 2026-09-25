# INFRASTRUCTURE
import html
import re
import json
from collections import Counter

from src.proxy.strip_sn_notice import _SN_NOTICE_MARKER, _SN_NOTICE_PARAGRAPH
from src.proxy.strip_bg_completed import _BG_CMD_MARKER, _BG_EXIT_RE
from src.proxy.payload_helpers import (
    _find_task_notification_blocks,
    _extract_task_notification_task_id,
    _extract_task_notification_output_file,
)

EXCLUDED_FILES = {
    'api_requests_worker_85d6f25b_timer-loop_1786044804_original.jsonl':
        "this worker's own live worktree session — growing during this investigation, "
        'self-contaminated by Read dumps of payload_helpers.py / message_passes.py / '
        'strip_sn_notice.py (their docstrings and regex literals contain the exact tag '
        'strings being measured here)',
}

_TASK_ID_TAG_RE = re.compile(r'<task-id>(.*?)</task-id>', re.DOTALL)
_STATUS_TAG_RE = re.compile(r'<status>(.*?)</status>', re.DOTALL)
_SUMMARY_TAG_RE = re.compile(r'<summary>(.*?)</summary>', re.DOTALL)
_EXIT_CODE_RE = re.compile(r'exit code (\d+)')
_CMD_QUOTE_RE = re.compile(r'"([^"]*)"')
_CANONICAL_TIMER_CMD = 'sleep 3300 && echo done'


# FUNCTIONS

def _iter_candidate_blocks(content):
    if isinstance(content, str):
        yield ('top_level_str', content)
        return
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get('type')
            if btype == 'text':
                yield ('text_block', block.get('text', ''))
            elif btype == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    yield ('tool_result_str', inner)
                elif isinstance(inner, list):
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            yield ('tool_result_list_text', sub.get('text', ''))


def _looks_like_tn_candidate(text, role):
    if not isinstance(text, str):
        return False
    stripped = text.lstrip()
    if stripped.startswith(_SN_NOTICE_PARAGRAPH) and '<task-notification>' in text:
        return True
    if role == 'system' and stripped.startswith('<task-notification>'):
        return True
    return False


def _looks_like_bare_candidate(text):
    return isinstance(text, str) and text.lstrip().startswith(_BG_CMD_MARKER)


def _normalize_summary(summary):
    return _CMD_QUOTE_RE.sub('"<CMD>"', summary, count=1)


def _is_canonical_timer_command(raw_command):
    return html.unescape(raw_command).strip() == _CANONICAL_TIMER_CMD


def _scan_file(path, findings, cmd_variant_counts, raw_dup_counter, bare_hits, session_is_worker):
    session = path.name
    is_worker = 'worker' in session
    session_is_worker[session] = is_worker
    seen_tn_blocks = set()
    seen_bare_texts = set()
    requests = 0
    parse_errors = 0
    with open(path, 'rb') as fh:
        for raw in fh:
            requests += 1
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            messages = entry.get('payload', {}).get('messages', [])
            for msg in messages:
                role = msg.get('role', '?')
                content = msg.get('content', '')
                for shape, text in _iter_candidate_blocks(content):
                    if _looks_like_tn_candidate(text, role):
                        raw_dup_counter[session] += 1
                        for tag_block in _find_task_notification_blocks(text):
                            if tag_block in seen_tn_blocks:
                                continue
                            seen_tn_blocks.add(tag_block)
                            _record_tn_event(tag_block, text, session, is_worker, shape, role,
                                              findings, cmd_variant_counts)
                    elif _looks_like_bare_candidate(text):
                        bare_hits[session] += 1
                        if text not in seen_bare_texts:
                            seen_bare_texts.add(text)
    return requests, parse_errors


def _record_tn_event(tag_block, full_text, session, is_worker, shape, role, findings, cmd_variant_counts):
    status_m = _STATUS_TAG_RE.search(tag_block)
    summary_m = _SUMMARY_TAG_RE.search(tag_block)
    status = status_m.group(1).strip() if status_m else '<NO-STATUS-TAG>'
    summary = summary_m.group(1).strip() if summary_m else '<NO-SUMMARY-TAG>'
    exit_m = _EXIT_CODE_RE.search(summary)
    exit_code = exit_m.group(1) if exit_m else '<NO-EXIT-CODE>'
    norm_summary = _normalize_summary(summary)
    key = (status, exit_code, norm_summary)
    rec = findings.setdefault(key, {
        'count': 0, 'main_sessions': set(), 'worker_sessions': set(), 'shapes': set(),
        'roles': set(), 'example_tag_block': tag_block, 'example_full_text': full_text,
        'session_counts': Counter(),
    })
    rec['count'] += 1
    rec['session_counts'][session] += 1
    (rec['worker_sessions'] if is_worker else rec['main_sessions']).add(session)
    rec['shapes'].add(shape)
    rec['roles'].add(role)

    cmd_m = _CMD_QUOTE_RE.search(summary)
    cmd_text = cmd_m.group(1) if cmd_m else '<NO-CMD>'
    variant_key = (status, exit_code)
    bucket = cmd_variant_counts.setdefault(variant_key, {'canonical_timer': 0, 'other': 0, 'examples': Counter()})
    if _is_canonical_timer_command(cmd_text):
        bucket['canonical_timer'] += 1
    else:
        bucket['other'] += 1
    bucket['examples'][cmd_text] += 1


def _mechanism_verdict(tag_block, full_text):
    marker_fires = _SN_NOTICE_MARKER in full_text
    tag_fires = '<task-notification>' in full_text
    task_id = _extract_task_notification_task_id(tag_block)
    output_file = _extract_task_notification_output_file(tag_block)
    return {
        'sn_marker_fires': marker_fires,
        'tn_tag_contains_fires': tag_fires,
        'task_id_extract': task_id or None,
        'output_file_extract': output_file or None,
    }
