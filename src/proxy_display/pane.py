# INFRASTRUCTURE
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
import time

from ..constants import (
    POLL_INTERVAL, INPUT_POLL_INTERVAL, PROXY_MESSAGES_KEEP_LAST,
    PROXY_REPARSE_INTERVAL_SECONDS,
)
from .parser import find_proxy_log_path, _find_original_log_path
from .forwarded_parser import parse_proxy_log_forwarded, _infer_model_family
from .dual_log_accumulator import accumulate_original_tools
from .proxy_pane_shared import (
    _entry_idx_from_key, _terminal_size, _prepare_copy_text, _toggle_expand_and_lazy_load,
    _run_pane_search, _handle_scroll_or_hover, _render_and_scroll_body, _accumulate_dual_logs_and_attach,
)
from .format import format_proxy_block
from ..panes.cache_turns import build_cache_turns
from ..input.click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event, copy_to_clipboard, wait_for_input,
)
from ..ram_audit import register_ram_dump
from ..pane_error_log import log_pane_error
from .. import search_bar

_PROXY_HEADER_LINES = 1
_SEARCH_BAR_LABEL = 'search: '

_KILL_LINE_CHAR = search_bar.KILL_LINE_CHAR

proxy_entries: List[dict] = []
proxy_expand_states: Dict[int, bool] = {}
proxy_line_map: Dict[int, int] = {}
proxy_hover_row: Optional[int] = None
proxy_scroll_offset: int = 0
proxy_log_position: int = 0

_proxy_jsonl_position: int = 0
_proxy_cache_turns: list = []
_proxy_fwd_pos: int = 0
_proxy_acc_fwd: dict = {}
_proxy_stripped_pos: int = 0
_proxy_injected_pos: int = 0
_proxy_acc_stripped: dict = {}
_proxy_acc_injected: dict = {}
_proxy_original_pos: int = 0
_proxy_acc_original: dict = {}
_proxy_log_path: Optional[Path] = None
_proxy_pane_width: int = 80
_proxy_copy_rows: Set[int] = set()
_copy_feedback_until: Dict[int, float] = {}
_last_full_parse_ts: float = 0.0
_proxy_just_expanded = None
_proxy_current_main_session: Optional[str] = None
_proxy_session_start_ts: Optional[str] = None
_proxy_undo_stack: list = []

_proxy_search: search_bar.SearchState = search_bar.SearchState()

# ORCHESTRATOR

def run_proxy_loop() -> None:
    from ..core import monitor as _monitor
    global _proxy_current_main_session, _proxy_session_start_ts, _copy_feedback_until

    register_ram_dump('proxy', _proxy_ram_state)
    _proxy_current_main_session = _monitor._get_newest_main_session()
    _proxy_session_start_ts = _monitor._get_session_start_ts()
    if _proxy_session_start_ts is None:
        _proxy_session_start_ts = datetime.utcnow().isoformat() + 'Z'
    last_output = None
    last_data_refresh = 0.0
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            try:
                input_changed = _poll_proxy_input()

                now = time.time()
                input_changed, last_data_refresh = _refresh_proxy_data(
                    now, input_changed, last_data_refresh, _monitor
                )

                _copy_feedback_until = {k: v for k, v in _copy_feedback_until.items() if v > now}
                if _copy_feedback_until:
                    input_changed = True

                if input_changed:
                    output = _build_proxy_output()
                    if output != last_output:
                        print("\033[2J\033[3J\033[H", end='', flush=True)
                        if output:
                            print(output)
                        last_output = output

                wait_for_input(INPUT_POLL_INTERVAL)
            except Exception:
                log_pane_error('proxy')
                wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

def _poll_proxy_input() -> bool:
    input_changed = False
    while True:
        char = read_keypress()
        if char is None:
            break
        if char == '\033':
            event = read_mouse_event(char)
            if event is not None and event[0] != -1:
                if _handle_proxy_mouse(*event):
                    input_changed = True
            elif event is not None:
                if _handle_proxy_search_release():
                    input_changed = True
            elif _proxy_search.focused:
                if _handle_proxy_search_cancel():
                    input_changed = True
        elif _proxy_search.focused:
            if _handle_proxy_search_input(char):
                input_changed = True
        elif char == 'u':
            if _undo_proxy_expand():
                input_changed = True
        elif char == '/':
            _proxy_search.focused = True
            input_changed = True
        elif char in ('n', 'N'):
            if _jump_search_match(forward=(char == 'n')):
                input_changed = True
    return input_changed

def _proxy_ram_state() -> list:
    return [
        ('proxy_entries',         proxy_entries),
        ('proxy_expand_states',   proxy_expand_states),
        ('proxy_line_map',        proxy_line_map),
        ('_proxy_cache_turns',    _proxy_cache_turns),
        ('_proxy_fwd_pos',        _proxy_fwd_pos),
        ('_proxy_acc_fwd',        _proxy_acc_fwd),
        ('proxy_hover_row',       str(proxy_hover_row)),
        ('proxy_scroll_offset',   proxy_scroll_offset),
        ('proxy_log_position',    proxy_log_position),
        ('_proxy_jsonl_position', _proxy_jsonl_position),
        ('_proxy_search_query',   _proxy_search.query),
        ('_proxy_search_matches', _proxy_search.matches),
    ]

def _handle_proxy_search_cancel() -> bool:
    return search_bar.handle_search_cancel(_proxy_search)

def _handle_proxy_search_input(char: str) -> bool:
    return search_bar.handle_search_input(_proxy_search, char, on_commit=_proxy_search_on_commit)

def _proxy_search_on_commit(state: search_bar.SearchState) -> None:
    _run_pane_search(state, proxy_entries, proxy_expand_states, _proxy_pane_width, _proxy_log_path, _jump_to_search_match)

def _jump_search_match(forward: bool) -> bool:
    if not _proxy_search.matches:
        return False
    _proxy_search.current_idx = (_proxy_search.current_idx + (1 if forward else -1)) % len(_proxy_search.matches)
    _jump_to_search_match()
    return True

def _jump_to_search_match() -> None:
    global _proxy_just_expanded
    target_entry_idx = _proxy_search.matches[_proxy_search.current_idx]
    _proxy_just_expanded = ('req', target_entry_idx)

def _search_col_to_query_index(col: int, query: str) -> int:
    return search_bar.col_to_query_index(col, query, _SEARCH_BAR_LABEL)

def _handle_proxy_search_release() -> bool:
    return search_bar.handle_search_mouse_release(_proxy_search, copy_to_clipboard)

def _render_proxy_search_bar(pane_width: int) -> str:
    return search_bar.render_search_bar(_proxy_search, pane_width, label=_SEARCH_BAR_LABEL)

def _handle_proxy_copy_click(key, entry_idx: Optional[int]) -> None:
    global _copy_feedback_until
    copy_to_clipboard(_prepare_copy_text(key, entry_idx, proxy_entries, _proxy_log_path))
    if entry_idx is not None:
        _copy_feedback_until[entry_idx] = time.time() + 1.5

def _handle_proxy_expand_click(key, entry_idx: Optional[int]) -> None:
    global _proxy_just_expanded, _proxy_undo_stack
    _proxy_undo_stack.append((key, proxy_expand_states.get(key, False)))
    if len(_proxy_undo_stack) > 200:
        _proxy_undo_stack.pop(0)
    if _toggle_expand_and_lazy_load(key, entry_idx, proxy_entries, _proxy_log_path, proxy_expand_states):
        _proxy_just_expanded = key

def _handle_proxy_mouse(button: int, col: int, row: int) -> bool:
    global proxy_scroll_offset, proxy_hover_row
    if button == 0:
        if row == 1:
            return search_bar.handle_search_mouse_press(_proxy_search, col, _SEARCH_BAR_LABEL)
        had_selection = _proxy_search.sel_anchor is not None
        search_bar.clear_selection(_proxy_search)
        key = proxy_line_map.get(row)
        if key is None:
            return had_selection
        is_req = (isinstance(key, tuple) and key[0] == 'req') or isinstance(key, int)
        entry_idx = _entry_idx_from_key(key)
        if is_req and col >= _proxy_pane_width - 2 and row in _proxy_copy_rows:
            _handle_proxy_copy_click(key, entry_idx)
        else:
            _handle_proxy_expand_click(key, entry_idx)
        return True
    handled, proxy_scroll_offset, proxy_hover_row = _handle_scroll_or_hover(
        button, col, row, _proxy_search, _SEARCH_BAR_LABEL, proxy_scroll_offset, proxy_hover_row)
    return handled

def _undo_proxy_expand() -> bool:
    global proxy_expand_states, _proxy_undo_stack
    if not _proxy_undo_stack:
        return False
    key, prev_state = _proxy_undo_stack.pop()
    proxy_expand_states[key] = prev_state
    return True

def _reset_proxy_positions(now: float) -> None:
    global proxy_log_position, _proxy_jsonl_position, _proxy_cache_turns, _proxy_fwd_pos
    global _proxy_stripped_pos, _proxy_injected_pos, _proxy_original_pos, _last_full_parse_ts
    proxy_entries.clear()
    proxy_line_map.clear()
    proxy_log_position = _proxy_jsonl_position = _proxy_fwd_pos = 0
    _proxy_cache_turns = []
    _proxy_acc_fwd.clear()
    _last_full_parse_ts = now
    _proxy_stripped_pos = _proxy_injected_pos = _proxy_original_pos = 0
    _proxy_acc_stripped.clear()
    _proxy_acc_injected.clear()
    _proxy_acc_original.clear()

def _reset_proxy_session_state(monitor, now: float) -> None:
    global _proxy_session_start_ts, proxy_scroll_offset, proxy_hover_row, _proxy_log_path
    _proxy_session_start_ts = monitor._get_session_start_ts()
    if _proxy_session_start_ts is None:
        _proxy_session_start_ts = datetime.utcnow().isoformat() + 'Z'
    _reset_proxy_positions(now)
    proxy_expand_states.clear()
    _proxy_undo_stack.clear()
    proxy_scroll_offset, proxy_hover_row, _proxy_log_path = 0, None, None
    search_bar.handle_search_cancel(_proxy_search)

def _reset_proxy_reparse_state(now: float) -> None:
    _reset_proxy_positions(now)

def _refresh_proxy_data(now: float, input_changed: bool, last_data_refresh: float, monitor) -> tuple:
    global _proxy_fwd_pos, _proxy_acc_fwd, _proxy_log_path, _last_full_parse_ts, _proxy_current_main_session
    global _proxy_stripped_pos, _proxy_injected_pos, _proxy_original_pos, _proxy_jsonl_position, _proxy_cache_turns
    if now - last_data_refresh < POLL_INTERVAL:
        return input_changed, last_data_refresh
    newest = monitor._get_newest_main_session()
    if newest != _proxy_current_main_session and newest is not None:
        _proxy_current_main_session = newest
        _reset_proxy_session_state(monitor, now)
        input_changed = True
    if _last_full_parse_ts == 0.0:
        _last_full_parse_ts = now
    elif now - _last_full_parse_ts >= PROXY_REPARSE_INTERVAL_SECONDS:
        _reset_proxy_reparse_state(now)
        input_changed = True
    new_entries, _proxy_fwd_pos = parse_proxy_log_forwarded(
        monitor.active_project_filter, _proxy_fwd_pos, _proxy_acc_fwd
    )
    filtered = [e for e in new_entries if e.get('timestamp', '') >= _proxy_session_start_ts]
    proxy_entries.extend(filtered)
    _proxy_log_path = find_proxy_log_path(monitor.active_project_filter)
    original_path = _find_original_log_path(_proxy_log_path)
    _proxy_original_pos = accumulate_original_tools(original_path, _proxy_original_pos, _proxy_acc_original)
    _proxy_stripped_pos, _proxy_injected_pos = _accumulate_dual_logs_and_attach(
        filtered, proxy_entries, proxy_expand_states, _proxy_log_path, _proxy_acc_stripped,
        _proxy_acc_injected, _proxy_stripped_pos, _proxy_injected_pos, _infer_model_family, _proxy_acc_original)
    main_sessions = monitor.get_main_session_files()
    if main_sessions:
        filepath = main_sessions[0]
        _proxy_cache_turns, _proxy_jsonl_position = build_cache_turns(
            filepath, _proxy_jsonl_position, _proxy_cache_turns
        )
    return True, now

def _build_proxy_output() -> str:
    global proxy_scroll_offset, _proxy_pane_width, _proxy_copy_rows, _proxy_just_expanded
    pane_height, pane_width = _terminal_size()
    _proxy_pane_width = pane_width
    header = _render_proxy_search_bar(pane_width)
    content_height = max(1, pane_height - _PROXY_HEADER_LINES)
    body_hover = (
        (proxy_hover_row - _PROXY_HEADER_LINES)
        if proxy_hover_row and proxy_hover_row > _PROXY_HEADER_LINES
        else None
    )
    _proxy_copy_rows.clear()
    if not proxy_entries:
        proxy_line_map.clear()
        _proxy_just_expanded = None
        body, _total_lines = format_proxy_block(proxy_entries, proxy_expand_states, proxy_line_map, body_hover, content_height, pane_width, proxy_scroll_offset)
        return header + '\n' + body
    current_match_entry_idx = (
        _proxy_search.matches[_proxy_search.current_idx]
        if _proxy_search.matches and _proxy_search.current_idx < len(_proxy_search.matches)
        else None
    )
    viewport_lines_n = max(1, content_height - 1)
    def _render(scroll_offset, want_item_positions):
        item_positions = {} if want_item_positions else None
        body, total_lines = format_proxy_block(
            proxy_entries, proxy_expand_states, proxy_line_map, body_hover, content_height, pane_width,
            scroll_offset, turns=_proxy_cache_turns, item_positions_out=item_positions,
            copy_feedback=_copy_feedback_until, copy_rows_out=_proxy_copy_rows,
            search_match_set=_proxy_search.match_set, search_current_entry_idx=current_match_entry_idx,
            search_query=_proxy_search.query,
        )
        return body, total_lines, item_positions
    body, proxy_scroll_offset = _render_and_scroll_body(
        _render, proxy_line_map, _proxy_copy_rows, _PROXY_HEADER_LINES, _proxy_just_expanded, proxy_scroll_offset, viewport_lines_n)
    _proxy_just_expanded = None
    return header + '\n' + body
