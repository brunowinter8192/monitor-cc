# INFRASTRUCTURE
from datetime import datetime, timedelta
import time
from pathlib import Path
from typing import Dict, Set, List, Optional

# From constants.py: Colors, config, shared constants
from ..constants import RESET, CYAN, POLL_INTERVAL, INPUT_POLL_INTERVAL, MODE_ALL, MODE_MAIN, MODE_RULES, MODE_WARNINGS, MODE_HOOKS, MODE_TOKENS, MODE_WORKERS, MODE_PROXY, MODE_METADATA, MODE_WORKER_PROXY, MODE_WORKER_METADATA, MODE_WASTE

# From session_finder.py: Discover active Claude Code sessions
from ..session_finder import find_active_sessions
# From jsonl/: Parse JSONL lines for session start timestamp
from ..jsonl import parse_jsonl_lines, read_new_lines
# From hooks/: Parse hook log entries
from ..hooks import get_current_position as get_hook_log_position
# From monitor_display.py: Session status output
from .monitor_display import print_session_status
# From monitor_session.py: Session file processing, task handling, historical load
from .monitor_session import get_file_end_position, get_initial_position, process_session_file, load_historical_main

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
hook_log_position: int = 0

# ORCHESTRATOR
def run_monitor(project_filter: Optional[str] = None, mode: str = MODE_ALL) -> None:
    global active_project_filter, active_mode, hook_log_position
    active_project_filter = project_filter
    active_mode = mode

    initialize_file_positions()

    if mode == MODE_WORKERS:
        from ..workers import run_workers_loop
        run_workers_loop()
    elif mode == MODE_TOKENS:
        from ..panes import run_tokens_loop
        run_tokens_loop()
    elif mode == MODE_RULES:
        from ..panes import run_rules_loop
        run_rules_loop()
    elif mode == MODE_WARNINGS:
        from ..panes import run_warnings_loop
        run_warnings_loop()
    elif mode == MODE_HOOKS:
        from ..hooks import run_hooks_loop
        run_hooks_loop()
    elif mode == MODE_PROXY:
        from ..proxy_display import run_proxy_loop
        run_proxy_loop()
    elif mode == MODE_METADATA:
        from ..metadata import run_metadata_loop
        run_metadata_loop()
    elif mode == MODE_WORKER_PROXY:
        from ..proxy_display import run_worker_proxy_loop
        run_worker_proxy_loop()
    elif mode == MODE_WORKER_METADATA:
        from ..metadata import run_worker_metadata_loop
        run_worker_metadata_loop()
    elif mode == MODE_WASTE:
        from ..panes import run_waste_loop
        run_waste_loop()
    else:
        sessions = find_active_sessions(active_project_filter)
        session_count = len(filter_sessions_by_mode(sessions, mode))
        print_session_status(session_count, project_filter, mode)
        run_main_loop()

# FUNCTIONS

# Initialize file positions for all existing sessions
def initialize_file_positions() -> int:
    global file_positions, active_project_filter, hook_log_position

    sessions = find_active_sessions(active_project_filter)

    for session_file in sessions:
        if session_file not in file_positions:
            pos = get_file_end_position(session_file)
            file_positions[session_file] = pos

    hook_log_position = initialize_hook_log_position()

    return len(sessions)

# Initialize hook log position at EOF to skip historical entries
def initialize_hook_log_position() -> int:
    pos = get_hook_log_position()
    return pos

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
    from ..panes import process_hook_log
    from ..input.click_handler import (
        read_keypress, setup_keyboard_input, restore_terminal,
        enable_mouse, disable_mouse, read_mouse_event,
    )
    from .monitor_display import render_main_buffer
    from . import monitor_display as _display

    load_historical_main()
    current_main_session = _get_newest_main_session()
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
                        button, col, row = event
                        if button == 64:  # WheelUp → older events
                            _display.main_scroll_offset = max(0, _display.main_scroll_offset + 3)
                            input_changed = True
                        elif button == 65:  # WheelDown → newer events
                            _display.main_scroll_offset = max(0, _display.main_scroll_offset - 3)
                            input_changed = True

            now = time.time()
            if now - last_data_refresh >= POLL_INTERVAL:
                process_hook_log()
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
                monitor_sessions()
                last_data_refresh = now
                input_changed = True

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
