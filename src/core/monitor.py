# INFRASTRUCTURE
from datetime import datetime, timedelta
from itertools import islice
from pathlib import Path
from typing import List, Optional

from src.core.modes import MODE_ALL, MODE_WARNINGS, MODE_TOKENS, MODE_WORKER_TOKENS, MODE_PROXY, MODE_WORKER_PROXY

from src.session_finder import find_active_sessions
from src.jsonl.jsonl_reader import JsonlReader

_SESSION_START_SCAN_RECORDS = 5

active_project_filter: Optional[str] = None
active_mode: str = MODE_ALL

# ORCHESTRATOR

def run_monitor(project_filter: Optional[str] = None, mode: str = MODE_ALL) -> None:
    _set_monitor_state(project_filter, mode)
    _dispatch_mode(mode)

# FUNCTIONS

def _set_monitor_state(project_filter: Optional[str], mode: str) -> None:
    global active_project_filter, active_mode
    active_project_filter = project_filter
    active_mode = mode

def _dispatch_mode(mode: str) -> None:
    if mode == MODE_WORKER_TOKENS:
        from src.workers import run_worker_tokens_loop
        run_worker_tokens_loop()
    elif mode == MODE_TOKENS:
        from src.panes import run_tokens_loop
        run_tokens_loop()
    elif mode == MODE_WARNINGS:
        from src.panes import run_warnings_loop
        run_warnings_loop()
    elif mode == MODE_PROXY:
        from src.proxy_display import run_proxy_loop
        run_proxy_loop()
    elif mode == MODE_WORKER_PROXY:
        from src.proxy_display import run_worker_proxy_loop
        run_worker_proxy_loop()
    else:
        raise ValueError(f"Unknown monitor mode: {mode!r}")

def _get_session_start_ts() -> Optional[str]:
    session = _get_newest_main_session()
    if not session:
        return None
    for msg in islice(JsonlReader(session), _SESSION_START_SCAN_RECORDS):
        ts = msg.get('timestamp')
        if ts:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            dt_adjusted = dt - timedelta(seconds=10)
            return dt_adjusted.isoformat().replace('+00:00', 'Z')
    return None

def _get_newest_main_session() -> Optional[Path]:
    main_sessions = get_main_session_files()
    return main_sessions[0] if main_sessions else None

def get_main_session_files() -> List[Path]:
    sessions = find_active_sessions(active_project_filter)
    return [s for s in sessions if not is_agent_file(s)]

def is_agent_file(filepath: Path) -> bool:
    return filepath.name.startswith('agent-')
