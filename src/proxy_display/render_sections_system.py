# INFRASTRUCTURE
from ..constants import SOFT_RESET, DIM, DIM_YELLOW_BG, DIM_GREEN_BG
from .format import _format_k
from .render_line_helpers import _emit_text_lines, _emit_span_lines, _emit_inline_spans

# FUNCTIONS

# Render system blocks section for an expanded request entry, returning (lines, keys)
def render_system_blocks(entry_idx: int, entry: dict, prev_entry_for_delta, expand_states: dict, pane_width: int, mods: list) -> tuple:
    lines = []
    keys = []
    sys_blocks = entry.get('system_blocks', [])
    sys_total = entry.get('system_total_chars', 0)
    if not sys_blocks:
        return lines, keys
    sys_key = ('sys', entry_idx)
    is_sys_expanded = expand_states.get(sys_key, False)
    sys_symbol = '▼' if is_sys_expanded else '▶'
    lines.append(f"    {DIM}{sys_symbol} sys: {len(sys_blocks)} blocks ({sys_total:,}c){SOFT_RESET}")
    keys.append(sys_key)
    if is_sys_expanded:
        b_lines, b_keys = _render_sys_blocks_body(entry_idx, entry, sys_blocks, prev_entry_for_delta, expand_states, mods)
        lines.extend(b_lines)
        keys.extend(b_keys)
    return lines, keys

# Render every changed system block (skips blocks whose preview matches the prior request's,
# unless this is the first request for the family) — returning (lines, keys)
def _render_sys_blocks_body(entry_idx: int, entry: dict, sys_blocks: list, prev_entry_for_delta, expand_states: dict, mods: list) -> tuple:
    lines = []
    keys = []
    prev_sys_blocks = prev_entry_for_delta.get('system_blocks', []) if prev_entry_for_delta else []
    use_dual = '_stripped_spans' in entry
    is_first_sys = not prev_sys_blocks
    prev_block_by_idx = {b['idx']: b for b in prev_sys_blocks}
    for sb in sys_blocks:
        if not is_first_sys and prev_block_by_idx.get(sb['idx'], {}).get('preview', '') == sb.get('preview', ''):
            continue
        blk_lines, blk_keys = _render_one_sys_block(entry_idx, entry, sb, use_dual, expand_states, mods)
        lines.extend(blk_lines)
        keys.extend(blk_keys)
    return lines, keys

# Look up the (stripped, injected) span markers for one system block coordinate — new dual-log
# path reads real span data; old side-channel path derives a marker-only True from `mods`.
def _sys_block_spans(entry: dict, bidx: int, use_dual: bool, mods: list) -> tuple:
    if use_dual:
        s_spans = entry['_stripped_spans']['system'].get(str(bidx))
        i_spans = entry['_injected_spans']['system'].get(str(bidx))
    else:
        is_old_stripped = ('replaced_system_prompt' in mods and bidx == 2) or ('stripped_sys3' in mods and bidx == 3)
        s_spans = True if is_old_stripped else None
        i_spans = None
    return s_spans, i_spans

# Render one system block: header (yellow/green/gray by span presence) + expanded content, returning (lines, keys)
def _render_one_sys_block(entry_idx: int, entry: dict, sb: dict, use_dual: bool, expand_states: dict, mods: list) -> tuple:
    lines = []
    keys = []
    bidx = sb['idx']
    bchars = sb.get('chars', 0)
    block_key = ('sys_block', entry_idx, bidx)
    is_block_expanded = expand_states.get(block_key, False)
    block_symbol = '▼' if is_block_expanded else '▶'
    s_spans, i_spans = _sys_block_spans(entry, bidx, use_dual, mods)
    hdr_bg = DIM_YELLOW_BG if s_spans else (DIM_GREEN_BG if i_spans else '')
    lines.append(f"      {hdr_bg}{DIM}{block_symbol} [{bidx}]: {_format_k(bchars)}{SOFT_RESET}")
    keys.append(block_key)
    if is_block_expanded:
        c_lines, c_keys = _render_sys_block_content(sb, s_spans, i_spans, use_dual)
        lines.extend(c_lines)
        keys.extend(c_keys)
    return lines, keys

# Render one expanded system block's content — new-format inline spans, or gray preview + stacked
# yellow/green (dual) / yellow original_text (legacy) — returning (lines, keys)
def _render_sys_block_content(sb: dict, s_spans, i_spans, use_dual: bool) -> tuple:
    lines = []
    keys = []
    if use_dual and i_spans and isinstance(i_spans[0], (list, tuple)):
        n_lines, n_keys = _emit_inline_spans(i_spans, "        ", DIM_GREEN_BG)
        lines.extend(n_lines)
        keys.extend(n_keys)
        s_lines, s_keys = _emit_span_lines(s_spans or [], "        ", DIM_YELLOW_BG)
        lines.extend(s_lines)
        keys.extend(s_keys)
        return lines, keys
    preview = sb.get('preview', '')
    if preview:
        p_lines, p_keys = _emit_text_lines(preview, "        ", '')
        lines.extend(p_lines)
        keys.extend(p_keys)
    else:
        lines.append(f"        {DIM}(no preview){SOFT_RESET}")
        keys.append(None)
    if use_dual:
        s_lines, s_keys = _emit_span_lines(s_spans or [], "        ", DIM_YELLOW_BG)
        lines.extend(s_lines)
        keys.extend(s_keys)
        i_lines, i_keys = _emit_span_lines(i_spans or [], "        ", DIM_GREEN_BG)
        lines.extend(i_lines)
        keys.extend(i_keys)
    else:
        original_text = sb.get('original_text', '')
        if original_text:
            o_lines, o_keys = _emit_text_lines(original_text, "        ", DIM_YELLOW_BG)
            lines.extend(o_lines)
            keys.extend(o_keys)
    return lines, keys
