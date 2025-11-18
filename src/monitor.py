# INFRASTRUCTURE
import logging
import os
import time
from pathlib import Path
from typing import Dict, Set, List, Optional

logging.basicConfig(
    filename='src/logs/monitor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# From session_finder.py: Discover active Claude Code sessions
from .session_finder import find_active_sessions
# From jsonl_parser.py: Parse JSONL and extract tool calls
from .jsonl_parser import parse_new_tool_calls
# From formatter.py: Format tool calls and warnings for display
from .formatter import format_tool_call, format_warning
# From subagent_ui.py: Render collapsible subagent list
from .subagent_ui import render_subagent_list, toggle_subagent, collapse_all, get_agent_display_name, extract_timestamp_from_agent, count_calls_for_agent, subagent_states

POLL_INTERVAL = 0.5
file_positions: Dict[Path, int] = {}
tool_use_caches: Dict[Path, dict] = {}
call_counter = 0
agent_to_task: Dict[str, str] = {}
buffered_subagent_calls: Dict[str, List[dict]] = {}
task_requests_seen: Set[str] = set()
active_project_filter: Optional[str] = None
active_mode: str = 'all'
ui_mode_active: bool = False
subagent_metadata: Dict[str, dict] = {}
tool_calls_by_agent: Dict[str, List[dict]] = {}
last_rendered_output: str = ""
fifo_fd: Optional[int] = None
fifo_path: Optional[str] = None

# ORCHESTRATOR
def run_monitor(project_filter: Optional[str] = None, mode: str = 'all', ui: bool = False) -> None:
    global active_project_filter, active_mode, ui_mode_active
    active_project_filter = project_filter
    active_mode = mode
    ui_mode_active = ui
    initialize_file_positions()

    if ui and mode == 'subagent':
        open_fifo_non_blocking()
        try:
            run_ui_loop()
        finally:
            close_fifo()
    else:
        run_streaming_loop()

# FUNCTIONS

# Initialize file positions for all existing sessions
def initialize_file_positions() -> None:
    global file_positions, active_project_filter

    sessions = find_active_sessions(active_project_filter)
    logging.info(f"Initialized monitoring for {len(sessions)} existing sessions")

    for session_file in sessions:
        if session_file not in file_positions:
            file_positions[session_file] = get_file_end_position(session_file)

# Monitor all active sessions for new tool calls
def monitor_sessions() -> None:
    global active_project_filter, active_mode
    sessions = find_active_sessions(active_project_filter)
    filtered_sessions = filter_sessions_by_mode(sessions, active_mode)
    update_session_tracking(filtered_sessions)
    process_all_sessions(filtered_sessions)

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

            if ui_mode_active:
                call_counter += 1
                tool_call['call_number'] = call_counter
                track_subagent_metadata(tool_call, filepath)
            elif active_mode == 'subagent':
                call_counter += 1
                display_tool_call(tool_call, call_counter)
            elif agent_id and agent_id in agent_to_task:
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

# Filter sessions based on mode (all, main, subagent)
def filter_sessions_by_mode(sessions: list, mode: str) -> list:
    if mode == 'all':
        return sessions
    elif mode == 'main':
        return [s for s in sessions if not is_agent_file(s)]
    elif mode == 'subagent':
        return [s for s in sessions if is_agent_file(s)]
    return sessions

# Check if tool call is a Task REQUEST
def is_task_request(tool_call: dict) -> bool:
    return tool_call.get('tool_name') == 'Task' and tool_call.get('output') is None

# Check if tool call is a Task RESPONSE
def is_task_response(tool_call: dict) -> bool:
    return tool_call.get('tool_name') == 'Task' and tool_call.get('output') is not None

# Check if tool call is from a Subagent
def is_subagent_call(tool_call: dict) -> bool:
    return tool_call.get('is_subagent', False)

# Runs continuous streaming monitor loop
def run_streaming_loop() -> None:
    while True:
        monitor_sessions()
        time.sleep(POLL_INTERVAL)

# Runs UI mode loop with collapsible subagent list
def run_ui_loop() -> None:
    while True:
        monitor_sessions()
        handle_fifo_commands()
        sync_ui_to_screen()
        time.sleep(POLL_INTERVAL)

# Tracks subagent metadata from tool calls
def track_subagent_metadata(tool_call: dict, filepath: Path) -> None:
    global subagent_metadata, tool_calls_by_agent

    agent_id = tool_call.get('agent_id')
    if not agent_id:
        return

    if agent_id not in subagent_metadata:
        subagent_type = extract_subagent_type(tool_call)
        timestamp = tool_call.get('timestamp', '')

        subagent_metadata[agent_id] = {
            'name': get_agent_display_name(subagent_type, agent_id),
            'agent_id': agent_id,
            'timestamp': timestamp,
            'file': filepath.name,
            'parent_task_id': agent_to_task.get(agent_id, ''),
            'call_count': 0
        }
        tool_calls_by_agent[agent_id] = []

    tool_calls_by_agent[agent_id].append(tool_call)
    subagent_metadata[agent_id]['call_count'] = count_calls_for_agent(tool_calls_by_agent[agent_id])

# Updates tool calls grouped by agent ID
def update_tool_calls_by_agent(agent_id: str, tool_call: dict) -> None:
    global tool_calls_by_agent

    if agent_id not in tool_calls_by_agent:
        tool_calls_by_agent[agent_id] = []

    tool_calls_by_agent[agent_id].append(tool_call)

# Syncs UI output to terminal screen
def sync_ui_to_screen() -> None:
    global subagent_metadata, tool_calls_by_agent, last_rendered_output

    formatted_output = render_subagent_list(subagent_metadata, tool_calls_by_agent)

    if formatted_output != last_rendered_output:
        print("\033[2J\033[H", end='')
        print(formatted_output)
        last_rendered_output = formatted_output

# Extracts subagent type from tool call input
def extract_subagent_type(tool_call: dict) -> str:
    parent_task_id = agent_to_task.get(tool_call.get('agent_id', ''), '')

    for cached_calls in tool_use_caches.values():
        if parent_task_id in cached_calls:
            parent_tool = cached_calls[parent_task_id]
            if parent_tool.get('tool_name') == 'Task':
                return parent_tool.get('input', {}).get('subagent_type', '')

    return ''

# Opens FIFO in non-blocking mode for reading mouse commands
def open_fifo_non_blocking() -> None:
    global fifo_fd, fifo_path
    fifo_path = os.environ.get('MONITOR_CC_FIFO')

    if not fifo_path:
        logging.warning("MONITOR_CC_FIFO not set, mouse clicks disabled")
        return

    try:
        fifo_fd = os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)
        logging.info(f"Opened FIFO at {fifo_path}")
    except Exception as e:
        logging.error(f"Failed to open FIFO: {e}")
        fifo_fd = None

# Closes FIFO file descriptor
def close_fifo() -> None:
    global fifo_fd
    if fifo_fd is not None:
        os.close(fifo_fd)
        fifo_fd = None
        logging.info("Closed FIFO")

# Reads and processes commands from FIFO
def handle_fifo_commands() -> None:
    global fifo_fd

    if fifo_fd is None:
        return

    try:
        data = os.read(fifo_fd, 1024).decode('utf-8').strip()
        if data:
            for line in data.split('\n'):
                if line:
                    process_fifo_command(line)
    except BlockingIOError:
        pass
    except Exception as e:
        logging.error(f"Error reading FIFO: {e}")

# Processes single FIFO command
def process_fifo_command(command: str) -> None:
    global subagent_metadata

    parts = command.split(':', 1)
    if len(parts) != 2:
        logging.warning(f"Invalid FIFO command: {command}")
        return

    action, value = parts

    if action == 'toggle':
        try:
            line_num = int(value)
            agent_id = get_agent_id_at_line(line_num)
            if agent_id:
                toggle_subagent(agent_id)
                logging.info(f"Toggled agent {agent_id} from line {line_num}")
            else:
                logging.warning(f"No agent found at line {line_num}")
        except ValueError:
            logging.error(f"Invalid line number: {value}")

# Maps display line number to agent_id
def get_agent_id_at_line(line_num: int) -> Optional[str]:
    global subagent_metadata, tool_calls_by_agent

    current_line = 1
    current_line += 2

    sorted_agents = sorted(subagent_metadata.items(), key=lambda x: x[1]['timestamp'])

    for agent_id, metadata in sorted_agents:
        is_expanded = subagent_states.get(agent_id, False)

        if current_line == line_num:
            return agent_id

        current_line += 1

        if is_expanded:
            tool_calls = tool_calls_by_agent.get(agent_id, [])
            current_line += len(tool_calls)

        current_line += 1

    return None
