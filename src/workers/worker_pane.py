# INFRASTRUCTURE
from typing import Dict, List, Optional, Set, Tuple
import time

from ..constants import POLL_INTERVAL, INPUT_POLL_INTERVAL
from ..jsonl import read_new_lines, parse_jsonl_lines, extract_cache_turns
from ..input.click_handler import (
    read_keypress, parse_digit_key, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
    copy_to_clipboard, wait_for_input,
)
# From worker_format.py: Worker data extraction and block rendering
from .worker_format import extract_worker_tokens, extract_worker_context_pct, format_workers_block
# From worker_tmux.py: tmux session discovery and status detection
from .worker_tmux import list_workers, find_worker_jsonl
# From worker_selection.py: selection IPC file path + write (split out 2026-09)
from .worker_selection import get_selection_file_path, _write_selection
# From worker_clipboard.py: clipboard serialization (split out 2026-09)
from .worker_clipboard import _serialize_workers
# From worker_render.py: pure viewport/row-render helpers (split out 2026-09)
from . import worker_render
# From worker_search.py: search on_commit reconstruction (split out 2026-09)
from . import worker_search
from ..ram_audit import register_ram_dump
# From pane_error_log.py: shared exception-safe pane-error sink
from ..pane_error_log import log_pane_error
# From search_bar.py: shared search-bar mechanics (state, key/mouse handling, drag-select,
# BG-restore sentinel resolution) — rollout sub-milestone 5, retrofitting the workers pane onto
# the proxy pane's reference implementation
from .. import search_bar

worker_expand_states: Dict[str, bool] = {}
worker_scroll_offsets: Dict[str, int] = {}
worker_line_map: Dict[int, str] = {}
worker_hover_row: Optional[int] = None
worker_cache_expand_states: Dict[str, Dict[tuple, bool]] = {}
worker_cache_line_map: Dict[int, tuple] = {}
worker_selected_name: Optional[str] = None
worker_scroll_offset: int = 0
worker_turns: Dict[str, list] = {}
worker_copy_rows: Set[int] = set()  # phys_rows where ⎘ copy button is rendered; populated by _build_workers_output
_worker_copy_feedback_until: Dict = {}  # name OR (name,turn_idx,call_idx) → expiry timestamp for ✓ flash
_worker_pane_width: int = 80  # updated each render cycle; used by click handler for copy-button column check
_worker_header_regions: Dict[Tuple[int, int, int], str] = {}  # (start_col,end_col,phys_row) → 'freeze'; empty when the header line has scrolled out of view

_WORKERS_SEARCH_BAR_LINES = 1  # fixed-height search bar row; the freeze badge (below it) is separate and conditional
_WORKERS_SEARCH_BAR_LABEL = 'search: '

# Search state — permanent row-1 search bar. .matches holds worker-tagged keys: str name
# (worker-level match), (name,'turn',turn_idx), or (name,turn_idx,call_idx) — see
# _workers_search_on_commit. No worker-switch reset analog exists for this pane (unlike the
# proxy/worker-proxy/tokens panes, each tracking exactly one current session/worker) — this pane
# shows ALL workers simultaneously; jump-to-match self-heals by re-parsing fresh at jump time
# (see _jump_to_workers_match), so a stale match referencing a since-vanished worker just
# becomes an inert no-op rather than showing wrong data.
_worker_search: search_bar.SearchState = search_bar.SearchState()

# ORCHESTRATOR

# Runs workers display loop (for dedicated workers tmux pane)
def run_workers_loop() -> None:
    from ..core import monitor as _monitor
    global worker_expand_states, worker_scroll_offsets, worker_line_map, worker_hover_row, worker_cache_expand_states, worker_cache_line_map, worker_selected_name, worker_scroll_offset, worker_turns, _worker_copy_feedback_until

    register_ram_dump('workers', _workers_ram_state)
    last_output = None
    workers: list = []
    worker_turns.clear()
    last_data_refresh = 0.0
    frozen = False
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            try:
                input_changed, frozen = _poll_workers_input(workers, frozen, _monitor.active_project_filter)

                now = time.time()
                workers, input_changed, last_data_refresh = _refresh_workers_data(
                    workers, now, frozen, input_changed, last_data_refresh,
                    _monitor.active_project_filter,
                )

                _worker_copy_feedback_until = {k: v for k, v in _worker_copy_feedback_until.items() if v > now}
                if _worker_copy_feedback_until:
                    input_changed = True

                if input_changed:
                    output = _build_workers_output(workers, frozen)
                    if output != last_output:
                        print("\033[2J\033[3J\033[H", end='', flush=True)
                        if output:
                            print(output)
                        last_output = output

                wait_for_input(INPUT_POLL_INTERVAL)
            except Exception:
                log_pane_error('workers')
                wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

# Drain all pending keyboard/mouse events for one tick; returns (input_changed, updated_frozen).
# Bare read_keypress/read_mouse_event lookups — must stay in THIS module (dev/pane_error_log's
# exception-survival probe monkeypatches them as attributes of src.workers.worker_pane, which
# only works while the call site doing the bare-name lookup is defined in this same module).
def _poll_workers_input(workers: list, frozen: bool, project_filter: Optional[str]) -> tuple:
    input_changed = False
    while True:
        char = read_keypress()
        if char is None:
            break
        if char == '\033':
            event = read_mouse_event(char)
            if event is not None and event[0] != -1:
                changed, frozen = _handle_workers_mouse(*event, project_filter, frozen)
                if changed:
                    input_changed = True
            elif event is not None:
                # (-1,-1,-1) release sentinel — no-op unless a row-1 drag was active
                if _handle_workers_search_release():
                    input_changed = True
            elif _worker_search.focused:  # bare ESC → cancel search
                if _handle_workers_search_cancel():
                    input_changed = True
        elif _worker_search.focused:
            if _handle_workers_search_input(char, workers, project_filter):
                input_changed = True
        elif char == '/':
            _worker_search.focused = True
            input_changed = True
        elif char in ('n', 'N'):
            if _jump_workers_search_match(char == 'n', workers, project_filter):
                input_changed = True
        else:
            changed, frozen = _handle_workers_key(char, workers, frozen, project_filter)
            if changed:
                input_changed = True
    return input_changed, frozen

# Return module-level state snapshot for RAM audit
def _workers_ram_state() -> list:
    return [
        ('worker_expand_states',       worker_expand_states),
        ('worker_scroll_offsets',      worker_scroll_offsets),
        ('worker_line_map',            worker_line_map),
        ('worker_cache_expand_states', worker_cache_expand_states),
        ('worker_cache_line_map',      worker_cache_line_map),
        ('worker_turns',               worker_turns),
        ('worker_hover_row',           str(worker_hover_row)),
        ('worker_selected_name',       str(worker_selected_name)),
        ('worker_scroll_offset',       worker_scroll_offset),
        ('_worker_search_query',       _worker_search.query),
        ('_worker_search_matches',     _worker_search.matches),
    ]

# Body-click handling for button==0, row>=2 (row 1 — the search bar — is handled by the caller).
# Header-region (freeze badge) hit, then copy-symbol hit (both row kinds), then cache-call
# toggle, then worker row select+expand. Kept local — the select branch rebinds the scalar
# global worker_selected_name, and the copy branches call copy_to_clipboard (monkeypatched by
# dev/pane_error_log and dev/pane_search as an attribute of THIS module).
def _handle_workers_body_click(col: int, row: int, project_filter: Optional[str], frozen: bool) -> tuple:
    global worker_selected_name, _worker_copy_feedback_until
    had_selection = _worker_search.sel_anchor is not None
    search_bar.clear_selection(_worker_search)
    for (sc, ec, er), action in _worker_header_regions.items():
        if row == er and sc <= col <= ec:
            if action == 'freeze':
                return True, not frozen
            return had_selection, frozen
    is_copy_click = col >= _worker_pane_width - 2 and row in worker_copy_rows
    cache_key = worker_cache_line_map.get(row)
    if cache_key:
        if is_copy_click:
            copy_to_clipboard(_serialize_workers(cache_key, worker_turns))
            _worker_copy_feedback_until[cache_key] = time.time() + 1.5
            return True, frozen
        w_name, t_idx, c_idx = cache_key
        states = worker_cache_expand_states.setdefault(w_name, {})
        states[(t_idx, c_idx)] = not states.get((t_idx, c_idx), False)
        return True, frozen
    name = worker_line_map.get(row)
    if name:
        if is_copy_click:
            copy_to_clipboard(_serialize_workers(name, worker_turns))
            _worker_copy_feedback_until[name] = time.time() + 1.5
            return True, frozen
        is_now_expanded = not worker_expand_states.get(name, False)
        worker_expand_states[name] = is_now_expanded
        if is_now_expanded:
            worker_scroll_offsets[name] = 0
        worker_selected_name = name
        _write_selection(project_filter, name)
        return True, frozen
    return had_selection, frozen

# Process one mouse event; returns (input_changed, updated_frozen)
def _handle_workers_mouse(button: int, col: int, row: int, project_filter: Optional[str], frozen: bool) -> tuple:
    global worker_hover_row
    if button == 0:
        if row == 1:  # search bar row — focuses; also anchors a potential drag-select
            return search_bar.handle_search_mouse_press(_worker_search, col, _WORKERS_SEARCH_BAR_LABEL), frozen
        return _handle_workers_body_click(col, row, project_filter, frozen)
    if button in (64, 65):
        changed = worker_render.apply_scroll(button, row, worker_cache_line_map, worker_line_map, worker_selected_name, worker_scroll_offsets)
        return changed, frozen
    if button == 32 and _worker_search.dragging:  # motion with left button held (0+32), row-1 drag active
        return search_bar.handle_search_mouse_motion(_worker_search, col, _WORKERS_SEARCH_BAR_LABEL), frozen
    if button >= 32:
        worker_hover_row = row
        return True, frozen
    return False, frozen

# Process one non-escape key event; returns (input_changed, updated_frozen)
def _handle_workers_key(char: str, workers: list, frozen: bool, project_filter: Optional[str]) -> tuple:
    global worker_selected_name
    if char == 'y':
        key = worker_render._resolve_workers_hover_key(worker_hover_row, worker_cache_line_map, worker_line_map)
        if key is not None:
            copy_to_clipboard(_serialize_workers(key, worker_turns))
        return False, frozen
    if char == 'f':
        return True, not frozen
    idx = parse_digit_key(char)
    if idx is not None and 1 <= idx <= len(workers):
        name = workers[idx - 1]['name']
        is_now_expanded = not worker_expand_states.get(name, False)
        worker_expand_states[name] = is_now_expanded
        if is_now_expanded:
            worker_scroll_offsets[name] = 0
        worker_selected_name = name
        _write_selection(project_filter, name)
        return True, frozen
    return False, frozen

# Cancel active search on bare ESC while focused; bar stays visible with an empty query.
# Thin wrapper — search_bar.handle_search_cancel resets query/focused/matches/match_set/
# selection all at once, identical across every pane.
def _handle_workers_search_cancel() -> bool:
    return search_bar.handle_search_cancel(_worker_search)

# Handle keyboard input while the search bar is focused; returns True if input_changed. Thin
# wrapper over search_bar.handle_search_input — on_commit is a closure binding this tick's
# `workers` list and `project_filter` plus the injected `_load_worker_turns`/jump callables
# worker_search.workers_search_on_commit needs (search_bar's generic on_commit signature only
# ever passes `state`, so the extra context this pane needs is captured here).
def _handle_workers_search_input(char: str, workers: list, project_filter: Optional[str]) -> bool:
    on_commit = lambda state: worker_search.workers_search_on_commit(
        state, workers, project_filter, _worker_pane_width, worker_turns,
        _load_worker_turns, lambda: _jump_to_workers_match(workers, project_filter),
    )
    return search_bar.handle_search_input(_worker_search, char, on_commit=on_commit)

# Jump to the next (forward=True) or previous search match, wrapping around; returns True if
# a jump happened (False when there are no matches, e.g. before the first Enter)
def _jump_workers_search_match(forward: bool, workers: list, project_filter: Optional[str]) -> bool:
    if not _worker_search.matches:
        return False
    _worker_search.current_idx = (_worker_search.current_idx + (1 if forward else -1)) % len(_worker_search.matches)
    _jump_to_workers_match(workers, project_filter)
    return True

# Auto-expand + auto-select the current match's worker (uniform across all 3 match levels).
# Deliberately NEVER touches worker_scroll_offset (the dormant pane-level bottom-anchor
# fail-safe — see this module's own Gotcha in workers/DOCS.md). Self-healing: ALWAYS re-parses
# the target worker's JSONL fresh at jump time rather than trusting worker_turns (which
# _refresh_workers_data clears every poll tick for a non-expanded worker). Kept local — rebinds
# the scalar global worker_selected_name.
def _jump_to_workers_match(workers: list, project_filter: Optional[str]) -> None:
    global worker_selected_name
    state = _worker_search
    if not state.matches or state.current_idx >= len(state.matches):
        return
    key = state.matches[state.current_idx]
    name = key if isinstance(key, str) else key[0]
    worker_expand_states[name] = True
    worker_selected_name = name
    _write_selection(project_filter, name)
    w = next((w for w in workers if w.get('name') == name), None)
    if w is None:
        return  # worker vanished between match and jump — self-healing no-op, not a crash
    turns = _load_worker_turns(w.get('session', ''))
    if turns is None:
        return
    worker_turns[name] = turns
    if isinstance(key, str):
        return  # worker-level match — nothing further to scroll to within the nested view
    per_worker_expand = worker_cache_expand_states.get(name, {})
    new_offset = worker_render.compute_jump_scroll_offset(key, turns, per_worker_expand, _worker_pane_width)
    if new_offset is not None:
        worker_scroll_offsets[name] = new_offset

# Finalize a row-1 drag on SGR mouse release; returns True if a redraw is needed. No-op (False)
# unless a row-1 drag was actually in progress. Thin wrapper — release-copies-to-clipboard is
# identical across every pane.
def _handle_workers_search_release() -> bool:
    return search_bar.handle_search_mouse_release(_worker_search, copy_to_clipboard)

# Render the always-visible search bar (row 1). Thin wrapper binding this pane's own label.
def _render_workers_search_bar(pane_width: int) -> str:
    return search_bar.render_search_bar(_worker_search, pane_width, label=_WORKERS_SEARCH_BAR_LABEL)

# Parse a worker's turns from an already-resolved JSONL path — the read->parse->extract half of
# the repeated chain, with no find_worker_jsonl call of its own (safe to reuse from anywhere
# that already has jsonl_path, e.g. _refresh_workers_data's own two loops).
def _parse_worker_turns(jsonl_path) -> list:
    lines = read_new_lines(jsonl_path, 0)
    messages, _ = parse_jsonl_lines(lines)
    return extract_cache_turns(messages)

# Resolve a worker's JSONL by session name and parse its turns fresh — the full find_worker_jsonl
# -> read_new_lines -> parse_jsonl_lines -> extract_cache_turns chain the on-commit search, jump,
# and refresh paths all repeated before this milestone, now the single source. None when no JSONL
# is found. Kept local — the ONE place doing find_worker_jsonl(...) (dev/pane_search/p7's
# monkeypatch target), so callers stay patchable regardless of where the caller itself lives.
def _load_worker_turns(session: str) -> Optional[list]:
    jsonl_path = find_worker_jsonl(session)
    if jsonl_path is None:
        return None
    return _parse_worker_turns(jsonl_path)

# Tick-boundary worker data refresh; returns (workers, input_changed, new_last_data_refresh)
def _refresh_workers_data(workers: list, now: float, frozen: bool, input_changed: bool,
                           last_data_refresh: float, project_filter: Optional[str]) -> tuple:
    global worker_turns, worker_selected_name
    if not frozen and now - last_data_refresh >= POLL_INTERVAL:
        workers = list_workers(project_filter) if project_filter else []
        if worker_selected_name is None and workers:
            worker_selected_name = workers[0]['name']
            _write_selection(project_filter, worker_selected_name)
        worker_turns.clear()
        for w in workers:
            name = w.get('name', '')
            jsonl_path = find_worker_jsonl(w.get('session', ''))
            if jsonl_path:
                w['tokens'] = extract_worker_tokens(jsonl_path)
                w['context_pct'] = extract_worker_context_pct(jsonl_path)
                if worker_expand_states.get(name, False):
                    worker_turns[name] = _parse_worker_turns(jsonl_path)
        return workers, True, now
    if input_changed:
        for w in workers:
            name = w.get('name', '')
            if worker_expand_states.get(name, False) and name not in worker_turns:
                jsonl_path = find_worker_jsonl(w.get('session', ''))
                if jsonl_path:
                    worker_turns[name] = _parse_worker_turns(jsonl_path)
    return workers, input_changed, last_data_refresh

# Format, clip viewport, and render workers to ANSI string; updates worker_line_map and worker_cache_line_map
def _build_workers_output(workers: list, frozen: bool) -> str:
    global worker_scroll_offset, _worker_pane_width, _worker_header_regions
    _worker_freeze_span: dict = {}
    current_match_key = (
        _worker_search.matches[_worker_search.current_idx]
        if _worker_search.matches and _worker_search.current_idx < len(_worker_search.matches)
        else None
    )
    all_lines, line_keys = format_workers_block(
        workers, worker_expand_states, worker_turns,
        worker_scroll_offsets, worker_cache_expand_states,
        frozen=frozen, selected_name=worker_selected_name,
        copy_feedback=_worker_copy_feedback_until,
        regions_out=_worker_freeze_span,
        search_match_set=_worker_search.match_set, search_current_key=current_match_key,
        search_query=_worker_search.query,
    )
    pane_height, pane_width = worker_render._workers_terminal_size()
    _worker_pane_width = pane_width
    content_height = pane_height - _WORKERS_SEARCH_BAR_LINES  # search bar always wins row 1
    # Viewport clipping: phys_row (1+_WORKERS_SEARCH_BAR_LINES)..N must equal terminal row
    # (1+_WORKERS_SEARCH_BAR_LINES)..N. worker_scroll_offset > 0 shifts viewport toward older
    # content (dormant in practice — see this module's own Gotcha in workers/DOCS.md).
    total_lines = len(all_lines)
    worker_scroll_offset, vp_start = worker_render._compute_viewport(total_lines, content_height, worker_scroll_offset)
    visible_all = all_lines[vp_start:vp_start + content_height]
    visible_keys = line_keys[vp_start:vp_start + content_height]
    worker_line_map.clear()
    worker_cache_line_map.clear()
    worker_copy_rows.clear()
    # Freeze badge is always all_lines[0] — only clickable when it survived viewport clipping
    # (vp_start == 0 AND at least one line is visible; a scrolled-away header registers nothing,
    # never a stale/wrong-row region). Row shifted by _WORKERS_SEARCH_BAR_LINES since the search
    # bar now owns physical row 1.
    _worker_header_regions.clear()
    if 'freeze' in _worker_freeze_span and vp_start == 0 and visible_all:
        sc, ec = _worker_freeze_span['freeze']
        _worker_header_regions[(sc, ec, 1 + _WORKERS_SEARCH_BAR_LINES)] = 'freeze'
    parent_count = sum(1 for k in line_keys[:vp_start] if isinstance(k, str))
    body_lines = worker_render._render_workers_rows(
        visible_all, visible_keys, worker_hover_row, 1 + _WORKERS_SEARCH_BAR_LINES, parent_count,
        pane_width, worker_line_map, worker_cache_line_map, worker_copy_rows,
    )
    result_lines = [_render_workers_search_bar(pane_width)] + body_lines
    return '\n'.join(result_lines)
