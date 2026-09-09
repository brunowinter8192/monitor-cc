# INFRASTRUCTURE
import os
from typing import Dict, Optional, Tuple

from ..colors import RESET, YELLOW, DIM, WHITE
from ..constants import PROXY_MESSAGES_KEEP_LAST
from .format import _is_standalone_entry
from .forwarded_parser import _lazy_load_messages_forwarded, reconstruct_all_messages
from .parser import _find_dual_log_paths
from .dual_log_accumulator import accumulate_dual_log
from .search import build_search_matches
from .. import search_bar
# From utils.py: strip ANSI codes to measure visible column offsets
from ..utils import _ANSI_ESCAPE_RE

# FUNCTIONS

# Register one click-region segment per physical row a marker spans (wrap-straddling markers get
# 2+ segments — both are legitimate hit areas for the same worker, none is skipped)
def _register_marker_regions(regions_out: Dict[Tuple[int, int, int], str], name: str,
                              start: int, end: int, pane_width: int) -> None:
    pos = start
    while pos <= end:
        row, col = divmod(pos, pane_width)
        row_end = row * pane_width + pane_width - 1
        seg_end = min(end, row_end)
        regions_out[(col + 1, seg_end - row * pane_width + 1, row + 1)] = name
        pos = seg_end + 1

# Build header line listing workers; populates regions_out with (start_col,end_col,phys_row)->name click targets
def _format_worker_proxy_header(workers: list, current_worker: Optional[str],
                                 pane_width: int = 80,
                                 regions_out: Optional[Dict[Tuple[int, int, int], str]] = None) -> str:
    label = f"{YELLOW}WORKER-PROXY{RESET}  "
    if regions_out is not None:
        regions_out.clear()
    if not workers:
        return label + f"{DIM}no workers{RESET}"
    parts = []
    visible_col = len(_ANSI_ESCAPE_RE.sub('', label))
    for i, w in enumerate(workers, 1):
        name = w['name']
        star = '*' if name == current_worker else ''
        marker = f"[{i}{star}]{name}" if name == current_worker else f"[{i}]{name}"
        color = WHITE if name == current_worker else DIM
        parts.append(f"{color}{marker}{RESET}")
        if regions_out is not None:
            _register_marker_regions(regions_out, name, visible_col, visible_col + len(marker) - 1, pane_width)
        visible_col += len(marker) + 2
    return label + '  '.join(parts)

# Extract entry_idx from any proxy line_map key variant — shared by pane.py and
# worker_proxy_pane.py, which used to carry byte-identical private copies of this
# (`_entry_idx_from_key` / `_wp_entry_idx_from_key`, folded together 2026-09).
def _entry_idx_from_key(key) -> Optional[int]:
    if isinstance(key, int):
        return key
    if isinstance(key, tuple):
        if isinstance(key[0], str):
            return key[1]
        if isinstance(key[0], int):
            return key[0]
    return None

# Walk backward from k-1 to find first non-standalone entry idx (prev_same reference) — shared by
# pane.py and worker_proxy_pane.py (folded together 2026-09, see _entry_idx_from_key).
def _resolve_prev_same(entries: list, k: int) -> Optional[int]:
    for i in range(k - 1, -1, -1):
        if not _is_standalone_entry(entries[i]):
            return i
    return None

# Strip messages from all entries outside the keep-last window that are not expanded — shared by
# pane.py and worker_proxy_pane.py (folded together 2026-09, see _entry_idx_from_key).
def _strip_inactive_messages(entries: list, expand_states: dict) -> None:
    cutoff = max(0, len(entries) - PROXY_MESSAGES_KEEP_LAST)
    for i in range(cutoff):
        e = entries[i]
        if e.get('messages') is None:
            continue
        is_active = (
            expand_states.get(i, False) or
            expand_states.get(('req', i), False) or
            expand_states.get((i, 'neg_delta'), False)
        )
        if not is_active:
            del e['messages']

# Serialize a proxy/worker-proxy entry to full untruncated text (all new-message blocks) for
# clipboard — shared by pane.py's `_serialize_proxy` and worker_proxy_pane.py's
# `_serialize_worker_proxy` (folded together 2026-09; the worker-proxy call site now passes
# worker_proxy_entries explicitly, matching pane.py's own pre-existing signature shape).
def _serialize_proxy_entry(key, entries: list) -> str:
    entry_idx = _entry_idx_from_key(key)
    if entry_idx is None or entry_idx >= len(entries):
        return ''
    entry = entries[entry_idx]
    model = entry.get('model', '?')
    msg_count = entry.get('message_count', 0)
    parts = [f"entry_idx={entry_idx}  model={model}  msgs={msg_count}"]
    prev_same_idx = _resolve_prev_same(entries, entry_idx)
    start = entries[prev_same_idx].get('message_count', 0) if prev_same_idx is not None else 0
    for msg_idx, msg in enumerate(entry.get('messages', [])[start:], start=start):
        role = msg.get('role', '?')
        msg_type = msg.get('type', '?')
        blocks = msg.get('blocks', [])
        if blocks:
            for blk in blocks:
                ft = blk.get('full_text', blk.get('preview', ''))
                if ft:
                    parts.append(f"\n--- msg[{msg_idx}] {role} {blk.get('type', '?')} ---")
                    parts.append(ft)
        else:
            ct = msg.get('content_tail', '') or msg.get('content_preview', '')
            if ct:
                parts.append(f"\n--- msg[{msg_idx}] {role} {msg_type} ---")
                parts.append(ct)
    return '\n'.join(parts)

# Body-row copy-button click, shared half: lazy-loads messages if needed and returns the
# serialized clipboard text. The actual `copy_to_clipboard(...)` call stays in the caller's OWN
# module (pane.py / worker_proxy_pane.py) rather than here — dev/pane_error_log and
# dev/pane_search monkeypatch `copy_to_clipboard` directly on THOSE modules, which only works
# while the call site is a bare-name lookup inside them.
def _prepare_copy_text(key, entry_idx: Optional[int], entries: list, log_path) -> str:
    if entry_idx is not None and entry_idx < len(entries) and log_path:
        e = entries[entry_idx]
        if e.get('messages') is None:
            fwd_path = log_path.parent / 'dual_log' / f'{log_path.stem}_forwarded.jsonl'
            _lazy_load_messages_forwarded(e, fwd_path)
    return _serialize_proxy_entry(key, entries)

# Body-row expand/collapse click, shared half: toggles `key`'s expand state and, on becoming
# expanded, lazy-loads this entry's (and its prev-same sibling's) messages if not already
# loaded. Returns the new state (True if now expanded) — the caller decides its own
# just_expanded assignment (and, for pane.py, the undo-stack push, which needs the OLD state
# read before this call — a proxy-only feature worker_proxy_pane.py does not have).
def _toggle_expand_and_lazy_load(key, entry_idx: Optional[int], entries: list, log_path,
                                  expand_states: dict) -> bool:
    new_state = not expand_states.get(key, False)
    expand_states[key] = new_state
    if new_state and entry_idx is not None and entry_idx < len(entries) and log_path:
        e = entries[entry_idx]
        fwd_path = log_path.parent / 'dual_log' / f'{log_path.stem}_forwarded.jsonl'
        if e.get('messages') is None:
            _lazy_load_messages_forwarded(e, fwd_path)
        prev_idx = _resolve_prev_same(entries, entry_idx)
        if prev_idx is not None:
            pe = entries[prev_idx]
            if pe.get('messages') is None:
                _lazy_load_messages_forwarded(pe, fwd_path)
    return new_state

# Accumulate the stripped/injected dual-logs for one log path and attach overlay references to
# the newly-added entries — the tail both refresh functions run identically once a log path is
# known. Returns (new_stripped_pos, new_injected_pos). Shared by pane.py's and
# worker_proxy_pane.py's refresh functions (folded together 2026-09); pane.py's own
# `_original`-tools accumulation stays separate (worker_proxy_pane.py has no equivalent).
def _accumulate_dual_logs_and_attach(new_entries: list, entries: list, expand_states: dict, log_path,
                                      acc_stripped: dict, acc_injected: dict, stripped_pos: int,
                                      injected_pos: int, infer_family_fn,
                                      original_tools_by_family: Optional[dict] = None) -> tuple:
    stripped_path, injected_path = _find_dual_log_paths(log_path)
    stripped_pos = accumulate_dual_log(stripped_path, stripped_pos, acc_stripped)
    injected_pos = accumulate_dual_log(injected_path, injected_pos, acc_injected)
    _attach_overlay_references(new_entries, acc_stripped, acc_injected, infer_family_fn, original_tools_by_family)
    _strip_inactive_messages(entries, expand_states)
    return stripped_pos, injected_pos

# Attach the per-entry overlay-reference lookups (dual-log strip/inject spans + the header-badge
# flow-lookups) onto every newly-added entry — shared by pane.py's and worker_proxy_pane.py's
# refresh functions (folded together 2026-09; the ONLY difference between the two call sites was
# pane.py's extra `_original_tools_by_name` line, since only the proxy pane tracks the `_original`
# dual-log — `original_tools_by_family=None` (worker-proxy's case) simply skips that one field).
# Entries hold a Python reference to each family's accumulator dict; in-place mutations there
# propagate to every entry automatically — this function only ever ASSIGNS references, never
# copies, so that property is preserved.
def _attach_overlay_references(entries: list, acc_stripped: dict, acc_injected: dict,
                                infer_family_fn, original_tools_by_family: Optional[dict] = None) -> None:
    for entry in entries:
        family = infer_family_fn(entry.get('model', ''))
        if family not in acc_stripped:
            acc_stripped[family] = {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}, '_has_content_by_flow_id': {}, '_msg_idx_by_flow_id': {}}
            acc_injected[family] = {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}, '_has_content_by_flow_id': {}, '_msg_idx_by_flow_id': {}}
        entry['_stripped_spans'] = acc_stripped[family]
        entry['_injected_spans'] = acc_injected[family]
        entry['_strip_fns_lookup'] = acc_stripped[family].setdefault('_has_content_by_flow_id', {})
        entry['_inject_fns_lookup'] = acc_injected[family].setdefault('_has_content_by_flow_id', {})
        entry['_strip_msgs_lookup'] = acc_stripped[family].setdefault('_msg_idx_by_flow_id', {})
        entry['_inject_msgs_lookup'] = acc_injected[family].setdefault('_msg_idx_by_flow_id', {})
        # One lag set governs BOTH sides — the class it corrects is a stripped total_tokens nuke
        # plus its injected "." at the same coordinate, and only the stripped line can identify it
        entry['_lag_msgs_lookup'] = acc_stripped[family].setdefault('_lag_msg_idx_by_flow_id', {})
        if original_tools_by_family is not None:
            # Reference to this family's latest {tool_name -> tool_def} snapshot from the
            # _original dual-log — drives the whole-stripped tool row's expanded description/
            # schema (render_sections._render_whole_stripped_tool). Reference, not copy, so
            # late-arriving _original lines are handled uniformly.
            entry['_original_tools_by_name'] = original_tools_by_family.setdefault(family, {})

# Shift every row key in line_map/copy_rows by `shift` physical rows — the row-shift mechanic
# both `_build_proxy_output` and `_build_worker_proxy_output` apply (once for the initial render,
# again if a just-expanded re-render fires) to move a body-relative render into physical
# terminal rows once the pane's own fixed header height is known.
def _shift_line_map_and_copy_rows(line_map: dict, copy_rows: set, shift: int) -> None:
    shifted = {r + shift: k for r, k in line_map.items()}
    line_map.clear()
    line_map.update(shifted)
    shifted_copy = {r + shift for r in copy_rows}
    copy_rows.clear()
    copy_rows.update(shifted_copy)

# Decide whether the just-expanded/jumped-to item needs a rescroll: returns the new scroll_offset
# if `just_expanded` falls outside the current viewport, else None (caller keeps its own
# already-clamped offset and does not re-render). Pure — the caller reassigns its own
# proxy_scroll_offset/worker_proxy_scroll_offset global and performs the actual re-render.
def _resolve_just_expanded_scroll(item_positions: dict, just_expanded, scroll_offset: int,
                                   total_lines: int, viewport_lines: int) -> Optional[int]:
    if just_expanded is None or just_expanded not in item_positions:
        return None
    item_line = item_positions[just_expanded]
    max_scroll = max(0, total_lines - viewport_lines)
    clamped = min(scroll_offset, max_scroll)
    start = max(0, total_lines - viewport_lines - clamped)
    if item_line < start or item_line >= start + viewport_lines:
        return max(0, total_lines - viewport_lines - item_line)
    return None

# search_bar.py's on_commit callback, shared half: one-sweep reconstruction of ALL entries'
# messages (merged by flow_id, via forwarded_parser.reconstruct_all_messages) when a log path
# is known, then the match index via search.py's real-render-based matcher, then a jump to the
# first match if any. Shared by pane.py's `_proxy_search_on_commit` and worker_proxy_pane.py's
# `_worker_proxy_search_on_commit` (folded together 2026-09) — `jump_fn` is the caller's own
# jump-to-first-match callback (`_jump_to_search_match` / `_jump_to_wp_search_match`), since the
# scroll-jump target assignment (`_proxy_just_expanded` / `_wp_just_expanded`) is a module global
# each pane owns separately.
def _run_pane_search(state: search_bar.SearchState, entries: list, expand_states: dict,
                      pane_width: int, log_path, jump_fn) -> None:
    if not state.query:
        state.matches = []
        state.match_set = set()
        return
    if log_path is not None:
        fwd_path = log_path.parent / 'dual_log' / f'{log_path.stem}_forwarded.jsonl'
        by_flow = reconstruct_all_messages(fwd_path)
        for e in entries:
            fid = e.get('flow_id')
            if fid in by_flow:
                e['messages'] = by_flow[fid]
                e['messages_total_chars'] = sum(s.get('chars', 0) for s in by_flow[fid])
    state.matches = build_search_matches(state.query, entries, expand_states, pane_width)
    state.match_set = set(state.matches)
    state.current_idx = 0
    if state.matches:
        jump_fn()

# The scroll-wheel / row-1-drag-motion / generic-hover button classes, identical in shape across
# both proxy panes' `_handle_*_mouse` (folded together 2026-09) — parameterized over the
# caller's own SearchState/label/current scroll+hover values. Returns
# (handled, new_scroll_offset, new_hover_row). `handled` is False either when none of these four
# button classes matched (caller's OWN button==0 body-click handling still applies) OR when the
# button==32 drag-motion case matched but search_bar.handle_search_mouse_motion itself reported
# a no-op motion — its own bool return is passed straight through, not hardcoded True, so a
# motion that changed nothing still does not trigger a redraw (matches both panes' pre-split behavior).
def _handle_scroll_or_hover(button: int, col: int, row: int, state: search_bar.SearchState,
                             label: str, scroll_offset: int, hover_row) -> tuple:
    if button == 64:
        return True, max(0, scroll_offset + 3), hover_row
    if button == 65:
        return True, max(0, scroll_offset - 3), hover_row
    if button == 32 and state.dragging:  # motion with left button held (0+32), row-1 drag active
        return search_bar.handle_search_mouse_motion(state, col, label), scroll_offset, hover_row
    if button >= 32:
        return True, scroll_offset, row
    return False, scroll_offset, hover_row

# Render the body, clamp scroll, and shift into physical rows — then, if the just-expanded/
# jumped-to item falls outside the viewport, recompute scroll and render+shift AGAIN. Shared by
# `_build_proxy_output` and `_render_worker_proxy_body` (folded together 2026-09). `render_fn(
# scroll_offset, want_item_positions)` must call the caller's own `format_proxy_block(...)` and
# return `(body, total_lines, item_positions_or_None)` — `item_positions` only needed on the
# FIRST call (the second call, if it happens, renders at the already-resolved final scroll
# position, so there is nothing left to resolve a jump target against). Returns
# `(body, new_scroll_offset)` — the caller reassigns its own scroll-offset global from the
# second element; this function never touches pane globals directly, per the milestone's own
# "parameterized by explicit arguments" requirement.
def _render_and_scroll_body(render_fn, line_map: dict, copy_rows: set, header_shift: int,
                             just_expanded, scroll_offset: int, viewport_lines: int) -> tuple:
    body, total_lines, item_positions = render_fn(scroll_offset, True)
    max_scroll = max(0, total_lines - viewport_lines)
    scroll_offset = min(scroll_offset, max_scroll)
    _shift_line_map_and_copy_rows(line_map, copy_rows, header_shift)
    new_scroll = _resolve_just_expanded_scroll(item_positions, just_expanded, scroll_offset, total_lines, viewport_lines)
    if new_scroll is not None:
        scroll_offset = new_scroll
        copy_rows.clear()
        body, total_lines, _ = render_fn(scroll_offset, False)
        _shift_line_map_and_copy_rows(line_map, copy_rows, header_shift)
    return body, scroll_offset

# Current (pane_height, pane_width), falling back to a fixed default when unavailable (piped
# stdout, no tty). pane_height is term.lines - 1, NOT the raw terminal line count — both
# _build_proxy_output and _build_worker_proxy_output reserve one row this way (shell's own last
# row); the fallback default is already the final intended pane_height, no further adjustment.
def _terminal_size(default_lines: int = 50, default_cols: int = 80) -> Tuple[int, int]:
    try:
        term = os.get_terminal_size()
        return term.lines - 1, term.columns
    except OSError:
        return default_lines, default_cols
