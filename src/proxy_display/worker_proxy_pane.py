# INFRASTRUCTURE
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import time

from ..constants import (
    RESET, YELLOW, DIM,
    POLL_INTERVAL, INPUT_POLL_INTERVAL,
    PROXY_REPARSE_INTERVAL_SECONDS,
)
from .parser import find_worker_proxy_log
from .forwarded_parser import _parse_forwarded_log, _infer_model_family
from .format import format_proxy_block
from ..panes.cache_turns import build_cache_turns
from ..workers.worker_tmux import find_worker_jsonl, list_workers
from ..workers.worker_pane import get_selection_file_path
from ..workers import write_selection
from ..input.click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event, parse_digit_key, copy_to_clipboard, wait_for_input,
)
from ..utils import visual_line_count
from ..ram_audit import register_ram_dump
# From pane_error_log.py: shared exception-safe pane-error sink
from ..pane_error_log import log_pane_error
from .proxy_pane_shared import (
    _format_worker_proxy_header, _entry_idx_from_key, _prepare_copy_text, _toggle_expand_and_lazy_load,
    _terminal_size, _run_pane_search, _handle_scroll_or_hover, _render_and_scroll_body,
    _accumulate_dual_logs_and_attach,
)
# From search_bar.py: shared search-bar mechanics (state, key/mouse handling, drag-select) —
# rollout sub-milestone 3, retrofitting the worker-proxy pane onto the proxy pane's reference
# implementation (src/proxy_display/pane.py, this pane's closest structural twin)
from .. import search_bar

worker_proxy_entries: List[dict] = []
worker_proxy_expand_states: Dict[int, bool] = {}
worker_proxy_line_map: Dict[int, int] = {}
worker_proxy_hover_row, worker_proxy_scroll_offset, worker_proxy_log_position = None, 0, 0

_worker_proxy_jsonl_position, _worker_proxy_cache_turns, _worker_proxy_workers, _worker_proxy_force_reload = 0, [], [], False
_worker_proxy_fwd_pos: int = 0          # forwarded-log byte position for incremental reads
_worker_proxy_acc_fwd: dict = {}        # family accumulator for _parse_forwarded_log
_worker_proxy_log_path: Optional[Path] = None  # current log file path, updated each poll cycle for lazy-reload
_worker_proxy_pane_width: int = 80  # updated each render cycle; used by click handler for copy-button column check
_worker_proxy_copy_rows: Set[int] = set()  # phys_rows where ⎘ copy button is rendered; populated by format_proxy_block
_worker_copy_feedback_until: Dict[int, float] = {}  # entry_idx → expiry timestamp for ✓ flash
_worker_proxy_last_full_parse_ts: float = 0.0  # timestamp of last re-init to position 0 (time-triggered reset)
_wp_just_expanded = None  # line_map key set by mouse handler on expand; cleared by _build_worker_proxy_output
_worker_proxy_last_worker_name: Optional[str] = None  # tracks worker change for full state reset
_worker_proxy_stripped_pos: int = 0    # dual-log read position for _stripped.jsonl
_worker_proxy_injected_pos: int = 0    # dual-log read position for _injected.jsonl
_worker_proxy_acc_stripped: dict = {}  # family → {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}}
_worker_proxy_acc_injected: dict = {}  # same; entries hold Python refs so in-place updates propagate
_worker_proxy_header_regions: Dict[Tuple[int, int, int], str] = {}  # (start_col,end_col,phys_row) → worker name; header marker click targets

_WP_SEARCH_BAR_LINES = 1  # fixed-height search bar row; unlike the worker-switcher header below it, this never wraps
_WP_SEARCH_BAR_LABEL = 'search: '  # matches the proxy pane's label — this pane's closest structural twin

# Search state — permanent row-1 search bar, shifting the worker-switcher header (variable
# height, click-region table) down by _WP_SEARCH_BAR_LINES. .matches holds entry_idx values,
# ordered by position in worker_proxy_entries — same shape/mechanics as pane.py's _proxy_search.
_worker_proxy_search: search_bar.SearchState = search_bar.SearchState()

# ORCHESTRATOR

# Runs worker-proxy pane — reads selected worker's proxy log and shows expandable entries
def run_worker_proxy_loop() -> None:
    from ..core import monitor as _monitor
    global _worker_copy_feedback_until
    register_ram_dump('worker_proxy', _worker_proxy_ram_state)
    last_output = None
    last_data_refresh = 0.0
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            try:
                input_changed = _poll_worker_proxy_input(_monitor)
                now = time.time()
                input_changed, last_data_refresh = _refresh_worker_proxy_data(now, input_changed, last_data_refresh, _monitor)
                _worker_copy_feedback_until = {k: v for k, v in _worker_copy_feedback_until.items() if v > now}
                if _worker_copy_feedback_until:
                    input_changed = True
                if input_changed:
                    output, header = _build_worker_proxy_output(_monitor)
                    if output != last_output:
                        print("\033[2J\033[3J\033[H", end='', flush=True)
                        if output:
                            print(output, end='', flush=True)
                            print(f"\033[H{header}\033[K", end='', flush=True)
                        last_output = output
                wait_for_input(INPUT_POLL_INTERVAL)
            except Exception:
                log_pane_error('worker_proxy')
                wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

# Drain the keyboard/mouse queue for one tick; returns True if any event changed display
# state. Stays LOCAL (not shared) — dev/pane_error_log monkeypatches read_keypress directly on
# THIS module, which only works while the call site is a bare-name lookup inside it.
def _poll_worker_proxy_input(monitor) -> bool:
    input_changed = False
    while True:
        char = read_keypress()
        if char is None:
            break
        if char == '\033':
            event = read_mouse_event(char)
            if event is not None and event[0] != -1:
                if _handle_worker_proxy_mouse(*event, monitor):
                    input_changed = True
            elif event is not None:
                # (-1,-1,-1) release sentinel — no-op unless a row-1 drag was active
                if _handle_worker_proxy_search_release():
                    input_changed = True
            elif _worker_proxy_search.focused:  # bare ESC → cancel search
                if _handle_worker_proxy_search_cancel():
                    input_changed = True
        elif _worker_proxy_search.focused:
            if _handle_worker_proxy_search_input(char):
                input_changed = True
        elif char == '/':
            _worker_proxy_search.focused = True
            input_changed = True
        elif char in ('n', 'N'):
            if _jump_worker_search_match(forward=(char == 'n')):
                input_changed = True
        else:
            if _handle_worker_proxy_key(char, monitor):
                input_changed = True
    return input_changed

# Return module-level state snapshot for RAM audit
def _worker_proxy_ram_state() -> list:
    return [
        ('worker_proxy_entries',          worker_proxy_entries),
        ('worker_proxy_expand_states',    worker_proxy_expand_states),
        ('worker_proxy_line_map',         worker_proxy_line_map),
        ('_worker_proxy_cache_turns',     _worker_proxy_cache_turns),
        ('_worker_proxy_workers',         _worker_proxy_workers),
        ('_worker_proxy_fwd_pos',         _worker_proxy_fwd_pos),
        ('_worker_proxy_acc_fwd',         _worker_proxy_acc_fwd),
        ('worker_proxy_hover_row',        str(worker_proxy_hover_row)),
        ('worker_proxy_scroll_offset',    worker_proxy_scroll_offset),
        ('worker_proxy_log_position',     worker_proxy_log_position),
        ('_worker_proxy_jsonl_position',  _worker_proxy_jsonl_position),
        ('_worker_proxy_force_reload',    _worker_proxy_force_reload),
        ('_worker_proxy_stripped_pos',    _worker_proxy_stripped_pos),
        ('_worker_proxy_injected_pos',    _worker_proxy_injected_pos),
        ('_worker_proxy_acc_stripped',    _worker_proxy_acc_stripped),
        ('_worker_proxy_acc_injected',    _worker_proxy_acc_injected),
        ('_worker_proxy_search_query',    _worker_proxy_search.query),
        ('_worker_proxy_search_matches',  _worker_proxy_search.matches),
    ]

# Body-row copy click: lazy-load+serialize half is shared (proxy_pane_shared._prepare_copy_text).
def _handle_worker_proxy_copy_click(key, entry_idx: Optional[int]) -> None:
    global _worker_copy_feedback_until
    copy_to_clipboard(_prepare_copy_text(key, entry_idx, worker_proxy_entries, _worker_proxy_log_path))
    if entry_idx is not None:
        _worker_copy_feedback_until[entry_idx] = time.time() + 1.5

# Body-row expand click: delegates to proxy_pane_shared._toggle_expand_and_lazy_load.
def _handle_worker_proxy_expand_click(key, entry_idx: Optional[int]) -> None:
    global _wp_just_expanded
    if _toggle_expand_and_lazy_load(key, entry_idx, worker_proxy_entries, _worker_proxy_log_path, worker_proxy_expand_states):
        _wp_just_expanded = key

# Process one mouse event; returns True if display should refresh
def _handle_worker_proxy_mouse(button: int, col: int, row: int, monitor) -> bool:
    global worker_proxy_scroll_offset, worker_proxy_hover_row, _worker_proxy_force_reload
    if button == 0:
        if row == 1:  # search bar row — focuses; also anchors a potential drag-select
            return search_bar.handle_search_mouse_press(_worker_proxy_search, col, _WP_SEARCH_BAR_LABEL)
        # Click elsewhere (header markers or body) clears any lingering drag-selection highlight
        # (before the header-region/body lookups below, so even a click on an unmapped row clears it)
        had_selection = _worker_proxy_search.sel_anchor is not None
        search_bar.clear_selection(_worker_proxy_search)
        for (sc, ec, er), name in _worker_proxy_header_regions.items():
            if row == er and sc <= col <= ec:
                if any(w['name'] == name for w in _worker_proxy_workers):
                    write_selection(monitor.active_project_filter, name)
                    _worker_proxy_force_reload = True
                return True
        key = worker_proxy_line_map.get(row)
        if key is None:
            return had_selection
        is_req = (isinstance(key, tuple) and key[0] == 'req') or isinstance(key, int)
        entry_idx = _entry_idx_from_key(key)
        if is_req and col >= _worker_proxy_pane_width - 2 and row in _worker_proxy_copy_rows:
            _handle_worker_proxy_copy_click(key, entry_idx)
        else:
            _handle_worker_proxy_expand_click(key, entry_idx)
        return True
    # Scroll wheel / row-1 drag motion / generic hover — shared with pane.py.
    handled, worker_proxy_scroll_offset, worker_proxy_hover_row = _handle_scroll_or_hover(
        button, col, row, _worker_proxy_search, _WP_SEARCH_BAR_LABEL, worker_proxy_scroll_offset, worker_proxy_hover_row)
    return handled

# Cancel active search on bare ESC while focused; bar stays visible with an empty query.
# Returns True (always triggers redraw). Thin wrapper — search_bar.handle_search_cancel resets
# query/focused/matches/match_set/selection all at once, identical across every pane.
def _handle_worker_proxy_search_cancel() -> bool:
    return search_bar.handle_search_cancel(_worker_proxy_search)

# Handle keyboard input while the search bar is focused; returns True if input_changed. Thin
# wrapper over search_bar.handle_search_input — _worker_proxy_search_on_commit is the
# pane-specific "run the actual search" callback, injected so the shared module stays
# data-model-agnostic.
def _handle_worker_proxy_search_input(char: str) -> bool:
    return search_bar.handle_search_input(_worker_proxy_search, char, on_commit=_worker_proxy_search_on_commit)

# on_commit callback for search_bar.handle_search_input (fires on Enter) — shared half lives
# in proxy_pane_shared._run_pane_search (with pane.py); always re-runs, no unchanged-query gate
# (no main-pane-style gate ever existed here to correct).
def _worker_proxy_search_on_commit(state: search_bar.SearchState) -> None:
    _run_pane_search(state, worker_proxy_entries, worker_proxy_expand_states, _worker_proxy_pane_width, _worker_proxy_log_path, _jump_to_wp_search_match)

# Jump to the next (forward=True) or previous search match, wrapping around; returns True if
# a jump happened (False when there are no matches, e.g. before the first Enter)
def _jump_worker_search_match(forward: bool) -> bool:
    if not _worker_proxy_search.matches:
        return False
    _worker_proxy_search.current_idx = (_worker_proxy_search.current_idx + (1 if forward else -1)) % len(_worker_proxy_search.matches)
    _jump_to_wp_search_match()
    return True

# Set the scroll-jump target to the current search match's REQ header row — reuses the EXISTING
# _wp_just_expanded/worker_item_positions/scroll-clamp mechanics in _build_worker_proxy_output
# (same anchor for both collapsed and expanded matches; ('req', idx) is always in item_positions
# regardless of expand state, since render_turn.py appends req_key unconditionally)
def _jump_to_wp_search_match() -> None:
    global _wp_just_expanded
    target_entry_idx = _worker_proxy_search.matches[_worker_proxy_search.current_idx]
    _wp_just_expanded = ('req', target_entry_idx)

# Finalize a row-1 drag on SGR mouse release; returns True if a redraw is needed. No-op (False)
# unless a row-1 drag was actually in progress — safe to call unconditionally on EVERY release
# sentinel, including releases after a plain click elsewhere (never armed) or after a normal
# header-marker/expand click (never armed either, dragging only set True by a row-1 press).
# Thin wrapper — release-copies-to-clipboard is identical across every pane.
def _handle_worker_proxy_search_release() -> bool:
    return search_bar.handle_search_mouse_release(_worker_proxy_search, copy_to_clipboard)

# Render the always-visible search bar (row 1). Thin wrapper binding this pane's own label.
def _render_worker_proxy_search_bar(pane_width: int) -> str:
    return search_bar.render_search_bar(_worker_proxy_search, pane_width, label=_WP_SEARCH_BAR_LABEL)

# Read the currently-selected worker name from the IPC selection file — shared by
# _refresh_worker_proxy_data and _build_worker_proxy_header_block.
def _read_selected_worker_name(monitor) -> Optional[str]:
    sel_path = get_selection_file_path(monitor.active_project_filter)
    try:
        with open(sel_path, 'r', encoding='utf-8') as f:
            return f.read().strip() or None
    except OSError:
        return None

# Process one digit-key event; writes worker selection via IPC; returns True if display should refresh
def _handle_worker_proxy_key(char: str, monitor) -> bool:
    global _worker_proxy_force_reload
    idx = parse_digit_key(char)
    if idx is not None and _worker_proxy_workers and 1 <= idx <= len(_worker_proxy_workers):
        write_selection(monitor.active_project_filter, _worker_proxy_workers[idx - 1]['name'])
        _worker_proxy_force_reload = True
        return True
    return False

# The parse-position/accumulator reset both worker-proxy resets clear IDENTICALLY — reparse
# resets only this; worker-selection resets this PLUS its own extra fields (below). Factored
# out 2026-09 (LOC-limit split) since reparse's own reset was a strict line-for-line subset of
# selection-change's.
def _reset_worker_proxy_positions(now: float) -> None:
    global worker_proxy_log_position, _worker_proxy_jsonl_position, _worker_proxy_cache_turns, _worker_proxy_fwd_pos
    global _worker_proxy_last_full_parse_ts, _worker_proxy_stripped_pos, _worker_proxy_injected_pos
    for c in (worker_proxy_entries, worker_proxy_line_map, _worker_proxy_acc_fwd, _worker_proxy_acc_stripped, _worker_proxy_acc_injected):
        c.clear()
    worker_proxy_log_position = _worker_proxy_jsonl_position = _worker_proxy_fwd_pos = 0
    _worker_proxy_cache_turns = []
    _worker_proxy_last_full_parse_ts = now
    _worker_proxy_stripped_pos = _worker_proxy_injected_pos = 0

# Worker-selection reset: clears every piece of incremental state tied to the previous
# selected worker (entries, positions, accumulators, search).
def _reset_worker_proxy_selection_state(now: float, worker_name: Optional[str]) -> None:
    global _worker_proxy_log_path, _worker_proxy_last_worker_name, worker_proxy_scroll_offset, worker_proxy_hover_row
    _reset_worker_proxy_positions(now)
    worker_proxy_expand_states.clear()
    worker_proxy_scroll_offset, worker_proxy_hover_row, _worker_proxy_log_path, _worker_proxy_last_worker_name = 0, None, None, worker_name
    # A stale _worker_proxy_search.matches list holds entry_idx values into the log just
    # switched away from — reset query/focused/matches/selection (mirrors pane.py's
    # session-change reset). Whether the switch came from a digit key or a header-marker
    # click, both converge here.
    search_bar.handle_search_cancel(_worker_proxy_search)

# Hourly reparse reset: re-runs the log from position 0 without disturbing which worker is selected.
def _reset_worker_proxy_reparse_state(now: float) -> None:
    _reset_worker_proxy_positions(now)

# Tick-boundary worker-proxy data refresh; returns (input_changed, new_last_data_refresh)
def _refresh_worker_proxy_data(now: float, input_changed: bool, last_data_refresh: float, monitor) -> tuple:
    global _worker_proxy_jsonl_position, _worker_proxy_cache_turns, _worker_proxy_fwd_pos, _worker_proxy_log_path
    global _worker_proxy_last_full_parse_ts, _worker_proxy_workers, _worker_proxy_force_reload, _worker_proxy_stripped_pos, _worker_proxy_injected_pos
    if not _worker_proxy_force_reload and now - last_data_refresh < POLL_INTERVAL:
        return input_changed, last_data_refresh
    _worker_proxy_force_reload = False
    worker_name = _read_selected_worker_name(monitor)
    _worker_proxy_workers = list_workers(monitor.active_project_filter) if monitor.active_project_filter else []
    if not _worker_proxy_workers:
        worker_name = None
    elif worker_name is not None and worker_name not in {w['name'] for w in _worker_proxy_workers}:
        worker_name = None
    if worker_name != _worker_proxy_last_worker_name:
        _reset_worker_proxy_selection_state(now, worker_name)
        input_changed = True
    if _worker_proxy_last_full_parse_ts == 0.0:
        _worker_proxy_last_full_parse_ts = now
    elif now - _worker_proxy_last_full_parse_ts >= PROXY_REPARSE_INTERVAL_SECONDS:
        _reset_worker_proxy_reparse_state(now)
        input_changed = True
    if worker_name:
        log_path = find_worker_proxy_log(worker_name, monitor.active_project_filter)
        if log_path:
            fwd_path = log_path.parent / 'dual_log' / f'{log_path.stem}_forwarded.jsonl'
            new_entries, _worker_proxy_fwd_pos = _parse_forwarded_log(fwd_path, _worker_proxy_fwd_pos, _worker_proxy_acc_fwd)
            for entry in new_entries:
                entry['_source_file'] = fwd_path.name
            worker_proxy_entries.extend(new_entries)
            _worker_proxy_stripped_pos, _worker_proxy_injected_pos = _accumulate_dual_logs_and_attach(
                new_entries, worker_proxy_entries, worker_proxy_expand_states, log_path,
                _worker_proxy_acc_stripped, _worker_proxy_acc_injected, _worker_proxy_stripped_pos, _worker_proxy_injected_pos, _infer_model_family)
            _worker_proxy_log_path = log_path
            if new_entries:
                input_changed = True
        worker_session = next((w.get('session', '') for w in _worker_proxy_workers if w.get('name') == worker_name), '')
        worker_jsonl = find_worker_jsonl(worker_session) if worker_session else None
        if worker_jsonl:
            _worker_proxy_cache_turns, _worker_proxy_jsonl_position = build_cache_turns(worker_jsonl, _worker_proxy_jsonl_position, _worker_proxy_cache_turns)
    return True, now

# Build and shift the search-bar + worker-switcher header block; returns (header, total_header_lines, current_worker).
def _build_worker_proxy_header_block(monitor, pane_width: int) -> tuple:
    current_worker = _read_selected_worker_name(monitor)
    search_bar_line = _render_worker_proxy_search_bar(pane_width)
    worker_header = _format_worker_proxy_header(_worker_proxy_workers, current_worker, pane_width, _worker_proxy_header_regions)
    # _format_worker_proxy_header computes region rows RELATIVE to its own top (row 1 = its own
    # first line) — shift them by _WP_SEARCH_BAR_LINES so they become physical rows, now that
    # the search bar takes row 1 and the worker header starts one row lower. Rebuilt fresh every
    # call (the helper itself clears regions_out), so this shift never accumulates.
    if _worker_proxy_header_regions:
        shifted_regions = {(sc, ec, er + _WP_SEARCH_BAR_LINES): name for (sc, ec, er), name in _worker_proxy_header_regions.items()}
        _worker_proxy_header_regions.clear()
        _worker_proxy_header_regions.update(shifted_regions)
    total_header_lines = _WP_SEARCH_BAR_LINES + visual_line_count(worker_header, pane_width)
    return search_bar_line + '\n' + worker_header, total_header_lines, current_worker

# Render the entries body — scroll clamp/row-shift/just-expanded rescroll shared via
# proxy_pane_shared._render_and_scroll_body (with pane.py).
def _render_worker_proxy_body(pane_width: int, content_height: int, total_header_lines: int, body_hover) -> str:
    global worker_proxy_scroll_offset, _worker_proxy_copy_rows
    _worker_proxy_copy_rows.clear()
    # format_proxy_block is called with content_height as its own pane_height argument and
    # internally derives its real viewport as max(1, pane_height - 1) — mirror that exact
    # value here (once) so both clamp sites below match what the renderer actually shows,
    # never content_height itself.
    viewport_lines_n = max(1, content_height - 1)
    matches = _worker_proxy_search.matches
    current_match_entry_idx = matches[_worker_proxy_search.current_idx] if matches and _worker_proxy_search.current_idx < len(matches) else None
    def _render(scroll_offset, want_item_positions):
        item_positions = {} if want_item_positions else None
        body, total_lines = format_proxy_block(
            worker_proxy_entries, worker_proxy_expand_states, worker_proxy_line_map, body_hover, content_height, pane_width, scroll_offset,
            turns=_worker_proxy_cache_turns, item_positions_out=item_positions, copy_feedback=_worker_copy_feedback_until, copy_rows_out=_worker_proxy_copy_rows,
            search_match_set=_worker_proxy_search.match_set, search_current_entry_idx=current_match_entry_idx, search_query=_worker_proxy_search.query)
        return body, total_lines, item_positions
    body, worker_proxy_scroll_offset = _render_and_scroll_body(
        _render, worker_proxy_line_map, _worker_proxy_copy_rows, total_header_lines, _wp_just_expanded, worker_proxy_scroll_offset, viewport_lines_n)
    return body

# Build ANSI output for worker-proxy pane with header+body split; returns (output, header) for overdraw
def _build_worker_proxy_output(monitor) -> tuple:
    global _worker_proxy_pane_width, worker_proxy_hover_row, _wp_just_expanded
    pane_height, pane_width = _terminal_size()
    _worker_proxy_pane_width = pane_width
    header, total_header_lines, current_worker = _build_worker_proxy_header_block(monitor, pane_width)
    content_height = max(1, pane_height - total_header_lines)
    body_hover = (worker_proxy_hover_row - total_header_lines) if worker_proxy_hover_row and worker_proxy_hover_row > total_header_lines else None
    if not current_worker:
        body = f"{DIM}Select a worker with digit keys 1-9{RESET}"
    elif not worker_proxy_entries:
        body = f"{YELLOW}Worker: {current_worker}{RESET}\n{DIM}No proxy data yet — is worker proxy running?{RESET}"
    else:
        body = _render_worker_proxy_body(pane_width, content_height, total_header_lines, body_hover)
    _wp_just_expanded = None
    return header + '\n' + body, header
