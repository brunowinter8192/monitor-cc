# INFRASTRUCTURE
import json
import os
import time
from pathlib import Path
from typing import List, NamedTuple, Optional

# From session_finder.py: Scan ~/.claude/projects directories
from ..session_finder import get_project_directories

ALIVE_WINDOW_SECS = 3600       # sessions older than 1h are stale
WORKING_THRESHOLD_SECS = 10    # <= 10s since last JSONL write = working
_TASKS_BASE = Path(f"/tmp/claude-{os.getuid()}")

class SessionInfo(NamedTuple):
    name: str          # display name: cwd basename for mains, worktree name for workers
    status: str        # 'working' | 'idle'
    has_bg: bool       # True if any in-progress background task exists
    encoded_dir: str   # ~/.claude/projects/ dir name, e.g. '-Users-.../Monitor_CC'
    project_name: str  # project this session belongs to (for grouping)
    is_worker: bool    # True if session lives under .claude/worktrees/

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

# Scan last 10 non-empty lines for a cwd field; returns first cwd found (newest first)
def _cwd_from_jsonl(path: Path) -> Optional[str]:
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            size = f.tell()
            if size == 0:
                return None
            f.seek(-min(8192, size), 2)
            chunk = f.read().decode('utf-8', errors='replace')
        count = 0
        for line in reversed(chunk.split('\n')):
            line = line.strip()
            if not line:
                continue
            count += 1
            if count > 10:
                break
            try:
                cwd = json.loads(line).get('cwd', '')
                if cwd:
                    return cwd
            except Exception:
                continue
    except Exception:
        pass
    return None

# Last-resort: decode encoded ~/.claude/projects dir name to readable project name
def _decode_dir_name(name: str) -> str:
    parts = [p for p in name.split('-') if p]
    if not parts:
        return name
    last = parts[-1]
    if len(last) <= 4 and len(parts) >= 2:
        return f'{parts[-2]}-{last}'
    return last

_WORKTREE_MARKER = '--claude-worktrees-'

# Split encoded_dir to determine project ownership and worker identity
def _classify_encoded_dir(encoded_dir: str) -> tuple:
    """Returns (project_name: str, is_worker: bool, worker_name: str)."""
    if _WORKTREE_MARKER in encoded_dir:
        left, _, worker_name = encoded_dir.partition(_WORKTREE_MARKER)
        return _decode_dir_name(left), True, worker_name
    return _decode_dir_name(encoded_dir), False, ''

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
    encoded_dir = project_dir.name
    project_name, is_worker, worker_name = _classify_encoded_dir(encoded_dir)
    if is_worker:
        name = worker_name
    else:
        cwd = _cwd_from_jsonl(jsonl)
        name = os.path.basename(cwd.rstrip('/')) if cwd else project_name
    status = 'working' if (now - mtime) <= WORKING_THRESHOLD_SECS else 'idle'
    session_id = jsonl.stem
    has_bg = _has_active_bg(encoded_dir, session_id)
    return SessionInfo(name=name, status=status, has_bg=has_bg, encoded_dir=encoded_dir,
                       project_name=project_name, is_worker=is_worker)
