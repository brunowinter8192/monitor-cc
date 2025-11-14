# INFRASTRUCTURE
import time
from pathlib import Path
from typing import Dict

from session_finder import find_active_sessions
from jsonl_parser import parse_new_tool_calls
from formatter import format_tool_call, format_warning

POLL_INTERVAL = 0.5
file_positions: Dict[Path, int] = {}
call_counter = 0

# ORCHESTRATOR
def run_monitor() -> None:
    initialize_file_positions()

    while True:
        monitor_sessions()
        time.sleep(POLL_INTERVAL)

# FUNCTIONS

# Initialize file positions for all existing sessions
def initialize_file_positions() -> None:
    global file_positions

    sessions = find_active_sessions()

    for session_file in sessions:
        if session_file not in file_positions:
            file_positions[session_file] = get_file_end_position(session_file)

# Monitor all active sessions for new tool calls
def monitor_sessions() -> None:
    sessions = find_active_sessions()
    update_session_tracking(sessions)
    process_all_sessions(sessions)

# Update tracking for new or removed sessions
def update_session_tracking(sessions: list) -> None:
    global file_positions

    current_files = set(sessions)
    tracked_files = set(file_positions.keys())

    new_files = current_files - tracked_files
    for new_file in new_files:
        file_positions[new_file] = get_file_end_position(new_file)

# Process all tracked session files
def process_all_sessions(sessions: list) -> None:
    global file_positions

    for session_file in sessions:
        if session_file in file_positions:
            process_session_file(session_file)

# Process single session file for new tool calls and warnings
def process_session_file(filepath: Path) -> None:
    global file_positions, call_counter

    last_position = file_positions[filepath]
    tool_calls, new_position, malformed_warnings = parse_new_tool_calls(filepath, last_position)

    for warning in malformed_warnings:
        display_warning(warning)

    for tool_call in tool_calls:
        call_counter += 1
        display_tool_call(tool_call, call_counter)

    file_positions[filepath] = new_position

# Display formatted tool call to console
def display_tool_call(tool_call: dict, call_number: int) -> None:
    formatted = format_tool_call(
        tool_name=tool_call['tool_name'],
        input_data=tool_call['input'],
        output_data=tool_call['output'] or '',
        tool_use_id=tool_call['tool_use_id'],
        timestamp=tool_call['timestamp'],
        call_number=call_number
    )

    print(formatted)
    print()

# Display formatted warning to console
def display_warning(warning: dict) -> None:
    formatted = format_warning(
        file_path=warning['file_path'],
        line_number=warning['line_number'],
        error_message=warning['error_message'],
        raw_line=warning['raw_line']
    )

    print(formatted)
    print()

# Get end position of file (for initializing at EOF)
def get_file_end_position(filepath: Path) -> int:
    if not filepath.exists():
        return 0
    return filepath.stat().st_size
