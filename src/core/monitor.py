# INFRASTRUCTURE
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# From modes.py: Mode constants (split out of ..constants — sole importer)
from .modes import MODE_ALL, MODE_WARNINGS, MODE_TOKENS, MODE_WORKERS, MODE_PROXY, MODE_WORKER_PROXY

# From session_finder.py: Discover active Claude Code sessions
from ..session_finder import find_active_sessions
# From jsonl/: Parse JSONL lines for session start timestamp
from ..jsonl import parse_jsonl_lines, read_new_lines

file_positions: Dict[Path, int] = {}
active_project_filter: Optional[str] = None
active_mode: str = MODE_ALL

# ORCHESTRATOR
def run_monitor(project_filter: Optional[str] = None, mode: str = MODE_ALL) -> None:
    global active_project_filter, active_mode
    active_project_filter = project_filter
    active_mode = mode

    initialize_file_positions()

    if mode == MODE_WORKERS:
        from ..workers import run_workers_loop
        run_workers_loop()
    elif mode == MODE_TOKENS:
        from ..panes import run_tokens_loop
        run_tokens_loop()
    elif mode == MODE_WARNINGS:
        from ..panes import run_warnings_loop
        run_warnings_loop()
    elif mode == MODE_PROXY:
        from ..proxy_display import run_proxy_loop
        run_proxy_loop()
    elif mode == MODE_WORKER_PROXY:
        from ..proxy_display import run_worker_proxy_loop
        run_worker_proxy_loop()
    else:
        raise ValueError(f"Unknown monitor mode: {mode!r}")

# FUNCTIONS

# Initialize file positions for all existing sessions
def initialize_file_positions() -> int:
    global file_positions, active_project_filter

    sessions = find_active_sessions(active_project_filter)

    for session_file in sessions:
        if session_file not in file_positions:
            file_positions[session_file] = get_file_end_position(session_file)

    return len(sessions)

# Track session-file lifecycle (new/removed sessions) for the active project filter — session
# bookkeeping only, no tool-call extraction; that pipeline lived in the main pane and was removed
# along with it, see process-docs/main_pane/
def monitor_sessions() -> None:
    global active_project_filter
    sessions = find_active_sessions(active_project_filter)
    update_session_tracking(sessions)

# Update tracking for new or removed sessions
def update_session_tracking(sessions: list) -> None:
    global file_positions

    current_files = set(sessions)
    tracked_files = set(file_positions.keys())

    new_files = current_files - tracked_files
    removed_files = tracked_files - current_files

    for new_file in new_files:
        file_positions[new_file] = get_initial_position(new_file)

    for removed_file in removed_files:
        del file_positions[removed_file]

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
