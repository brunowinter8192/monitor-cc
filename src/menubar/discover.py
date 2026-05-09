# INFRASTRUCTURE
import json
import os
import time
from pathlib import Path
from typing import List, NamedTuple, Optional

# From session_finder.py: Scan ~/.claude/projects directories
from ..session_finder import get_project_directories

ALIVE_WINDOW_SECS = 300        # sessions older than 5 min are stale
WORKING_THRESHOLD_SECS = 10    # <= 10s since last JSONL write = working
_TASKS_BASE = Path(f"/tmp/claude-{os.getuid()}")

class SessionInfo(NamedTuple):
    name: str          # project basename from cwd field
    status: str        # 'working' | 'idle'
    has_bg: bool       # True if any in-progress background task exists
    encoded_dir: str   # ~/.claude/projects/ dir name, e.g. '-Users-.../Monitor_CC'

# ORCHESTRATOR

# Return list of alive CC sessions across all projects; swallows per-session errors
def list_alive_sessions() -> List[SessionInfo]:
    now = time.time()
    results = []
    for project_dir in get_project_directories():
        try:
            info = _process_project_dir(project_dir, now)
            if info is not None:
                results.append(info)
        except Exception:
            continue
    return results

# FUNCTIONS

# Pick newest top-level *.jsonl in project_dir (excludes subagents/ subtree)
def _newest_jsonl(project_dir: Path) -> Optional[Path]:
    files = [f for f in project_dir.glob('*.jsonl') if f.is_file()]
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)

# Read last non-empty line of file as parsed JSON; None on any error
def _read_last_line(path: Path) -> Optional[dict]:
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            size = f.tell()
            if size == 0:
                return None
            f.seek(-min(8192, size), 2)
            chunk = f.read().decode('utf-8', errors='replace')
        for line in reversed(chunk.split('\n')):
            line = line.strip()
            if line:
                return json.loads(line)
    except Exception:
        pass
    return None

# Extract friendly project name from a parsed JSONL line
def _project_name(last_line: dict) -> str:
    cwd = last_line.get('cwd', '')
    if cwd:
        return os.path.basename(cwd.rstrip('/'))
    return 'unknown'

# True if any *.output file in the session tasks dir has 0 bytes (= in-progress task)
def _has_active_bg(encoded_dir: str, session_id: str) -> bool:
    tasks_dir = _TASKS_BASE / encoded_dir / session_id / 'tasks'
    if not tasks_dir.exists():
        return False
    try:
        return any(f.stat().st_size == 0 for f in tasks_dir.glob('*.output') if f.is_file())
    except OSError:
        return False

# Build SessionInfo for one project dir; None if stale or unreadable
def _process_project_dir(project_dir: Path, now: float) -> Optional[SessionInfo]:
    jsonl = _newest_jsonl(project_dir)
    if jsonl is None:
        return None
    mtime = jsonl.stat().st_mtime
    if now - mtime > ALIVE_WINDOW_SECS:
        return None
    last_line = _read_last_line(jsonl)
    name = _project_name(last_line) if last_line else project_dir.name
    status = 'working' if (now - mtime) <= WORKING_THRESHOLD_SECS else 'idle'
    session_id = jsonl.stem
    encoded_dir = project_dir.name
    has_bg = _has_active_bg(encoded_dir, session_id)
    return SessionInfo(name=name, status=status, has_bg=has_bg, encoded_dir=encoded_dir)
