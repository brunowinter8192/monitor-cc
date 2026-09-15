# INFRASTRUCTURE
from datetime import datetime
from pathlib import Path

from strip_audit_classify import _classify_req, _TEMPLATE_TO_RULE, _SR_TEMPLATES

CHUNK_HEAD = 120   # chars of chunk to display in report

# FUNCTIONS

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
    for tid, spec in _SR_TEMPLATES.items():
        identifier, mode = spec[0], spec[1]
        rule = _TEMPLATE_TO_RULE[tid]
        if isinstance(identifier, list):
            ident_display = ' | '.join(i[:35] for i in identifier)
        else:
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


# Render the "REQ #n ..." header line + diff summary
def _render_req_header(req_num, entry, prev):
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

    return f'REQ #{req_num}  [{ts}]  msg_count={prev_mc}→{curr_mc}  diff={diff_str}'


# Render the EFF (effective strip) section for one REQ
def _render_eff_section(cls, raw_messages):
    lines = []
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
    return lines


# Render one REQ block using compact BUCKET:RULE notation
def _render_req_section(req_num, entry, prev, cls):
    lines = [_render_req_header(req_num, entry, prev)]

    raw_messages = entry.get('raw_payload', {}).get('messages', [])

    lines += _render_eff_section(cls, raw_messages)

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


# Build delta log section — one entry per opus REQ
def _build_delta_log(entries):
    lines = ['## Delta Log', '']
    prev = None
    for i, entry in enumerate(entries):
        cls = _classify_req(entry, prev)
        lines += _render_req_section(i + 1, entry, prev, cls)
        prev = entry
    return lines


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
