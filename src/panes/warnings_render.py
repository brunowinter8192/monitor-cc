# INFRASTRUCTURE
import datetime
import json
import time
from typing import List, Optional

from ..constants import (
    YELLOW, RED, DIM, WHITE, RESET, HOVER_BG, ZEBRA_BG_A, ZEBRA_BG_B, SOFT_RESET,
    DIM_YELLOW_BG, WARNINGS_POLL_INTERVAL,
    SEARCH_MATCH_BG, SEARCH_CURRENT_BG,
)
from ..utils import truncate_visible, first_word_of_call, format_worker_prefix, append_copy_symbol, highlight_query_in_line, _ANSI_ESCAPE_RE
from ..format.strip_marker import highlight_stripped
# From search_bar.py: shared BG-restore sentinel (2026-08-18, rollout sub-milestone 6) — this
# module doesn't know a row's eventual chosen_bg (zebra/hover) at embed time, only its own row
# loop (below) does, once computed; same pattern as format/token_format.py
from ..search_bar import _BG_RESTORE_SENTINEL, resolve_bg_restore
INDENT = '  '

# FUNCTIONS

# True when an error's own searchable text (tool_name, worker_name, tool_call_input, full_text)
# contains query, case-insensitive — checked against the underlying dict fields directly rather
# than re-rendering (this pane's render is trivial, no branching to risk diverging from), and
# covers the FULL untruncated full_text regardless of collapsed/expanded display state.
def _error_matches_query(err: dict, q: str) -> bool:
    if q in err.get('tool_name', '').lower():
        return True
    if q in (err.get('worker_name') or '').lower():
        return True
    for k, v in err.get('tool_call_input', {}).items():
        if q in str(k).lower() or q in str(v).lower():
            return True
    if q in (err.get('full_text') or '').lower():
        return True
    return False

# Build the ordered list of err_idx whose content matches query (case-insensitive) — the match
# key IS the bare int err_idx (matches error_line_map/_serialize_warnings' own key shape, no
# nesting needed — this pane has only one expand level).
def build_warnings_search_matches(query: str, tool_errors: list) -> List[int]:
    if not query:
        return []
    q = query.lower()
    return [i for i, err in enumerate(tool_errors) if _error_matches_query(err, q)]

# Build header line showing refresh key, last refresh time, poll interval, and a [refresh] button;
# when regions_out given, registers the button's (start_col,end_col,phys_row=1) -> 'refresh'
# region — only when it fits pane_width (no button appended, no region, when it doesn't)
def _format_warnings_header(last_refresh_ts: float, pane_width: int = 80, regions_out: Optional[dict] = None) -> str:
    if regions_out is not None:
        regions_out.clear()
    if last_refresh_ts:
        last_dt = datetime.datetime.fromtimestamp(last_refresh_ts)
        last_str = last_dt.strftime('%H:%M:%S')
    else:
        last_str = '--:--:--'
    text = f"{DIM}[r]efresh · last: {last_str} · polling: {int(WARNINGS_POLL_INTERVAL)}s{RESET}"
    if regions_out is None:
        return text
    label = '[refresh]'
    start_col = len(_ANSI_ESCAPE_RE.sub('', text)) + 2
    end_col = start_col + len(label) - 1
    if end_col >= pane_width:
        return text
    regions_out[(start_col + 1, end_col + 1, 1)] = 'refresh'
    return text + '  ' + f"{WHITE}{label}{RESET}"


# Build the header line + optional expanded-detail lines for ONE error — the part of
# _format_warnings_pane's overall render (see that function's own comment for the full contract)
# that handles a single error entry. A match's header line is container-marked UNCONDITIONALLY
# (marker+line+_BG_RESTORE_SENTINEL, mirrors token_format's turn-header treatment) -- BEFORE
# append_copy_symbol, so the copy button stays outside the marked span. When expanded, the
# matching detail lines (tool_call_input k/v + full_text body) ADDITIONALLY get browser-find
# substring-highlighted via utils.highlight_query_in_line. Returns (lines, keys) -- keys[0] is
# ('error', err_idx) for the header line, None for every detail line.
def _build_one_warning_lines(err_idx: int, err: dict, is_expanded: bool,
                              search_match_set: Optional[set], search_current_key, search_query: str,
                              copy_feedback: Optional[dict], pane_width: int) -> tuple:
    symbol = '\u25bc' if is_expanded else '\u25b6'
    tool_col = f"{WHITE}{err['tool_name']:<16}{SOFT_RESET}"
    w_prefix = format_worker_prefix(err.get('worker_name', ''))
    inline = first_word_of_call(err['tool_name'], err.get('tool_call_input', {}))
    line = f"{DIM}{symbol} {err['timestamp']}  {w_prefix}{tool_col}  {DIM}{inline}{SOFT_RESET}"
    is_match = bool(search_match_set) and err_idx in search_match_set
    marker = None
    if is_match:
        marker = SEARCH_CURRENT_BG if err_idx == search_current_key else SEARCH_MATCH_BG
        line = f"{marker}{line}{_BG_RESTORE_SENTINEL}"
    if copy_feedback is not None:
        is_flash = copy_feedback.get(err_idx, 0) > time.time()
        line = append_copy_symbol(line, '\u2713' if is_flash else '\u2398', pane_width)
    lines = [line]
    keys = [('error', err_idx)]
    if is_expanded:
        for k, v in err.get('tool_call_input', {}).items():
            val_str = str(v).replace('\n', ' ')
            detail_line = f"    {DIM}{k}: {val_str}{SOFT_RESET}"
            if is_match and search_query:
                detail_line = highlight_query_in_line(detail_line, search_query, marker, _BG_RESTORE_SENTINEL)
            lines.append(detail_line)
            keys.append(None)
        pre_strip = err.get('_pre_strip_text')
        chunks = err.get('_stripped_chunks', [])
        raw_text = err['full_text']
        display_text = highlight_stripped(pre_strip, chunks) if pre_strip else raw_text
        for raw_line in display_text.split('\n'):
            raw_line = raw_line.expandtabs(8)
            detail_line = f"    {DIM}{raw_line}{SOFT_RESET}" if raw_line else ''
            if is_match and search_query and detail_line:
                detail_line = highlight_query_in_line(detail_line, search_query, marker, _BG_RESTORE_SENTINEL)
            lines.append(detail_line)
            keys.append(None)
    return lines, keys


# Build all_lines/all_keys for the whole tool_errors list -- section header + one
# _build_one_warning_lines call per error, or the "No warnings." placeholder.
def _build_warnings_lines(tool_errors: list, error_expand_states: dict, copy_feedback: Optional[dict],
                           pane_width: int, search_match_set: Optional[set], search_current_key,
                           search_query: str) -> tuple:
    all_lines: list = []
    all_keys: list = []
    if tool_errors:
        all_lines.append(f"{RED}TOOL ERRORS ({len(tool_errors)}){SOFT_RESET}")
        all_keys.append(None)
        for err_idx, err in enumerate(tool_errors):
            is_expanded = error_expand_states.get(err_idx, False)
            lines, keys = _build_one_warning_lines(
                err_idx, err, is_expanded, search_match_set, search_current_key, search_query,
                copy_feedback, pane_width,
            )
            all_lines.extend(lines)
            all_keys.extend(keys)
    else:
        all_lines.append(f"{DIM}No warnings.{SOFT_RESET}")
        all_keys.append(None)
    return all_lines, all_keys


# Render the visible slice's rows with zebra/hover backgrounds. Returns (rendered_lines,
# new_error_line_map); copy_rows_out, if given, is populated in place (caller clears it first).
def _render_warnings_rows(visible_lines: list, visible_keys: list, phys_row: int, parent_count: int,
                           pane_width: int, hover_row, copy_rows_out: Optional[set]) -> tuple:
    new_error_line_map = {}
    rendered: list = []
    for line, key in zip(visible_lines, visible_keys):
        if key is not None:
            zebra_bg = ZEBRA_BG_B if parent_count % 2 else ZEBRA_BG_A
            parent_count += 1
        else:
            zebra_bg = ZEBRA_BG_A
        is_hovered = (key is not None and hover_row is not None and phys_row == hover_row)
        if is_hovered:
            chosen_bg = HOVER_BG
        elif DIM_YELLOW_BG in line:
            chosen_bg = DIM_YELLOW_BG
        else:
            chosen_bg = zebra_bg
        line = resolve_bg_restore(line, chosen_bg)
        if key is not None:
            key_type, key_idx = key
            if key_type == 'error':
                new_error_line_map[phys_row] = key_idx
                if copy_rows_out is not None and ('⎘' in line or '✓' in line):
                    copy_rows_out.add(phys_row)
        rendered.append(f"{chosen_bg}{truncate_visible(line, pane_width)}\033[K{RESET}")
        phys_row += 1
    return rendered, new_error_line_map


# Render all warning sections; returns (rendered_str, new_error_line_map). Thin orchestrator over
# _build_warnings_lines (section content) + _render_warnings_rows (viewport clip + zebra/hover).
# (2026-08-18, rollout sub-milestone 6) header_lines (default 1, preserves every pre-existing
# caller's exact behavior) generalizes the previously-hardcoded single-header-row assumption --
# warnings_pane.py passes 2 (search bar + [refresh] header). search_match_set/search_current_key
# hold bare int err_idx (no nesting -- this pane has one expand level).
def _format_warnings_pane(
    tool_errors: list,
    error_expand_states: dict,
    error_hover_row,
    error_scroll_offset: int,
    pane_height: int,
    pane_width: int,
    header: str,
    copy_feedback: Optional[dict] = None,
    copy_rows_out: Optional[set] = None,
    header_lines: int = 1,
    search_match_set: Optional[set] = None,
    search_current_key=None,
    search_query: str = '',
) -> tuple:
    content_height = max(1, pane_height - header_lines)
    if copy_rows_out is not None:
        copy_rows_out.clear()
    all_lines, all_keys = _build_warnings_lines(
        tool_errors, error_expand_states, copy_feedback, pane_width,
        search_match_set, search_current_key, search_query,
    )
    header_offset = 1 + header_lines  # row 1..header_lines = header rows, body starts after
    visible_lines = all_lines[error_scroll_offset:error_scroll_offset + content_height]
    visible_keys = all_keys[error_scroll_offset:error_scroll_offset + content_height]
    parent_count = sum(1 for k in all_keys[:error_scroll_offset] if k is not None)
    rendered, new_error_line_map = _render_warnings_rows(
        visible_lines, visible_keys, header_offset, parent_count, pane_width,
        error_hover_row, copy_rows_out,
    )
    return header + '\n' + '\n'.join(rendered), new_error_line_map


# Serialize a warnings-pane entry to full untruncated text for clipboard; key is the bare int error_line_map stores
def _serialize_warnings(key, tool_errors: list) -> str:
    if isinstance(key, int) and 0 <= key < len(tool_errors):
        err = tool_errors[key]
        parts = [err.get('tool_name', '?')]
        inp = err.get('tool_call_input', {})
        if inp:
            parts.append(json.dumps(inp, ensure_ascii=False, indent=2))
        parts.append('')
        parts.append(err.get('full_text', ''))
        return '\n'.join(parts)
    return ''
