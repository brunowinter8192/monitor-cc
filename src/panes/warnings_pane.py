# INFRASTRUCTURE
from pathlib import Path
from typing import Dict, Optional, Set, Tuple
import json
import os
import time

from ..constants import INPUT_POLL_INTERVAL, WARNINGS_POLL_INTERVAL
from ..utils import format_timestamp
from ..ram_audit import register_ram_dump
from ..pane_error_log import log_pane_error
from ..input.click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
    resolve_parent_key, copy_to_clipboard, wait_for_input,
)
from .warnings_render import (
    _format_warnings_pane, _format_warnings_header, _serialize_warnings,
    build_warnings_search_matches,
)
from .. import search_bar

tool_errors: list = []
error_expand_states: Dict[int, bool] = {}
error_line_map: Dict[int, int] = {}
error_hover_row: Optional[int] = None
error_scroll_offset: int = 0
error_copy_rows: Set[int] = set()
_error_copy_feedback_until: Dict[int, float] = {}
_error_pane_width: int = 80
_warnings_header_regions: Dict[Tuple[int, int, int], str] = {}
_last_project_filter: Optional[str] = None
_last_refresh_ts: float = 0.0
_force_refresh: bool = False
_monitor_start_ts: float = 0.0
_errors_log_pos: int = 0
_errors_log_path: Optional[Path] = None
_worker_errors_positions: Dict[str, int] = {}

_WARNINGS_SEARCH_BAR_LINES = 1
_WARNINGS_SEARCH_BAR_LABEL = 'search: '

_warnings_search: search_bar.SearchState = search_bar.SearchState()

# ORCHESTRATOR

def run_warnings_loop() -> None:
    global tool_errors, error_expand_states, error_line_map, error_hover_row
    global error_scroll_offset, _last_project_filter, _error_copy_feedback_until
    global _last_refresh_ts, _force_refresh
    global _monitor_start_ts, _errors_log_pos, _errors_log_path, _worker_errors_positions

    register_ram_dump('warnings', _warnings_ram_state)
    _monitor_start_ts = time.time()
    load_historical_warnings()
    last_output = None
    last_data_refresh = 0.0
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            try:
                input_changed = _poll_warnings_input()

                now = time.time()
                input_changed, last_data_refresh = _refresh_warnings_data(
                    now, input_changed, last_data_refresh
                )

                _error_copy_feedback_until = {k: v for k, v in _error_copy_feedback_until.items() if v > now}
                if _error_copy_feedback_until:
                    input_changed = True

                if input_changed:
                    output, header = _build_warnings_output()
                    if output != last_output:
                        print("\033[2J\033[3J\033[H", end='', flush=True)
                        if output:
                            print(output, end='', flush=True)
                            print(f"\033[H{header}\033[K", end='', flush=True)
                        last_output = output

                wait_for_input(INPUT_POLL_INTERVAL)
            except Exception:
                log_pane_error('warnings')
                wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

def _poll_warnings_input() -> bool:
    input_changed = False
    while True:
        char = read_keypress()
        if char is None:
            break
        if char == '\033':
            event = read_mouse_event(char)
            if event is not None and event[0] != -1:
                if _handle_warnings_mouse(*event):
                    input_changed = True
            elif event is not None:
                if _handle_warnings_search_release():
                    input_changed = True
            elif _warnings_search.focused:
                if _handle_warnings_search_cancel():
                    input_changed = True
        elif _warnings_search.focused:
            if _handle_warnings_search_input(char):
                input_changed = True
        elif char == '/':
            _warnings_search.focused = True
            input_changed = True
        elif char in ('n', 'N'):
            if _jump_warnings_search_match(forward=(char == 'n')):
                input_changed = True
        else:
            if _handle_warnings_key(char):
                input_changed = True
    return input_changed

def load_historical_warnings() -> None:
    from ..core import monitor as _monitor
    _monitor.monitor_sessions()

def _warnings_ram_state() -> list:
    return [
        ('tool_errors',                  tool_errors),
        ('error_expand_states',          error_expand_states),
        ('error_line_map',               error_line_map),
        ('_worker_errors_positions',     _worker_errors_positions),
        ('error_hover_row',              str(error_hover_row)),
        ('error_scroll_offset',          error_scroll_offset),
        ('_errors_log_pos',              _errors_log_pos),
        ('_errors_log_path',             str(_errors_log_path)),
        ('_last_project_filter',         str(_last_project_filter)),
        ('_last_refresh_ts',             _last_refresh_ts),
        ('_force_refresh',               _force_refresh),
        ('_monitor_start_ts',            _monitor_start_ts),
        ('_warnings_search_query',       _warnings_search.query),
        ('_warnings_search_matches',     _warnings_search.matches),
    ]

def _handle_warnings_mouse(button: int, col: int, row: int) -> bool:
    global error_hover_row, error_scroll_offset, error_expand_states, _error_copy_feedback_until, _force_refresh
    if button == 0:
        if row == 1:
            return search_bar.handle_search_mouse_press(_warnings_search, col, _WARNINGS_SEARCH_BAR_LABEL)
        had_selection = _warnings_search.sel_anchor is not None
        search_bar.clear_selection(_warnings_search)
        for (sc, ec, er), action in _warnings_header_regions.items():
            if row == er and sc <= col <= ec:
                if action == 'refresh':
                    _force_refresh = True
                    return True
                return had_selection
        ekey = error_line_map.get(row)
        if ekey is None:
            return had_selection
        if col >= _error_pane_width - 2 and row in error_copy_rows:
            copy_to_clipboard(_serialize_warnings(ekey, tool_errors))
            _error_copy_feedback_until[ekey] = time.time() + 1.5
            return True
        error_expand_states[ekey] = not error_expand_states.get(ekey, False)
        return True
    if button == 64:
        error_scroll_offset = max(0, error_scroll_offset - 3)
        return True
    if button == 65:
        error_scroll_offset = error_scroll_offset + 3
        return True
    if button == 32 and _warnings_search.dragging:
        return search_bar.handle_search_mouse_motion(_warnings_search, col, _WARNINGS_SEARCH_BAR_LABEL)
    if button >= 32:
        error_hover_row = row
        return True
    return False

def _handle_warnings_key(char: str) -> bool:
    global _force_refresh
    if char == 'y':
        key = resolve_parent_key(error_line_map, error_hover_row)
        if key is not None:
            copy_to_clipboard(_serialize_warnings(key, tool_errors))
        return False
    if char in ('r', 'R'):
        _force_refresh = True
        return True
    return False

def _handle_warnings_search_cancel() -> bool:
    return search_bar.handle_search_cancel(_warnings_search)

def _handle_warnings_search_input(char: str) -> bool:
    return search_bar.handle_search_input(_warnings_search, char, on_commit=_warnings_search_on_commit)

def _warnings_search_on_commit(state: search_bar.SearchState) -> None:
    state.matches = build_warnings_search_matches(state.query, tool_errors)
    state.match_set = set(state.matches)
    state.current_idx = 0

def _jump_warnings_search_match(forward: bool) -> bool:
    if not _warnings_search.matches:
        return False
    _warnings_search.current_idx = (_warnings_search.current_idx + (1 if forward else -1)) % len(_warnings_search.matches)
    return True

def _handle_warnings_search_release() -> bool:
    return search_bar.handle_search_mouse_release(_warnings_search, copy_to_clipboard)

def _render_warnings_search_bar(pane_width: int) -> str:
    return search_bar.render_search_bar(_warnings_search, pane_width, label=_WARNINGS_SEARCH_BAR_LABEL)

def _errors_record_to_display(rec: dict) -> dict:
    worker_field = rec.get('worker', '')
    worker_name = worker_field[len('worker:'):] if worker_field.startswith('worker:') else \
                  rec.get('_worker_name_from_file', '')
    ts_raw = rec.get('ts', '')
    error_full = rec.get('error_full', '') or ''
    return {
        'timestamp': format_timestamp(ts_raw) if ts_raw else '??:??:??',
        'tool_name': rec.get('tool_name', ''),
        'summary': error_full[:80],
        'full_text': error_full,
        'tool_call_input': {},
        'worker_name': worker_name,
        '_tool_use_id': rec.get('tool_use_id', ''),
        '_ts_raw': ts_raw,
        '_proxy_file': rec.get('proxy_file', ''),
        '_request_id': rec.get('request_id', ''),
    }

def _read_errors_log(path: Path, last_pos: int) -> tuple:
    records: list = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            f.seek(last_pos)
            while True:
                raw_line = f.readline()
                if not raw_line:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return records, f.tell()
    except OSError:
        return records, last_pos

def _refresh_warnings_data(now: float, input_changed: bool, last_data_refresh: float) -> tuple:
    from ..core import monitor as _monitor
    from ..proxy_display.parser import (
        find_errors_log_path,
        proxy_session_id_for_project, get_proxy_session_start_ts,
    )
    from ..proxy_display.side_logs import scan_worker_errors_logs
    global tool_errors, error_expand_states, error_line_map, error_scroll_offset, error_hover_row
    global _last_project_filter, _last_refresh_ts, _force_refresh, _monitor_start_ts
    global _errors_log_pos, _errors_log_path, _worker_errors_positions

    if not (_force_refresh or now - last_data_refresh >= WARNINGS_POLL_INTERVAL):
        return input_changed, last_data_refresh
    _force_refresh = False
    _monitor.monitor_sessions()

    project_filter = _monitor.active_project_filter
    errors_path = find_errors_log_path(project_filter)

    if project_filter != _last_project_filter or errors_path != _errors_log_path:
        _errors_log_pos = 0
        _errors_log_path = errors_path
        _worker_errors_positions.clear()
        _monitor_start_ts = get_proxy_session_start_ts(project_filter) if project_filter else time.time()
        tool_errors = []
        error_expand_states.clear()
        error_scroll_offset = 0
        error_hover_row = None
        _last_project_filter = project_filter

    new_errors: list = []
    if errors_path and errors_path.exists():
        raw_recs, _errors_log_pos = _read_errors_log(errors_path, _errors_log_pos)
        new_errors.extend(_errors_record_to_display(r) for r in raw_recs)

    _worker_sid = proxy_session_id_for_project(project_filter) if project_filter else ''
    worker_recs, _worker_errors_positions = scan_worker_errors_logs(
        _worker_errors_positions, _worker_sid, min_mtime=_monitor_start_ts,
    )
    new_errors.extend(_errors_record_to_display(r) for r in worker_recs)

    tool_errors.extend(new_errors)
    _last_refresh_ts = now
    return True, now

def _build_warnings_output() -> tuple:
    global error_line_map, error_copy_rows, _error_pane_width, _warnings_header_regions
    try:
        term = os.get_terminal_size()
        pane_height = term.lines - 1
        pane_width = term.columns
    except OSError:
        pane_height = 50
        pane_width = 80
    _error_pane_width = pane_width
    refresh_header = _format_warnings_header(_last_refresh_ts, pane_width, _warnings_header_regions)
    if _warnings_header_regions:
        shifted = {
            (sc, ec, er + _WARNINGS_SEARCH_BAR_LINES): action
            for (sc, ec, er), action in _warnings_header_regions.items()
        }
        _warnings_header_regions.clear()
        _warnings_header_regions.update(shifted)
    header = _render_warnings_search_bar(pane_width) + '\n' + refresh_header
    current_match_key = (
        _warnings_search.matches[_warnings_search.current_idx]
        if _warnings_search.matches and _warnings_search.current_idx < len(_warnings_search.matches)
        else None
    )
    output, error_line_map = _format_warnings_pane(
        tool_errors, error_expand_states, error_hover_row, error_scroll_offset,
        pane_height, pane_width, header,
        copy_feedback=_error_copy_feedback_until, copy_rows_out=error_copy_rows,
        header_lines=1 + _WARNINGS_SEARCH_BAR_LINES,
        search_match_set=_warnings_search.match_set, search_current_key=current_match_key,
        search_query=_warnings_search.query,
    )
    return output, header
