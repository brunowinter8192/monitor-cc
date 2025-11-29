# INFRASTRUCTURE
from datetime import datetime
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
INDENT = '  '

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

# Tagged logging helper
def log_tagged(logger, tag: str, color: str, message: str) -> None:
    colored_tag = f"{color}[{tag}]{RESET}"
    logger.info(f"{colored_tag} {message}")

# From session_finder.py: Discover active Claude Code sessions
from .session_finder import find_active_sessions
# From jsonl_parser.py: Parse JSONL and extract tool calls
from .jsonl_parser import parse_new_tool_calls
# From formatter.py: Format tool calls for display
from .formatter import format_tool_call
# From subagent_ui.py: Render auto-expanded subagent list
from .subagent_ui import render_subagent_list, get_agent_display_name, extract_timestamp_from_agent, count_calls_for_agent, subagent_states, line_to_agent_map, toggle_subagent_state
# From click_handler.py: Mouse event handling
from .click_handler import setup_mouse_tracking, restore_terminal, read_mouse_event, parse_sgr_mouse, process_click

POLL_INTERVAL = 0.5
file_positions: Dict[Path, int] = {}
tool_use_caches: Dict[Path, dict] = {}
call_counter = 0
agent_to_task: Dict[str, str] = {}
agent_to_type: Dict[str, str] = {}
buffered_subagent_calls: Dict[str, List[dict]] = {}
task_requests_seen: Set[str] = set()
active_project_filter: Optional[str] = None
active_mode: str = 'all'
ui_mode_active: bool = False
subagent_metadata: Dict[str, dict] = {}
tool_calls_by_agent: Dict[str, List[dict]] = {}
last_rendered_output: str = ""
ui_loop_iteration: int = 0
_last_monitored_count: Optional[int] = None
_last_agent_count: int = 0
_last_expanded_count: int = 0

# ORCHESTRATOR
def run_monitor(project_filter: Optional[str] = None, mode: str = 'all', ui: bool = False) -> None:
    global active_project_filter, active_mode, ui_mode_active
    active_project_filter = project_filter
    active_mode = mode
    ui_mode_active = ui

    log_tagged(logger_init, "RUN_MONITOR", MAGENTA, f"run_monitor: project={project_filter}, mode={mode}, ui={ui}")

    session_count = initialize_file_positions()
    print_session_status(session_count, project_filter, mode)

    if ui and mode == 'subagent':
        log_tagged(logger_init, "UI_MODE", CYAN, "Starting UI mode")
        run_ui_loop()
    else:
        log_tagged(logger_init, "STREAM_MODE", CYAN, "Starting streaming mode")
        run_streaming_loop()

# FUNCTIONS

# Initialize file positions for all existing sessions
def initialize_file_positions() -> int:
    global file_positions, active_project_filter

    sessions = find_active_sessions(active_project_filter)
    log_tagged(logger_init, "INIT_SESS", BLUE, f"Initializing {len(sessions)} sessions: {[s.name for s in sessions]}")

    for session_file in sessions:
        if session_file not in file_positions:
            pos = get_file_end_position(session_file)
            file_positions[session_file] = pos
            log_tagged(logger_init, "FILE_POS_INIT", BLUE, f"Initialized {session_file.name} at position {pos}")

    return len(sessions)

# Monitor all active sessions for new tool calls
def monitor_sessions() -> None:
    global active_project_filter, active_mode, _last_monitored_count
    sessions = find_active_sessions(active_project_filter)

    if _last_monitored_count != len(sessions):
        log_tagged(logger_routing, "MON_SESS", BLUE, f"Sessions changed: {len(sessions)} (was {_last_monitored_count})")
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
    global file_positions, tool_use_caches, call_counter, agent_to_task, agent_to_type, buffered_subagent_calls, task_requests_seen

    if filepath not in tool_use_caches:
        tool_use_caches[filepath] = {}

    last_position = file_positions[filepath]
    cache = tool_use_caches[filepath]

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
                subagent_type = tool_call.get('input', {}).get('subagent_type', '')
                agent_to_type[spawned_agent_id] = subagent_type

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

    if task_requests > 0 or task_responses > 0 or subagent_ui_tracked > 0 or subagent_displayed > 0 or subagent_buffered > 0 or other_displayed > 0:
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

# Print session status after initialization
def print_session_status(session_count: int, project_filter: Optional[str] = None, mode: str = 'all') -> None:
    if session_count == 0:
        print(f"{YELLOW}No sessions found.{RESET}")
        if project_filter:
            print(f"{YELLOW}Project {project_filter} has no active Claude Code sessions.{RESET}\n")
        else:
            print(f"{YELLOW}No sessions in ~/.claude/projects{RESET}\n")
    else:
        mode_label = ''
        if mode == 'main':
            mode_label = ' (main agent only)'
        elif mode == 'subagent':
            mode_label = ' (subagent only)'

        print(f"{GREEN}Monitoring {session_count} sessions{mode_label}{RESET}")
        if project_filter:
            print(f"{CYAN}Project: {project_filter}{RESET}")
        print(f"{CYAN}Waiting for new tool calls...{RESET}\n")

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

# Runs UI mode loop with auto-expanded subagent list
def run_ui_loop() -> None:
    global ui_loop_iteration

    setup_mouse_tracking()

    try:
        while True:
            ui_loop_iteration += 1
            if ui_loop_iteration % 10 == 0:
                log_tagged(logger_ui, "UI_ITER", WHITE, f"UI loop iteration #{ui_loop_iteration}")

            handle_pending_clicks()
            monitor_sessions()
            sync_ui_to_screen()
            time.sleep(POLL_INTERVAL)
    finally:
        restore_terminal()

# Processes any pending mouse click events
def handle_pending_clicks() -> None:
    mouse_data = read_mouse_event()
    if mouse_data:
        click = parse_sgr_mouse(mouse_data)
        if click:
            agent_id = process_click(click, line_to_agent_map)
            if agent_id:
                toggle_subagent_state(agent_id)

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
        subagent_states[agent_id] = False
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
    global subagent_metadata, tool_calls_by_agent, last_rendered_output, _last_agent_count, _last_expanded_count

    agent_count = len(subagent_metadata)
    expanded_count = sum(1 for agent_id in subagent_states if subagent_states.get(agent_id, False))

    formatted_output = render_subagent_list(subagent_metadata, tool_calls_by_agent)

    if formatted_output != last_rendered_output:
        log_tagged(logger_ui, "UI_SYNC", PURPLE, f"sync_ui_to_screen: agents={agent_count}, expanded={expanded_count}")
        log_tagged(logger_ui, "UI_RENDER", PURPLE, f"Re-rendering UI: {len(formatted_output)} chars, agents={agent_count}, expanded={expanded_count}")
        print("\033[2J\033[H", end='')
        print(formatted_output)
        last_rendered_output = formatted_output
        _last_agent_count = agent_count
        _last_expanded_count = expanded_count

# Extracts subagent type from agent_to_type mapping
def extract_subagent_type(tool_call: dict) -> str:
    agent_id = tool_call.get('agent_id', '')
    return agent_to_type.get(agent_id, '')

# Format WARNING header with yellow color for malformed lines
def format_warning(file_path: str, line_number: int, error_message: str, raw_line: str) -> str:
    now = datetime.now().strftime('%H:%M:%S')
    header = f"{YELLOW}[{now}] [!] WARNING - Malformed JSON{RESET}"

    truncated_line = truncate_line(raw_line, 200)

    details = [
        f"{INDENT}File: {file_path}",
        f"{INDENT}Line: {line_number}",
        f"{INDENT}Error: {error_message}",
        f"{INDENT}Content: {truncated_line}"
    ]

    return f"{header}\n" + '\n'.join(details)

# Truncate line to max length for display
def truncate_line(line: str, max_length: int) -> str:
    if len(line) <= max_length:
        return line
    return line[:max_length] + '...'
