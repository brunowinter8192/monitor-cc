# INFRASTRUCTURE
from datetime import datetime
import io
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Set, List, Optional

# From constants.py: Colors, config, shared constants
from .constants import RESET, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, PURPLE, HOVER_BG, POLL_INTERVAL, INPUT_POLL_INTERVAL, TOOL_TASK, MODE_ALL, MODE_MAIN, MODE_SUBAGENT, MODE_RULES, MODE_WARNINGS, MODE_HOOKS, MODE_TOKENS, MODE_WORKERS, MODE_SUBAGENTS, HOOK_INSTRUCTIONS_LOADED, DIM
INDENT = '  '

# From session_finder.py: Discover active Claude Code sessions
from .session_finder import find_active_sessions, encode_project_path
# From jsonl_parser.py: Parse JSONL and extract tool calls
from .jsonl_parser import parse_new_tool_calls, parse_jsonl_lines, read_new_lines, get_message_content, is_tool_use, extract_cache_turns
# From formatter.py: Format tool calls for display
from .formatter import format_tool_call, format_user_prompt, format_user_media, format_thinking, format_skill_activation, format_unknown_type_warning, format_hook_event, format_cache_tracker, format_workers_block
# From hook_parser.py: Parse hook log entries
from .hook_parser import parse_new_hook_entries, filter_by_project, get_current_position as get_hook_log_position
# From subagent_ui.py: Subagent state management and rendering
from .subagent_ui import subagent_states, toggle_subagent_state, build_collapsed_entry
# From click_handler.py: Keyboard input for token and workers panes
from .click_handler import read_keypress, parse_digit_key, setup_keyboard_input, restore_terminal, enable_mouse, disable_mouse, read_mouse_event, get_agent_by_index
# From ui_mode.py: Subagent tracking and rules formatting
from .ui_mode import track_subagent_metadata

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
rules_invokers: Dict[str, Dict[str, str]] = {}
rules_expand_states: Dict[str, bool] = {}
rules_line_map: Dict[int, str] = {}
rules_hover_row: Optional[int] = None
rules_scroll_offset: int = 0
rules_total_lines: int = 0
warned_unknown_types: Set[str] = set()
unknown_type_counts: Dict[str, int] = {}
cache_expand_states: Dict[tuple, bool] = {}
cache_line_map: Dict[int, tuple] = {}
cache_hover_row: Optional[int] = None
cache_scroll_offset: int = 0
worker_expand_states: Dict[str, bool] = {}
worker_scroll_offsets: Dict[str, int] = {}
worker_line_map: Dict[int, str] = {}
hover_row: Optional[int] = None
agent_turns: Dict[str, list] = {}
agent_pane_line_map: Dict[int, str] = {}
agent_pane_hover_row: Optional[int] = None
agent_cache_scroll_offsets: Dict[str, int] = {}
worker_cache_expand_states: Dict[str, Dict[tuple, bool]] = {}
worker_cache_line_map: Dict[int, tuple] = {}
agent_cache_expand_states: Dict[str, Dict[tuple, bool]] = {}
agent_cache_line_map: Dict[int, tuple] = {}

# ORCHESTRATOR
def run_monitor(project_filter: Optional[str] = None, mode: str = MODE_ALL, ui: bool = False) -> None:
    global active_project_filter, active_mode, ui_mode_active, hook_log_position
    active_project_filter = project_filter
    active_mode = mode
    ui_mode_active = ui

    initialize_file_positions()

    if mode == MODE_WORKERS:
        run_workers_loop()
    elif mode == MODE_SUBAGENTS:
        run_subagents_loop()
    elif mode == MODE_TOKENS:
        run_tokens_loop()
    elif mode == MODE_RULES:
        run_rules_loop()
    elif mode == MODE_WARNINGS:
        run_warnings_loop()
    elif mode == MODE_HOOKS:
        run_hooks_loop()
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

    tool_calls, new_position, malformed_warnings, user_media, thinking_blocks, user_prompts, skill_activations, unknown_types, _ = parse_new_tool_calls(filepath, last_position, cache)

    for ut in unknown_types:
        track_unknown_type(ut)

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

# Track unknown JSONL message type for warnings pane
def track_unknown_type(unknown_entry: dict) -> None:
    global warned_unknown_types, unknown_type_counts
    msg_type = unknown_entry.get('type', '')
    if not msg_type:
        return
    count = unknown_entry.get('count', 1)
    unknown_type_counts[msg_type] = unknown_type_counts.get(msg_type, 0) + count

# Load historical warnings from newest main session
def load_historical_warnings() -> None:
    global file_positions, tool_use_caches
    main_sessions = get_main_session_files()
    if main_sessions:
        filepath = main_sessions[0]
        file_positions[filepath] = 0
        tool_use_caches[filepath] = {}

# Runs warnings-only display loop (for dedicated warnings tmux pane)
def run_warnings_loop() -> None:
    load_historical_warnings()
    last_output = None
    while True:
        monitor_sessions()
        output = format_warnings_block()
        if output != last_output:
            print("\033[2J\033[3J\033[H", end='', flush=True)
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

# Return main session files (non-agent) sorted by recency
def get_main_session_files() -> List[Path]:
    sessions = find_active_sessions(active_project_filter)
    return [s for s in sessions if not is_agent_file(s)]

# Build cache turns from the most recent main session JSONL
def build_cache_turns() -> list:
    main_sessions = get_main_session_files()
    if not main_sessions:
        return []
    filepath = main_sessions[0]
    lines = read_new_lines(filepath, 0)
    messages, _ = parse_jsonl_lines(lines)
    return extract_cache_turns(messages)

# Runs cache tracker display loop (for dedicated tokens tmux pane)
def run_tokens_loop() -> None:
    global cache_expand_states, cache_line_map, cache_hover_row, cache_scroll_offset
    last_output = None
    turns = []
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
                        if button == 0:
                            key = cache_line_map.get(row)
                            if key:
                                cache_expand_states[key] = not cache_expand_states.get(key, False)
                                input_changed = True
                        elif button == 64:
                            cache_scroll_offset += 3
                            input_changed = True
                        elif button == 65:
                            cache_scroll_offset = max(0, cache_scroll_offset - 3)
                            input_changed = True
                        elif button >= 32:
                            cache_hover_row = row
                            input_changed = True

            now = time.time()
            if now - last_data_refresh >= POLL_INTERVAL:
                turns = build_cache_turns()
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
                output = format_cache_tracker(turns, cache_expand_states, cache_line_map, cache_hover_row, pane_height, pane_width, cache_scroll_offset)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# Derive worker project name from project path (worktree-aware, matches tmux_spawn.sh logic)
def get_worker_project_name(project_path: str) -> str:
    if '/.claude/worktrees/' in project_path:
        base = project_path.split('/.claude/worktrees/')[0]
        return os.path.basename(base)
    return os.path.basename(os.path.normpath(project_path))

# Read a single env var from a tmux session
def get_tmux_env(session: str, var: str) -> str:
    result = subprocess.run(
        ["tmux", "show-environment", "-t", session, var],
        capture_output=True, text=True
    )
    if result.returncode == 0 and '=' in result.stdout:
        return result.stdout.strip().split('=', 1)[1]
    return ''

# Detect worker status: working, idle, exited, or unknown
def detect_worker_status(session: str) -> str:
    dead = subprocess.run(
        ["tmux", "display-message", "-t", f"{session}:^", "-p", "#{pane_dead}"],
        capture_output=True, text=True
    ).stdout.strip()

    if dead == "1":
        return "exited"
    if dead != "0":
        return "unknown"

    now = int(time.time())
    last_activity = subprocess.run(
        ["tmux", "list-panes", "-t", session, "-F", "#{window_activity}"],
        capture_output=True, text=True
    ).stdout.strip().split('\n')[0]
    delta = now - int(last_activity or "0")

    if delta > 10:
        return "idle"
    return "working"

# List all workers for the current project
def list_workers(project_path: str) -> List[dict]:
    project = get_worker_project_name(project_path)
    prefix = f"worker-{project}-"

    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return []

    sessions = [s for s in result.stdout.strip().split('\n') if s.startswith(prefix)]
    workers = []
    for session in sessions:
        if not session:
            continue
        name = session[len(prefix):]
        workers.append({
            'name': name,
            'session': session,
            'status': detect_worker_status(session),
            'spawned': get_tmux_env(session, 'WORKER_SPAWNED'),
            'purpose': get_tmux_env(session, 'WORKER_PURPOSE'),
            'model': get_tmux_env(session, 'WORKER_MODEL') or 'sonnet',
        })
    return workers

# Find the most recent JSONL file for a worker's Claude Code session
def find_worker_jsonl(session_name: str) -> Optional[Path]:
    result = subprocess.run(
        ["tmux", "display-message", "-t", f"{session_name}:^", "-p", "#{pane_current_path}"],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None

    working_dir = result.stdout.strip()
    encoded = encode_project_path(working_dir)
    project_dir = Path.home() / '.claude' / 'projects' / encoded

    if not project_dir.exists():
        return None

    jsonl_files = [f for f in project_dir.glob('*.jsonl') if not f.name.startswith('agent-')]
    if not jsonl_files:
        return None

    return max(jsonl_files, key=lambda f: f.stat().st_mtime)

# Extract all tool_use entries from a worker's JSONL file
def extract_worker_tokens(jsonl_path: Path) -> dict:
    lines = read_new_lines(jsonl_path, 0)
    messages, _ = parse_jsonl_lines(lines)
    total_input = 0
    total_output = 0
    for message in messages:
        if message.get('type') != 'assistant':
            continue
        usage = message.get('message', {}).get('usage', {})
        total_input += usage.get('input_tokens', 0) + usage.get('cache_creation_input_tokens', 0) + usage.get('cache_read_input_tokens', 0)
        total_output += usage.get('output_tokens', 0)
    return {'input': total_input, 'output': total_output}

def extract_worker_tool_calls(jsonl_path: Path) -> List[dict]:
    lines = read_new_lines(jsonl_path, 0)
    messages, _ = parse_jsonl_lines(lines)
    calls = []
    call_number = 0
    for message in messages:
        content_blocks = get_message_content(message)
        timestamp = message.get('timestamp', '')
        for block in content_blocks:
            if is_tool_use(block):
                call_number += 1
                calls.append({
                    'tool_name': block.get('name', 'Unknown'),
                    'input': block.get('input', {}),
                    'timestamp': timestamp,
                    'call_number': call_number,
                })
    return calls

# Runs workers display loop (for dedicated workers tmux pane)
def run_workers_loop() -> None:
    global worker_expand_states, worker_scroll_offsets, worker_line_map, hover_row, ui_mode_active, worker_cache_expand_states, worker_cache_line_map
    ui_mode_active = True
    last_output = None
    workers = []
    worker_turns: Dict[str, list] = {}
    last_data_refresh = 0.0
    frozen = False
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
                        if button == 0:
                            cache_key = worker_cache_line_map.get(row)
                            if cache_key:
                                w_name, t_idx, c_idx = cache_key
                                states = worker_cache_expand_states.setdefault(w_name, {})
                                states[(t_idx, c_idx)] = not states.get((t_idx, c_idx), False)
                                input_changed = True
                            else:
                                name = worker_line_map.get(row)
                                if name:
                                    is_now_expanded = not worker_expand_states.get(name, False)
                                    worker_expand_states[name] = is_now_expanded
                                    if is_now_expanded:
                                        worker_scroll_offsets[name] = 0
                                    input_changed = True
                        elif button == 64:
                            name = worker_line_map.get(row)
                            if name:
                                worker_scroll_offsets[name] = worker_scroll_offsets.get(name, 0) + 3
                                input_changed = True
                        elif button == 65:
                            name = worker_line_map.get(row)
                            if name:
                                worker_scroll_offsets[name] = max(0, worker_scroll_offsets.get(name, 0) - 3)
                                input_changed = True
                        elif button >= 32:
                            hover_row = row
                            input_changed = True
                else:
                    if char == 'f':
                        frozen = not frozen
                        input_changed = True
                    else:
                        idx = parse_digit_key(char)
                        if idx is not None:
                            if 1 <= idx <= len(workers):
                                name = workers[idx - 1]['name']
                                is_now_expanded = not worker_expand_states.get(name, False)
                                worker_expand_states[name] = is_now_expanded
                                if is_now_expanded:
                                    worker_scroll_offsets[name] = 0
                                input_changed = True

            now = time.time()
            if not frozen and now - last_data_refresh >= POLL_INTERVAL:
                workers = list_workers(active_project_filter) if active_project_filter else []
                worker_turns = {}
                for w in workers:
                    name = w.get('name', '')
                    jsonl_path = find_worker_jsonl(w.get('session', ''))
                    if jsonl_path:
                        w['tokens'] = extract_worker_tokens(jsonl_path)
                        if worker_expand_states.get(name, False):
                            lines = read_new_lines(jsonl_path, 0)
                            messages, _ = parse_jsonl_lines(lines)
                            worker_turns[name] = extract_cache_turns(messages)
                last_data_refresh = now
                input_changed = True
            elif input_changed:
                for w in workers:
                    name = w.get('name', '')
                    if worker_expand_states.get(name, False) and name not in worker_turns:
                        jsonl_path = find_worker_jsonl(w.get('session', ''))
                        if jsonl_path:
                            lines = read_new_lines(jsonl_path, 0)
                            messages, _ = parse_jsonl_lines(lines)
                            worker_turns[name] = extract_cache_turns(messages)

            output = format_workers_block(workers, worker_expand_states, worker_turns, worker_line_map, hover_row, worker_scroll_offsets, worker_cache_expand_states, worker_cache_line_map, frozen=frozen)
            if output != last_output:
                print("\033[2J\033[3J\033[H", end='', flush=True)
                if output:
                    print(output)
                last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# Find agent JSONL file by agent_id across all active sessions
def find_agent_jsonl(agent_id: str) -> Optional[Path]:
    sessions = find_active_sessions(active_project_filter)
    target_name = f'agent-{agent_id}.jsonl'
    for session_file in sessions:
        if session_file.name == target_name:
            return session_file
    return None

# Render subagent list with cache-tracker turns for expanded agents
def render_subagents_with_tokens(subagent_metadata_map, turns_by_agent, pane_line_map, pane_hover_row, pane_height, pane_width, scroll_offsets, cache_expand_states=None, cache_line_map=None, frozen: bool = False) -> str:
    agent_count = len(subagent_metadata_map)
    all_lines = []
    all_keys = []

    freeze_indicator = f" {YELLOW}[FROZEN]{RESET}" if frozen else f" {CYAN}[LIVE]{RESET}"
    header = f"{CYAN}Active Subagents ({agent_count}){RESET}{freeze_indicator}"
    all_lines.append(header)
    all_keys.append(None)
    all_lines.append('')
    all_keys.append(None)

    if not subagent_metadata_map:
        all_lines.append(f"{YELLOW}No subagents active yet{RESET}")
        all_keys.append(None)
        if pane_line_map is not None:
            pane_line_map.clear()
        return '\n'.join(all_lines)

    for idx, (agent_id, metadata) in enumerate(sorted(subagent_metadata_map.items(), key=lambda x: x[1]['timestamp']), 1):
        is_expanded = subagent_states.get(agent_id, False)
        entry_header = build_collapsed_entry(idx, metadata, is_expanded=is_expanded)
        all_lines.append(entry_header)
        all_keys.append(agent_id)

        if is_expanded:
            turns = turns_by_agent.get(agent_id, [])
            scroll_offset = scroll_offsets.get(agent_id, 0)
            if not turns:
                all_lines.append(f"  {YELLOW}(no token data yet){RESET}")
                all_keys.append(None)
            else:
                per_agent_expand = (cache_expand_states or {}).get(agent_id, {})
                if cache_line_map is not None:
                    temp_clm: dict = {}
                    cache_output = format_cache_tracker(turns, per_agent_expand, temp_clm, None, 15, pane_width - 2, scroll_offset)
                    cache_start = len(all_lines) + 1
                    for rel_row, key in temp_clm.items():
                        cache_line_map[rel_row + cache_start - 1] = (agent_id, key[0], key[1])
                else:
                    cache_output = format_cache_tracker(turns, per_agent_expand, None, None, 15, pane_width - 2, scroll_offset)
                for cl in cache_output.split('\n'):
                    all_lines.append(f"  {cl}")
                    all_keys.append(None)

        all_lines.append('')
        all_keys.append(None)

    while all_lines and all_lines[-1] == '':
        all_lines.pop()
        all_keys.pop()

    if pane_line_map is not None:
        pane_line_map.clear()
        for row_idx, key in enumerate(all_keys):
            if key is not None:
                pane_line_map[row_idx + 1] = key

    result_lines = []
    for row_offset, line in enumerate(all_lines):
        row = row_offset + 1
        key = all_keys[row_offset]
        if key is not None and pane_hover_row is not None and row == pane_hover_row:
            result_lines.append(f"{HOVER_BG}{line}{RESET}")
        else:
            result_lines.append(line)

    return '\n'.join(result_lines)

# Find the nearest agent ID at or above a given row in the pane line map
def _find_agent_at_row(row: int, line_map: dict) -> Optional[str]:
    agent_id = line_map.get(row)
    if agent_id:
        return agent_id
    for r in range(row - 1, 0, -1):
        agent_id = line_map.get(r)
        if agent_id:
            return agent_id
    return None

# Runs subagents display loop (for dedicated subagents tmux pane, shows per-agent cache token view)
def run_subagents_loop() -> None:
    global agent_turns, agent_pane_line_map, agent_pane_hover_row, agent_cache_scroll_offsets, ui_mode_active, agent_cache_expand_states, agent_cache_line_map
    ui_mode_active = True
    load_historical_subagents()
    current_main_session = _get_newest_main_session()
    last_output = None
    last_data_refresh = 0.0
    frozen = False
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
                        if button == 0:
                            cache_key = agent_cache_line_map.get(row)
                            if cache_key:
                                ag_id, t_idx, c_idx = cache_key
                                states = agent_cache_expand_states.setdefault(ag_id, {})
                                states[(t_idx, c_idx)] = not states.get((t_idx, c_idx), False)
                                input_changed = True
                            else:
                                agent_id = agent_pane_line_map.get(row)
                                if agent_id:
                                    toggle_subagent_state(agent_id)
                                    input_changed = True
                        elif button == 64:
                            agent_id = _find_agent_at_row(row, agent_pane_line_map)
                            if agent_id and subagent_states.get(agent_id, False):
                                agent_cache_scroll_offsets[agent_id] = agent_cache_scroll_offsets.get(agent_id, 0) + 3
                                input_changed = True
                        elif button == 65:
                            agent_id = _find_agent_at_row(row, agent_pane_line_map)
                            if agent_id and subagent_states.get(agent_id, False):
                                agent_cache_scroll_offsets[agent_id] = max(0, agent_cache_scroll_offsets.get(agent_id, 0) - 3)
                                input_changed = True
                        elif button >= 32:
                            agent_pane_hover_row = row
                            input_changed = True
                else:
                    if char == 'f':
                        frozen = not frozen
                        input_changed = True
                    else:
                        idx = parse_digit_key(char)
                        if idx is not None:
                            agent_id = get_agent_by_index(idx, subagent_metadata)
                            if agent_id:
                                toggle_subagent_state(agent_id)
                                input_changed = True

            now = time.time()
            if not frozen and now - last_data_refresh >= POLL_INTERVAL:
                newest = _get_newest_main_session()
                if newest != current_main_session and newest is not None:
                    current_main_session = newest
                    subagent_metadata.clear()
                    agent_turns.clear()
                    agent_cache_expand_states.clear()
                    agent_cache_line_map.clear()
                    agent_cache_scroll_offsets.clear()
                    subagent_states.clear()
                    file_positions.clear()
                    tool_use_caches.clear()
                    load_historical_subagents()
                _stdout = sys.stdout
                sys.stdout = io.StringIO()
                monitor_sessions()
                sys.stdout = _stdout
                agent_turns = {}
                for agent_id in subagent_metadata:
                    jsonl_path = find_agent_jsonl(agent_id)
                    if jsonl_path:
                        agent_lines = read_new_lines(jsonl_path, 0)
                        messages, _ = parse_jsonl_lines(agent_lines)
                        agent_turns[agent_id] = extract_cache_turns(messages)
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
                output = render_subagents_with_tokens(subagent_metadata, agent_turns, agent_pane_line_map, agent_pane_hover_row, pane_height, pane_width, agent_cache_scroll_offsets, agent_cache_expand_states, agent_cache_line_map, frozen=frozen)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# Load historical hook entries for display
def load_historical_hooks() -> None:
    global hook_log_position
    entries, new_pos = parse_new_hook_entries(0)
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
    hook_log_position = new_pos

# Runs hooks display loop (for dedicated hooks tmux pane)
def run_hooks_loop() -> None:
    load_historical_hooks()
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

# Derive source label from cwd path
def derive_rule_source(cwd: str) -> str:
    if not cwd:
        return 'unknown'
    worktree_marker = '/.claude/worktrees/'
    idx = cwd.find(worktree_marker)
    if idx >= 0:
        remainder = cwd[idx + len(worktree_marker):]
        worker_name = remainder.split('/')[0]
        return f'worker:{worker_name}'
    return 'main'

# Record a rule and its invoker from a hook entry
def record_rule_invoker(entry: dict) -> None:
    from .utils import format_timestamp
    output = entry.get('output', '')
    if not output:
        return
    if output.startswith('[P]'):
        active_rules['project'].add(output[4:])
        rule_key = output
    elif output.startswith('[G]'):
        active_rules['global'].add(output[4:])
        rule_key = output
    else:
        return
    cwd = entry.get('cwd', '')
    source = derive_rule_source(cwd)
    ts = format_timestamp(entry.get('timestamp', ''))
    if rule_key not in rules_invokers:
        rules_invokers[rule_key] = {}
    rules_invokers[rule_key][source] = ts

# Load historical rules from hook log (with invoker data from cwd)
def load_historical_rules() -> None:
    global hook_log_position
    entries, new_pos = parse_new_hook_entries(0)
    filtered = filter_by_project(entries, active_project_filter) if active_project_filter else entries
    for entry in filtered:
        if entry.get('hook_event') == HOOK_INSTRUCTIONS_LOADED:
            record_rule_invoker(entry)
    hook_log_position = new_pos

# Runs rules-only display loop (for dedicated rules tmux pane)
def run_rules_loop() -> None:
    global rules_expand_states, rules_line_map, rules_hover_row, rules_scroll_offset, rules_total_lines
    from .ui_mode import format_rules_block
    load_historical_rules()
    last_output = None
    last_data_refresh = 0.0
    frozen = False
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
                        button, _col, row = event
                        if button == 0:
                            rule_key = rules_line_map.get(row)
                            if rule_key:
                                rules_expand_states[rule_key] = not rules_expand_states.get(rule_key, False)
                                input_changed = True
                        elif button == 64:
                            rules_scroll_offset = min(rules_scroll_offset + 3, max(0, rules_total_lines - 5))
                            input_changed = True
                        elif button == 65:
                            rules_scroll_offset = max(0, rules_scroll_offset - 3)
                            input_changed = True
                        elif button >= 32:
                            rules_hover_row = row
                            input_changed = True
                else:
                    if char == 'f':
                        frozen = not frozen
                        input_changed = True
                    else:
                        idx = parse_digit_key(char)
                        if idx is not None:
                            all_keys = _get_sorted_rule_keys()
                            if 1 <= idx <= len(all_keys):
                                rule_key = all_keys[idx - 1]
                                rules_expand_states[rule_key] = not rules_expand_states.get(rule_key, False)
                                input_changed = True

            now = time.time()
            if not frozen and now - last_data_refresh >= POLL_INTERVAL:
                process_hook_log()
                last_data_refresh = now

            output, rules_total_lines = format_rules_block(active_rules, rules_invokers, rules_expand_states, rules_line_map, rules_hover_row, rules_scroll_offset, frozen)
            if output != last_output:
                print("\033[2J\033[3J\033[H", end='', flush=True)
                if output:
                    print(output)
                last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# Build sorted list of all rule keys ([P]/[G] prefixed)
def _get_sorted_rule_keys() -> List[str]:
    project_keys = [f'[P] {r}' for r in sorted(active_rules.get('project', set()))]
    global_keys = [f'[G] {r}' for r in sorted(active_rules.get('global', set()))]
    return project_keys + global_keys

# Process hook log for InstructionsLoaded entries (rules pane routing)
def process_hook_log() -> None:
    global hook_log_position, active_project_filter

    entries, hook_log_position = parse_new_hook_entries(hook_log_position)
    filtered = filter_by_project(entries, active_project_filter) if active_project_filter else entries

    for entry in filtered:
        if entry.get('hook_event') == HOOK_INSTRUCTIONS_LOADED:
            record_rule_invoker(entry)

# Display USER PROMPT detected from session JSONL
def display_user_prompt_from_jsonl(prompt_item: dict) -> None:
    formatted = format_user_prompt(prompt_item.get('timestamp', ''))
    print(formatted)
    print()

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
