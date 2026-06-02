# INFRASTRUCTURE
import json, os, time
from pathlib import Path
from typing import List, NamedTuple, Optional

# From session_finder.py: Scan ~/.claude/projects directories + encode project path
from ..session_finder import get_project_directories, encode_project_path
# From proc_cache.py: Process/tmux/proxy/hook caches
from .proc_cache import (
    _refresh_cc_proc_cache, _refresh_tmux_state,
    _tmux_session_exists, _tmux_window_activity, _read_hook_state, _proxy_log_newest_mtime,
    _has_active_bg, _cc_proc_cache,
)
# From ghostty.py: Ghostty TTY-to-UUID mapping + cwd-UUID file write for hook delivery
from .ghostty import _refresh_ghostty_tty_to_id, _write_cwd_uuid_map, _ghostty_tty_to_id

ALIVE_WINDOW_SECS      = 3600   # stale threshold for main sessions (1h)
WORKING_THRESHOLD_SECS = 10     # stale threshold: workers = window_activity age, mains = JSONL mtime
THINKING_OVERRIDE_MAX_SECS = 300  # max expected thinking duration for proxy-mtime override
_WORKTREE_MARKER = '--claude-worktrees-'

class SessionInfo(NamedTuple):
    name: str                # display name: cwd basename for mains, worktree name for workers
    status: str              # 'working' | 'idle'
    has_bg: bool             # True if any in-progress background task exists
    encoded_dir: str         # ~/.claude/projects/ dir name, e.g. '-Users-.../Monitor_CC'
    project_name: str        # project this session belongs to (for grouping); decoded-path heuristic — may not equal worker_tmux_session basename for nested paths like Meta/ClaudeCode/MCP/RAG (project_name='MCP-RAG', basename='RAG')
    is_worker: bool          # True if session lives under .claude/worktrees/
    cwd: str                 # full working directory (non-empty for mains; '' for workers)
    session_id: str          # JSONL stem = CC session identifier (key for msg_queue.json)
    tmux_session_name: str   # worker-{basename(project_path)}-{worker_name} per iterative-dev convention; '' for mains. Used for orchestrator-signal lookup in app.py:_has_recent_send_signal — DO NOT reconstruct from project_name (decode heuristic mismatch).

# ORCHESTRATOR

# Return list of alive CC sessions across all projects; swallows per-session errors
def list_alive_sessions() -> List[SessionInfo]:
    now = time.time()
    _refresh_cc_proc_cache(now)
    _refresh_ghostty_tty_to_id(now)
    _refresh_tmux_state(now)
    _read_hook_state(now)   # warm cache once per tick; _process_project_dir reads from cache
    _write_cwd_uuid_map()   # refresh {cwd: uuid} file for hook_writer.py delivery (change-detected)
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

# Split encoded_dir to determine project ownership and worker identity
def _classify_encoded_dir(encoded_dir: str) -> tuple:
    """Returns (project_name: str, is_worker: bool, worker_name: str)."""
    if _WORKTREE_MARKER in encoded_dir:
        left, _, worker_name = encoded_dir.partition(_WORKTREE_MARKER)
        return _decode_dir_name(left), True, worker_name
    return _decode_dir_name(encoded_dir), False, ''

# Find launch cwd for a main session by matching encode(proc_cwd) against encoded_dir.
# proc_cwd never changes during a session (user `cd` runs in Bash subprocess, exits);
# JSONL cwd drifts with each Bash `cd`. Returns None if proc cache has no match (stale).
def _proc_cwd_for_encoded_dir(encoded_dir: str) -> Optional[str]:
    for _pid, (tty, proc_cwd) in _cc_proc_cache.items():
        if encode_project_path(proc_cwd).lower() == encoded_dir.lower():
            return proc_cwd
    return None

# Build tmux session name from worker JSONL cwd; None if cwd is not a worktree path
def _worker_tmux_session(cwd: str, worker_name: str) -> Optional[str]:
    if '/.claude/worktrees/' not in cwd:
        return None
    project_path, _, _ = cwd.partition('/.claude/worktrees/')
    basename = os.path.basename(project_path)
    return f'worker-{basename}-{worker_name}'

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
    hook_state = _read_hook_state(now)

    if is_worker:
        cwd = _cwd_from_jsonl(jsonl)
        tmux_session = ''
        display_name = worker_name   # fallback: lossy encoded-dir name (underscores → hyphens)
        if cwd and '/.claude/worktrees/' in cwd:
            # Real worker name from cwd preserves underscores (encode_project_path is lossy: _ → -)
            display_name = os.path.basename(cwd)
            # Live project dir basename overrides stale decoded-dir name; fallback keeps decode value
            project_name = os.path.basename(cwd.partition('/.claude/worktrees/')[0]) or project_name
            # Worker alive iff its tmux session exists (consistent with worker-cli)
            tmux_session = _worker_tmux_session(cwd, display_name) or ''
            if not tmux_session or not _tmux_session_exists(tmux_session):
                return None
        else:
            # cwd unavailable — alive guard via JSONL age
            if now - mtime > ALIVE_WINDOW_SECS:
                return None
        hook_entry = hook_state.get(session_id)
        hook_fresh = (hook_entry is not None
                      and (now - hook_entry.get('updated_ts', 0)) <= ALIVE_WINDOW_SECS)
        if hook_fresh:
            status = hook_entry['status']
            # Crash-safety: 'working' hook + no recent pane activity = CC crashed or context-limited
            # before Stop-hook fired. window_activity tracks spinner ticks → stays fresh through
            # thinking phases (unlike JSONL mtime which only updates on message completion).
            # Skip demote when tmux_session is empty (cwd-unavailable fallback — no activity signal).
            if status == 'working' and tmux_session:
                wa = _tmux_window_activity(tmux_session)
                if wa == 0 or (now - wa) > WORKING_THRESHOLD_SECS:
                    status = 'idle'
        else:
            status = 'idle'
        return SessionInfo(name=display_name, status=status, has_bg=has_bg,
                           encoded_dir=encoded_dir, project_name=project_name,
                           is_worker=True, cwd='', session_id=session_id,
                           tmux_session_name=tmux_session)
    else:
        # Main session alive ONLY if a live claude process exists for it.
        # Without this, exited mains stay visible until JSONL > 1h (ALIVE_WINDOW_SECS).
        proc_cwd = _proc_cwd_for_encoded_dir(encoded_dir)
        if proc_cwd is None:
            return None
        # Live cwd basename overrides stale decoded-dir name (encode path never physically renamed)
        project_name = os.path.basename(proc_cwd.rstrip('/'))
        # proc-cwd is launch cwd (stable); JSONL cwd drifts when user `cd`s in chat.
        cwd = proc_cwd
        name = os.path.basename(cwd.rstrip('/')) if cwd else project_name
        # Priority 1: hook state (real-time signal from CC's UserPromptSubmit/Stop hooks).
        # Covers thinking phase from T=0 and holds 'working' for the full turn duration.
        # Falls back to JSONL+proxy when hook state is absent (hooks not installed) or stale.
        hook_entry  = hook_state.get(session_id)
        hook_fresh  = (hook_entry is not None
                       and (now - hook_entry.get('updated_ts', 0)) <= ALIVE_WINDOW_SECS)
        if hook_fresh:
            status = hook_entry['status']
        else:
            # Priority 2: JSONL mtime (TTY mtime removed — cursor blinks cause false-working)
            status = 'working' if (now - mtime) <= WORKING_THRESHOLD_SECS else 'idle'
            # Priority 3: proxy log newer than JSONL → request in flight (reasoning phase).
            # Old condition was (now - proxy_mtime) <= 10s — only fired for first 10s of
            # thinking. Correct signal: proxy_mtime > mtime (request sent after last JSONL
            # write). After response the proxy latency entry lands ~0.1s before CC writes
            # JSONL, so proxy_mtime drops just below mtime → no false positive.
            if status == 'idle':
                project_key = project_name.lower().replace('-', '_').replace(' ', '_')
                proxy_mtime = _proxy_log_newest_mtime(project_key, now)
                if (proxy_mtime is not None and proxy_mtime > mtime
                        and (now - proxy_mtime) <= THINKING_OVERRIDE_MAX_SECS):
                    status = 'working'
        return SessionInfo(name=name, status=status, has_bg=has_bg,
                           encoded_dir=encoded_dir, project_name=project_name,
                           is_worker=False, cwd=cwd or '', session_id=session_id,
                           tmux_session_name='')
