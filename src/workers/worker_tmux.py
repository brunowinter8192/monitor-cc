# INFRASTRUCTURE
from typing import List, Optional
from pathlib import Path
import subprocess
import time

from ..session_finder import encode_project_path
# From worker_format.py: Derive project name from path
from .worker_format import get_worker_project_name

# FUNCTIONS

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
