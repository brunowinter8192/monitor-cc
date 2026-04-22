#!/usr/bin/env python3
"""Per-REQ delta audit for proxy strip verification.

Computes per-request deltas (newly-stripped messages, new rule firings,
leaked/suspect tags) instead of repeating the full accumulated state.

Input:  JSONL path (positional arg, optional — auto-picks newest
        src/logs/api_requests_opus_monitor_cc_*.jsonl when not given)
Output: dev/tool_use_analysis/<YYYYMMDDHHMM>_strip_audit.md
"""

# INFRASTRUCTURE

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# SR templates — mirrors src/proxy/strip_sr.py:_SR_TEMPLATES exactly
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
# Derived from rules.py/addon.py modifications.append() calls
_TEMPLATE_TO_RULE = {
    'task-tools-nag':      'stripped_task_tools_nag',
    'pyright-diagnostics': 'stripped_pyright_diagnostics',
    'deferred-tools':      'stripped_deferred_tools_sr',
    'user-interrupt':      'stripped_user_interrupt_sr',
    'system-notification': 'stripped_all_sr_msg0',   # catch-all final pass
    'file-modified':       'stripped_all_sr_msg0',   # catch-all final pass
    'claudemd-contents':   'stripped_claudemd_sr',
    'date-changed':        'stripped_all_sr_msg0',   # catch-all final pass
    'skills-available':    'stripped_skills_sr',
    'plan-mode':           'removed_plan_mode_sr',
}

# Baseline rules that fire on every opus request (not interesting as deltas on their own)
_BASELINE_RULES = frozenset({
    'replaced_system_prompt', 'stripped_session_guidance', 'stripped_git_status',
    'injected_mcp_tools', 'stripped_sys3', 'injected_model_override',
    'stripped_deferred_tools_sr', 'stripped_skills_sr', 'stripped_claudemd_sr',
})

# Non-SR tags for leak/suspect detection
_TN_TAG = '<task-notification>'
_PO_TAG = '<persisted-output>'   # no active rule (rolled back) — always SUSPECT

# Regex for SR block inner-text extraction on raw Python strings
_SR_BLOCK_RE = re.compile(r'<system-reminder>(.*?)</system-reminder>', re.DOTALL)

CHUNK_HEAD = 120   # chars of chunk to display in report


# ORCHESTRATOR

def strip_audit_workflow(jsonl_path, output_path):
    entries, n_haiku, n_skipped = _load_entries(jsonl_path)
    lines = []
    lines += _build_header(jsonl_path, len(entries), n_haiku, n_skipped)
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


# Build rule catalog section
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
        '| rule | tag | notes |',
        '|---|---|---|',
        '| `trimmed_task_notification` | `<task-notification>` | strips full TN block |',
        '| *(none — rolled back)* | `<persisted-output>` | no rule; always SUSPECT |',
        '',
    ]
    return lines


# Build delta log section — one entry per opus REQ
def _build_delta_log(entries):
    lines = ['## Delta Log', '']
    prev = None
    for i, entry in enumerate(entries):
        lines += _build_req_section(i + 1, entry, prev)
        prev = entry
    return lines


# Build one REQ block
def _build_req_section(req_num, entry, prev):
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

    # --- delta computation ---
    prev_stripped_set  = set(prev.get('stripped_msg_indices', [])) if prev else set()
    curr_stripped_set  = set(entry.get('stripped_msg_indices', []))
    new_stripped       = curr_stripped_set - prev_stripped_set

    prev_mods_ctr = Counter(prev.get('modifications', [])) if prev else Counter()
    curr_mods_ctr = Counter(entry.get('modifications', []))
    new_mods = {
        rule: curr_mods_ctr[rule] - prev_mods_ctr.get(rule, 0)
        for rule in curr_mods_ctr
        if curr_mods_ctr[rule] > prev_mods_ctr.get(rule, 0)
    }

    raw_messages = entry.get('raw_payload', {}).get('messages', [])
    stripped_removed = entry.get('stripped_msg_removed', {})

    # --- new rules (first time ever) ---
    for rule in sorted(new_mods):
        if rule not in prev_mods_ctr and rule not in _BASELINE_RULES:
            lines.append(f'  NEW RULE: {rule} (first fired this REQ, ×{new_mods[rule]})')

    # --- strip events for newly-stripped message indices ---
    for idx in sorted(new_stripped):
        chunks = stripped_removed.get(str(idx), [])
        is_tr = _is_tool_result(raw_messages, idx)
        tool_name = _get_tool_name(raw_messages, idx) if is_tr else None
        tr_label = f' [tool_result:{tool_name}]' if tool_name else (' [tool_result]' if is_tr else '')

        if not chunks:
            lines.append(f'  NEW STRIP msg[{idx}]{tr_label}: (no chunk data in stripped_msg_removed)')
        else:
            for ci, chunk in enumerate(chunks):
                rule_id, mode = _classify_chunk(chunk)
                head = chunk[:CHUNK_HEAD].replace('\n', '↵').replace('\r', '')
                lines.append(f'  NEW STRIP msg[{idx}]{tr_label}: {rule_id} (mode={mode})')
                lines.append(f'    chunk[{ci}] head="{head}"')

        if is_tr:
            tname = tool_name or 'tool'
            lines.append(f'    ⚠ SUSPECT FALSE POSITIVE: {tname} tool_result stripped — may be source code')

    # --- tag leak/suspect detection in raw_payload ---
    tag_lines, _, _ = _check_tags(entry, curr_mods_ctr)
    lines += tag_lines

    if not new_stripped and not tag_lines:
        lines.append('  (no new strips, no suspect tags)')

    lines.append('')
    return lines


# Detect leaked/suspect tags in raw_payload messages; returns (lines, n_leaks, n_suspects)
def _check_tags(entry, curr_mods_ctr):
    lines = []
    n_leaks = 0
    n_suspects = 0
    mods_set = set(curr_mods_ctr.keys())

    raw_messages = entry.get('raw_payload', {}).get('messages', [])
    texts = list(_extract_msg_texts(raw_messages))

    # --- SR blocks: find, match template, classify ---
    seen_tids = set()
    for text in texts:
        for m in _SR_BLOCK_RE.finditer(text):
            inner = m.group(1).strip()
            tid, _ = _match_template(inner)
            if tid is None:
                continue          # unrecognized SR — intentional non-strip, skip
            if tid in seen_tids:
                continue          # deduplicate per template per REQ
            seen_tids.add(tid)
            rule = _TEMPLATE_TO_RULE[tid]
            head = inner[:80].replace('\n', '↵')
            if rule in mods_set:
                lines.append(f'  ⚠ LEAK: <system-reminder> ({tid}) still in raw_payload — rule `{rule}` fired but tag survived')
                lines.append(f'    inner head="{head}"')
                n_leaks += 1
            else:
                lines.append(f'  ⚠ SUSPECT: <system-reminder> ({tid}) in raw_payload — rule `{rule}` did not fire')
                lines.append(f'    inner head="{head}"')
                n_suspects += 1

    # --- <task-notification> ---
    for text in texts:
        if _TN_TAG in text:
            rule = 'trimmed_task_notification'
            if rule in mods_set:
                lines.append(f'  ⚠ LEAK: {_TN_TAG} still in raw_payload after `{rule}` fired')
                n_leaks += 1
            else:
                lines.append(f'  ⚠ SUSPECT: {_TN_TAG} in raw_payload — `{rule}` did not fire')
                n_suspects += 1
            break  # one flag per REQ

    # --- <persisted-output>: always SUSPECT (no active rule) ---
    for text in texts:
        if _PO_TAG in text:
            lines.append(f'  ⚠ SUSPECT: {_PO_TAG} in raw_payload — no strip rule (rolled back)')
            n_suspects += 1
            break  # one flag per REQ

    return lines, n_leaks, n_suspects


# Build summary section (second pass over entries)
def _build_summary(entries):
    total = len(entries)
    n_new_strip_reqs = 0
    n_suspects = 0
    n_leaks = 0
    n_fp = 0
    prev = None

    for entry in entries:
        prev_stripped = set(prev.get('stripped_msg_indices', [])) if prev else set()
        curr_stripped = set(entry.get('stripped_msg_indices', []))
        new_stripped  = curr_stripped - prev_stripped

        if new_stripped:
            n_new_strip_reqs += 1

        raw_messages = entry.get('raw_payload', {}).get('messages', [])
        for idx in new_stripped:
            if _is_tool_result(raw_messages, idx):
                n_fp += 1

        curr_mods_ctr = Counter(entry.get('modifications', []))
        _, nl, ns = _check_tags(entry, curr_mods_ctr)
        n_leaks   += nl
        n_suspects += ns

        prev = entry

    return [
        '## Summary',
        '',
        f'- Total REQs (opus): {total}',
        f'- REQs with new strips: {n_new_strip_reqs}',
        f'- Suspect tags (no rule fired): {n_suspects} occurrences',
        f'- Leaked tags (rule fired, tag survived): {n_leaks} occurrences',
        f'- False-positive candidates (tool_result stripped): {n_fp}',
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


# Classify a removed chunk → (rule_id, mode)
def _classify_chunk(chunk):
    if chunk.startswith(_TN_TAG):
        return 'trimmed_task_notification', 'full'
    # Try full SR block match (has both open + close tags)
    m = _SR_BLOCK_RE.search(chunk)
    if m:
        # Decode literal \n (two-char escape stored in JSONL) before stripping
        inner = m.group(1).replace('\\n', '\n').strip()
    elif '<system-reminder>' in chunk:
        # Truncated/partial chunk — JSONL stored only the head of the SR block.
        # Extract inner text best-effort: everything after <system-reminder>.
        # Handle both real newlines and literal \n (two-char escape) from stored content.
        after_open = chunk.split('<system-reminder>', 1)[1]
        inner = after_open.replace('\\n', '\n').strip()
    else:
        # No SR/TN wrapper — plain text removal (e.g. rejection marker)
        return 'unknown (no SR/TN wrapper)', 'unknown'
    tid, mode = _match_template(inner)
    if tid:
        return _TEMPLATE_TO_RULE[tid], mode
    return 'stripped_all_sr_msg0 (unrecognized template)', 'unknown'


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
