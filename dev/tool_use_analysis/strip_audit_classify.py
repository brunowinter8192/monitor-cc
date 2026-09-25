# INFRASTRUCTURE
import json
import os
import sys
from collections import Counter
from pathlib import Path

_root_dir = os.environ.get('MONITOR_CC_ROOT', str(Path(__file__).parent.parent.parent))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from src.proxy.strip_vocab import RULES, classify_req as vocab_classify_req
from src.proxy.strip_sr import _SR_TEMPLATES, _PRESERVE_PREAMBLE

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

_TN_TAG = '<task-notification>'
_ND_TAG = '<new-diagnostics>'
_PO_TAG = '<persisted-output>'

_SR_STRIP_RULE_NAMES: frozenset = frozenset(
    fn for code, (fn, _) in RULES.items() if code not in ('TN',)
)

# FUNCTIONS

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
                n_haiku += 1
    return entries, n_haiku, n_skipped


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


def _attribute_sr_inner(inner):
    for code, (_fn, markers) in RULES.items():
        if code in ('TN', 'ALL'):
            continue
        for marker in markers:
            if marker in inner:
                return code
    return None


def _tag_strip_in_delta(smr, start, tag: str) -> bool:
    for idx_str, chunks in smr.items():
        if int(idx_str) < start:
            continue
        for chunk in (chunks or []):
            if tag in chunk:
                return True
    return False


def _check_sr_tags(texts, smr, start):
    lines = []
    n_leaks = 0
    n_suspects = 0
    seen_sr: set = set()
    for text in texts:
        pos = 0
        while True:
            idx = text.find('<system-reminder>', pos)
            if idx == -1:
                break
            after = idx + len('<system-reminder>')
            close_idx = text.find('</system-reminder>', after)
            if close_idx != -1:
                inner = text[after:close_idx].strip()
            else:
                inner = None
            if inner is not None and inner.startswith(_PRESERVE_PREAMBLE):
                pos = after
                continue
            head_text = text[after:after + 80].strip()
            code = _attribute_sr_inner(inner if inner is not None else head_text)
            dedup_key = (code, head_text[:30])
            if dedup_key not in seen_sr:
                seen_sr.add(dedup_key)
                head = head_text[:80].replace('\n', '↵')
                code_sfx = f'/{code}' if code is not None else '/?'
                if _tag_strip_in_delta(smr, start, '<system-reminder>'):
                    lines.append(f'  LEAK:<SR>{code_sfx}  "{head}"')
                    n_leaks += 1
                else:
                    lines.append(f'  SUS:<SR>{code_sfx}  "{head}"')
                    n_suspects += 1
            pos = after
    return lines, n_leaks, n_suspects


def _check_simple_tag(texts, smr, start, tag, label):
    for text in texts:
        if tag in text:
            if _tag_strip_in_delta(smr, start, tag):
                return [f'  LEAK:<{label}>'], 1, 0
            return [f'  SUS:<{label}>'], 0, 1
    return [], 0, 0


def _check_tags(entry, curr_mods_ctr):
    raw_messages = entry.get('raw_payload', {}).get('messages', [])
    diff = entry.get('diff_from_prev') or {}
    start = diff.get('first_diff_index', 0) if diff else 0
    if start < 0:
        return [], 0, 0
    texts = list(_extract_msg_texts(raw_messages[start:]))
    smr = entry.get('stripped_msg_removed') or {}

    sr_lines, sr_leaks, sr_susp = _check_sr_tags(texts, smr, start)
    tn_lines, tn_leaks, tn_susp = _check_simple_tag(texts, smr, start, _TN_TAG, 'TN')
    nd_lines, nd_leaks, nd_susp = _check_simple_tag(texts, smr, start, _ND_TAG, 'ND')
    po_hit = any(_PO_TAG in text for text in texts)
    po_lines = ['  SUS:<PO>'] if po_hit else []
    po_susp = 1 if po_hit else 0

    lines = sr_lines + tn_lines + nd_lines + po_lines
    n_leaks = sr_leaks + tn_leaks + nd_leaks
    n_suspects = sr_susp + tn_susp + nd_susp + po_susp
    return lines, n_leaks, n_suspects


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
                elif btype == 'tool_use':
                    name = block.get('name', '?')
                    inp = block.get('input', {})
                    yield name + '\n' + json.dumps(inp)


def _match_template(inner):
    if inner.startswith(_PRESERVE_PREAMBLE):
        return None, None
    for tid, spec in _SR_TEMPLATES.items():
        identifiers = spec[0] if isinstance(spec[0], list) else [spec[0]]
        mode = spec[1]
        for identifier in identifiers:
            if inner.startswith(identifier):
                return tid, mode
    return None, None
