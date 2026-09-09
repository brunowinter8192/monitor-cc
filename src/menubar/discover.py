# INFRASTRUCTURE
import json, os, time
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

from ..session_finder import get_project_directories, encode_project_path
from .proc_cache import (
    _refresh_cc_proc_cache, _refresh_tmux_state, _refresh_bg_task_cache,
    _tmux_session_exists, _tmux_window_activity, _read_hook_state, _proxy_log_newest_mtime,
    _has_active_bg, _cc_proc_cache,
)
from .ghostty import _refresh_ghostty_tty_to_id, _write_cwd_uuid_map, _ghostty_tty_to_id
from .desktop_detection import detect_main_desktop_numbers

ALIVE_WINDOW_SECS      = 3600
WORKING_THRESHOLD_SECS = 10
THINKING_OVERRIDE_MAX_SECS = 300
_WORKTREE_MARKER = '--claude-worktrees-'

class SessionInfo(NamedTuple):
    name: str
    status: str
    has_bg: bool
    encoded_dir: str
    project_name: str
    is_worker: bool
    cwd: str
    session_id: str
    tmux_session_name: str
    desktop_no: Optional[int] = None

_last_timings: Dict[str, float] = {}

# ORCHESTRATOR

def list_alive_sessions() -> List[SessionInfo]:
    global _last_timings
    now = time.time()
    timings: Dict[str, float] = {}
    t0 = time.monotonic()
    _refresh_cc_proc_cache(now)
    timings['proc_cache'] = time.monotonic() - t0
    t0 = time.monotonic()
    _refresh_ghostty_tty_to_id(now)
    timings['ghostty'] = time.monotonic() - t0
    t0 = time.monotonic()
    _refresh_tmux_state(now)
    timings['tmux_state'] = time.monotonic() - t0
    t0 = time.monotonic()
    _refresh_bg_task_cache(now)
    timings['bg_task_lsof'] = time.monotonic() - t0
    t0 = time.monotonic()
    _read_hook_state(now)
    _write_cwd_uuid_map()
    results = []
    for project_dir in get_project_directories():
        try:
            info = _process_project_dir(project_dir, now)
            if info is not None:
                results.append(info)
        except Exception:
            continue
    timings['per_project_loop'] = time.monotonic() - t0
    t0 = time.monotonic()
    main_cwds = {s.cwd for s in results if not s.is_worker and s.cwd}
    if main_cwds:
        cwd_tty_map  = {cwd: tty for _pid, (tty, cwd) in _cc_proc_cache.items() if tty and cwd}
        cwd_uuid_map = {cwd: _ghostty_tty_to_id[tty]
                        for _pid, (tty, cwd) in _cc_proc_cache.items()
                        if tty and cwd and tty in _ghostty_tty_to_id}
        dno_map = detect_main_desktop_numbers(cwd_uuid_map, cwd_tty_map, now)
        results = [s._replace(desktop_no=dno_map.get(s.cwd)) if not s.is_worker else s
                   for s in results]
    timings['desktop_detection'] = time.monotonic() - t0
    _last_timings = timings
    return results

def get_last_session_timings() -> Dict[str, float]:
    return dict(_last_timings)

# FUNCTIONS

def _newest_jsonl(project_dir: Path) -> Optional[Path]:
    files = [f for f in project_dir.glob('*.jsonl') if f.is_file()]
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)

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

def _decode_dir_name(name: str) -> str:
    parts = [p for p in name.split('-') if p]
    if not parts:
        return name
    last = parts[-1]
    if len(last) <= 4 and len(parts) >= 2:
        return f'{parts[-2]}-{last}'
    return last

def _classify_encoded_dir(encoded_dir: str) -> tuple:
    if _WORKTREE_MARKER in encoded_dir:
        left, _, worker_name = encoded_dir.partition(_WORKTREE_MARKER)
        return _decode_dir_name(left), True, worker_name
    return _decode_dir_name(encoded_dir), False, ''

def _proc_cwd_for_encoded_dir(encoded_dir: str) -> Optional[str]:
    for _pid, (tty, proc_cwd) in _cc_proc_cache.items():
        if encode_project_path(proc_cwd).lower() == encoded_dir.lower():
            return proc_cwd
    return None

def _worker_tmux_session(cwd: str, worker_name: str) -> Optional[str]:
    if '/.claude/worktrees/' not in cwd:
        return None
    project_path, _, _ = cwd.partition('/.claude/worktrees/')
    basename = os.path.basename(project_path)
    return f'worker-{basename}-{worker_name}'

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
        return _worker_session_info(jsonl, mtime, encoded_dir, project_name, worker_name,
                                    session_id, has_bg, hook_state, now)
    return _main_session_info(encoded_dir, session_id, has_bg, hook_state, mtime, now)

def _hook_freshness(hook_state: dict, session_id: str, now: float) -> tuple:
    hook_entry = hook_state.get(session_id)
    hook_fresh = (hook_entry is not None
                  and (now - hook_entry.get('updated_ts', 0)) <= ALIVE_WINDOW_SECS)
    return hook_entry, hook_fresh

def _worker_session_info(jsonl: Path, mtime: float, encoded_dir: str, project_name: str,
                         worker_name: str, session_id: str, has_bg: bool, hook_state: dict,
                         now: float) -> Optional[SessionInfo]:
    cwd = _cwd_from_jsonl(jsonl)
    tmux_session = ''
    display_name = worker_name
    if cwd and '/.claude/worktrees/' in cwd:
        project_path, _, worktree_rest = cwd.partition('/.claude/worktrees/')
        display_name = worktree_rest.split('/')[0] or worker_name
        project_name = os.path.basename(project_path) or project_name
        tmux_session = _worker_tmux_session(cwd, display_name) or ''
        if not tmux_session or not _tmux_session_exists(tmux_session):
            return None
    else:
        if now - mtime > ALIVE_WINDOW_SECS:
            return None
    hook_entry, hook_fresh = _hook_freshness(hook_state, session_id, now)
    if hook_fresh:
        status = hook_entry['status']
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

def _main_session_info(encoded_dir: str, session_id: str, has_bg: bool, hook_state: dict,
                       mtime: float, now: float) -> Optional[SessionInfo]:
    proc_cwd = _proc_cwd_for_encoded_dir(encoded_dir)
    if proc_cwd is None:
        return None
    project_name = os.path.basename(proc_cwd.rstrip('/'))
    cwd = proc_cwd
    name = os.path.basename(cwd.rstrip('/')) if cwd else project_name
    hook_entry, hook_fresh = _hook_freshness(hook_state, session_id, now)
    if hook_fresh:
        status = hook_entry['status']
    else:
        status = 'working' if (now - mtime) <= WORKING_THRESHOLD_SECS else 'idle'
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
