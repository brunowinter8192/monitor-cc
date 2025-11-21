# INFRASTRUCTURE
import logging
import os
import time
from pathlib import Path
from typing import Dict, Set, List, Optional

# ANSI Colors
RESET = '\033[0m'
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
MAGENTA = '\033[95m'
CYAN = '\033[96m'
WHITE = '\033[97m'
PURPLE = '\033[38;5;135m'
ORANGE = '\033[38;5;208m'

# Setup 7 loggers for different workflow phases
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 02_initialization.log
logger_init = logging.getLogger('monitor.init')
init_handler = logging.FileHandler('src/logs/02_initialization.log')
init_handler.setFormatter(log_format)
logger_init.addHandler(init_handler)
logger_init.setLevel(logging.INFO)

# 03_session_discovery.log (shares with session_finder.py)
logger_discovery = logging.getLogger('monitor.discovery')
discovery_handler = logging.FileHandler('src/logs/03_session_discovery.log')
discovery_handler.setFormatter(log_format)
logger_discovery.addHandler(discovery_handler)
logger_discovery.setLevel(logging.INFO)

# 04_file_reading.log (shares with jsonl_parser.py)
logger_file = logging.getLogger('monitor.file')
file_handler = logging.FileHandler('src/logs/04_file_reading.log')
file_handler.setFormatter(log_format)
logger_file.addHandler(file_handler)
logger_file.setLevel(logging.INFO)

# 07_display_routing.log
logger_routing = logging.getLogger('monitor.routing')
routing_handler = logging.FileHandler('src/logs/07_display_routing.log')
routing_handler.setFormatter(log_format)
logger_routing.addHandler(routing_handler)
logger_routing.setLevel(logging.INFO)

# 08_ui_rendering.log (shares with subagent_ui.py)
logger_ui = logging.getLogger('monitor.ui')
ui_handler = logging.FileHandler('src/logs/08_ui_rendering.log')
ui_handler.setFormatter(log_format)
logger_ui.addHandler(ui_handler)
logger_ui.setLevel(logging.INFO)

# 09_click_handling.log
logger_clicks = logging.getLogger('monitor.clicks')
clicks_handler = logging.FileHandler('src/logs/09_click_handling.log')
clicks_handler.setFormatter(log_format)
logger_clicks.addHandler(clicks_handler)
logger_clicks.setLevel(logging.INFO)

# Tagged logging helper
def log_tagged(logger, tag: str, color: str, message: str) -> None:
    colored_tag = f"{color}[{tag}]{RESET}"
    logger.info(f"{colored_tag} {message}")

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
ui_loop_iteration: int = 0

# ORCHESTRATOR
def run_monitor(project_filter: Optional[str] = None, mode: str = 'all', ui: bool = False) -> None:
    global active_project_filter, active_mode, ui_mode_active
    active_project_filter = project_filter
    active_mode = mode
    ui_mode_active = ui

    log_tagged(logger_init, "RUN_MONITOR", MAGENTA, f"run_monitor: project={project_filter}, mode={mode}, ui={ui}")

    initialize_file_positions()

    if ui and mode == 'subagent':
        log_tagged(logger_init, "UI_MODE", CYAN, "Starting UI mode with FIFO")
        open_fifo_non_blocking()
        try:
            run_ui_loop()
        finally:
            close_fifo()
    else:
        log_tagged(logger_init, "STREAM_MODE", CYAN, "Starting streaming mode")
        run_streaming_loop()

# FUNCTIONS

# Initialize file positions for all existing sessions
def initialize_file_positions() -> None:
    global file_positions, active_project_filter

    sessions = find_active_sessions(active_project_filter)
    log_tagged(logger_init, "INIT_SESS", BLUE, f"Initializing {len(sessions)} sessions: {[s.name for s in sessions]}")

    for session_file in sessions:
        if session_file not in file_positions:
            pos = get_file_end_position(session_file)
            file_positions[session_file] = pos
            log_tagged(logger_init, "FILE_POS_INIT", BLUE, f"Initialized {session_file.name} at position {pos}")

# Monitor all active sessions for new tool calls
def monitor_sessions() -> None:
    global active_project_filter, active_mode
    sessions = find_active_sessions(active_project_filter)
    log_tagged(logger_routing, "MON_SESS", BLUE, f"monitor_sessions: found={len(sessions)}, mode={active_mode}, tracking={len(file_positions)}")
    filtered_sessions = filter_sessions_by_mode(sessions, active_mode)
    log_tagged(logger_routing, "MODE_FILTER", BLUE, f"monitor_sessions: after_filter={len(filtered_sessions)}")
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
        log_tagged(logger_file, "NEW_SESS", GREEN, f"New session discovered: {new_file}")
        file_positions[new_file] = get_initial_position(new_file)
        tool_use_caches[new_file] = {}

    for removed_file in removed_files:
        log_tagged(logger_file, "SESS_REMOVED", YELLOW, f"Session removed: {removed_file}")
        del file_positions[removed_file]
        if removed_file in tool_use_caches:
            del tool_use_caches[removed_file]

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
    log_tagged(logger_file, "PROCESS_FILE", BLUE, f"Processing {filepath.name}: last_pos={last_position}, cache_size={len(cache)}")

    tool_calls, new_position, malformed_warnings = parse_new_tool_calls(filepath, last_position, cache)

    for warning in malformed_warnings:
        display_warning(warning)

    task_requests = 0
    task_responses = 0
    subagent_ui_tracked = 0
    subagent_displayed = 0
    subagent_buffered = 0
    other_displayed = 0

    for tool_call in tool_calls:
        if is_task_request(tool_call):
            task_requests += 1
            call_counter += 1
            task_requests_seen.add(tool_call['tool_use_id'])
            display_tool_call(tool_call, call_counter)

        elif is_task_response(tool_call):
            task_responses += 1
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
                subagent_ui_tracked += 1
                call_counter += 1
                tool_call['call_number'] = call_counter
                track_subagent_metadata(tool_call, filepath)
            elif active_mode == 'subagent':
                subagent_displayed += 1
                call_counter += 1
                display_tool_call(tool_call, call_counter)
            elif agent_id and agent_id in agent_to_task:
                subagent_displayed += 1
                call_counter += 1
                display_tool_call(tool_call, call_counter)
            else:
                if agent_id:
                    subagent_buffered += 1
                    if agent_id not in buffered_subagent_calls:
                        buffered_subagent_calls[agent_id] = []
                    buffered_subagent_calls[agent_id].append(tool_call)

        else:
            other_displayed += 1
            call_counter += 1
            display_tool_call(tool_call, call_counter)

    file_positions[filepath] = new_position
    log_tagged(logger_routing, "PROC_STATS", WHITE, f"Processed {filepath.name}: task_req={task_requests}, task_resp={task_responses}, subagent_ui={subagent_ui_tracked}, subagent_displayed={subagent_displayed}, subagent_buffered={subagent_buffered}, other={other_displayed}")

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
        filtered = sessions
    elif mode == 'main':
        filtered = [s for s in sessions if not is_agent_file(s)]
    elif mode == 'subagent':
        filtered = [s for s in sessions if is_agent_file(s)]
    else:
        filtered = sessions

    log_tagged(logger_routing, "FILTER_MODE", BLUE, f"filter_sessions_by_mode: mode={mode}, in={len(sessions)}, out={len(filtered)}")
    return filtered

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
    global ui_loop_iteration
    while True:
        ui_loop_iteration += 1
        if ui_loop_iteration % 10 == 0:
            log_tagged(logger_ui, "UI_ITER", WHITE, f"UI loop iteration #{ui_loop_iteration}")
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
        log_tagged(logger_ui, "AGENT_DISC", CYAN, f"Discovered new agent: {agent_id}, type={subagent_type}, file={filepath.name}")

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

    expanded_count = sum(1 for agent_id in subagent_states if subagent_states.get(agent_id, False))
    log_tagged(logger_ui, "UI_SYNC", PURPLE, f"sync_ui_to_screen: agents={len(subagent_metadata)}, expanded={expanded_count}")

    formatted_output = render_subagent_list(subagent_metadata, tool_calls_by_agent)

    if formatted_output != last_rendered_output:
        log_tagged(logger_ui, "UI_RENDER", PURPLE, f"Re-rendering UI: {len(formatted_output)} chars, agents={len(subagent_metadata)}, expanded={expanded_count}")
        print("\033[2J\033[H", end='')
        print(formatted_output)
        last_rendered_output = formatted_output
    else:
        log_tagged(logger_ui, "UI_SKIP", WHITE, "sync_ui_to_screen: no change, skipping re-render")

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
        log_tagged(logger_init, "FIFO_WARN", YELLOW, "MONITOR_CC_FIFO not set, mouse clicks disabled")
        return

    try:
        fifo_fd = os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)
        log_tagged(logger_init, "FIFO_OPEN", GREEN, f"Opened FIFO at {fifo_path}")
    except Exception as e:
        log_tagged(logger_init, "FIFO_ERROR", RED, f"Failed to open FIFO: {e}")
        fifo_fd = None

# Closes FIFO file descriptor
def close_fifo() -> None:
    global fifo_fd
    if fifo_fd is not None:
        os.close(fifo_fd)
        fifo_fd = None
        log_tagged(logger_ui, "FIFO_CLOSE", CYAN, "Closed FIFO")

# Reads and processes commands from FIFO
def handle_fifo_commands() -> None:
    global fifo_fd

    if fifo_fd is None:
        return

    try:
        data = os.read(fifo_fd, 1024).decode('utf-8').strip()
        if data:
            log_tagged(logger_clicks, "FIFO_READ", CYAN, f"Read from FIFO: '{data}'")
            for line in data.split('\n'):
                if line:
                    process_fifo_command(line)
    except BlockingIOError:
        pass
    except Exception as e:
        log_tagged(logger_clicks, "FIFO_ERROR", RED, f"Error reading FIFO: {e}")

# Processes single FIFO command
def process_fifo_command(command: str) -> None:
    global subagent_metadata

    log_tagged(logger_clicks, "FIFO_CMD", CYAN, f"Processing command: '{command}'")

    parts = command.split(':', 2)
    if len(parts) != 3:
        log_tagged(logger_clicks, "FIFO_INVALID", RED, f"Invalid FIFO command format: {command}")
        return

    action, mouse_y, scroll_pos = parts

    if action == 'toggle':
        try:
            y = int(mouse_y)
            scroll = int(scroll_pos)
            line_num = y + scroll + 1
            agent_id = get_agent_id_at_line(line_num)
            if agent_id:
                toggle_subagent(agent_id)
                log_tagged(logger_clicks, "TOGGLE_OK", GREEN, f"Toggled agent {agent_id} at line {line_num}")
            else:
                log_tagged(logger_clicks, "NO_AGENT", RED, f"No agent found at line {line_num}")
        except ValueError:
            log_tagged(logger_clicks, "INVALID_POS", RED, f"Invalid mouse position: y={mouse_y}, scroll={scroll_pos}")

# Maps display line number to agent_id
def get_agent_id_at_line(line_num: int) -> Optional[str]:
    global subagent_metadata, tool_calls_by_agent

    current_line = 1
    current_line += 2

    sorted_agents = sorted(subagent_metadata.items(), key=lambda x: x[1]['timestamp'])

    for agent_id, metadata in sorted_agents:
        is_expanded = subagent_states.get(agent_id, False)

        range_start = current_line
        range_end = current_line

        if is_expanded:
            tool_calls = tool_calls_by_agent.get(agent_id, [])
            range_end += len(tool_calls)

        range_end += 1

        if range_start <= line_num <= range_end:
            return agent_id

        current_line = range_end + 1

    return None
