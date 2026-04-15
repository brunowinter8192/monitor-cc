# INFRASTRUCTURE
from datetime import datetime, timedelta
import time
from pathlib import Path
from typing import Dict, Set, List, Optional

# From constants.py: Colors, config, shared constants
from .constants import RESET, CYAN, POLL_INTERVAL, MODE_ALL, MODE_MAIN, MODE_SUBAGENT, MODE_RULES, MODE_WARNINGS, MODE_HOOKS, MODE_TOKENS, MODE_WORKERS, MODE_PROXY, MODE_METADATA, MODE_WORKER_PROXY, MODE_WORKER_METADATA

# From session_finder.py: Discover active Claude Code sessions
from .session_finder import find_active_sessions
# From jsonl_parser.py: Parse JSONL lines for session start timestamp
from .jsonl_parser import parse_jsonl_lines, read_new_lines
# From hooks/: Parse hook log entries
from .hooks import get_current_position as get_hook_log_position
# From monitor_display.py: Session status output
from .monitor_display import print_session_status
# From monitor_session.py: Session file processing, task handling, historical load
from .monitor_session import get_file_end_position, get_initial_position, process_session_file, load_historical_main, load_historical_subagents

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
        from .workers import run_workers_loop
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
        from .hooks import run_hooks_loop
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
