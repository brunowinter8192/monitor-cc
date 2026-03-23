# INFRASTRUCTURE
from datetime import datetime
import logging
import os
import time
from pathlib import Path
from typing import Dict, Set, List, Optional

# From utils.py: Logging utility
from .utils import log_tagged
# From constants.py: Colors, config, shared constants
from .constants import RESET, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, PURPLE, POLL_INTERVAL, TOOL_TASK, MODE_ALL, MODE_MAIN, MODE_SUBAGENT, MODE_RULES, MODE_WARNINGS, MODE_HOOKS, MODE_TOKENS, HOOK_INSTRUCTIONS_LOADED
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

# From session_finder.py: Discover active Claude Code sessions
from .session_finder import find_active_sessions
# From jsonl_parser.py: Parse JSONL and extract tool calls
from .jsonl_parser import parse_new_tool_calls
# From formatter.py: Format tool calls for display
from .formatter import format_tool_call, format_user_prompt, format_user_media, format_thinking, format_skill_activation, format_unknown_type_warning, format_hook_event, format_pane_header, format_token_profile
# From hook_parser.py: Parse hook log entries
from .hook_parser import parse_new_hook_entries, filter_by_project, get_current_position as get_hook_log_position
# From subagent_ui.py: Subagent state management
from .subagent_ui import subagent_states
# From ui_mode.py: UI mode loop and subagent tracking
from .ui_mode import run_ui_loop, track_subagent_metadata

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
active_rules: Dict[str, set] = {'project': set(), 'global': set()}
warned_unknown_types: Set[str] = set()
unknown_type_counts: Dict[str, int] = {}
token_profile: Dict[str, int] = {'thinking': 0, 'tool_use': 0, 'text': 0, 'total': 0, 'turns': 0}
token_profile_tools: Dict[str, int] = {}
token_profile_request_ids: Set[str] = set()

# ORCHESTRATOR
def run_monitor(project_filter: Optional[str] = None, mode: str = MODE_ALL, ui: bool = False) -> None:
    global active_project_filter, active_mode, ui_mode_active, hook_log_position
    active_project_filter = project_filter
    active_mode = mode
    ui_mode_active = ui

    log_tagged(logger_init, "RUN_MONITOR", MAGENTA, f"run_monitor: project={project_filter}, mode={mode}, ui={ui}")

    initialize_file_positions()

    if mode == MODE_TOKENS:
        log_tagged(logger_init, "TOKENS_MODE", CYAN, "Starting tokens mode")
        run_tokens_loop()
    elif mode == MODE_RULES:
        log_tagged(logger_init, "RULES_MODE", CYAN, "Starting rules mode")
        run_rules_loop()
    elif mode == MODE_WARNINGS:
        log_tagged(logger_init, "WARNINGS_MODE", CYAN, "Starting warnings mode")
        run_warnings_loop()
    elif mode == MODE_HOOKS:
        log_tagged(logger_init, "HOOKS_MODE", CYAN, "Starting hooks mode")
        run_hooks_loop()
    elif ui and mode == MODE_SUBAGENT:
        log_tagged(logger_init, "UI_MODE", CYAN, "Starting UI mode")
        session_count = len(find_active_sessions(active_project_filter))
        print_session_status(session_count, project_filter, mode)
        run_ui_loop(subagent_metadata, tool_calls_by_agent, agent_to_task, agent_to_type, monitor_sessions, active_rules)
    else:
        log_tagged(logger_init, "STREAM_MODE", CYAN, "Starting streaming mode")
        session_count = len(find_active_sessions(active_project_filter))
        print_session_status(session_count, project_filter, mode)
        run_streaming_loop()

# FUNCTIONS

# Initialize file positions for all existing sessions
def initialize_file_positions() -> int:
    global file_positions, active_project_filter, hook_log_position

    sessions = find_active_sessions(active_project_filter)
    log_tagged(logger_init, "INIT_SESS", BLUE, f"Initializing {len(sessions)} sessions: {[s.name for s in sessions]}")

    for session_file in sessions:
        if session_file not in file_positions:
            pos = get_file_end_position(session_file)
            file_positions[session_file] = pos
            log_tagged(logger_init, "FILE_POS_INIT", BLUE, f"Initialized {session_file.name} at position {pos}")

    hook_log_position = initialize_hook_log_position()

    return len(sessions)

# Initialize hook log position at EOF to skip historical entries
def initialize_hook_log_position() -> int:
    pos = get_hook_log_position()
    log_tagged(logger_init, "HOOK_POS_INIT", BLUE, f"Hook log initialized at position {pos}")
    return pos

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
    global file_positions, tool_use_caches, call_counter

    if filepath not in tool_use_caches:
        tool_use_caches[filepath] = {}

    last_position = file_positions[filepath]
    cache = tool_use_caches[filepath]

    tool_calls, new_position, malformed_warnings, user_media, thinking_blocks, user_prompts, skill_activations, unknown_types, usage_data = parse_new_tool_calls(filepath, last_position, cache)

    for ut in unknown_types:
        track_unknown_type(ut)

    for ud in usage_data:
        accumulate_tokens(ud)

    file_positions[filepath] = new_position

    if active_mode in (MODE_WARNINGS, MODE_TOKENS):
        return

    for warning in malformed_warnings:
        display_warning(warning)

    for prompt_item in user_prompts:
        display_user_prompt_from_jsonl(prompt_item)

    for skill_item in skill_activations:
        display_skill_activation(skill_item)

    for media_item in user_media:
        display_user_media(media_item)

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

# Display formatted user media to console
def display_user_media(media_item: dict) -> None:
    formatted = format_user_media(media_item)
    print(formatted)
    print()

# Display formatted skill/command activation to console
def display_skill_activation(skill_item: dict) -> None:
    formatted = format_skill_activation(skill_item)
    print(formatted)
    print()

# Display formatted thinking block to console
def display_thinking(thinking_item: dict) -> None:
    formatted = format_thinking(thinking_item)
    print(formatted)
    print()

# Display formatted tool call to console
def display_tool_call(tool_call: dict, call_number: int) -> None:
    tool_name = tool_call['tool_name']

    formatted = format_tool_call(
        tool_name=tool_name,
        input_data=tool_call['input'],
        output_data=tool_call['output'] or '',
        tool_use_id=tool_call['tool_use_id'],
        timestamp=tool_call['timestamp'],
        call_number=call_number,
        is_subagent=tool_call.get('is_subagent', False),
        system_reminders=tool_call.get('system_reminders', []),
        is_error=tool_call.get('is_error', False)
    )

    print(formatted)
    print()

# Print session status after initialization
def print_session_status(session_count: int, project_filter: Optional[str] = None, mode: str = MODE_ALL) -> None:
    if session_count == 0:
        print(f"{YELLOW}No sessions found.{RESET}")
        if project_filter:
            print(f"{YELLOW}Project {project_filter} has no active Claude Code sessions.{RESET}\n")
        else:
            print(f"{YELLOW}No sessions in ~/.claude/projects{RESET}\n")
    else:
        mode_label = ''
        if mode == MODE_MAIN:
            mode_label = ' (main agent only)'
        elif mode == MODE_SUBAGENT:
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

# Runs continuous streaming monitor loop
def run_streaming_loop() -> None:
    print(format_pane_header('main'))
    while True:
        process_hook_log()
        monitor_sessions()
        time.sleep(POLL_INTERVAL)

# Track unknown JSONL message type for warnings pane
def track_unknown_type(unknown_entry: dict) -> None:
    global warned_unknown_types, unknown_type_counts
    msg_type = unknown_entry.get('type', '')
    if not msg_type:
        return
    count = unknown_entry.get('count', 1)
    unknown_type_counts[msg_type] = unknown_type_counts.get(msg_type, 0) + count

# Runs warnings-only display loop (for dedicated warnings tmux pane)
def run_warnings_loop() -> None:
    header = format_pane_header('warnings')
    last_output = None
    while True:
        monitor_sessions()
        output = format_warnings_block()
        if output != last_output:
            print("\033[2J\033[3J\033[H", end='', flush=True)
            print(header)
            if output:
                print(output)
            last_output = output
        time.sleep(POLL_INTERVAL)

# Format warnings block for dedicated pane
def format_warnings_block() -> str:
    if not unknown_type_counts:
        return ''
    header = f"{YELLOW}FORMAT WARNINGS ({len(unknown_type_counts)} unknown types){RESET}"
    lines = [header]
    for msg_type, count in sorted(unknown_type_counts.items(), key=lambda x: x[1], reverse=True):
        warning = format_unknown_type_warning(msg_type, count)
        lines.append(warning)
    return '\n'.join(lines)

# Accumulate token usage from a single usage entry into session profile
def accumulate_tokens(usage_entry: dict) -> None:
    global token_profile, token_profile_tools, token_profile_request_ids

    request_id = usage_entry.get('request_id', '')
    output_tokens = usage_entry.get('output_tokens', 0)
    block_type = usage_entry.get('type', 'text')
    tool_name = usage_entry.get('tool_name')

    token_profile[block_type] = token_profile.get(block_type, 0) + output_tokens
    token_profile['total'] = token_profile.get('total', 0) + output_tokens

    if request_id and request_id not in token_profile_request_ids:
        token_profile_request_ids.add(request_id)
        token_profile['turns'] = len(token_profile_request_ids)

    if block_type == 'tool_use' and tool_name:
        token_profile_tools[tool_name] = token_profile_tools.get(tool_name, 0) + output_tokens

# Runs token profiling display loop (for dedicated tokens tmux pane)
def run_tokens_loop() -> None:
    header = format_pane_header('tokens')
    last_output = None
    while True:
        monitor_sessions()
        output = format_tokens_block()
        if output != last_output:
            print("\033[2J\033[3J\033[H", end='', flush=True)
            print(header)
            if output:
                print(output)
            last_output = output
        time.sleep(POLL_INTERVAL)

# Format token profile block for dedicated pane
def format_tokens_block() -> str:
    total = token_profile.get('total', 0)
    if total == 0:
        return ''

    turns = token_profile.get('turns', 0)
    profile = {
        'total': total,
        'turns': turns,
        'thinking': token_profile.get('thinking', 0),
        'tool_use': token_profile.get('tool_use', 0),
        'text': token_profile.get('text', 0),
        'tools': dict(sorted(token_profile_tools.items(), key=lambda x: x[1], reverse=True)),
    }

    return format_token_profile(profile)

# Runs hooks display loop (for dedicated hooks tmux pane)
def run_hooks_loop() -> None:
    print(format_pane_header('hooks'))
    while True:
        process_hook_log_for_display()
        time.sleep(POLL_INTERVAL)

# Process hook log and display hooks with output immediately
def process_hook_log_for_display() -> None:
    global hook_log_position

    entries, hook_log_position = parse_new_hook_entries(hook_log_position)
    filtered = filter_by_project(entries, active_project_filter) if active_project_filter else entries

    for entry in filtered:
        output = entry.get('output', '')
        if not output:
            continue
        formatted = format_hook_event(
            timestamp=entry.get('timestamp', ''),
            hook_event=entry.get('hook_event', ''),
            hook_script=entry.get('hook_script', ''),
            output=output
        )
        print(formatted)
        print()

# Runs rules-only display loop (for dedicated rules tmux pane)
def run_rules_loop() -> None:
    from .ui_mode import format_rules_block
    header = format_pane_header('rules')
    last_output = None
    while True:
        process_hook_log()
        output = format_rules_block(active_rules)
        if output != last_output:
            print("\033[2J\033[3J\033[H", end='', flush=True)
            print(header)
            if output:
                print(output)
            last_output = output
        time.sleep(POLL_INTERVAL)

# Process hook log for InstructionsLoaded entries (rules pane routing)
def process_hook_log() -> None:
    global hook_log_position, active_project_filter

    entries, hook_log_position = parse_new_hook_entries(hook_log_position)
    filtered = filter_by_project(entries, active_project_filter) if active_project_filter else entries

    for entry in filtered:
        if entry.get('hook_event') == HOOK_INSTRUCTIONS_LOADED:
            output = entry.get('output', '')
            if output.startswith('[P]'):
                active_rules['project'].add(output[4:])
            elif output.startswith('[G]'):
                active_rules['global'].add(output[4:])

# Display USER PROMPT detected from session JSONL
def display_user_prompt_from_jsonl(prompt_item: dict) -> None:
    formatted = format_user_prompt(prompt_item.get('timestamp', ''))
    print(formatted)
    print()
    log_tagged(logger_routing, "USER_PROMPT", PURPLE, f"Displayed USER PROMPT from JSONL")

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
