# INFRASTRUCTURE
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from .paths import HOOKS_FILE as _HOOK_STATE_FILE

_PROC_REFRESH_INTERVAL = 10.0
_HOOK_REFRESH_INTERVAL = 1.0
_TMUX_REFRESH_INTERVAL = 3.0
_TASKS_BASE = Path(f"/tmp/claude-{os.getuid()}")
_TASKS_BASE_REAL = str(_TASKS_BASE.resolve())
_PROXY_LOG_DIR = Path('/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs')

_cc_proc_cache: Dict[str, Tuple[str, str]] = {}
_cc_proc_cache_lock = threading.Lock()
_cc_proc_last_refresh: float = 0.0

_bg_task_open_paths: set = set()
_bg_task_last_refresh: float = 0.0

_tmux_state_cache: set = set()
_tmux_state_last_refresh: float = 0.0

_proxy_log_mtime_cache: Dict[str, Tuple[float, Optional[float]]] = {}

_hook_state_cache: Dict[str, dict] = {}
_hook_state_last_read: float = 0.0

# ORCHESTRATOR

# FUNCTIONS

def _has_active_bg(encoded_dir: str, session_id: str) -> bool:
    try:
        tasks_dir_real = f'{_TASKS_BASE_REAL}/{encoded_dir}/{session_id}/tasks/'
        return any(p.startswith(tasks_dir_real) for p in _bg_task_open_paths)
    except OSError:
        return False

def _refresh_bg_task_cache(now: float) -> None:
    global _bg_task_open_paths, _bg_task_last_refresh
    if now - _bg_task_last_refresh < _PROC_REFRESH_INTERVAL:
        return
    _bg_task_last_refresh = now
    if not _TASKS_BASE.exists():
        _bg_task_open_paths = set()
        return
    try:
        r = subprocess.run(['lsof', '+D', str(_TASKS_BASE), '-Fn'],
                            capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=3)
    except Exception:
        return
    _bg_task_open_paths = {line[1:] for line in r.stdout.split('\n')
                            if line.startswith('n') and line.endswith('.output')}

def _refresh_cc_proc_cache(now: float) -> None:
    global _cc_proc_last_refresh
    if now - _cc_proc_last_refresh < _PROC_REFRESH_INTERVAL:
        return
    _cc_proc_last_refresh = now
    try:
        r = subprocess.run(['ps', '-A', '-o', 'pid,tty,comm'],
                           capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=3)
    except Exception:
        return
    active: Dict[str, str] = {}
    for line in r.stdout.strip().split('\n')[1:]:
        parts = line.split(None, 2)
        if len(parts) == 3 and 'claude' in parts[2].lower() and parts[1] != '??':
            active[parts[0].strip()] = parts[1].strip()
    with _cc_proc_cache_lock:
        known_pids = set(_cc_proc_cache)
    new_entries: Dict[str, Tuple[str, str]] = {}
    for pid, tty in active.items():
        if pid in known_pids:
            continue
        try:
            r2 = subprocess.run(['lsof', '-a', '-d', 'cwd', '-p', pid],
                                 capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=2)
            for line in r2.stdout.strip().split('\n'):
                if line.startswith('COMMAND') or not line:
                    continue
                fields = line.split(None, 8)
                if len(fields) == 9:
                    new_entries[pid] = (tty, fields[8])
                    break
        except Exception:
            continue
    with _cc_proc_cache_lock:
        for pid in list(_cc_proc_cache):
            if pid not in active:
                del _cc_proc_cache[pid]
        _cc_proc_cache.update(new_entries)

def cc_proc_cache_snapshot() -> Dict[str, Tuple[str, str]]:
    with _cc_proc_cache_lock:
        return dict(_cc_proc_cache)

def _refresh_tmux_state(now: float) -> None:
    global _tmux_state_cache, _tmux_state_last_refresh
    if now - _tmux_state_last_refresh < _TMUX_REFRESH_INTERVAL:
        return
    _tmux_state_last_refresh = now
    try:
        r = subprocess.run(
            ['tmux', 'list-sessions', '-F', '#{session_name}'],
            capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=3)
        if r.returncode != 0:
            _tmux_state_cache = set()
            return
    except Exception:
        return
    _tmux_state_cache = {line.strip() for line in r.stdout.strip().split('\n') if line.strip()}

def _tmux_session_exists(session_name: str) -> bool:
    return session_name in _tmux_state_cache

def _tmux_window_activity(session: str) -> int:
    try:
        result = subprocess.run(
            ['tmux', 'display-message', '-t', f'{session}:^', '-p', '#{window_activity}'],
            capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=2)
        if result.returncode != 0:
            return 0
        return int(result.stdout.strip())
    except Exception:
        return 0

def _proxy_log_newest_mtime(project_key: str, now: float) -> Optional[float]:
    cached = _proxy_log_mtime_cache.get(project_key)
    if cached is not None and (now - cached[0]) < _PROC_REFRESH_INTERVAL:
        return cached[1]
    result: Optional[float] = None
    if _PROXY_LOG_DIR.is_dir():
        needle = f'_opus_{project_key}_'
        for p in _PROXY_LOG_DIR.glob('api_requests_*.jsonl'):
            if needle in p.stem:
                try:
                    mt = p.stat().st_mtime
                    if result is None or mt > result:
                        result = mt
                except OSError:
                    pass
    _proxy_log_mtime_cache[project_key] = (now, result)
    return result

def _read_hook_state(now: float) -> Dict[str, dict]:
    global _hook_state_cache, _hook_state_last_read
    if now - _hook_state_last_read < _HOOK_REFRESH_INTERVAL:
        return _hook_state_cache
    _hook_state_last_read = now
    try:
        _hook_state_cache = json.loads(_HOOK_STATE_FILE.read_text(encoding='utf-8'))
    except Exception:
        _hook_state_cache = {}
    return _hook_state_cache
