# INFRASTRUCTURE
from datetime import datetime, timedelta
import time
from pathlib import Path
from typing import Dict, Set, List, Optional

# From constants.py: Colors, config, shared constants
from ..constants import RESET, CYAN, POLL_INTERVAL, INPUT_POLL_INTERVAL, MODE_ALL, MODE_MAIN, MODE_WARNINGS, MODE_TOKENS, MODE_WORKERS, MODE_PROXY, MODE_WORKER_PROXY

# From session_finder.py: Discover active Claude Code sessions
from ..session_finder import find_active_sessions
# From jsonl/: Parse JSONL lines for session start timestamp
from ..jsonl import parse_jsonl_lines, read_new_lines
# From monitor_display.py: Session status output
from .monitor_display import print_session_status
# From monitor_session.py: Session file processing, task handling, historical load
from .monitor_session import get_file_end_position, get_initial_position, process_session_file, load_historical_main
# From ram_audit: register tracemalloc + SIGUSR1 dump handler for this pane
from ..ram_audit import register_ram_dump

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
    import os
    from ..input.click_handler import (
        read_keypress, setup_keyboard_input, restore_terminal,
        enable_mouse, disable_mouse, read_mouse_event,
        resolve_parent_key, copy_to_clipboard,
    )
    from .monitor_display import render_main_buffer
    from . import monitor_display as _display

    def _ram_state():
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
    register_ram_dump('main', _ram_state)

    load_historical_main()
    current_main_session = _get_newest_main_session()
    last_output = None
    last_data_refresh = 0.0
    _last_janitor_ts = 0.0
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
                        button, col, row = event
                        pw = _display._main_pane_width
                        if button == 0:  # left click
                            if row == 1:  # search bar row
                                if col >= pw - 2:  # [→] next match
                                    if _display._search_matches:
                                        _display._search_current_idx = (_display._search_current_idx + 1) % len(_display._search_matches)
                                        _display.ensure_match_visible()
                                        input_changed = True
                                elif col >= pw - 6:  # [←] prev match
                                    if _display._search_matches:
                                        _display._search_current_idx = (_display._search_current_idx - 1) % len(_display._search_matches)
                                        _display.ensure_match_visible()
                                        input_changed = True
                                else:  # search text area → focus
                                    _display._search_focused = True
                                    input_changed = True
                            else:  # buffer area (row >= 2) — never unfocus; always check copy
                                entry = _display._main_copy_rows.get(row)
                                if entry is not None and col >= pw - 2:
                                    event_idx, part = entry
                                    copy_to_clipboard(_display.serialize_main_event(event_idx, part))
                                    _display._main_copy_feedback_until[(event_idx, part)] = time.time() + 1.5
                                    input_changed = True
                        elif button == 64:  # WheelUp → older events
                            _display.main_scroll_offset = max(0, _display.main_scroll_offset + 3)
                            input_changed = True
                        elif button == 65:  # WheelDown → newer events
                            _display.main_scroll_offset = max(0, _display.main_scroll_offset - 3)
                            input_changed = True
                        elif button >= 32:  # motion/hover
                            _display.main_hover_row = row
                            input_changed = True
                    elif event is not None:  # (-1,-1,-1) sentinel → release event, ignore
                        pass
                    elif _display._search_focused:  # event is None: bare ESC → cancel search
                        _display._search_focused = False
                        _display._search_query = ''
                        _display._search_committed = False
                        _display._search_matches = []
                        _display._search_match_set = set()
                        _display._search_match_line_offsets = {}
                        input_changed = True
                elif _display._search_focused:  # search input mode
                    if char in ('\x7f', '\x08'):  # backspace (DEL or BS)
                        _display._search_query = _display._search_query[:-1]
                        _display._search_committed = False
                        _display._search_matches = []
                        _display._search_match_set = set()
                        _display._search_match_line_offsets = {}
                        input_changed = True
                    elif char in ('\r', '\n'):  # enter → commit search, unfocus
                        if _display._search_query != _display._search_cached_query:
                            _display._search_matches, _display._search_match_set = _display._compute_search_matches(_display._search_query)
                            _display._search_cached_query = _display._search_query
                            _display._search_current_idx = 0
                        _display._search_match_line_offsets = _display._compute_match_line_offsets(
                            _display._search_query, _display._search_matches
                        )
                        _display._search_committed = True
                        _display._search_focused = False
                        _display.ensure_match_visible()
                        input_changed = True
                    elif char.isprintable():
                        if len(_display._search_query) < 200:
                            _display._search_query += char
                            _display._search_committed = False
                            _display._search_matches = []
                            _display._search_match_set = set()
                            _display._search_match_line_offsets = {}
                            input_changed = True
                elif char == 'y':
                    key = resolve_parent_key(_display.main_line_map, _display.main_hover_row)
                    if key is not None:
                        copy_to_clipboard(_display.serialize_main_event(key))

            now = time.time()
            _display._main_copy_feedback_until = {
                k: v for k, v in _display._main_copy_feedback_until.items() if v > now
            }
            if _display._main_copy_feedback_until:
                input_changed = True
            if now - last_data_refresh >= POLL_INTERVAL:
                newest = _get_newest_main_session()
                if newest != current_main_session and newest is not None:
                    current_main_session = newest
                    file_positions[newest] = 0
                    tool_use_caches[newest] = {}
                    _display.main_event_buffer.clear()
                    _display.main_scroll_offset = 0
                    _display.main_event_buffer.append(
                        {'type': 'session_banner', 'data': {}, 'call_number': None}
                    )
                # sticky-scroll: snapshot rendered line count before new events arrive
                _sticky_pre = None
                if _display.main_scroll_offset > 0:
                    try:
                        _sticky_pw = os.get_terminal_size().columns
                    except OSError:
                        _sticky_pw = 80
                    _sticky_pre = _display._count_buffer_lines(_sticky_pw)
                monitor_sessions()
                # sticky-scroll: offset grows by line delta so absolute viewport stays pinned
                if _sticky_pre is not None and _display.main_scroll_offset > 0:
                    try:
                        _sticky_pw = os.get_terminal_size().columns
                    except OSError:
                        _sticky_pw = 80
                    _sticky_delta = _display._count_buffer_lines(_sticky_pw) - _sticky_pre
                    if _sticky_delta != 0:
                        _display.main_scroll_offset = max(0, _display.main_scroll_offset + _sticky_delta)
                last_data_refresh = now
                input_changed = True
                if now - _last_janitor_ts >= 86400:
                    from ..log_janitor import cleanup_old_jsonl, sweep_eligible_specs
                    _logs = Path(__file__).parent.parent / 'logs'
                    for _, _path in sweep_eligible_specs(_logs):
                        cleanup_old_jsonl(_path)
                    _last_janitor_ts = now

            if input_changed:
                try:
                    term = os.get_terminal_size()
                    pane_height = term.lines - 1
                    pane_width = term.columns
                except OSError:
                    pane_height = 50
                    pane_width = 80
                output = render_main_buffer(pane_height, pane_width, _display.main_scroll_offset)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

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
