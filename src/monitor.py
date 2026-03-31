# INFRASTRUCTURE
from datetime import datetime
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Set, List, Optional

# From constants.py: Colors, config, shared constants
from .constants import RESET, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, PURPLE, POLL_INTERVAL, TOOL_TASK, MODE_ALL, MODE_MAIN, MODE_SUBAGENT, MODE_RULES, MODE_WARNINGS, MODE_HOOKS, MODE_TOKENS, MODE_WORKERS, HOOK_INSTRUCTIONS_LOADED
INDENT = '  '

# From session_finder.py: Discover active Claude Code sessions
from .session_finder import find_active_sessions, encode_project_path
# From jsonl_parser.py: Parse JSONL and extract tool calls
from .jsonl_parser import parse_new_tool_calls, parse_jsonl_lines, read_new_lines, get_message_content, is_tool_use
# From formatter.py: Format tool calls for display
from .formatter import format_tool_call, format_user_prompt, format_user_media, format_thinking, format_skill_activation, format_unknown_type_warning, format_hook_event, format_token_profile, format_token_profile_cumulative, format_workers_block
# From hook_parser.py: Parse hook log entries
from .hook_parser import parse_new_hook_entries, filter_by_project, get_current_position as get_hook_log_position
# From subagent_ui.py: Subagent state management
from .subagent_ui import subagent_states
# From click_handler.py: Keyboard input for token and workers panes
from .click_handler import read_keypress, parse_digit_key, setup_keyboard_input, restore_terminal, enable_mouse, disable_mouse, read_mouse_event
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
token_cumulative_n: Optional[int] = None
token_input_buffer: str = ''
worker_expand_states: Dict[str, bool] = {}
worker_line_map: Dict[int, str] = {}
hover_row: Optional[int] = None

# ORCHESTRATOR
def run_monitor(project_filter: Optional[str] = None, mode: str = MODE_ALL, ui: bool = False) -> None:
    global active_project_filter, active_mode, ui_mode_active, hook_log_position
    active_project_filter = project_filter
    active_mode = mode
    ui_mode_active = ui

    initialize_file_positions()

    if mode == MODE_WORKERS:
        run_workers_loop()
    elif mode == MODE_TOKENS:
        run_tokens_loop()
    elif mode == MODE_RULES:
        run_rules_loop()
    elif mode == MODE_WARNINGS:
        run_warnings_loop()
    elif mode == MODE_HOOKS:
        run_hooks_loop()
    elif ui and mode == MODE_SUBAGENT:
        sessions = find_active_sessions(active_project_filter)
        session_count = len(filter_sessions_by_mode(sessions, mode))
        print_session_status(session_count, project_filter, mode)
        run_ui_loop(subagent_metadata, tool_calls_by_agent, agent_to_task, agent_to_type, monitor_sessions, active_rules)
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

# Runs continuous streaming monitor loop
def run_streaming_loop() -> None:
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

# Read all token usage from last N main session files (position 0)
def compute_cumulative_tokens(n: int) -> List[dict]:
    main_sessions = get_main_session_files()
    selected = main_sessions[:n]
    sessions_data = []
    for filepath in selected:
        _, _, _, _, _, _, _, _, usage_data = parse_new_tool_calls(filepath, 0, {})
        stats: dict = {
            'file': filepath.name,
            'input_total': 0,
            'output_total': 0,
            'cache_creation': 0,
            'cache_read': 0,
            'turns': 0,
            'tools': {},
            'text': 0,
        }
        request_ids: Set[str] = set()
        for ud in usage_data:
            cache_c = ud.get('cache_creation_input_tokens', 0)
            cache_r = ud.get('cache_read_input_tokens', 0)
            output_tok = ud.get('output_tokens', 0)
            block_type = ud.get('type', 'text')
            tool_name = ud.get('tool_name')
            stats['input_total'] += ud.get('input_tokens', 0) + cache_c + cache_r
            stats['output_total'] += output_tok
            stats['cache_creation'] += cache_c
            stats['cache_read'] += cache_r
            if block_type == 'tool_use' and tool_name:
                stats['tools'][tool_name] = stats['tools'].get(tool_name, 0) + output_tok
            elif block_type == 'text':
                stats['text'] += output_tok
            rid = ud.get('request_id', '')
            if rid:
                request_ids.add(rid)
        stats['turns'] = len(request_ids)
        sessions_data.append(stats)
    return sessions_data


# Runs token profiling display loop (for dedicated tokens tmux pane)
def run_tokens_loop() -> None:
    global token_cumulative_n, token_input_buffer
    last_output = None
    setup_keyboard_input()
    try:
        while True:
            char = read_keypress()
            if char is not None:
                if char in '\r\n':
                    stripped = token_input_buffer.strip()
                    if stripped == '' or stripped == 'q':
                        token_cumulative_n = None
                    else:
                        try:
                            n = int(stripped)
                            if n == 0:
                                token_cumulative_n = None
                            elif n > 0:
                                token_cumulative_n = n
                        except ValueError:
                            pass
                    token_input_buffer = ''
                elif char == 'q' and not token_input_buffer:
                    token_cumulative_n = None
                elif char in ('\x7f', '\x08'):
                    token_input_buffer = token_input_buffer[:-1]
                elif char.isdigit():
                    token_input_buffer += char

            monitor_sessions()
            output = format_tokens_block()
            if output != last_output:
                print("\033[2J\033[3J\033[H", end='', flush=True)
                if output:
                    print(output)
                last_output = output
            time.sleep(POLL_INTERVAL)
    finally:
        restore_terminal()

# Format token profile block for dedicated pane
def format_tokens_block() -> str:
    session_count = len(get_main_session_files())
    header_line = f"{CYAN}Sessions: {session_count}{RESET}"

    if token_cumulative_n is not None:
        sessions_data = compute_cumulative_tokens(token_cumulative_n + 1)
        profile_str = format_token_profile_cumulative(sessions_data, token_cumulative_n)
    else:
        sessions_data = compute_cumulative_tokens(1)
        if not sessions_data:
            profile_str = ''
        else:
            s = sessions_data[0]
            profile = {
                'total': s['output_total'],
                'turns': s['turns'],
                'text': s.get('text', 0),
                'tools': s.get('tools', {}),
                'input_total': s['input_total'],
                'input_tokens': s['input_total'] - s['cache_creation'] - s['cache_read'],
                'cache_creation': s['cache_creation'],
                'cache_read': s['cache_read'],
            }
            profile_str = format_token_profile(profile)

    if token_input_buffer:
        prompt_line = f"{YELLOW}Last N sessions › {token_input_buffer}_{RESET}"
    else:
        prompt_line = f"{YELLOW}Last N sessions › {RESET}"

    parts = [header_line, '']
    if profile_str:
        parts.append(profile_str)
        parts.append('')
    parts.append(prompt_line)
    return '\n'.join(parts)

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
    global worker_expand_states, worker_line_map, hover_row
    last_output = None
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            workers = list_workers(active_project_filter) if active_project_filter else []

            while True:
                char = read_keypress()
                if char is None:
                    break
                if char == '\033':
                    event = read_mouse_event(char)
                    if event is not None:
                        button, col, row = event
                        if button == 0:
                            name = worker_line_map.get(row)
                            if name:
                                worker_expand_states[name] = not worker_expand_states.get(name, False)
                        elif button >= 32:
                            hover_row = row
                else:
                    idx = parse_digit_key(char)
                    if idx is not None and 1 <= idx <= len(workers):
                        name = workers[idx - 1]['name']
                        worker_expand_states[name] = not worker_expand_states.get(name, False)

            tool_calls_by_worker: Dict[str, List[dict]] = {}
            for w in workers:
                name = w.get('name', '')
                if worker_expand_states.get(name, False):
                    jsonl_path = find_worker_jsonl(w.get('session', ''))
                    if jsonl_path:
                        tool_calls_by_worker[name] = extract_worker_tool_calls(jsonl_path)

            output = format_workers_block(workers, worker_expand_states, tool_calls_by_worker, worker_line_map, hover_row)
            if output != last_output:
                print("\033[2J\033[3J\033[H", end='', flush=True)
                if output:
                    print(output)
                last_output = output
            time.sleep(POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# Runs hooks display loop (for dedicated hooks tmux pane)
def run_hooks_loop() -> None:
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
    last_output = None
    while True:
        process_hook_log()
        output = format_rules_block(active_rules)
        if output != last_output:
            print("\033[2J\033[3J\033[H", end='', flush=True)
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
