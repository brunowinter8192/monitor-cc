# INFRASTRUCTURE
from datetime import datetime, timedelta
import os
import time
from pathlib import Path
from typing import Dict, Set, List, Optional

# From constants.py: Colors, config, shared constants
from ..constants import RESET, CYAN, POLL_INTERVAL, INPUT_POLL_INTERVAL, MODE_ALL, MODE_MAIN, MODE_WARNINGS, MODE_TOKENS, MODE_WORKERS, MODE_PROXY, MODE_WORKER_PROXY

# From session_finder.py: Discover active Claude Code sessions
from ..session_finder import find_active_sessions
# From jsonl/: Parse JSONL lines for session start timestamp
from ..jsonl import parse_jsonl_lines, read_new_lines
# From monitor_display.py: Session status output + main-loop rendering
from .monitor_display import print_session_status, render_main_buffer
from . import monitor_display as _md
# From monitor_session.py: Session file processing, task handling, historical load
from .monitor_session import get_file_end_position, get_initial_position, process_session_file, load_historical_main
# From ram_audit: register tracemalloc + SIGUSR1 dump handler for this pane
from ..ram_audit import register_ram_dump
# From click_handler: keyboard/mouse I/O for main loop
from ..input.click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
    resolve_parent_key, copy_to_clipboard,
)

file_positions: Dict[Path, int] = {}
tool_use_caches: Dict[Path, dict] = {}
call_counter = 0
agent_to_task: Dict[str, str] = {}
agent_to_type: Dict[str, str] = {}
buffered_subagent_calls: Dict[str, List[dict]] = {}
task_requests_seen: Set[str] = set()
active_project_filter: Optional[str] = None
active_mode: str = MODE_ALL
_last_monitored_count: Optional[int] = None

# ORCHESTRATOR
def run_monitor(project_filter: Optional[str] = None, mode: str = MODE_ALL) -> None:
    global active_project_filter, active_mode
    active_project_filter = project_filter
    active_mode = mode

    initialize_file_positions()

    if mode == MODE_WORKERS:
        from ..workers import run_workers_loop
        run_workers_loop()
    elif mode == MODE_TOKENS:
        from ..panes import run_tokens_loop
        run_tokens_loop()
    elif mode == MODE_WARNINGS:
        from ..panes import run_warnings_loop
        run_warnings_loop()
    elif mode == MODE_PROXY:
        from ..proxy_display import run_proxy_loop
        run_proxy_loop()
    elif mode == MODE_WORKER_PROXY:
        from ..proxy_display import run_worker_proxy_loop
        run_worker_proxy_loop()
    else:
        sessions = find_active_sessions(active_project_filter)
        session_count = len(filter_sessions_by_mode(sessions, mode))
        print_session_status(session_count, project_filter, mode)
        run_main_loop()

# FUNCTIONS

# Initialize file positions for all existing sessions
def initialize_file_positions() -> int:
    global file_positions, active_project_filter

    sessions = find_active_sessions(active_project_filter)

    for session_file in sessions:
        if session_file not in file_positions:
            pos = get_file_end_position(session_file)
            file_positions[session_file] = pos

    return len(sessions)

# Monitor all active sessions for new tool calls
def monitor_sessions() -> None:
    global active_project_filter, active_mode, _last_monitored_count
    sessions = find_active_sessions(active_project_filter)

    if _last_monitored_count != len(sessions):
        _last_monitored_count = len(sessions)

    filtered_sessions = filter_sessions_by_mode(sessions, active_mode)
    update_session_tracking(filtered_sessions)
    process_all_sessions(filtered_sessions)

# Update tracking for new or removed sessions
def update_session_tracking(sessions: list) -> None:
    global file_positions, tool_use_caches

    current_files = set(sessions)
    tracked_files = set(file_positions.keys())

    new_files = current_files - tracked_files
    removed_files = tracked_files - current_files

    for new_file in new_files:
        file_positions[new_file] = get_initial_position(new_file)
        tool_use_caches[new_file] = {}

    for removed_file in removed_files:
        del file_positions[removed_file]
        if removed_file in tool_use_caches:
            del tool_use_caches[removed_file]

# Process all tracked session files
def process_all_sessions(sessions: list) -> None:
    global file_positions

    for session_file in sessions:
        if session_file in file_positions:
            process_session_file(session_file)

# Check if file is a subagent file
def is_agent_file(filepath: Path) -> bool:
    return filepath.name.startswith('agent-')

# Filter sessions based on mode (all vs main-only)
def filter_sessions_by_mode(sessions: list, mode: str) -> list:
    if mode == MODE_MAIN:
        filtered = [s for s in sessions if not is_agent_file(s)]
    else:
        filtered = sessions

    return filtered

# Runs virtual-rendering main loop with mouse-scroll, zebra, and truncation
def run_main_loop() -> None:
    register_ram_dump('main', _main_ram_state)
    load_historical_main()
    current_main_session = _get_newest_main_session()
    last_output = None
    last_data_refresh = 0.0
    last_janitor_ts = 0.0
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
                    if event is not None and event[0] != -1:
                        if _handle_main_mouse(*event):
                            input_changed = True
                    elif event is not None:  # (-1,-1,-1) sentinel → release, ignore
                        pass
                    elif _md._search_focused:  # bare ESC → cancel search
                        if _handle_main_search_cancel():
                            input_changed = True
                elif _md._search_focused:
                    if _handle_main_search_input(char):
                        input_changed = True
                elif char == 'y':
                    key = resolve_parent_key(_md.main_line_map, _md.main_hover_row)
                    if key is not None:
                        copy_to_clipboard(_md.serialize_main_event(key))
            now = time.time()
            _md._main_copy_feedback_until = {
                k: v for k, v in _md._main_copy_feedback_until.items() if v > now
            }
            if _md._main_copy_feedback_until:
                input_changed = True
            changed, last_data_refresh, last_janitor_ts, current_main_session = (
                _refresh_main_data(now, last_data_refresh, last_janitor_ts, current_main_session)
            )
            input_changed = input_changed or changed
            if input_changed:
                last_output = _build_main_output(last_output)
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# RAM state snapshot for the main pane (registered via register_ram_dump)
def _main_ram_state() -> list:
    return [
        ('file_positions',          file_positions),
        ('tool_use_caches',         tool_use_caches),
        ('agent_to_task',           agent_to_task),
        ('agent_to_type',           agent_to_type),
        ('buffered_subagent_calls', buffered_subagent_calls),
        ('task_requests_seen',      task_requests_seen),
        ('call_counter',            call_counter),
        ('active_project_filter',   str(active_project_filter)),
        ('active_mode',             active_mode),
        ('_last_monitored_count',   str(_last_monitored_count)),
    ]

# Handle mouse events for the main pane; returns True if input_changed.
def _handle_main_mouse(button: int, col: int, row: int) -> bool:
    pw = _md._main_pane_width
    if button == 0:  # left click
        if row == 1:  # search bar row
            if col >= pw - 2:  # [→] next match
                if _md._search_matches:
                    _md._search_current_idx = (_md._search_current_idx + 1) % len(_md._search_matches)
                    _md.ensure_match_visible()
                    return True
            elif col >= pw - 6:  # [←] prev match
                if _md._search_matches:
                    _md._search_current_idx = (_md._search_current_idx - 1) % len(_md._search_matches)
                    _md.ensure_match_visible()
                    return True
            else:  # search text area → focus
                _md._search_focused = True
                return True
        else:  # buffer area (row >= 2) — always check copy
            entry = _md._main_copy_rows.get(row)
            if entry is not None and col >= pw - 2:
                event_idx, part = entry
                copy_to_clipboard(_md.serialize_main_event(event_idx, part))
                _md._main_copy_feedback_until[(event_idx, part)] = time.time() + 1.5
                return True
    elif button == 64:  # WheelUp → older events
        _md.main_scroll_offset = max(0, _md.main_scroll_offset + 3)
        return True
    elif button == 65:  # WheelDown → newer events
        _md.main_scroll_offset = max(0, _md.main_scroll_offset - 3)
        return True
    elif button >= 32:  # motion/hover
        _md.main_hover_row = row
        return True
    return False

# Cancel active search on bare ESC; returns True (always triggers redraw).
def _handle_main_search_cancel() -> bool:
    _md._search_focused = False
    _md._search_query = ''
    _md._search_committed = False
    _md._search_matches = []
    _md._search_match_set = set()
    _md._search_match_line_offsets = {}
    return True

# Handle keyboard input while search is focused; returns True if input_changed.
def _handle_main_search_input(char: str) -> bool:
    if char in ('\x7f', '\x08'):  # backspace (DEL or BS)
        _md._search_query = _md._search_query[:-1]
        _md._search_committed = False
        _md._search_matches = []
        _md._search_match_set = set()
        _md._search_match_line_offsets = {}
        return True
    if char in ('\r', '\n'):  # enter → commit search, unfocus
        if _md._search_query != _md._search_cached_query:
            _md._search_matches, _md._search_match_set = _md._compute_search_matches(_md._search_query)
            _md._search_cached_query = _md._search_query
            _md._search_current_idx = 0
        _md._search_match_line_offsets = _md._compute_match_line_offsets(
            _md._search_query, _md._search_matches
        )
        _md._search_committed = True
        _md._search_focused = False
        _md.ensure_match_visible()
        return True
    if char.isprintable():
        if len(_md._search_query) < 200:
            _md._search_query += char
            _md._search_committed = False
            _md._search_matches = []
            _md._search_match_set = set()
            _md._search_match_line_offsets = {}
            return True
    return False

# Tick-boundary data refresh: session change, sticky-scroll, monitor_sessions, janitor.
# Returns (input_changed, last_data_refresh, last_janitor_ts, current_main_session).
def _refresh_main_data(now: float, last_data_refresh: float, last_janitor_ts: float, current_main_session) -> tuple:
    if now - last_data_refresh < POLL_INTERVAL:
        return False, last_data_refresh, last_janitor_ts, current_main_session
    newest = _get_newest_main_session()
    if newest != current_main_session and newest is not None:
        current_main_session = newest
        file_positions[newest] = 0
        tool_use_caches[newest] = {}
        _md.main_event_buffer.clear()
        _md.main_scroll_offset = 0
        _md.main_event_buffer.append({'type': 'session_banner', 'data': {}, 'call_number': None})
    _sticky_pre = None
    if _md.main_scroll_offset > 0:
        try:
            _sticky_pw = os.get_terminal_size().columns
        except OSError:
            _sticky_pw = 80
        _sticky_pre = _md._count_buffer_lines(_sticky_pw)
    monitor_sessions()
    if _sticky_pre is not None and _md.main_scroll_offset > 0:
        try:
            _sticky_pw = os.get_terminal_size().columns
        except OSError:
            _sticky_pw = 80
        _sticky_delta = _md._count_buffer_lines(_sticky_pw) - _sticky_pre
        if _sticky_delta != 0:
            _md.main_scroll_offset = max(0, _md.main_scroll_offset + _sticky_delta)
    if now - last_janitor_ts >= 86400:
        from ..log_janitor import cleanup_old_jsonl, sweep_eligible_specs
        _logs = Path(__file__).parent.parent / 'logs'
        for _, _path in sweep_eligible_specs(_logs):
            cleanup_old_jsonl(_path)
        last_janitor_ts = now
    return True, now, last_janitor_ts, current_main_session

# Render main buffer, print if changed; returns new last_output.
def _build_main_output(last_output):
    try:
        term = os.get_terminal_size()
        pane_height = term.lines - 1
        pane_width = term.columns
    except OSError:
        pane_height = 50
        pane_width = 80
    output = render_main_buffer(pane_height, pane_width, _md.main_scroll_offset)
    if output != last_output:
        print("\033[2J\033[3J\033[H", end='', flush=True)
        if output:
            print(output)
        return output
    return last_output

# Get the newest main (non-agent) session file
def _get_newest_main_session() -> Optional[Path]:
    main_sessions = get_main_session_files()
    return main_sessions[0] if main_sessions else None

# Extract timestamp 60s before the first message in the newest main session JSONL
def _get_session_start_ts() -> Optional[str]:
    session = _get_newest_main_session()
    if not session:
        return None
    lines = read_new_lines(session, 0)
    messages, _ = parse_jsonl_lines(lines[:5])
    for msg in messages:
        ts = msg.get('timestamp')
        if ts:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            dt_adjusted = dt - timedelta(seconds=10)
            return dt_adjusted.isoformat().replace('+00:00', 'Z')
    return None

# Return main session files (non-agent) sorted by recency
def get_main_session_files() -> List[Path]:
    sessions = find_active_sessions(active_project_filter)
    return [s for s in sessions if not is_agent_file(s)]
