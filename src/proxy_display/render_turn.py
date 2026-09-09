# INFRASTRUCTURE
import time
from typing import Optional
from ..constants import (
    SOFT_RESET, RED, GREEN, WHITE, YELLOW, DIM,
    SEARCH_MATCH_BG, SEARCH_CURRENT_BG,
)
from ..utils import _ANSI_ESCAPE_RE, _cell_width, highlight_query_in_line
from .format import _shorten_model, _format_k, _is_standalone_entry, _fmt_thinking_budget, _fmt_effort
from .render_messages import _aggregate_req_buckets
from .proxy_badge import badge_flags
# From search_bar.py: shared BG-restore sentinel (2026-08-18 extraction — single source, see
# format.py's import comment)
from ..search_bar import _BG_RESTORE_SENTINEL

# FUNCTIONS

# Walk backward from entry_idx-1 for the first non-standalone entry of the SAME family
# (haiku vs non-haiku) — the reference used for ⚠T / section-diff rendering. None for
# standalone entries (haiku/zero-context) or when no matching predecessor exists.
def _resolve_prev_same_family(entries: list, entry_idx: int) -> Optional[dict]:
    entry = entries[entry_idx]
    if _is_standalone_entry(entry):
        return None
    ef = 'haiku' if 'haiku' in entry.get('model', '').lower() else 'opus'
    for i in range(entry_idx - 1, -1, -1):
        pf = 'haiku' if 'haiku' in entries[i].get('model', '').lower() else 'opus'
        if pf == ef and not _is_standalone_entry(entries[i]):
            return entries[i]
    return None

# Compute tool-mod string (🔧+N / -N / ±N) comparing entry tools to prev_same, or ''
def _compute_req_mods_str(entry: dict, prev_same) -> str:
    _curr = entry.get('tools_names', [])
    _prev = prev_same.get('tools_names', []) if prev_same is not None else []
    added = len(set(_curr) - set(_prev))
    removed = len(set(_prev) - set(_curr))
    if added > 0 and removed > 0:
        return f" {YELLOW}🔧+{added}-{removed}{SOFT_RESET}"
    if added > 0:
        return f" {YELLOW}🔧+{added}{SOFT_RESET}"
    if removed > 0:
        return f" {YELLOW}🔧-{removed}{SOFT_RESET}"
    return ''

# Build the request header line string with haiku_info, eff/think, tag_badge, copy ⎘/✓ right-pad
# is_search_current wins over is_search_match — wraps only the header's own TEXT EXTENT (from
# req_symbol through the last badge, i.e. the "body" below) in a search-highlight BG span with a
# _BG_RESTORE_SENTINEL close — NOT the leading 2-space indent and NOT the copy-button padding
# appended after this function returns, so the highlight never reaches the right pane edge.
# _apply_row_backgrounds substitutes the sentinel for the row's real chosen_bg once known.
# Header stays marked for a search hit regardless of expand state (uniform, keeps orientation
# when scrolling inside a long expanded request).
def _build_req_header_line(entry: dict, entry_idx: int, num_label: str, req_symbol: str, model_short: str, msg_count: int, mods_str: str, warn_str: str, pane_width: int, copy_feedback, is_search_match: bool = False, is_search_current: bool = False) -> str:
    e_sys = entry.get('system_total_chars', entry.get('system_prompt_chars', 0))
    e_tools = entry.get('tools_total_chars', entry.get('tools_chars', 0))
    e_msgs = entry.get('messages_total_chars', 0)
    haiku_info = f"  sys:{_format_k(e_sys)} tools:{_format_k(e_tools)} msgs:{_format_k(e_msgs)}" if model_short == 'haiku' else ''
    eff_val = entry.get('effort_value')
    eff_str = f" eff:{_fmt_effort(eff_val)}" if eff_val is not None else ''
    mt = entry.get('max_tokens') or 0
    think_str = f" think:{_fmt_thinking_budget(mt)}" if (mt and model_short != 'haiku') else ''
    _has_strip, _has_inj = badge_flags(entry)
    _has_think = entry.get('has_thinking_delta', False)
    _badge_parts = []
    if _has_strip: _badge_parts.append(f'{YELLOW}strip{SOFT_RESET}')
    if _has_inj:   _badge_parts.append(f'{GREEN}inject{SOFT_RESET}')
    if _has_think: _badge_parts.append(f'{GREEN}🧠{SOFT_RESET}')
    tag_badge = (' ' + ' '.join(_badge_parts)) if _badge_parts else ''
    body = f"{WHITE}{req_symbol} {num_label} {model_short} {msg_count}msg{eff_str}{think_str}{mods_str}{warn_str}{haiku_info}{tag_badge}{SOFT_RESET}"
    if is_search_match:
        search_marker = SEARCH_CURRENT_BG if is_search_current else SEARCH_MATCH_BG
        body = f"{search_marker}{body}{_BG_RESTORE_SENTINEL}"
    header_raw = f"  {body}"
    if copy_feedback is not None:
        _stripped_h = _ANSI_ESCAPE_RE.sub('', header_raw)
        visible_len = sum(_cell_width(ch) for ch in _stripped_h)
        is_flash = copy_feedback.get(entry_idx, 0) > time.time()
        copy_sym = '✓' if is_flash else '⎘'
        sym_cells = _cell_width(copy_sym)
        pad = pane_width - 1 - sym_cells - visible_len  # 1 space + sym_cells
        if pad >= 0:
            return header_raw + ' ' * pad + ' ' + copy_sym
    return header_raw

# Highlight ONLY the literal query substring occurrence(s) within each line (browser-find
# style, via utils.highlight_query_in_line) — NOT the whole line/row. Uses _BG_RESTORE_SENTINEL
# as the restore code so _apply_row_backgrounds can substitute the row's real chosen_bg
# (zebra/hover/strip/collision) once known, instead of blowing a hole to the terminal default.
# A line not containing the query is returned unchanged (highlight_query_in_line's own no-op).
def _mark_search_lines(lines: list, query: str, is_current: bool) -> list:
    if not query:
        return lines
    marker = SEARCH_CURRENT_BG if is_current else SEARCH_MATCH_BG
    return [highlight_query_in_line(line, query, marker, _BG_RESTORE_SENTINEL) for line in lines]

# Render expanded section for one request entry (buckets, fields, beta, directives, sys, tools, messages)
# search_query/is_search_current: when query is truthy, every rendered line containing it
# (case-insensitive) gets a search-highlight BG marker — "exactly what this expanded view shows".
def _render_req_expanded(entry_idx: int, entry: dict, entries: list, is_standalone: bool, prev_same, expand_states: dict, pane_width: int, search_query: str = '', is_search_current: bool = False) -> tuple:
    from .render_sections import render_system_blocks, render_tools, render_fields_delta, render_beta, render_directives
    from .render_messages import render_messages
    lines = []
    keys = []
    mods = entry.get('modifications', [])
    _section_ref = None if is_standalone else prev_same
    buckets = _aggregate_req_buckets(entry, _section_ref)
    parts = [f'INERT:{c}' for c in buckets['inert_codes']]
    parts += [f'IDX:{i}' for i in buckets['idx_msgs']]
    parts += buckets['leak_signals']
    parts += buckets['sus_signals']
    if parts:
        lines.append(f"    {DIM}{'  '.join(parts)}{SOFT_RESET}")
        keys.append(None)
    f_lines, f_keys = render_fields_delta(entry_idx, entry, expand_states, pane_width)
    lines.extend(f_lines)
    keys.extend(f_keys)
    b_lines, b_keys = render_beta(entry_idx, entry, expand_states)
    lines.extend(b_lines)
    keys.extend(b_keys)
    d_lines, d_keys = render_directives(entry_idx, entry, expand_states)
    lines.extend(d_lines)
    keys.extend(d_keys)
    s_lines, s_keys = render_system_blocks(entry_idx, entry, _section_ref, expand_states, pane_width, mods)
    lines.extend(s_lines)
    keys.extend(s_keys)
    t_lines, t_keys = render_tools(entry_idx, entry, _section_ref, expand_states, pane_width)
    lines.extend(t_lines)
    keys.extend(t_keys)
    m_lines, m_keys = render_messages(entry_idx, entry, _section_ref, entries, expand_states, pane_width)
    lines.extend(m_lines)
    keys.extend(m_keys)
    lines = _mark_search_lines(lines, search_query, is_search_current)
    return lines, keys

# Render all per-request rows for an expanded turn group, returning (lines, keys, opus_req_num, sub_req_num)
# search_match_set/search_current_entry_idx/search_query: optional — None/empty (defaults) means
# search is inactive and every entry renders exactly as before (no behavior change for callers
# that don't pass these, e.g. worker_proxy_pane.py).
def render_turn_expanded(group: dict, entries: list, expand_states: dict, pane_width: int, opus_req_num: int, sub_req_num: int, turns=None, turn_idx: int = 0, rendered_opus_labels: list = None, copy_feedback=None, copy_rows_out=None, search_match_set: set = None, search_current_entry_idx: int = None, search_query: str = '') -> tuple:
    lines = []
    keys = []
    for entry_idx, entry in group['entry_pairs']:
        model_short = _shorten_model(entry.get('model', '?'))
        if _is_standalone_entry(entry):
            num_label = 'H' if model_short == 'haiku' else 'S'
        else:
            if (entry.get('diff_from_prev') or {}).get('messages_added', 1) > 0:
                opus_req_num += 1
                sub_req_num = 0
                num_label = f'#{opus_req_num}'
            else:
                sub_req_num += 1
                num_label = f'#{opus_req_num}.{sub_req_num}'
        msg_count = entry.get('message_count', 0)
        warn_parts = []
        is_standalone = _is_standalone_entry(entry)
        if model_short != 'haiku' and not is_standalone and rendered_opus_labels is not None:
            rendered_opus_labels.append((entry_idx, num_label))
        prev_same = _resolve_prev_same_family(entries, entry_idx)
        if prev_same is not None:
            if entry.get('tools_hash') and prev_same.get('tools_hash') and entry.get('tools_hash') != prev_same.get('tools_hash'):
                warn_parts.append(f"{RED}⚠T{SOFT_RESET}")
        warn_str = f"  {'  '.join(warn_parts)}" if warn_parts else ''
        req_key = ('req', entry_idx)
        is_req_expanded = expand_states.get(req_key, False)
        req_symbol = '▼' if is_req_expanded else '▶'
        mods_str = _compute_req_mods_str(entry, prev_same)
        is_search_current = search_current_entry_idx is not None and entry_idx == search_current_entry_idx
        is_search_match = bool(search_match_set) and entry_idx in search_match_set
        lines.append(_build_req_header_line(entry, entry_idx, num_label, req_symbol, model_short, msg_count, mods_str, warn_str, pane_width, copy_feedback, is_search_match, is_search_current))
        keys.append(req_key)
        if is_req_expanded:
            e_lines, e_keys = _render_req_expanded(entry_idx, entry, entries, is_standalone, prev_same, expand_states, pane_width, search_query if is_search_match else '', is_search_current)
            lines.extend(e_lines)
            keys.extend(e_keys)
    return lines, keys, opus_req_num, sub_req_num
