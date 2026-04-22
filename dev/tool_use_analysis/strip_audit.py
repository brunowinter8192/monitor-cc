#!/usr/bin/env python3
"""Per-REQ delta audit for proxy strip verification.

Computes per-request deltas across five buckets (EFF / INERT / IDX / LEAK / SUS)
using rule-counter diffs and marker-based chunk attribution from strip_vocab.
Legend at report top; Delta-Log in compact BUCKET:RULE notation.

Input:  JSONL path (positional arg, optional — auto-picks newest
        src/logs/api_requests_opus_monitor_cc_*.jsonl when not given)
Output: dev/tool_use_analysis/<YYYYMMDDHHMM>_strip_audit.md
"""

# INFRASTRUCTURE

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Path insertion so "from proxy.strip_vocab import ..." resolves from dev/ script
_src_dir = os.path.join(
    os.environ.get('MONITOR_CC_ROOT', str(Path(__file__).parent.parent.parent)),
    'src',
)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from proxy.strip_vocab import (
    BUCKETS, RULES, TAG_LITERALS,
    attribute_chunk, classify_req as vocab_classify_req, code_for_rule,
    legend_markdown, STRIP_RULE_CODES,
)

# SR templates — mirrors src/proxy/strip_sr.py:_SR_TEMPLATES exactly
# Kept locally for _check_tags LEAK/SUSPECT template matching (audit-internal)
_SR_TEMPLATES = {
    'task-tools-nag':      ("The task tools haven't been used recently",                'full'),
    'pyright-diagnostics': ('<new-diagnostics>',                                        'full'),
    'deferred-tools':      ('The following deferred tools are now available via ToolSearch', 'full'),
    'user-interrupt':      ('The user sent a new message while you were working:',      'partial'),
    'system-notification': ('[SYSTEM NOTIFICATION - NOT USER INPUT]',                   'full'),
    'file-modified':       ('Note: ',                                                   'full'),
    'claudemd-contents':   ('Contents of ',                                             'full'),
    'date-changed':        ('The date has changed.',                                    'full'),
    'skills-available':    ('The following skills are available',                       'full'),
    'plan-mode':           ('Plan mode ',                                               'full'),
}

# Template ID → rule name as it appears in modifications[]
_TEMPLATE_TO_RULE = {
    'task-tools-nag':      'stripped_task_tools_nag',
    'pyright-diagnostics': 'stripped_pyright_diagnostics',
    'deferred-tools':      'stripped_deferred_tools_sr',
    'user-interrupt':      'stripped_user_interrupt_sr',
    'system-notification': 'stripped_all_sr_msg0',
    'file-modified':       'stripped_all_sr_msg0',
    'claudemd-contents':   'stripped_claudemd_sr',
    'date-changed':        'stripped_all_sr_msg0',
    'skills-available':    'stripped_skills_sr',
    'plan-mode':           'removed_plan_mode_sr',
}

# Non-SR tag literals for LEAK/SUSPECT detection
_TN_TAG = '<task-notification>'
_PO_TAG = '<persisted-output>'   # no active rule (rolled back) — always SUS

# Regex for SR block inner-text extraction
_SR_BLOCK_RE = re.compile(r'<system-reminder>(.*?)</system-reminder>', re.DOTALL)

CHUNK_HEAD = 120   # chars of chunk to display in report


# ORCHESTRATOR

def strip_audit_workflow(jsonl_path, output_path):
    entries, n_haiku, n_skipped = _load_entries(jsonl_path)
    lines = []
    lines += _build_header(jsonl_path, len(entries), n_haiku, n_skipped)
    lines.append(legend_markdown())
    lines += _build_rule_catalog()
    lines += _build_delta_log(entries)
    lines += _build_summary(entries)
    output_path.write_text('\n'.join(lines))
    print(output_path)


# FUNCTIONS

# Load and filter JSONL — keep only claude-opus-* entries in file order
def _load_entries(path):
    entries = []
    n_haiku = 0
    n_skipped = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                n_skipped += 1
                continue
            model = entry.get('model') or ''
            if model.startswith('claude-opus-'):
                entries.append(entry)
            elif model:
                n_haiku += 1  # any non-opus model (haiku, sonnet subagents)
            # null-model sent_meta entries: silently skipped
    return entries, n_haiku, n_skipped


# Build header section
def _build_header(jsonl_path, n_opus, n_haiku, n_skipped):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        f'# Strip Audit — {ts}',
        '',
        f'Source: `{Path(jsonl_path).name}`',
        f'Opus entries: {n_opus}  |  Non-opus (skipped): {n_haiku}'
        + (f'  |  Parse errors: {n_skipped}' if n_skipped else ''),
        '',
    ]
    return lines


# Build rule catalog section — deeper reference below the Legend
def _build_rule_catalog():
    lines = [
        '## Rule Catalog',
        '',
        '### SR Templates (src/proxy/strip_sr.py:_SR_TEMPLATES)',
        '| rule (modifications name) | template_id | identifier (startswith) | mode |',
        '|---|---|---|---|',
    ]
    for tid, (identifier, mode) in _SR_TEMPLATES.items():
        rule = _TEMPLATE_TO_RULE[tid]
        ident_display = identifier[:70] + ('…' if len(identifier) > 70 else '')
        lines.append(f'| `{rule}` | `{tid}` | `{ident_display}` | {mode} |')
    lines += [
        '',
        '### Non-SR Rules',
        '| rule | tag / literal | notes |',
        '|---|---|---|',
        '| `trimmed_task_notification` | `<task-notification>` | strips full TN block; chunk starts with TN tag |',
        '| `stripped_rejection_message` | `(rejection marker stripped by proxy)` | replaces rejection message with literal |',
        '| *(none — rolled back)* | `<persisted-output>` | no rule; always SUS |',
        '',
        '### Attribution Note',
        'Chunk→rule attribution inverts proxy capture logic: `_find_system_reminder_blocks(content, MARKER)` '
        'finds SR blocks containing MARKER anywhere. Attribution checks each chunk for marker substrings '
        'in priority order (see Legend). `stripped_all_sr_msg0` (Final-Pass) never writes '
        '`stripped_msg_removed` — always INERT or triggers IDX when the index has no tracked chunks.',
        '',
    ]
    return lines


# Build delta log section — one entry per opus REQ
def _build_delta_log(entries):
    lines = ['## Delta Log', '']
    prev = None
    for i, entry in enumerate(entries):
        cls = _classify_req(entry, prev)
        lines += _render_req_section(i + 1, entry, prev, cls)
        prev = entry
    return lines


# Classify one REQ into five buckets — delegates to vocab_classify_req for
# effective/inert/idx/unattributed; builds verbose tag_lines locally via _check_tags
# (audit needs raw_payload SR-block scanning; classify_tags uses monitor-format blocks)
def _classify_req(entry, prev):
    cls = vocab_classify_req(entry, prev)
    curr_mods_ctr = Counter(entry.get('modifications', []))
    tag_lines, n_leaks, n_suspects = _check_tags(entry, curr_mods_ctr)
    return {
        'effective':        cls['effective'],
        'inert':            cls['inert'],
        'indexed_no_chunks': cls['idx_msgs'],
        'tag_lines':        tag_lines,
        'n_leaks':          n_leaks,
        'n_suspects':       n_suspects,
        'unattributed':     cls['unattributed'],
    }


# Render one REQ block using compact BUCKET:RULE notation
def _render_req_section(req_num, entry, prev, cls):
    lines = []

    ts = _format_ts(entry.get('timestamp', ''))
    prev_mc = prev.get('message_count', 0) if prev else 0
    curr_mc = entry.get('message_count', 0)

    diff = entry.get('diff_from_prev', {})
    n_added    = diff.get('messages_added', 0)
    n_modified = diff.get('messages_modified', 0)
    first_idx  = diff.get('first_diff_index', '?')

    if n_added > 0:
        idx_list = ', '.join(f'+{first_idx + k}' for k in range(n_added))
        diff_str = f'[{idx_list}]'
    elif n_modified > 0:
        diff_str = f'[~{first_idx} modified ×{n_modified}]'
    else:
        diff_str = '[no new msgs]'

    lines.append(f'REQ #{req_num}  [{ts}]  msg_count={prev_mc}→{curr_mc}  diff={diff_str}')

    raw_messages = entry.get('raw_payload', {}).get('messages', [])

    for code in sorted(cls['effective']):
        by_idx = {}
        for idx, chunk in cls['effective'][code]:
            by_idx.setdefault(idx, []).append(chunk)
        for idx in sorted(by_idx):
            idx_chunks = by_idx[idx]
            n = len(idx_chunks)
            total_chars = sum(len(c) for c in idx_chunks)
            is_tr = _is_tool_result(raw_messages, idx)
            tool_name = _get_tool_name(raw_messages, idx) if is_tr else None
            tr_label = f' [tool_result:{tool_name}]' if tool_name else (' [tool_result]' if is_tr else '')
            chunk_word = 'chunks' if n != 1 else 'chunk'
            lines.append(f'  EFF:{code}  msg[{idx}]{tr_label}  {n} {chunk_word}  {total_chars:,}c')
            for ci, chunk in enumerate(idx_chunks):
                head = chunk[:CHUNK_HEAD].replace('\n', '↵').replace('\r', '')
                lines.append(f'    chunk[{ci}] "{head}"')

    for code in cls['inert']:
        lines.append(f'  INERT:{code}')

    for idx in cls['indexed_no_chunks']:
        is_tr = _is_tool_result(raw_messages, idx)
        tool_name = _get_tool_name(raw_messages, idx) if is_tr else None
        tr_label = f' [tool_result:{tool_name}]' if tool_name else (' [tool_result]' if is_tr else '')
        lines.append(f'  IDX  msg[{idx}]{tr_label}')

    lines += cls['tag_lines']

    if cls['unattributed']:
        for idx, chunk in cls['unattributed']:
            head = chunk[:CHUNK_HEAD].replace('\n', '↵').replace('\r', '')
            lines.append(f'  UNATTRIB  msg[{idx}] "{head}"')

    if not any([cls['effective'], cls['inert'], cls['indexed_no_chunks'],
                cls['tag_lines'], cls['unattributed']]):
        lines.append('  (no new strips, no suspect tags)')

    lines.append('')
    return lines


# Detect leaked/suspect tags in raw_payload; returns (lines, n_leaks, n_suspects)
# Lines use compact notation: LEAK:<SR>/CODE, SUS:<PO>, LEAK:<TN>, etc.
def _check_tags(entry, curr_mods_ctr):
    lines = []
    n_leaks = 0
    n_suspects = 0
    mods_set = set(curr_mods_ctr.keys())

    raw_messages = entry.get('raw_payload', {}).get('messages', [])
    texts = list(_extract_msg_texts(raw_messages))

    seen_tids = set()
    for text in texts:
        for m in _SR_BLOCK_RE.finditer(text):
            inner = m.group(1).strip()
            tid, _ = _match_template(inner)
            if tid is None:
                continue
            if tid in seen_tids:
                continue
            seen_tids.add(tid)
            rule = _TEMPLATE_TO_RULE[tid]
            code = code_for_rule(rule)
            code_sfx = f'/{code}' if code else f'/{rule}'
            head = inner[:80].replace('\n', '↵')
            if rule in mods_set:
                lines.append(f'  LEAK:<SR>{code_sfx}  "{head}"')
                n_leaks += 1
            else:
                lines.append(f'  SUS:<SR>{code_sfx}  "{head}"')
                n_suspects += 1

    for text in texts:
        if _TN_TAG in text:
            rule = 'trimmed_task_notification'
            if rule in mods_set:
                lines.append(f'  LEAK:<TN>')
                n_leaks += 1
            else:
                lines.append(f'  SUS:<TN>')
                n_suspects += 1
            break

    for text in texts:
        if _PO_TAG in text:
            lines.append(f'  SUS:<PO>')
            n_suspects += 1
            break

    return lines, n_leaks, n_suspects


# Build summary section
def _build_summary(entries):
    total = len(entries)
    n_effective_reqs = 0
    n_inert_firings = 0
    n_indexed_no_chunks = 0
    n_suspects = 0
    n_leaks = 0
    prev = None

    for entry in entries:
        cls = _classify_req(entry, prev)
        if cls['effective']:
            n_effective_reqs += 1
        n_inert_firings += len(cls['inert'])
        n_indexed_no_chunks += len(cls['indexed_no_chunks'])
        n_suspects += cls['n_suspects']
        n_leaks += cls['n_leaks']
        prev = entry

    return [
        '## Summary',
        '',
        f'- Total REQs (opus): {total}',
        f'- REQs with effective strips (EFF): {n_effective_reqs}',
        f'- Inert rule firings (INERT): {n_inert_firings}',
        f'- Indexed-no-chunks (IDX — Final-Pass tracking gap): {n_indexed_no_chunks}',
        f'- Suspect tags (SUS): {n_suspects} occurrences',
        f'- Leaked tags (LEAK): {n_leaks} occurrences',
        '',
    ]


# Extract all raw text strings from message content (various shapes)
def _extract_msg_texts(messages):
    for msg in messages:
        content = msg.get('content', '')
        if isinstance(content, str):
            yield content
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get('type')
                if btype == 'text':
                    yield block.get('text', '')
                elif btype == 'tool_result':
                    inner = block.get('content', '')
                    if isinstance(inner, str):
                        yield inner
                    elif isinstance(inner, list):
                        for sub in inner:
                            if isinstance(sub, dict) and sub.get('type') == 'text':
                                yield sub.get('text', '')


# Match SR inner text against templates; returns (template_id, mode) or (None, None)
def _match_template(inner):
    for tid, (identifier, mode) in _SR_TEMPLATES.items():
        if inner.startswith(identifier):
            return tid, mode
    return None, None


# Check whether message at idx in raw_payload is a tool_result
def _is_tool_result(messages, idx):
    if idx >= len(messages):
        return False
    msg = messages[idx]
    if msg.get('role') != 'user':
        return False
    content = msg.get('content', '')
    if isinstance(content, list):
        return any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in content)
    return False


# Find tool name by matching tool_use_id backward through messages
def _get_tool_name(messages, idx):
    if idx >= len(messages):
        return None
    content = messages[idx].get('content', [])
    if not isinstance(content, list):
        return None
    for block in content:
        if isinstance(block, dict) and block.get('type') == 'tool_result':
            tuid = block.get('tool_use_id')
            if not tuid:
                continue
            for prev_msg in reversed(messages[:idx]):
                for pb in (prev_msg.get('content', []) if isinstance(prev_msg.get('content'), list) else []):
                    if isinstance(pb, dict) and pb.get('type') == 'tool_use' and pb.get('id') == tuid:
                        return pb.get('name')
    return None


# Format UTC timestamp to local HH:MM:SS
def _format_ts(ts_raw):
    if not ts_raw:
        return '??:??:??'
    try:
        dt = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
        return dt.astimezone().strftime('%H:%M:%S')
    except Exception:
        return ts_raw[:8]


# Parse CLI args; auto-pick newest log when path is omitted
def _parse_args():
    parser = argparse.ArgumentParser(description='Per-REQ strip delta audit for proxy logs')
    parser.add_argument('jsonl', nargs='?', help='JSONL log path (auto-picks newest if omitted)')
    parser.add_argument('--output', help='Output MD path (auto-generated if omitted)')
    args = parser.parse_args()

    if args.jsonl:
        jsonl_path = Path(args.jsonl)
        if not jsonl_path.exists():
            print(f'ERROR: {jsonl_path} not found', file=sys.stderr)
            sys.exit(1)
    else:
        candidates = sorted(
            Path('src/logs').glob('api_requests_opus_monitor_cc_*.jsonl'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            print('ERROR: no api_requests_opus_monitor_cc_*.jsonl in src/logs/', file=sys.stderr)
            sys.exit(1)
        jsonl_path = candidates[0]

    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime('%Y%m%d%H%M')
        output_path = Path(f'dev/tool_use_analysis/{ts}_strip_audit.md')

    return jsonl_path, output_path


if __name__ == '__main__':
    jsonl_path, output_path = _parse_args()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    strip_audit_workflow(jsonl_path, output_path)
