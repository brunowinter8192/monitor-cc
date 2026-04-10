# INFRASTRUCTURE
from datetime import datetime, timedelta
import time
from pathlib import Path
from typing import Dict, Set, List, Optional

# From constants.py: Colors, config, shared constants
from .constants import RESET, CYAN, POLL_INTERVAL, MODE_ALL, MODE_MAIN, MODE_SUBAGENT, MODE_RULES, MODE_WARNINGS, MODE_HOOKS, MODE_TOKENS, MODE_WORKERS, MODE_PROXY, MODE_METADATA, MODE_WORKER_PROXY, MODE_WORKER_METADATA, TOOL_TASK

# From session_finder.py: Discover active Claude Code sessions
from .session_finder import find_active_sessions
# From jsonl_parser.py: Parse JSONL and extract tool calls
from .jsonl_parser import parse_new_tool_calls, parse_jsonl_lines, read_new_lines
# From hook_parser.py: Parse hook log entries
from .hook_parser import get_current_position as get_hook_log_position
# From ui_mode.py: Subagent tracking and rules formatting
from .ui_mode import track_subagent_metadata
# From warnings_pane.py: Unknown type tracking
from .warnings_pane import track_unknown_type
# From monitor_display.py: Console output for tool calls and session status
from .monitor_display import display_warning, display_user_media, display_skill_activation, display_thinking, display_tool_call, display_user_prompt_from_jsonl, display_system_message, print_session_status

file_positions: Dict[Path, int] = {}
tool_use_caches: Dict[Path, dict] = {}
call_counter = 0
agent_to_task: Dict[str, str] = {}
agent_to_type: Dict[str, str] = {}
buffered_subagent_calls: Dict[str, List[dict]] = {}
task_requests_seen: Set[str] = set()
active_project_filter: Optional[str] = None
active_mode: str = MODE_ALL
ui_mode_active: bool = False
subagent_metadata: Dict[str, dict] = {}
tool_calls_by_agent: Dict[str, List[dict]] = {}
_last_monitored_count: Optional[int] = None
hook_log_position: int = 0

# ORCHESTRATOR
def run_monitor(project_filter: Optional[str] = None, mode: str = MODE_ALL, ui: bool = False) -> None:
    global active_project_filter, active_mode, ui_mode_active, hook_log_position
    active_project_filter = project_filter
    active_mode = mode
    ui_mode_active = ui

    initialize_file_positions()

    if mode == MODE_WORKERS:
        from .worker_pane import run_workers_loop
        run_workers_loop()
    elif mode == MODE_TOKENS:
        from .token_pane import run_tokens_loop
        run_tokens_loop()
    elif mode == MODE_RULES:
        from .rules_pane import run_rules_loop
        run_rules_loop()
    elif mode == MODE_WARNINGS:
        from .warnings_pane import run_warnings_loop
        run_warnings_loop()
    elif mode == MODE_HOOKS:
        from .hooks_pane import run_hooks_loop
        run_hooks_loop()
    elif mode == MODE_PROXY:
        from .proxy_display import run_proxy_loop
        run_proxy_loop()
    elif mode == MODE_METADATA:
        from .metadata_pane import run_metadata_loop
        run_metadata_loop()
    elif mode == MODE_WORKER_PROXY:
        from .proxy_display import run_worker_proxy_loop
        run_worker_proxy_loop()
    elif mode == MODE_WORKER_METADATA:
        from .metadata_pane import run_worker_metadata_loop
        run_worker_metadata_loop()
    else:
        sessions = find_active_sessions(active_project_filter)
        session_count = len(filter_sessions_by_mode(sessions, mode))
        print_session_status(session_count, project_filter, mode)
        run_streaming_loop()

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

# Process single session file for new tool calls and warnings
def process_session_file(filepath: Path) -> None:
    global file_positions, tool_use_caches, call_counter

    if filepath not in tool_use_caches:
        tool_use_caches[filepath] = {}

    last_position = file_positions[filepath]
    cache = tool_use_caches[filepath]

    tool_calls, new_position, malformed_warnings, user_media, thinking_blocks, user_prompts, skill_activations, unknown_types, _, system_messages = parse_new_tool_calls(filepath, last_position, cache)

    for ut in unknown_types:
        track_unknown_type(ut)

    file_positions[filepath] = new_position

    if active_mode in (MODE_WARNINGS, MODE_TOKENS):
        return

    for warning in malformed_warnings:
        display_warning(warning)

    for prompt_item in user_prompts:
        display_user_prompt_from_jsonl(prompt_item)

    for sys_msg in system_messages:
        display_system_message(sys_msg)

    for skill_item in skill_activations:
        display_skill_activation(skill_item)

    media_groups: dict = {}
    for media_item in user_media:
        ts = media_item.get('timestamp', '')
        media_groups.setdefault(ts, []).append(media_item)
    for ts_group in media_groups.values():
        display_user_media(ts_group)

    for thinking_item in thinking_blocks:
        display_thinking(thinking_item)

    task_requests = 0
    task_responses = 0
    subagent_ui_tracked = 0
    subagent_displayed = 0
    subagent_buffered = 0
    other_displayed = 0

    for tool_call in tool_calls:
        if is_task_request(tool_call):
            task_requests += handle_task_request(tool_call)
        elif is_task_response(tool_call):
            task_responses += handle_task_response(tool_call)
        elif is_subagent_call(tool_call):
            ui, disp, buff = handle_subagent_call(tool_call, filepath)
            subagent_ui_tracked += ui
            subagent_displayed += disp
            subagent_buffered += buff
        else:
            other_displayed += 1
            call_counter += 1
            display_tool_call(tool_call, call_counter)


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
    if mode in (MODE_ALL, MODE_WARNINGS, MODE_TOKENS):
        filtered = sessions
    elif mode == MODE_MAIN:
        filtered = [s for s in sessions if not is_agent_file(s)]
    elif mode == MODE_SUBAGENT:
        filtered = [s for s in sessions if is_agent_file(s)]
    else:
        filtered = sessions

    return filtered

# Check if tool call is a Task REQUEST
def is_task_request(tool_call: dict) -> bool:
    return tool_call.get('tool_name') == TOOL_TASK and tool_call.get('output') is None

# Check if tool call is a Task RESPONSE
def is_task_response(tool_call: dict) -> bool:
    return tool_call.get('tool_name') == TOOL_TASK and tool_call.get('output') is not None

# Check if tool call is from a Subagent
def is_subagent_call(tool_call: dict) -> bool:
    return tool_call.get('is_subagent', False)

# Handle Task tool REQUEST (no output yet)
def handle_task_request(tool_call: dict) -> int:
    global call_counter, task_requests_seen
    call_counter += 1
    task_requests_seen.add(tool_call['tool_use_id'])
    display_tool_call(tool_call, call_counter)
    return 1

# Handle Task tool RESPONSE (has output, may spawn agent)
def handle_task_response(tool_call: dict) -> int:
    global call_counter, agent_to_task, agent_to_type, buffered_subagent_calls

    spawned_agent_id = tool_call.get('spawned_agent_id')
    if spawned_agent_id:
        agent_to_task[spawned_agent_id] = tool_call['tool_use_id']
        subagent_type = tool_call.get('input', {}).get('subagent_type', '')
        agent_to_type[spawned_agent_id] = subagent_type

        if spawned_agent_id in buffered_subagent_calls:
            if not ui_mode_active:
                for buffered_call in buffered_subagent_calls[spawned_agent_id]:
                    call_counter += 1
                    display_tool_call(buffered_call, call_counter)
            del buffered_subagent_calls[spawned_agent_id]

    call_counter += 1
    display_tool_call(tool_call, call_counter)
    return 1

# Handle tool call from subagent
def handle_subagent_call(tool_call: dict, filepath: Path) -> tuple:
    global call_counter, buffered_subagent_calls

    agent_id = tool_call.get('agent_id')
    ui_tracked = 0
    displayed = 0
    buffered = 0

    if active_mode == MODE_MAIN:
        return ui_tracked, displayed, buffered

    if ui_mode_active:
        ui_tracked = 1
        call_counter += 1
        tool_call['call_number'] = call_counter
        track_subagent_metadata(tool_call, filepath, subagent_metadata, tool_calls_by_agent, agent_to_task, agent_to_type)
    elif active_mode == MODE_SUBAGENT:
        displayed = 1
        call_counter += 1
        display_tool_call(tool_call, call_counter)
    elif agent_id and agent_id in agent_to_task:
        displayed = 1
        call_counter += 1
        display_tool_call(tool_call, call_counter)
    elif agent_id:
        buffered = 1
        if agent_id not in buffered_subagent_calls:
            buffered_subagent_calls[agent_id] = []
        buffered_subagent_calls[agent_id].append(tool_call)

    return ui_tracked, displayed, buffered

# Load historical data from newest main session for initial display
def load_historical_main() -> None:
    global file_positions, tool_use_caches
    main_sessions = get_main_session_files()
    if main_sessions:
        filepath = main_sessions[0]
        file_positions[filepath] = 0
        tool_use_caches[filepath] = {}

# Load historical data from newest main session + its agent files for subagents pane
def load_historical_subagents() -> None:
    global file_positions, tool_use_caches
    main_sessions = get_main_session_files()
    if not main_sessions:
        return
    filepath = main_sessions[0]
    file_positions[filepath] = 0
    tool_use_caches[filepath] = {}
    subagents_dir = filepath.parent / filepath.stem / 'subagents'
    if subagents_dir.exists():
        for agent_file in subagents_dir.glob('agent-*.jsonl'):
            file_positions[agent_file] = 0
            tool_use_caches[agent_file] = {}

# Runs continuous streaming monitor loop
def run_streaming_loop() -> None:
    from .rules_pane import process_hook_log
    load_historical_main()
    current_main_session = _get_newest_main_session()
    while True:
        process_hook_log()
        newest = _get_newest_main_session()
        if newest != current_main_session and newest is not None:
            current_main_session = newest
            file_positions[newest] = 0
            tool_use_caches[newest] = {}
            print("\033[2J\033[3J\033[H", end='', flush=True)
            print(f"{CYAN}--- New session detected ---{RESET}\n")
        monitor_sessions()
        time.sleep(POLL_INTERVAL)

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

