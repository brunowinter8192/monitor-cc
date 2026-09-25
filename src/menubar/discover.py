# INFRASTRUCTURE
import json, os, time
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

from src.session_finder import get_project_directories, encode_project_path
from src.menubar.proc_cache import (
    _refresh_cc_proc_cache, _refresh_tmux_state, _refresh_bg_task_cache,
    _tmux_session_exists, _tmux_window_activity, _read_hook_state, _proxy_log_newest_mtime,
    _has_active_bg, _cc_proc_cache,
)
from src.menubar.ghostty import _refresh_ghostty_tty_to_id, _write_cwd_uuid_map, _ghostty_tty_to_id
from src.menubar.desktop_detection import detect_main_desktop_numbers
from src.menubar.menubar_log import log_menubar_change

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
    now = time.time()
    timings: Dict[str, float] = {}
    _timed(timings, 'proc_cache', _refresh_cc_proc_cache, now)
    _timed(timings, 'ghostty', _refresh_ghostty_tty_to_id, now)
    _timed(timings, 'tmux_state', _refresh_tmux_state, now)
    _timed(timings, 'bg_task_lsof', _refresh_bg_task_cache, now)
    results = _timed(timings, 'per_project_loop', _scan_project_dirs, now)
    results = _timed(timings, 'desktop_detection', _assign_desktop_numbers, results, now)
    _store_timings(timings)
    return results

# FUNCTIONS

def get_last_session_timings() -> Dict[str, float]:
    return dict(_last_timings)

def _timed(timings: Dict[str, float], name: str, fn, *args):
    t0 = time.monotonic()
    result = fn(*args)
    timings[name] = time.monotonic() - t0
    return result

def _store_timings(timings: Dict[str, float]) -> None:
    global _last_timings
    _last_timings = timings

def _scan_project_dirs(now: float) -> List[SessionInfo]:
    _read_hook_state(now)
    _write_cwd_uuid_map()
    results = []
    for project_dir in get_project_directories():
        _collect_project(results, project_dir, now)
    return results

def _collect_project(results: List[SessionInfo], project_dir: Path, now: float) -> None:
    try:
        info = _process_project_dir(project_dir, now)
        if info is not None:
            results.append(info)
    except Exception as exc:
        log_menubar_change('discover', f'project:{project_dir.name}',
                           f'project skipped dir={project_dir.name} err={exc!r}')
        return
    log_menubar_change('discover', f'project:{project_dir.name}', None)

def _assign_desktop_numbers(results: List[SessionInfo], now: float) -> List[SessionInfo]:
    main_cwds = {s.cwd for s in results if not s.is_worker and s.cwd}
    if not main_cwds:
        return results
    cwd_tty_map, cwd_uuid_map = _build_cwd_maps()
    dno_map = detect_main_desktop_numbers(cwd_uuid_map, cwd_tty_map, now)
    return [s._replace(desktop_no=dno_map.get(s.cwd)) if not s.is_worker else s
            for s in results]

def _build_cwd_maps() -> tuple:
    cwd_tty_map  = {cwd: tty for _pid, (tty, cwd) in _cc_proc_cache.items() if tty and cwd}
    cwd_uuid_map = {cwd: _ghostty_tty_to_id[tty]
                    for _pid, (tty, cwd) in _cc_proc_cache.items()
                    if tty and cwd and tty in _ghostty_tty_to_id}
    return cwd_tty_map, cwd_uuid_map

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
            except (ValueError, AttributeError):
                continue
    except OSError as exc:
        log_menubar_change('discover', f'cwd_jsonl:{path}', f'cwd read failed path={path} err={exc!r}')
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
        display_name = worktree_rest.split('/')[0]
        project_name = os.path.basename(project_path)
        tmux_session = _worker_tmux_session(cwd, display_name) or ''
        if not tmux_session or not _tmux_session_exists(tmux_session):
            return None
        alive_route = 'tmux'
    else:
        if now - mtime > ALIVE_WINDOW_SECS:
            return None
        alive_route = 'mtime'
    hook_entry, hook_fresh = _hook_freshness(hook_state, session_id, now)
    if hook_fresh:
        status = hook_entry['status']
        status_route = 'hook'
        if status == 'working' and tmux_session:
            wa = _tmux_window_activity(tmux_session)
            if wa is not None and (wa == 0 or (now - wa) > WORKING_THRESHOLD_SECS):
                status = 'idle'
                status_route = 'hook_tmux_demote'
    else:
        status = 'idle'
        status_route = 'no_fresh_hook'
    _log_routes(session_id, display_name, alive_route, status_route)
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
    hook_entry, hook_fresh = _hook_freshness(hook_state, session_id, now)
    if hook_fresh:
        status = hook_entry['status']
        status_route = 'hook'
    else:
        status = 'working' if (now - mtime) <= WORKING_THRESHOLD_SECS else 'idle'
        status_route = 'mtime'
        if status == 'idle':
            project_key = project_name.lower().replace('-', '_').replace(' ', '_')
            proxy_mtime = _proxy_log_newest_mtime(project_key, now)
            if (proxy_mtime is not None and proxy_mtime > mtime
                    and (now - proxy_mtime) <= THINKING_OVERRIDE_MAX_SECS):
                status = 'working'
                status_route = 'proxy_override'
    _log_routes(session_id, project_name, 'process', status_route)
    return SessionInfo(name=project_name, status=status, has_bg=has_bg,
                       encoded_dir=encoded_dir, project_name=project_name,
                       is_worker=False, cwd=proc_cwd, session_id=session_id,
                       tmux_session_name='')

def _log_routes(session_id: str, name: str, alive_route: str, status_route: str) -> None:
    log_menubar_change('discover', f'routes:{session_id}',
                       f'session={name} alive_route={alive_route} status_route={status_route}')
