# INFRASTRUCTURE
import re
from collections import Counter
from ..colors import (
    SOFT_RESET, RED, WHITE, DIM, DIM_YELLOW_BG, DIM_GREEN_BG, LIGHT_RED_BG, RESET,
)
from ..proxy.strip_vocab import attribute_chunk, classify_req
from ..utils import wrap_visible

_BLOCK_CONTENT_INDENT = "        "

_SUSPECT_TAG_RE = re.compile(
    r'(<(?:new-diagnostics|persisted-output|system-reminder|task-notification)>)'
)

# FUNCTIONS

def _render_stripped_block(entry: dict, msg_idx: int, msg: dict, show_chars: bool = True) -> tuple:
    lines = []
    keys = []
    role = msg.get('role', '?')[:4]
    msg_type = msg.get('type', 'text')
    removed_map = entry.get('stripped_msg_removed')
    removed_chunks = removed_map.get(str(msg_idx), []) if removed_map is not None else []
    if removed_chunks:
        if show_chars:
            chars_fmt = f"{msg.get('chars', 0):,}c"
            lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {msg_type:<20} {chars_fmt:>8}  [STRIPPED]{SOFT_RESET}")
        else:
            lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {msg_type:<20}  [STRIPPED]{SOFT_RESET}")
        for chunk in removed_chunks:
            rule_code = attribute_chunk(chunk)
            label = f'EFF:{rule_code}' if rule_code else 'EFF:?'
            lines.append(f"      {WHITE}{label}{SOFT_RESET}")
            keys.append(None)
            for raw_line in chunk.split('\n'):
                raw_line = raw_line.expandtabs(8)
                if not raw_line:
                    lines.append(f"      {DIM_YELLOW_BG}{DIM}{SOFT_RESET}")
                    keys.append(None)
                    continue
                lines.append(f"      {DIM_YELLOW_BG}{DIM}{raw_line}{SOFT_RESET}")
                keys.append(None)
    else:
        originals = entry.get('stripped_msg_originals', {})
        orig_text = originals.get(str(msg_idx), '')
        if show_chars:
            chars_fmt = f"{msg.get('chars', 0):,}c"
            lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {msg_type:<20} {chars_fmt:>8}  [STRIPPED]  IDX{SOFT_RESET}")
        else:
            lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {msg_type:<20}  [STRIPPED]  IDX{SOFT_RESET}")
        if orig_text:
            for raw_line in orig_text.split('\n'):
                raw_line = raw_line.expandtabs(8)
                if not raw_line:
                    lines.append(f"      {DIM_YELLOW_BG}{DIM}{SOFT_RESET}")
                    keys.append(None)
                    continue
                lines.append(f"      {DIM_YELLOW_BG}{DIM}{raw_line}{SOFT_RESET}")
                keys.append(None)
    keys.append(None)
    return lines, keys

def _render_span_content(full_text: str, i_blk: list, s_blk: list, indent: str, highlight_suspect: bool = True) -> tuple:
    lines = []
    keys = []
    if i_blk and isinstance(i_blk[0], (list, tuple)):
        for tag, span_text in i_blk:
            bg = DIM_GREEN_BG if tag == "injected" else ""
            for raw_line in span_text.split('\n'):
                raw_line = raw_line.expandtabs(8)
                if not raw_line:
                    lines.append(f"{indent}{bg}{DIM}{SOFT_RESET}")
                    keys.append(None)
                    continue
                highlighted = _SUSPECT_TAG_RE.sub(
                    lambda m: f'{LIGHT_RED_BG}{m.group(0)}{RESET}{DIM}', raw_line
                )
                lines.append(f"{indent}{bg}{DIM}{highlighted}{SOFT_RESET}")
                keys.append(None)
        for span_text in s_blk:
            for raw_line in span_text.split('\n'):
                raw_line = raw_line.expandtabs(8)
                lines.append(f"{indent}{DIM_YELLOW_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                keys.append(None)
    else:
        if full_text:
            for raw_line in full_text.split('\n'):
                raw_line = raw_line.expandtabs(8)
                if not raw_line:
                    lines.append(f"{indent}{DIM}{SOFT_RESET}")
                    keys.append(None)
                    continue
                line_out = (
                    _SUSPECT_TAG_RE.sub(lambda m: f'{LIGHT_RED_BG}{m.group(0)}{RESET}{DIM}', raw_line)
                    if highlight_suspect else raw_line
                )
                lines.append(f"{indent}{DIM}{line_out}{SOFT_RESET}")
                keys.append(None)
        for span_text in s_blk:
            for raw_line in span_text.split('\n'):
                raw_line = raw_line.expandtabs(8)
                lines.append(f"{indent}{DIM_YELLOW_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                keys.append(None)
        for span_text in i_blk:
            for raw_line in span_text.split('\n'):
                raw_line = raw_line.expandtabs(8)
                lines.append(f"{indent}{DIM_GREEN_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                keys.append(None)
    return lines, keys

def _lookup_spans(entry: dict, msg_idx: int, bidx, use_dual: bool) -> tuple:
    if not use_dual:
        return [], []
    msg_key = str(msg_idx)
    i_blk = entry['_injected_spans']['messages'].get(msg_key, {}).get(str(bidx)) or []
    s_blk = entry['_stripped_spans']['messages'].get(msg_key, {}).get(str(bidx)) or []
    fid = entry.get('flow_id', '')
    lagged = entry.get('_lag_msgs_lookup', {}).get(fid, set())
    if '_inject_msgs_lookup' in entry and msg_key not in entry['_inject_msgs_lookup'].get(fid, set()) and msg_key not in lagged:
        i_blk = []
    if '_strip_msgs_lookup' in entry and msg_key not in entry['_strip_msgs_lookup'].get(fid, set()) and msg_key not in lagged:
        s_blk = []
    return i_blk, s_blk

def _wrap_thinking_text(full_text: str, indent: str, pane_width: int) -> str:
    width_cells = max(1, pane_width - len(indent))
    out_lines = []
    for para in full_text.split('\n'):
        out_lines.extend(wrap_visible(para.expandtabs(8), width_cells))
    return '\n'.join(out_lines)

def _render_block_spans(entry_idx: int, msg_idx: int, bidx: int, blk: dict, entry: dict, use_dual: bool, expand_states: dict, pane_width: int) -> tuple:
    lines = []
    keys = []
    btype = blk.get('type', 'text')
    bchars = blk.get('chars', 0)
    bcc = ' [CC]' if blk.get('has_cc') else ''
    full_text = blk.get('full_text', blk.get('preview', ''))
    if btype == 'thinking':
        sig_chars = blk.get('sig_chars', 0)
        think_key = ('think', entry_idx, msg_idx, bidx)
        is_think_expanded = expand_states.get(think_key, False)
        think_symbol = '▼' if is_think_expanded else '▶'
        lines.append(f"      {DIM}{think_symbol} [{bidx}] {btype:<12} text:{bchars:>5,}c sig:{sig_chars:>4,}c{bcc}{SOFT_RESET}")
        keys.append(think_key)
        if is_think_expanded:
            i_blk, s_blk = _lookup_spans(entry, msg_idx, bidx, use_dual)
            wrapped_text = _wrap_thinking_text(full_text, _BLOCK_CONTENT_INDENT, pane_width)
            content_lines, content_keys = _render_span_content(wrapped_text, i_blk, s_blk, _BLOCK_CONTENT_INDENT)
            lines.extend(content_lines)
            keys.extend(content_keys)
        return lines, keys
    lines.append(f"      {DIM}[{bidx}] {btype:<12} {bchars:>6,}c{bcc}{SOFT_RESET}")
    keys.append(None)
    i_blk, s_blk = _lookup_spans(entry, msg_idx, bidx, use_dual)
    content_lines, content_keys = _render_span_content(full_text, i_blk, s_blk, _BLOCK_CONTENT_INDENT)
    lines.extend(content_lines)
    keys.extend(content_keys)
    return lines, keys

def _render_prestripped_range(entry: dict, messages: list, fdi: int, upper: int, stripped_indices: set, use_dual: bool, show_chars: bool) -> tuple:
    lines = []
    keys = []
    if fdi >= 0 and not use_dual:
        for msg_idx in sorted(s for s in stripped_indices if fdi <= s < upper):
            s_lines, s_keys = _render_stripped_block(entry, msg_idx, messages[msg_idx], show_chars=show_chars)
            lines.extend(s_lines)
            keys.extend(s_keys)
    return lines, keys

def _render_new_messages(entry_idx: int, entry: dict, messages: list, prev_msg_count: int, fdi: int, stripped_indices: set, use_dual: bool, expand_states: dict, pane_width: int) -> tuple:
    lines, keys = _render_prestripped_range(entry, messages, fdi, prev_msg_count, stripped_indices, use_dual, show_chars=True)
    for msg_idx in range(prev_msg_count, len(messages)):
        msg = messages[msg_idx]
        is_stripped = msg_idx in stripped_indices
        blocks = msg.get('blocks', [])
        if is_stripped and not use_dual:
            s_lines, s_keys = _render_stripped_block(entry, msg_idx, msg, show_chars=True)
            lines.extend(s_lines)
            keys.extend(s_keys)
        else:
            role = msg.get('role', '?')[:4]
            msg_type = msg.get('type', 'text')
            chars_fmt = f"{msg.get('chars', 0):,}c"
            type_label = f"{len(blocks)} blocks" if len(blocks) > 1 else msg_type
            lines.append(f"    {WHITE}[{msg_idx:3d}] {role:<4}  {type_label:<20} {chars_fmt:>8}{SOFT_RESET}")
            keys.append(None)
        if blocks:
            for bidx, blk in enumerate(blocks):
                b_lines, b_keys = _render_block_spans(entry_idx, msg_idx, bidx, blk, entry, use_dual, expand_states, pane_width)
                lines.extend(b_lines)
                keys.extend(b_keys)
        else:
            preview = msg.get('content_preview', '')
            i_blk, s_blk = _lookup_spans(entry, msg_idx, 0, use_dual)
            content_lines, content_keys = _render_span_content(preview, i_blk, s_blk, "      ", highlight_suspect=False)
            lines.extend(content_lines)
            keys.extend(content_keys)
    return lines, keys

def _compute_diff_start(messages: list, prev_messages: list) -> int:
    diff_start = len(messages)
    for j in range(1, min(len(messages), len(prev_messages)) + 1):
        curr_msg = messages[-j]
        prev_msg = prev_messages[-j]
        if curr_msg.get('chars', 0) != prev_msg.get('chars', 0) or curr_msg.get('type', '') != prev_msg.get('type', ''):
            diff_start = len(messages) - j
        else:
            break
    return diff_start

def _render_removed_tail(messages: list, prev_messages: list) -> tuple:
    lines = []
    keys = []
    removed_from_prev = prev_messages[len(messages):]
    for m_offset, msg in enumerate(removed_from_prev):
        m_idx = len(messages) + m_offset
        role = msg.get('role', '?')[:4]
        m_type = msg.get('type', 'text')
        m_chars = msg.get('chars', 0)
        lines.append(f"    {RED}removed:{SOFT_RESET} {DIM}[{m_idx:3d}] {role:<4}  {m_type:<20} {m_chars:,}c{SOFT_RESET}")
        keys.append(None)
    return lines, keys

def _render_modified_messages(entry_idx: int, entry: dict, messages: list, prev_entry_for_delta, fdi: int, stripped_indices: set, use_dual: bool, expand_states: dict, pane_width: int) -> tuple:
    prev_messages = prev_entry_for_delta.get('messages', []) if prev_entry_for_delta is not None else []
    diff_start = _compute_diff_start(messages, prev_messages)
    lines, keys = _render_prestripped_range(entry, messages, fdi, diff_start, stripped_indices, use_dual, show_chars=False)
    for msg_idx in range(diff_start, len(messages)):
        msg = messages[msg_idx]
        is_stripped = msg_idx in stripped_indices
        blocks = msg.get('blocks', [])
        if is_stripped and not use_dual:
            s_lines, s_keys = _render_stripped_block(entry, msg_idx, msg, show_chars=False)
            lines.extend(s_lines)
            keys.extend(s_keys)
        else:
            role = msg.get('role', '?')[:4]
            msg_type = msg.get('type', 'text')
            type_label = f"{len(blocks)} blocks" if len(blocks) > 1 else msg_type
            lines.append(f"    {DIM}[{msg_idx:3d}] {role:<4}  {type_label:<20}{SOFT_RESET}")
            keys.append(None)
        if blocks:
            for bidx, blk in enumerate(blocks):
                b_lines, b_keys = _render_block_spans(entry_idx, msg_idx, bidx, blk, entry, use_dual, expand_states, pane_width)
                lines.extend(b_lines)
                keys.extend(b_keys)
        else:
            tail = msg.get('content_tail', '')
            i_blk, s_blk = _lookup_spans(entry, msg_idx, 0, use_dual)
            content_lines, content_keys = _render_span_content(tail, i_blk, s_blk, "      ", highlight_suspect=False)
            lines.extend(content_lines)
            keys.extend(content_keys)
    r_lines, r_keys = _render_removed_tail(messages, prev_messages)
    lines.extend(r_lines)
    keys.extend(r_keys)
    return lines, keys

def render_messages(entry_idx: int, entry: dict, prev_entry_for_delta, entries: list, expand_states: dict, pane_width: int) -> tuple:
    messages = entry.get('messages', [])
    stripped_indices = set(entry.get('stripped_msg_indices', []))
    prev_msg_count = prev_entry_for_delta.get('message_count', 0) if prev_entry_for_delta is not None else 0
    diff = entry.get('diff_from_prev') or {}
    fdi = diff.get('first_diff_index')
    if fdi is None:
        fdi = 0
    use_dual = '_stripped_spans' in entry
    if prev_msg_count < len(messages):
        return _render_new_messages(entry_idx, entry, messages, prev_msg_count, fdi, stripped_indices, use_dual, expand_states, pane_width)
    return _render_modified_messages(entry_idx, entry, messages, prev_entry_for_delta, fdi, stripped_indices, use_dual, expand_states, pane_width)


def _aggregate_req_buckets(entry: dict, prev_entry) -> dict:
    cls = classify_req(entry, prev_entry)
    return {
        'inert_codes':  cls['inert'],
        'idx_msgs':     cls['idx_msgs'],
        'leak_signals': cls['leak_signals'],
        'sus_signals':  cls['sus_signals'],
    }
