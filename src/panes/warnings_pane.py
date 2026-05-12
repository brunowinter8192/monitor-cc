# INFRASTRUCTURE
from pathlib import Path
from typing import Dict, Optional, Set
import os
import time

from ..constants import INPUT_POLL_INTERVAL, WARNINGS_POLL_INTERVAL, WARNINGS_INITIAL_TAIL_BYTES
from ..utils import format_timestamp
from ..ram_audit import register_ram_dump
from ..input.click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
    resolve_parent_key, copy_to_clipboard, wait_for_input,
)
from .warnings_parse import _iso_to_float
from .warnings_scan import _scan_proxy_entries_for_errors, _scan_proxy_entries_for_zero_results
from .warnings_render import _format_warnings_pane, _format_warnings_header, _serialize_warnings

tool_errors: list = []
error_expand_states: Dict[int, bool] = {}
error_line_map: Dict[int, int] = {}
error_hover_row: Optional[int] = None
error_scroll_offset: int = 0
_proxy_log_position: int = 0
_last_project_filter: Optional[str] = None
_last_log_path: Optional[Path] = None
_last_refresh_ts: float = 0.0
_force_refresh: bool = False
_monitor_start_ts: float = 0.0
_worker_log_positions: Dict[str, int] = {}

schema_warnings: list = []  # list of {timestamp, model, warnings: list[str]}
zero_results: list = []  # list of {timestamp, tool_name, reason, tool_call_input}
zero_result_expand_states: Dict[int, bool] = {}
zero_result_line_map: Dict[int, int] = {}

# Dedup sets: proxy entries carry cumulative message history, so the same tool_result
# block reappears in every subsequent entry. Keys prevent re-counting historic results.
# Key format: (msg_idx, blk_idx, text_key) for zero-results; (msg_idx, text_key) for errors.
# Note: msg_idx is stable as long as messages are only appended. Context-trimming (rare)
# may cause a deduped item to appear at a shifted index — acceptable edge-case for v1.
_seen_zero_keys: Set = set()
_seen_error_keys: Set = set()
_proxy_pending_by_rid: dict = {}  # persisted across polling cycles for latency_update merge

# ORCHESTRATOR

# Runs warnings-only display loop (for dedicated warnings tmux pane)
def run_warnings_loop() -> None:
    global tool_errors, error_expand_states, error_line_map, error_hover_row
    global error_scroll_offset, _proxy_log_position, _last_project_filter
    global _last_refresh_ts, _force_refresh
    global schema_warnings, zero_results, zero_result_expand_states, zero_result_line_map
    global _monitor_start_ts, _worker_log_positions, _last_log_path, _proxy_pending_by_rid

    register_ram_dump('warnings', _warnings_ram_state)
    _monitor_start_ts = time.time()
    load_historical_warnings()
    last_output = None
    last_data_refresh = 0.0
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            input_changed = False
            while True:
                char = read_keypress()
                if char is None:
                    break
                if char == '\033':
                    event = read_mouse_event(char)
                    if event is not None:
                        if _handle_warnings_mouse(*event):
                            input_changed = True
                else:
                    if _handle_warnings_key(char):
                        input_changed = True

            now = time.time()
            input_changed, last_data_refresh = _refresh_warnings_data(
                now, input_changed, last_data_refresh
            )

            if input_changed:
                output = _build_warnings_output()
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output, end='', flush=True)
                        print(f"\033[H{_format_warnings_header(_last_refresh_ts)}\033[K", end='', flush=True)
                    last_output = output

            wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

# Load historical warnings from newest main session
def load_historical_warnings() -> None:
    from ..core import monitor as _monitor
    main_sessions = _monitor.get_main_session_files()
    if main_sessions:
        filepath = main_sessions[0]
        _monitor.file_positions[filepath] = 0
        _monitor.tool_use_caches[filepath] = {}

# Return module-level state snapshot for RAM audit
def _warnings_ram_state() -> list:
    return [
        ('tool_errors',                  tool_errors),
        ('error_expand_states',          error_expand_states),
        ('error_line_map',               error_line_map),
        ('schema_warnings',              schema_warnings),
        ('zero_results',                 zero_results),
        ('zero_result_expand_states',    zero_result_expand_states),
        ('zero_result_line_map',         zero_result_line_map),
        ('_worker_log_positions',        _worker_log_positions),
        ('_seen_zero_keys',              _seen_zero_keys),
        ('_seen_error_keys',             _seen_error_keys),
        ('_proxy_pending_by_rid',        _proxy_pending_by_rid),
        ('error_hover_row',              str(error_hover_row)),
        ('error_scroll_offset',          error_scroll_offset),
        ('_proxy_log_position',          _proxy_log_position),
        ('_last_project_filter',         str(_last_project_filter)),
        ('_last_log_path',               str(_last_log_path)),
        ('_last_refresh_ts',             _last_refresh_ts),
        ('_force_refresh',               _force_refresh),
        ('_monitor_start_ts',            _monitor_start_ts),
    ]

# Process one mouse event; returns True if display should refresh
def _handle_warnings_mouse(button: int, col: int, row: int) -> bool:
    global error_hover_row, error_scroll_offset, error_expand_states, zero_result_expand_states
    if button == 0:
        ekey = error_line_map.get(row)
        if ekey is not None:
            error_expand_states[ekey] = not error_expand_states.get(ekey, False)
            return True
        zkey = zero_result_line_map.get(row)
        if zkey is not None:
            zero_result_expand_states[zkey] = not zero_result_expand_states.get(zkey, False)
            return True
        return False
    if button == 64:
        # tmux.h: MOUSE_WHEEL_UP=64 → scroll viewport up → offset decreases.
        # NOTE: token_pane uses offset+3 for button 64 because it renders
        # bottom-to-top (start = len-height-offset). warnings_pane renders
        # top-to-bottom (visible = lines[offset:offset+height]), so directions
        # are opposite: wheel-up must decrease offset here.
        error_scroll_offset = max(0, error_scroll_offset - 3)
        return True
    if button == 65:
        # tmux.h: MOUSE_WHEEL_DOWN=65 → scroll viewport down → offset increases
        error_scroll_offset = error_scroll_offset + 3
        return True
    if button >= 32:
        error_hover_row = row
        return True
    return False

# Process one non-escape key event; returns True if display should refresh
def _handle_warnings_key(char: str) -> bool:
    global _force_refresh
    if char == 'y':
        key = resolve_parent_key(error_line_map, error_hover_row)
        if key is None:
            key = resolve_parent_key(zero_result_line_map, error_hover_row)
        if key is not None:
            copy_to_clipboard(_serialize_warnings(key, tool_errors, zero_results))
        return False
    if char in ('r', 'R'):
        _force_refresh = True
        return True
    return False

# Tick-boundary warnings data refresh; returns (input_changed, new_last_data_refresh)
def _refresh_warnings_data(now: float, input_changed: bool, last_data_refresh: float) -> tuple:
    from ..core import monitor as _monitor
    from ..proxy_display.parser import (
        parse_proxy_log, scan_worker_logs, get_proxy_session_start_ts,
        find_proxy_log_path, proxy_session_id_for_project,
    )
    global tool_errors, error_expand_states, error_line_map, error_scroll_offset, error_hover_row
    global _proxy_log_position, _last_project_filter, _last_log_path
    global schema_warnings, zero_results, zero_result_expand_states, zero_result_line_map
    global _monitor_start_ts, _worker_log_positions, _last_refresh_ts, _force_refresh
    global _seen_zero_keys, _seen_error_keys, _proxy_pending_by_rid

    if not (_force_refresh or now - last_data_refresh >= WARNINGS_POLL_INTERVAL):
        return input_changed, last_data_refresh
    _force_refresh = False
    _monitor.monitor_sessions()

    project_filter = _monitor.active_project_filter
    log_path = find_proxy_log_path(project_filter)

    if project_filter != _last_project_filter or log_path != _last_log_path:
        # Seek to last WARNINGS_INITIAL_TAIL_BYTES instead of position 0 to bound
        # peak pymalloc allocation. Partial first line at seek point is silently
        # skipped by _parse_log_file's JSONDecodeError handler.
        _proxy_log_position = 0
        if log_path and log_path.exists():
            try:
                fsize = log_path.stat().st_size
                if fsize > WARNINGS_INITIAL_TAIL_BYTES:
                    _proxy_log_position = fsize - WARNINGS_INITIAL_TAIL_BYTES
            except OSError:
                pass
        _monitor_start_ts = get_proxy_session_start_ts(project_filter) if project_filter else time.time()
        _worker_log_positions.clear()
        tool_errors = []
        zero_results = []
        schema_warnings = []
        error_expand_states.clear()
        zero_result_expand_states.clear()
        _seen_zero_keys.clear()
        _seen_error_keys.clear()
        _proxy_pending_by_rid.clear()
        error_scroll_offset = 0
        error_hover_row = None
        _last_project_filter = project_filter
        _last_log_path = log_path

    # Detect file truncation (proxy restarted with same path)
    if log_path and log_path.exists():
        try:
            file_size = log_path.stat().st_size
        except OSError:
            file_size = None
        if file_size is not None and file_size < _proxy_log_position:
            _proxy_log_position = 0
            tool_errors = []
            zero_results = []
            schema_warnings = []
            error_expand_states.clear()
            zero_result_expand_states.clear()
            _seen_zero_keys.clear()
            _seen_error_keys.clear()
            _proxy_pending_by_rid.clear()
            error_scroll_offset = 0

    new_entries, _proxy_log_position = parse_proxy_log(project_filter, _proxy_log_position, _proxy_pending_by_rid)
    _worker_sid = proxy_session_id_for_project(project_filter) if project_filter else ''
    worker_entries, _worker_log_positions = scan_worker_logs(
        _worker_log_positions, _worker_sid,
        tail_bytes=WARNINGS_INITIAL_TAIL_BYTES,
        # Strict current-session only: worker logs are always written AFTER the proxy
        # session starts, so their mtime is always >> _monitor_start_ts. No clock-skew
        # buffer needed.
        min_mtime=_monitor_start_ts,
    )
    all_new_entries = new_entries + worker_entries

    new_errors, new_error_keys = _scan_proxy_entries_for_errors(
        all_new_entries, _monitor_start_ts, _seen_error_keys)
    _seen_error_keys.update(new_error_keys)
    tool_errors.extend(new_errors)

    new_zero, new_zero_keys = _scan_proxy_entries_for_zero_results(
        all_new_entries, _monitor_start_ts, _seen_zero_keys)
    _seen_zero_keys.update(new_zero_keys)
    zero_results.extend(new_zero)

    for entry in new_entries:
        if entry.get('type') == 'schema_warning':
            ts_raw = entry.get('timestamp', '')
            if ts_raw and _iso_to_float(ts_raw) < _monitor_start_ts:
                continue
            ts = format_timestamp(ts_raw) if ts_raw else '??:??:??'
            schema_warnings.append({
                'timestamp': ts,
                'model': entry.get('model', ''),
                'warnings': entry.get('warnings', []),
            })

    _last_refresh_ts = now
    return True, now

# Render warnings pane to ANSI string; updates error_line_map and zero_result_line_map
def _build_warnings_output() -> str:
    global error_line_map, zero_result_line_map
    try:
        term = os.get_terminal_size()
        pane_height = term.lines - 1
        pane_width = term.columns
    except OSError:
        pane_height = 50
        pane_width = 80
    output, error_line_map, zero_result_line_map = _format_warnings_pane(
        tool_errors, error_expand_states, error_hover_row, error_scroll_offset,
        schema_warnings, zero_results, zero_result_expand_states,
        pane_height, pane_width, _last_refresh_ts,
    )
    return output
