# INFRASTRUCTURE
import logging
import time
from pathlib import Path
from typing import Dict, Set, List

logging.basicConfig(
    filename='logs/monitor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# From session_finder.py: Discover active Claude Code sessions
from session_finder import find_active_sessions
# From jsonl_parser.py: Parse JSONL and extract tool calls
from jsonl_parser import parse_new_tool_calls
# From formatter.py: Format tool calls and warnings for display
from formatter import format_tool_call, format_warning

POLL_INTERVAL = 0.5
file_positions: Dict[Path, int] = {}
tool_use_caches: Dict[Path, dict] = {}
call_counter = 0
agent_to_task: Dict[str, str] = {}
buffered_subagent_calls: Dict[str, List[dict]] = {}
task_requests_seen: Set[str] = set()

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
    logging.info(f"Initialized monitoring for {len(sessions)} existing sessions")

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
    global file_positions, tool_use_caches

    current_files = set(sessions)
    tracked_files = set(file_positions.keys())

    new_files = current_files - tracked_files
    for new_file in new_files:
        logging.info(f"New session discovered: {new_file}")
        file_positions[new_file] = get_initial_position(new_file)
        tool_use_caches[new_file] = {}

# Process all tracked session files
def process_all_sessions(sessions: list) -> None:
    global file_positions

    for session_file in sessions:
        if session_file in file_positions:
            process_session_file(session_file)

# Process single session file for new tool calls and warnings
def process_session_file(filepath: Path) -> None:
    global file_positions, tool_use_caches, call_counter, agent_to_task, buffered_subagent_calls, task_requests_seen

    if filepath not in tool_use_caches:
        tool_use_caches[filepath] = {}

    last_position = file_positions[filepath]
    cache = tool_use_caches[filepath]
    tool_calls, new_position, malformed_warnings = parse_new_tool_calls(filepath, last_position, cache)

    for warning in malformed_warnings:
        display_warning(warning)

    for tool_call in tool_calls:
        if is_task_request(tool_call):
            call_counter += 1
            task_requests_seen.add(tool_call['tool_use_id'])
            display_tool_call(tool_call, call_counter)

        elif is_task_response(tool_call):
            spawned_agent_id = tool_call.get('spawned_agent_id')
            if spawned_agent_id:
                agent_to_task[spawned_agent_id] = tool_call['tool_use_id']

                if spawned_agent_id in buffered_subagent_calls:
                    for buffered_call in buffered_subagent_calls[spawned_agent_id]:
                        call_counter += 1
                        display_tool_call(buffered_call, call_counter)
                    del buffered_subagent_calls[spawned_agent_id]

            call_counter += 1
            display_tool_call(tool_call, call_counter)

        elif is_subagent_call(tool_call):
            agent_id = tool_call.get('agent_id')
            if agent_id and agent_id in agent_to_task:
                call_counter += 1
                display_tool_call(tool_call, call_counter)
            else:
                if agent_id:
                    if agent_id not in buffered_subagent_calls:
                        buffered_subagent_calls[agent_id] = []
                    buffered_subagent_calls[agent_id].append(tool_call)

        else:
            call_counter += 1
            display_tool_call(tool_call, call_counter)

    file_positions[filepath] = new_position

# Display formatted warning to console
def display_warning(warning: dict) -> None:
    logging.warning(f"Malformed JSONL at {warning['file_path']}:{warning['line_number']} - {warning['error_message']}")

    formatted = format_warning(
        file_path=warning['file_path'],
        line_number=warning['line_number'],
        error_message=warning['error_message'],
        raw_line=warning['raw_line']
    )

    print(formatted)
    print()

# Display formatted tool call to console
def display_tool_call(tool_call: dict, call_number: int) -> None:
    formatted = format_tool_call(
        tool_name=tool_call['tool_name'],
        input_data=tool_call['input'],
        output_data=tool_call['output'] or '',
        tool_use_id=tool_call['tool_use_id'],
        timestamp=tool_call['timestamp'],
        call_number=call_number,
        is_subagent=tool_call.get('is_subagent', False)
    )

    print(formatted)
    print()

# Get end position of file (for initializing at EOF)
def get_file_end_position(filepath: Path) -> int:
    if not filepath.exists():
        return 0
    return filepath.stat().st_size

# Get initial position for new session file
def get_initial_position(filepath: Path) -> int:
    if is_agent_file(filepath):
        return 0
    return get_file_end_position(filepath)

# Check if file is a subagent file
def is_agent_file(filepath: Path) -> bool:
    return filepath.name.startswith('agent-')

# Check if tool call is a Task REQUEST
def is_task_request(tool_call: dict) -> bool:
    return tool_call.get('tool_name') == 'Task' and tool_call.get('output') is None

# Check if tool call is a Task RESPONSE
def is_task_response(tool_call: dict) -> bool:
    return tool_call.get('tool_name') == 'Task' and tool_call.get('output') is not None

# Check if tool call is from a Subagent
def is_subagent_call(tool_call: dict) -> bool:
    return tool_call.get('is_subagent', False)
