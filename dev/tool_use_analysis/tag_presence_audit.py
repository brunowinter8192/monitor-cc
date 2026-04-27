#!/usr/bin/env python3
"""Tag presence audit: per-REQ delta-scoped scan for leftover SR/TN/ND/PO tags in raw_payload.

For each opus REQ with tag occurrences in its delta range, reports:
  - Full content of each leftover tag block with no truncation
  - stripped_msg_removed entries for the same delta range
  - Whether each SR was stripped (captured) or bypassed

Aggregate: per-tag-type counts and per-SR-template bypass_rate table.

Input:  JSONL path (positional, optional) — auto-picks newest api_requests_opus_monitor_cc_*.jsonl
Output: dev/tool_use_analysis/<YYYYMMDDHHMM>_tag_presence_audit.md
"""

# INFRASTRUCTURE

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Mirror of _SR_TEMPLATES from src/proxy/strip_sr.py (copy — no proxy/ import needed here)
_SR_TEMPLATES = {
    'task-tools-nag':      ("The task tools haven't been used recently",                  'full'),
    'pyright-diagnostics': ('<new-diagnostics>',                                          'full'),
    'deferred-tools':      ('The following deferred tools are now available via ToolSearch', 'full'),
    'user-interrupt':      ('The user sent a new message while you were working:',        'partial'),
    'system-notification': ('[SYSTEM NOTIFICATION - NOT USER INPUT]',                     'full'),
    'file-modified':       ('Note: ',                                                     'full'),
    'claudemd-contents':   (["As you answer the user's questions", 'Contents of '],       'full'),
    'date-changed':        ('The date has changed.',                                      'full'),
    'skills-available':    ('The following skills are available',                         'full'),
    'plan-mode':           ('Plan mode ',                                                 'full'),
}

# Preserved preamble: SR blocks starting with this are kept by design (CLAUDE.md context delivery)
_PRESERVE_PREAMBLE = "As you answer the user's questions, you can use the following context:"

# Standalone SR block regex (line-anchored) — used only for scanning stripped_msg_removed chunks
_STANDALONE_SR_RE = re.compile(r'(?m)^<system-reminder>(.*?)</system-reminder>', re.DOTALL)

# Non-SR tag literals
_TN_TAG = '<task-notification>'
_ND_TAG = '<new-diagnostics>'
_PO_TAG = '<persisted-output>'

# Resolve log directory — handles both main repo and worktree execution
_script_dir = Path(__file__).resolve().parent          # dev/tool_use_analysis/
_repo_candidate = _script_dir.parent.parent            # worktree or main root
if (_repo_candidate / 'src' / 'logs').is_dir():
    _LOGS_DIR = _repo_candidate / 'src' / 'logs'
else:
    # Worktree case: root/.claude/worktrees/<name>/ → root is 3 levels up
    _main_repo = _repo_candidate.parent.parent.parent
    _LOGS_DIR = _main_repo / 'src' / 'logs'


# ORCHESTRATOR

def tag_presence_audit_workflow(jsonl_path, output_path):
    blocks, tag_counts, sr_bypassed, sr_captured, n_opus, n_reqs_with_tags, n_non_opus = (
        _stream_and_audit(jsonl_path)
    )
    lines = _build_report(
        jsonl_path, blocks, tag_counts, sr_bypassed, sr_captured,
        n_opus, n_reqs_with_tags, n_non_opus,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('\n'.join(lines))
    print(output_path)


# FUNCTIONS

# Stream JSONL, accumulate aggregate counters, buffer only tag-positive REQ blocks
def _stream_and_audit(jsonl_path):
    blocks = []
    tag_counts = {'SR': 0, 'TN': 0, 'ND': 0, 'PO': 0}
    sr_bypassed = {tid: 0 for tid in _SR_TEMPLATES}
    sr_captured = {tid: 0 for tid in _SR_TEMPLATES}
    n_opus = 0
    n_reqs_with_tags = 0
    n_non_opus = 0
    prev = None
    req_num = 0

    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            model = entry.get('model') or ''
            if not model.startswith('claude-opus-'):
                if model:
                    n_non_opus += 1
                continue
            n_opus += 1
            req_num += 1

            block_lines, tc_d, byp_d, cap_d, has_tags = _scan_entry(entry, prev, req_num)

            for k in tag_counts:
                tag_counts[k] += tc_d[k]
            for tid in _SR_TEMPLATES:
                sr_bypassed[tid] += byp_d[tid]
                sr_captured[tid] += cap_d[tid]

            if has_tags:
                n_reqs_with_tags += 1
                blocks.extend(block_lines)

            prev = entry

    return blocks, tag_counts, sr_bypassed, sr_captured, n_opus, n_reqs_with_tags, n_non_opus


# Scan one opus REQ for tag occurrences in delta range and captured SR in stripped_msg_removed
def _scan_entry(entry, prev, req_num):
    messages = entry.get('raw_payload', {}).get('messages', [])
    diff = entry.get('diff_from_prev') or {}
    start = diff.get('first_diff_index')
    if not isinstance(start, int) or start < 0:
        start = 0

    prev_mc = prev.get('message_count', 0) if prev else 0
    curr_mc = entry.get('message_count', 0)
    ts = _format_ts(entry.get('timestamp', ''))

    tag_occurrences = []  # list of (header_line, content_lines)
    tc = {'SR': 0, 'TN': 0, 'ND': 0, 'PO': 0}
    byp = {tid: 0 for tid in _SR_TEMPLATES}
    seen = set()  # dedup within REQ

    for abs_idx in range(start, len(messages)):
        for layer, text in _iter_msg_text_with_layer(messages, abs_idx):
            if not text:
                continue

            # SR scan — substring loop handles non-line-start occurrences in tool_result strings
            pos = 0
            while True:
                si = text.find('<system-reminder>', pos)
                if si == -1:
                    break
                after = si + len('<system-reminder>')
                ci = text.find('</system-reminder>', after)
                if ci != -1:
                    inner = text[after:ci].strip()
                else:
                    inner = text[after:after + 500].strip()

                if inner.startswith(_PRESERVE_PREAMBLE):
                    pos = after
                    continue

                dedup_key = (abs_idx, layer, inner[:100])
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    tid, _ = _match_template(inner)
                    tid_str = f'/{tid}' if tid else '/?'
                    tool_label = _make_tool_label(messages, abs_idx)
                    header = f'  <SR>{tid_str}  msg[{abs_idx}]{tool_label}  layer={layer}'
                    content_lines = _indent_lines(inner, 4)
                    tag_occurrences.append((header, content_lines))
                    tc['SR'] += 1
                    if tid:
                        byp[tid] += 1

                pos = after

            # Non-SR tag scans (TN / ND / PO)
            for tag_type, tag_str in (('TN', _TN_TAG), ('ND', _ND_TAG), ('PO', _PO_TAG)):
                if tag_str in text:
                    dk = (abs_idx, layer, tag_type)
                    if dk not in seen:
                        seen.add(dk)
                        tool_label = _make_tool_label(messages, abs_idx)
                        header = f'  <{tag_type}>  msg[{abs_idx}]{tool_label}  layer={layer}'
                        content_lines = _context_neighborhood(text, tag_str, 4)
                        tag_occurrences.append((header, content_lines))
                        tc[tag_type] += 1

    # Scan stripped_msg_removed for captured SR (always, for aggregate accuracy)
    smr = entry.get('stripped_msg_removed') or {}
    cap = {tid: 0 for tid in _SR_TEMPLATES}
    delta_keys = sorted([k for k in smr if int(k) >= start], key=int)
    stripped_lines = []

    for idx_str in delta_keys:
        abs_idx = int(idx_str)
        chunks = smr[idx_str] or []
        if not chunks:
            continue
        tool_label = _make_tool_label(messages, abs_idx)
        stripped_lines.append(f'  STRIPPED msg[{abs_idx}]{tool_label}:')
        for ci, chunk in enumerate(chunks):
            stripped_lines.append(f'    chunk[{ci}]:')
            for cline in chunk.splitlines():
                stripped_lines.append(f'      {cline}')
        for chunk in chunks:
            for inner in _find_sr_inners(chunk):
                tid, _ = _match_template(inner)
                if tid:
                    cap[tid] += 1

    if not stripped_lines:
        stripped_lines = ['  STRIPPED (none in delta)']

    has_tags = bool(tag_occurrences)
    if not has_tags:
        return [], tc, byp, cap, False

    # Build REQ block
    block_lines = [
        f'### REQ #{req_num}  [{ts}]  msg_count={prev_mc}→{curr_mc}  delta_start={start}',
        '',
    ]
    for header, content_lines in tag_occurrences:
        block_lines.append(header)
        block_lines.extend(content_lines)
        block_lines.append('')
    block_lines.extend(stripped_lines)
    block_lines += ['', '---', '']

    return block_lines, tc, byp, cap, True


# Yield (layer_label, text) for all text content in messages[abs_idx]
def _iter_msg_text_with_layer(messages, abs_idx):
    if abs_idx >= len(messages):
        return
    msg = messages[abs_idx]
    content = msg.get('content', '')
    if isinstance(content, str):
        if content:
            yield 'plain_str', content
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get('type')
            if btype == 'text':
                t = block.get('text', '')
                if t:
                    yield 'text', t
            elif btype == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    if inner:
                        yield 'tool_result_str', inner
                elif isinstance(inner, list):
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            t = sub.get('text', '')
                            if t:
                                yield 'tool_result_nested', t
            elif btype == 'tool_use':
                name = block.get('name', '?')
                inp = block.get('input', {})
                yield 'tool_use', name + '\n' + json.dumps(inp)


# Find inner texts of standalone SR blocks in text (line-start anchored) — for smr chunks
def _find_sr_inners(text):
    if '<system-reminder>' not in text:
        return
    for m in _STANDALONE_SR_RE.finditer(text):
        yield m.group(1).strip()


# Match SR inner text against templates; returns (template_id, mode) or (None, None)
def _match_template(inner):
    for tid, (identifier, mode) in _SR_TEMPLATES.items():
        identifiers = identifier if isinstance(identifier, list) else [identifier]
        for ident in identifiers:
            if inner.startswith(ident):
                return tid, mode
    return None, None


# Return ' [tool_result:ToolName]' or ' [tool_result]' or '' for messages[abs_idx]
def _make_tool_label(messages, abs_idx):
    if not _is_tool_result(messages, abs_idx):
        return ''
    name = _get_tool_name(messages, abs_idx)
    return f' [tool_result:{name}]' if name else ' [tool_result]'


# Check whether messages[idx] is a user-role tool_result message
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
                pc = prev_msg.get('content', [])
                if not isinstance(pc, list):
                    continue
                for pb in pc:
                    if (isinstance(pb, dict) and pb.get('type') == 'tool_use'
                            and pb.get('id') == tuid):
                        return pb.get('name')
    return None


# Return list of lines with n-space indent for multiline text
def _indent_lines(text, n):
    prefix = ' ' * n
    return [prefix + line for line in text.splitlines()] if text else []


# Return indented context around tag_str — full text if short, neighborhood if long
def _context_neighborhood(text, tag_str, n):
    stripped = text.strip()
    if len(stripped) <= 3000:
        return _indent_lines(stripped, n)
    pos = text.find(tag_str)
    if pos == -1:
        return _indent_lines(stripped[:2000], n)
    lo = max(0, pos - 800)
    hi = min(len(text), pos + len(tag_str) + 800)
    snippet = ('…' if lo > 0 else '') + text[lo:hi] + ('…' if hi < len(text) else '')
    return _indent_lines(snippet.strip(), n)


# Format UTC ISO timestamp to local HH:MM:SS
def _format_ts(ts_raw):
    if not ts_raw:
        return '??:??:??'
    try:
        dt = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
        return dt.astimezone().strftime('%H:%M:%S')
    except Exception:
        return ts_raw[:8]


# Assemble full report lines
def _build_report(jsonl_path, blocks, tag_counts, sr_bypassed, sr_captured,
                  n_opus, n_reqs_with_tags, n_non_opus):
    total_tags = sum(tag_counts.values())
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        f'# Tag Presence Audit — {ts}',
        '',
        f'Source: `{Path(jsonl_path).name}`',
        f'Opus entries: {n_opus}  |  Non-opus (skipped): {n_non_opus}',
        f'REQs with tag occurrences in delta: {n_reqs_with_tags}  |  Total tag occurrences: {total_tags}',
        '',
        '---',
        '',
    ]
    lines.extend(blocks)
    lines.extend(_build_aggregate(tag_counts, sr_bypassed, sr_captured, n_opus, n_reqs_with_tags))
    return lines


# Build aggregate footer section
def _build_aggregate(tag_counts, sr_bypassed, sr_captured, n_opus, n_reqs_with_tags):
    total_tags = sum(tag_counts.values())
    lines = [
        '## Aggregate (delta-scoped)',
        '',
        '### Tag Type Counts',
        '',
        '| tag | occurrences_in_delta |',
        '|---|---|',
    ]
    for tag_type, label in (('SR', '`<SR>`'), ('TN', '`<TN>`'), ('ND', '`<ND>`'), ('PO', '`<PO>`')):
        lines.append(f'| {label} | {tag_counts[tag_type]} |')
    lines += [
        '',
        '### SR Template Breakdown',
        '',
        '| template_id | bypassed_in_delta | captured_in_delta | bypass_rate |',
        '|---|---|---|---|',
    ]
    for tid in _SR_TEMPLATES:
        b = sr_bypassed[tid]
        c = sr_captured[tid]
        total = b + c
        rate = 'n/a' if total == 0 else f'{100 * b / total:.1f}%'
        lines.append(f'| {tid} | {b} | {c} | {rate} |')
    lines += [
        '',
        f'Total opus REQs: {n_opus} | REQs with tag occurrences in delta: {n_reqs_with_tags}'
        f' | Total tag occurrences: {total_tags}',
        '',
    ]
    return lines


# Parse CLI args; auto-pick newest opus log when path is omitted
def _parse_args():
    parser = argparse.ArgumentParser(description='Tag presence audit for proxy logs')
    parser.add_argument('jsonl', nargs='?', help='JSONL log path (auto-picks newest if omitted)')
    parser.add_argument('--output', help='Output MD path (auto-generated if omitted)')
    args = parser.parse_args()

    if args.jsonl:
        jsonl_path = Path(args.jsonl)
        if not jsonl_path.exists():
            print(f'ERROR: {jsonl_path} not found', file=sys.stderr)
            sys.exit(1)
    else:
        if not _LOGS_DIR.is_dir():
            print(f'ERROR: logs dir not found: {_LOGS_DIR}', file=sys.stderr)
            sys.exit(1)
        candidates = sorted(
            _LOGS_DIR.glob('api_requests_opus_monitor_cc_*.jsonl'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            print(f'ERROR: no api_requests_opus_monitor_cc_*.jsonl in {_LOGS_DIR}',
                  file=sys.stderr)
            sys.exit(1)
        jsonl_path = candidates[0]

    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime('%Y%m%d%H%M')
        output_path = Path(__file__).parent / f'{ts}_tag_presence_audit.md'

    return jsonl_path, output_path


if __name__ == '__main__':
    jsonl_path, output_path = _parse_args()
    tag_presence_audit_workflow(jsonl_path, output_path)
