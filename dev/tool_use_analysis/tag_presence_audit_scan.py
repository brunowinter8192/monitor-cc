# INFRASTRUCTURE
import json
import re
from datetime import datetime

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

# Standalone TN/ND block regexes (line-anchored, mirrors proxy strip logic)
_STANDALONE_TN_RE = re.compile(r'(?m)^<task-notification>.*?</task-notification>', re.DOTALL)
_STANDALONE_ND_RE = re.compile(r'(?m)^<new-diagnostics>.*?</new-diagnostics>', re.DOTALL)
# PO preview regex — mirror of src/proxy/strip_po.py:_PO_PREVIEW_RE
_PO_PREVIEW_RE = re.compile(
    r'(?P<open><persisted-output>\nOutput too large[^\n]+)'
    r'(?P<preview>\n+Preview \(first [^\n]+\):\n.*?)'
    r'(?P<close>\n?</persisted-output>)',
    re.DOTALL,
)

# FUNCTIONS

# Return a fresh scan-state accumulator
def _init_scan_state():
    return {
        'blocks': [],
        'tag_counts': {'SR': 0, 'TN': 0, 'ND': 0, 'PO': 0},
        'sr_bypassed': {tid: 0 for tid in _SR_TEMPLATES},
        'sr_captured': {tid: 0 for tid in _SR_TEMPLATES},
        'tn_bypassed': 0, 'tn_captured': 0,
        'nd_bypassed': 0, 'nd_captured': 0,
        'po_bypassed': 0, 'po_captured': 0,
        'n_opus': 0, 'n_reqs_with_tags': 0, 'n_non_opus': 0,
    }


# Merge one _scan_entry result into the accumulator state
def _merge_scan_result(state, result):
    block_lines, tc_d, byp_d, cap_d, tn_b, tn_c, nd_b, nd_c, po_b, po_c, has_tags = result
    for k in state['tag_counts']:
        state['tag_counts'][k] += tc_d[k]
    for tid in _SR_TEMPLATES:
        state['sr_bypassed'][tid] += byp_d[tid]
        state['sr_captured'][tid] += cap_d[tid]
    state['tn_bypassed'] += tn_b
    state['tn_captured'] += tn_c
    state['nd_bypassed'] += nd_b
    state['nd_captured'] += nd_c
    state['po_bypassed'] += po_b
    state['po_captured'] += po_c
    if has_tags:
        state['n_reqs_with_tags'] += 1
        state['blocks'].extend(block_lines)


# Stream JSONL, accumulate aggregate counters, buffer only tag-positive REQ blocks
def _stream_and_audit(jsonl_path):
    state = _init_scan_state()
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
                    state['n_non_opus'] += 1
                continue
            state['n_opus'] += 1
            req_num += 1

            result = _scan_entry(entry, prev, req_num)
            _merge_scan_result(state, result)

            prev = entry

    return (state['blocks'], state['tag_counts'], state['sr_bypassed'], state['sr_captured'],
            state['n_opus'], state['n_reqs_with_tags'], state['n_non_opus'],
            state['tn_bypassed'], state['tn_captured'], state['nd_bypassed'], state['nd_captured'],
            state['po_bypassed'], state['po_captured'])


# Scan messages[start:] for SR/TN/ND/PO tag occurrences; returns
# (tag_occurrences, tc, byp, tn_byp, nd_byp, po_byp)
# SR scan for one text — anchored regex (mirrors proxy logic: only line-start SR blocks stripped)
def _scan_sr_in_text(messages, abs_idx, layer, text, seen, tag_occurrences, tc, byp):
    for m in _STANDALONE_SR_RE.finditer(text):
        inner = m.group(1).strip()

        if inner.startswith(_PRESERVE_PREAMBLE):
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


# Non-SR (TN/ND/PO) tag scan for one text — returns (tn_byp, nd_byp, po_byp) deltas
def _scan_non_sr_in_text(messages, abs_idx, layer, text, seen, tag_occurrences, tc):
    tn_byp = nd_byp = po_byp = 0
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
            # Bypass counting: line-anchored blocks still present in post-strip payload
            if tag_type == 'TN':
                tn_byp += len(_STANDALONE_TN_RE.findall(text))
            elif tag_type == 'ND':
                nd_byp += len(_STANDALONE_ND_RE.findall(text))
            elif tag_type == 'PO':
                po_byp += len(_PO_PREVIEW_RE.findall(text))
    return tn_byp, nd_byp, po_byp


def _scan_tag_occurrences(messages, start):
    tag_occurrences = []  # list of (header_line, content_lines)
    tc = {'SR': 0, 'TN': 0, 'ND': 0, 'PO': 0}
    byp = {tid: 0 for tid in _SR_TEMPLATES}
    tn_byp = nd_byp = po_byp = 0
    seen = set()  # dedup within REQ

    for abs_idx in range(start, len(messages)):
        for layer, text in _iter_msg_text_with_layer(messages, abs_idx):
            if not text:
                continue
            _scan_sr_in_text(messages, abs_idx, layer, text, seen, tag_occurrences, tc, byp)
            d_tn, d_nd, d_po = _scan_non_sr_in_text(messages, abs_idx, layer, text, seen, tag_occurrences, tc)
            tn_byp += d_tn
            nd_byp += d_nd
            po_byp += d_po

    return tag_occurrences, tc, byp, tn_byp, nd_byp, po_byp


# Scan stripped_msg_removed for captured SR/TN/ND/PO chunks; returns
# (cap, tn_cap, nd_cap, po_cap, stripped_lines)
def _scan_captured(entry, start, messages):
    smr = entry.get('stripped_msg_removed') or {}
    cap = {tid: 0 for tid in _SR_TEMPLATES}
    tn_cap = nd_cap = po_cap = 0
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
            inners = list(_find_sr_inners(chunk))
            if inners:
                for inner in inners:
                    tid, _ = _match_template(inner)
                    if tid:
                        cap[tid] += 1
            else:
                # partial-mode or fragment chunk — try direct match on raw chunk
                tid, _ = _match_template(chunk.strip())
                if tid:
                    cap[tid] += 1
            # TN/ND/PO captured detection
            chunk_s = chunk.strip()
            if chunk_s.startswith('<task-notification>'):
                tn_cap += 1
            if '<new-diagnostics>' in chunk:
                nd_cap += 1
            if chunk_s.startswith('Preview (first '):
                po_cap += 1

    if not stripped_lines:
        stripped_lines = ['  STRIPPED (none in delta)']

    return cap, tn_cap, nd_cap, po_cap, stripped_lines


# Build the "### REQ #n ..." block from tag_occurrences + stripped_lines
def _build_req_block(req_num, entry, prev, start, tag_occurrences, stripped_lines):
    prev_mc = prev.get('message_count', 0) if prev else 0
    curr_mc = entry.get('message_count', 0)
    ts = _format_ts(entry.get('timestamp', ''))

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
    return block_lines


# Scan one opus REQ for tag occurrences in delta range and captured SR in stripped_msg_removed
def _scan_entry(entry, prev, req_num):
    messages = entry.get('raw_payload', {}).get('messages', [])
    diff = entry.get('diff_from_prev') or {}
    start = diff.get('first_diff_index')
    if not isinstance(start, int) or start < 0:
        start = 0

    tag_occurrences, tc, byp, tn_byp, nd_byp, po_byp = _scan_tag_occurrences(messages, start)
    cap, tn_cap, nd_cap, po_cap, stripped_lines = _scan_captured(entry, start, messages)

    has_tags = bool(tag_occurrences)
    if not has_tags:
        return [], tc, byp, cap, tn_byp, tn_cap, nd_byp, nd_cap, po_byp, po_cap, False

    block_lines = _build_req_block(req_num, entry, prev, start, tag_occurrences, stripped_lines)

    return block_lines, tc, byp, cap, tn_byp, tn_cap, nd_byp, nd_cap, po_byp, po_cap, True


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
