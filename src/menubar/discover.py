# INFRASTRUCTURE
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

# From session_finder.py: Scan ~/.claude/projects directories
from ..session_finder import get_project_directories

ALIVE_WINDOW_SECS      = 3600   # stale threshold for main sessions (1h)
WORKING_THRESHOLD_SECS = 10     # JSONL-mtime fallback: <= 10s = working
_TTY_WORKING_THRESHOLD = 3      # TTY mtime: <= 3s since last byte = working
_WORKER_ACTIVITY_THRESHOLD = 10 # tmux window_activity: <= 10s = working
_PROC_REFRESH_INTERVAL = 10.0   # seconds between ps/lsof cache rebuilds
_TASKS_BASE = Path(f"/tmp/claude-{os.getuid()}")
_GHOSTTY_TTY_REFRESH_INTERVAL = 10.0   # cooldown between new-TTY probe cycles
_GHOSTTY_MARKER_PREFIX = '__GHT_'      # OSC 2 title marker prefix (not used by CC)

# Module-level (pid, tty, cwd) cache for CC processes; refreshed every 10s
_cc_proc_cache: List[Tuple[str, str, str]] = []
_cc_proc_last_refresh: float = 0.0

# tty→Ghostty terminal UUID; populated by OSC 2 title-marker probe (incremental)
_ghostty_tty_to_id: Dict[str, str] = {}
_ghostty_tty_last_refresh: float = 0.0

class SessionInfo(NamedTuple):
    name: str          # display name: cwd basename for mains, worktree name for workers
    status: str        # 'working' | 'idle'
    has_bg: bool       # True if any in-progress background task exists
    encoded_dir: str   # ~/.claude/projects/ dir name, e.g. '-Users-.../Monitor_CC'
    project_name: str  # project this session belongs to (for grouping)
    is_worker: bool    # True if session lives under .claude/worktrees/
    cwd: str           # full working directory (non-empty for mains; '' for workers)

# Module-level (pid, tty, cwd) cache for CC processes; refreshed every 10s
_cc_proc_cache: List[Tuple[str, str, str]] = []
_cc_proc_last_refresh: float = 0.0

# ORCHESTRATOR

# Return list of alive CC sessions across all projects; swallows per-session errors
def list_alive_sessions() -> List[SessionInfo]:
    now = time.time()
    _refresh_cc_proc_cache(now)
    _refresh_ghostty_tty_to_id(now)
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

# Rebuild (pid, tty, cwd) list for all claude.exe processes; no-op within TTL
def _refresh_cc_proc_cache(now: float) -> None:
    global _cc_proc_cache, _cc_proc_last_refresh
    if now - _cc_proc_last_refresh < _PROC_REFRESH_INTERVAL:
        return
    procs: List[Tuple[str, str, str]] = []
    try:
        r = subprocess.run(['ps', '-A', '-o', 'pid,tty,comm'],
                           capture_output=True, text=True, timeout=3)
        pid_tty_pairs = []
        for line in r.stdout.strip().split('\n')[1:]:
            parts = line.split(None, 2)
            if len(parts) == 3 and 'claude' in parts[2].lower() and parts[1] != '??':
                pid_tty_pairs.append((parts[0].strip(), parts[1].strip()))
        for pid, tty in pid_tty_pairs:
            r2 = subprocess.run(['lsof', '-a', '-d', 'cwd', '-p', pid],
                                 capture_output=True, text=True, timeout=2)
            for line in r2.stdout.strip().split('\n'):
                if line.startswith('COMMAND') or not line:
                    continue
                fields = line.split(None, 8)
                if len(fields) == 9:
                    procs.append((pid, tty, fields[8]))
    except Exception:
        pass
    _cc_proc_cache = procs
    _cc_proc_last_refresh = now

# Return PID string of running Ghostty.app process, or None
def _ghostty_pid() -> Optional[str]:
    try:
        # ps -o comm= returns full path on macOS; pgrep -f matches full command line
        r = subprocess.run(['pgrep', '-f', 'Ghostty.app/Contents/MacOS'],
                           capture_output=True, text=True, timeout=2)
        pid = r.stdout.strip().split('\n')[0].strip()
        return pid if pid else None
    except Exception:
        return None

# Return TTY names for all direct children of ghostty_pid (one ps call)
def _ghostty_child_ttys(ghostty_pid: str) -> List[str]:
    try:
        r = subprocess.run(['ps', '-A', '-o', 'pid=,ppid=,tty='],
                           capture_output=True, text=True, timeout=3)
        ttys = []
        for line in r.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 3 and parts[1] == ghostty_pid and parts[2] != '??':
                ttys.append(parts[2])
        return ttys
    except Exception:
        return []

# Probe new Ghostty TTYs via OSC 2 marker + AppleScript; merge into _ghostty_tty_to_id
def _refresh_ghostty_tty_to_id(now: float) -> None:
    global _ghostty_tty_to_id, _ghostty_tty_last_refresh
    if now - _ghostty_tty_last_refresh < _GHOSTTY_TTY_REFRESH_INTERVAL:
        return
    ghostty_pid = _ghostty_pid()
    if not ghostty_pid:
        return
    all_ttys = _ghostty_child_ttys(ghostty_pid)
    # Stale cleanup: remove cache entries for closed Ghostty terminals
    for tty in list(_ghostty_tty_to_id):
        if tty not in all_ttys:
            del _ghostty_tty_to_id[tty]
    # Only probe TTYs not yet mapped — avoids title-flash on already-known terminals
    new_ttys = [t for t in all_ttys if t not in _ghostty_tty_to_id]
    if not new_ttys:
        return  # no probe; timestamp NOT updated so next tick re-checks
    # Write unique OSC 2 marker into each new TTY
    tty_marker: List[Tuple[str, str]] = []
    for tty in new_ttys:
        marker = f'{_GHOSTTY_MARKER_PREFIX}{os.urandom(4).hex()}'
        tty_marker.append((tty, marker))
        try:
            with open(f'/dev/{tty}', 'wb', buffering=0) as fh:
                fh.write(f'\033]2;{marker}\007'.encode())
        except OSError:
            pass
    time.sleep(0.12)
    # Query Ghostty for id|||name pairs (newline-separated)
    osa = (
        'tell application "Ghostty"\n'
        '  set pairs to {}\n'
        '  repeat with t in every terminal\n'
        '    set end of pairs to (id of t) & "|||" & (name of t)\n'
        '  end repeat\n'
        '  set AppleScript\'s text item delimiters to ASCII character 10\n'
        '  return pairs as text\n'
        'end tell'
    )
    try:
        r3 = subprocess.run(['osascript', '-e', osa],
                            capture_output=True, text=True, timeout=3)
    except Exception:
        r3 = None
    # Cleanup: restore shell-default title on all probed TTYs
    for tty, _ in tty_marker:
        try:
            with open(f'/dev/{tty}', 'wb', buffering=0) as fh:
                fh.write(b'\033]2;\007')
        except OSError:
            pass
    if not r3 or r3.returncode != 0:
        return
    # Parse output and merge new tty→id entries into cache
    name_to_id: Dict[str, str] = {}
    for line in r3.stdout.strip().split('\n'):
        if '|||' in line:
            tid, _, tname = line.partition('|||')
            name_to_id[tname.strip()] = tid.strip()
    for tty, marker in tty_marker:
        if marker in name_to_id:
            _ghostty_tty_to_id[tty] = name_to_id[marker]
    _ghostty_tty_last_refresh = now

# Return tty name for the CC process with the given cwd; None if not in cache
def _tty_for_cwd(cwd: str) -> Optional[str]:
    for _, tty, proc_cwd in _cc_proc_cache:
        if proc_cwd == cwd:
            return tty
    return None

# Return Ghostty terminal UUID for a main CC session's cwd, or None if not mapped
def get_ghostty_terminal_id(cwd: str) -> Optional[str]:
    tty = _tty_for_cwd(cwd)
    if tty is None:
        return None
    return _ghostty_tty_to_id.get(tty)

# True if TTY for the main session's cwd had output within _TTY_WORKING_THRESHOLD seconds
def _main_is_working(cwd: str) -> bool:
    tty = _tty_for_cwd(cwd)
    if tty is None:
        return False
    try:
        mtime = os.stat(f'/dev/{tty}').st_mtime
        return (time.time() - mtime) <= _TTY_WORKING_THRESHOLD
    except OSError:
        return False

# Build tmux session name from worker JSONL cwd; None if cwd is not a worktree path
def _worker_tmux_session(cwd: str, worker_name: str) -> Optional[str]:
    if '/.claude/worktrees/' not in cwd:
        return None
    project_path, _, _ = cwd.partition('/.claude/worktrees/')
    basename = os.path.basename(project_path)
    return f'worker-{basename}-{worker_name}'

# True if the named tmux session exists (= prefix enforces exact match)
def _tmux_session_exists(session_name: str) -> bool:
    r = subprocess.run(['tmux', 'has-session', '-t', f'={session_name}'],
                       capture_output=True)
    return r.returncode == 0

# True if tmux window_activity for the session is within _WORKER_ACTIVITY_THRESHOLD
def _worker_is_working(session_name: str) -> bool:
    try:
        r = subprocess.run(
            ['tmux', 'display-message', '-t', session_name, '-p', '#{window_activity}'],
            capture_output=True, text=True, timeout=2)
        if r.returncode != 0:
            return False
        return (time.time() - int(r.stdout.strip())) <= _WORKER_ACTIVITY_THRESHOLD
    except (ValueError, Exception):
        return False

# Build SessionInfo for one project dir; None if session is gone or unreadable
def _process_project_dir(project_dir: Path, now: float) -> Optional[SessionInfo]:
    jsonl = _newest_jsonl(project_dir)
    if jsonl is None:
        return None
    mtime = jsonl.stat().st_mtime
    encoded_dir = project_dir.name
    project_name, is_worker, worker_name = _classify_encoded_dir(encoded_dir)
    session_id = jsonl.stem
    has_bg = _has_active_bg(encoded_dir, session_id)

    if is_worker:
        cwd = _cwd_from_jsonl(jsonl)
        if cwd and '/.claude/worktrees/' in cwd:
            # Worker alive iff its tmux session exists (consistent with worker-cli)
            tmux_session = _worker_tmux_session(cwd, worker_name)
            if not tmux_session or not _tmux_session_exists(tmux_session):
                return None
            status = 'working' if _worker_is_working(tmux_session) else 'idle'
        else:
            # cwd unavailable — fall back to JSONL age
            if now - mtime > ALIVE_WINDOW_SECS:
                return None
            status = 'working' if (now - mtime) <= WORKING_THRESHOLD_SECS else 'idle'
        return SessionInfo(name=worker_name, status=status, has_bg=has_bg,
                           encoded_dir=encoded_dir, project_name=project_name,
                           is_worker=True, cwd='')
    else:
        # Main session: stale if JSONL > 1h
        if now - mtime > ALIVE_WINDOW_SECS:
            return None
        cwd = _cwd_from_jsonl(jsonl)
        name = os.path.basename(cwd.rstrip('/')) if cwd else project_name
        # Activity: TTY mtime if CC process found, else JSONL-mtime fallback
        if cwd and _tty_for_cwd(cwd):
            status = 'working' if _main_is_working(cwd) else 'idle'
        else:
            status = 'working' if (now - mtime) <= WORKING_THRESHOLD_SECS else 'idle'
        return SessionInfo(name=name, status=status, has_bg=has_bg,
                           encoded_dir=encoded_dir, project_name=project_name,
                           is_worker=False, cwd=cwd or '')
