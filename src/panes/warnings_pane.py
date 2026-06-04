# INFRASTRUCTURE
from pathlib import Path
from typing import Dict, Optional
import json
import os
import time

from ..constants import INPUT_POLL_INTERVAL, WARNINGS_POLL_INTERVAL
from ..utils import format_timestamp
from ..ram_audit import register_ram_dump
from ..input.click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
    resolve_parent_key, copy_to_clipboard, wait_for_input,
)
from .warnings_render import _format_warnings_pane, _format_warnings_header, _serialize_warnings

tool_errors: list = []
error_expand_states: Dict[int, bool] = {}
error_line_map: Dict[int, int] = {}
error_hover_row: Optional[int] = None
error_scroll_offset: int = 0
_last_project_filter: Optional[str] = None
_last_refresh_ts: float = 0.0
_force_refresh: bool = False
_monitor_start_ts: float = 0.0
_errors_log_pos: int = 0               # byte position in current session _errors log
_errors_log_path: Optional[Path] = None  # resolved path for change-detection
_worker_errors_positions: Dict[str, int] = {}  # per-file byte positions for worker _errors logs

# ORCHESTRATOR

# Runs warnings-only display loop (for dedicated warnings tmux pane)
def run_warnings_loop() -> None:
    global tool_errors, error_expand_states, error_line_map, error_hover_row
    global error_scroll_offset, _last_project_filter
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

# Prime monitor_sessions so the pane has fresh session state on startup
def load_historical_warnings() -> None:
    from ..core import monitor as _monitor
    _monitor.monitor_sessions()

# Return module-level state snapshot for RAM audit
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
    ]

# Process one mouse event; returns True if display should refresh
def _handle_warnings_mouse(button: int, col: int, row: int) -> bool:
    global error_hover_row, error_scroll_offset, error_expand_states
    if button == 0:
        ekey = error_line_map.get(row)
        if ekey is not None:
            error_expand_states[ekey] = not error_expand_states.get(ekey, False)
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
        if key is not None:
            copy_to_clipboard(_serialize_warnings(key, tool_errors))
        return False
    if char in ('r', 'R'):
        _force_refresh = True
        return True
    return False

# Convert one _errors-log record to a tool_errors display dict.
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

# Read new records from an _errors log file starting at last_pos. Returns (records, new_pos).
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

# Tick-boundary warnings data refresh; returns (input_changed, new_last_data_refresh)
def _refresh_warnings_data(now: float, input_changed: bool, last_data_refresh: float) -> tuple:
    from ..core import monitor as _monitor
    from ..proxy_display.parser import (
        find_errors_log_path, scan_worker_errors_logs,
        proxy_session_id_for_project, get_proxy_session_start_ts,
    )
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

    # Read main session _errors log (current-session-only by design; starts at pos 0 per session)
    new_errors: list = []
    if errors_path and errors_path.exists():
        raw_recs, _errors_log_pos = _read_errors_log(errors_path, _errors_log_pos)
        new_errors.extend(_errors_record_to_display(r) for r in raw_recs)

    # Read worker _errors dual-logs
    _worker_sid = proxy_session_id_for_project(project_filter) if project_filter else ''
    worker_recs, _worker_errors_positions = scan_worker_errors_logs(
        _worker_errors_positions, _worker_sid, min_mtime=_monitor_start_ts,
    )
    new_errors.extend(_errors_record_to_display(r) for r in worker_recs)

    tool_errors.extend(new_errors)
    _last_refresh_ts = now
    return True, now

# Render warnings pane to ANSI string; updates error_line_map
def _build_warnings_output() -> str:
    global error_line_map
    try:
        term = os.get_terminal_size()
        pane_height = term.lines - 1
        pane_width = term.columns
    except OSError:
        pane_height = 50
        pane_width = 80
    output, error_line_map = _format_warnings_pane(
        tool_errors, error_expand_states, error_hover_row, error_scroll_offset,
        pane_height, pane_width, _last_refresh_ts,
    )
    return output
