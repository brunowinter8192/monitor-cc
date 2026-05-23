# INFRASTRUCTURE
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
# From paths.py: APP_SUPPORT-relative hook state path + orchestrator signal file
from .paths import HOOKS_FILE as _HOOK_STATE_FILE, ORCHESTRATOR_SIGNALS_FILE as _ORCHESTRATOR_SIGNALS_FILE

_PROC_REFRESH_INTERVAL = 10.0   # seconds between ps/lsof cache rebuilds (expensive: ps -A + lsof)
_HOOK_REFRESH_INTERVAL = 1.0    # seconds between hooks.json reads (cheap: 1KB JSON; MUST be < POLL_INTERVAL=1.5s for tick-freshness; see decisions/OldThemes/menubar_signal_grace/initial_design.md)
_TMUX_REFRESH_INTERVAL = 3.0    # seconds between tmux list-sessions polls
ORCHESTRATOR_SIGNAL_BUFFER_SECS = 5.0   # workers with orchestrator_signals.json timestamp newer than this are treated as 'working' for auto-abort (covers send → UserPromptSubmit-hook latency)
_TASKS_BASE = Path(f"/tmp/claude-{os.getuid()}")
# central log dir — proxy lives in Monitor_CC and intercepts all CC sessions via ANTHROPIC_BASE_URL
_PROXY_LOG_DIR = Path('/Users/brunowinter2000/Documents/ai/Monitor_CC/src/logs')

# pid→(tty, cwd) cache for CC processes; incremental: lsof only on new PIDs
_cc_proc_cache: Dict[str, Tuple[str, str]] = {}
_cc_proc_last_refresh: float = 0.0

# session_name set (alive check only); one list-sessions call per 3s
_tmux_state_cache: set = set()
_tmux_state_last_refresh: float = 0.0

# opus_<project_key>→(checked_at: float, mtime: float|None); TTL = _PROC_REFRESH_INTERVAL
_proxy_log_mtime_cache: Dict[str, Tuple[float, Optional[float]]] = {}

# Hook state file written by hook_writer.py; {session_id → {status, cwd, updated_ts}}
# cached contents + last-read timestamp; TTL = _HOOK_REFRESH_INTERVAL (1s, not coupled to proc cache)
_hook_state_cache: Dict[str, dict] = {}
_hook_state_last_read: float = 0.0

# Orchestrator-signal file written by worker-cli send; {tmux_session_name → send_unix_ts}
# cached contents + last-read timestamp; TTL = _HOOK_REFRESH_INTERVAL (same urgency as hook state)
_orchestrator_signal_cache: Dict[str, float] = {}
_orchestrator_signal_last_read: float = 0.0

# ORCHESTRATOR

# (No single orchestrator — module exposes independent cache-refresh entry points)

# FUNCTIONS

# True if any *.output file in the session tasks dir has 0 bytes (= in-progress task)
def _has_active_bg(encoded_dir: str, session_id: str) -> bool:
    tasks_dir = _TASKS_BASE / encoded_dir / session_id / 'tasks'
    if not tasks_dir.exists():
        return False
    try:
        return any(f.stat().st_size == 0 for f in tasks_dir.glob('*.output') if f.is_file())
    except OSError:
        return False

# Update pid→(tty,cwd) cache incrementally: drop gone PIDs, lsof only for new ones
def _refresh_cc_proc_cache(now: float) -> None:
    global _cc_proc_last_refresh
    if now - _cc_proc_last_refresh < _PROC_REFRESH_INTERVAL:
        return
    _cc_proc_last_refresh = now
    try:
        r = subprocess.run(['ps', '-A', '-o', 'pid,tty,comm'],
                           capture_output=True, text=True, timeout=3)
    except Exception:
        return
    # Build {pid: tty} for active CC processes with valid TTY
    active: Dict[str, str] = {}
    for line in r.stdout.strip().split('\n')[1:]:
        parts = line.split(None, 2)
        if len(parts) == 3 and 'claude' in parts[2].lower() and parts[1] != '??':
            active[parts[0].strip()] = parts[1].strip()
    # Drop entries for gone PIDs
    for pid in list(_cc_proc_cache):
        if pid not in active:
            del _cc_proc_cache[pid]
    # lsof only for PIDs not yet in cache (cwd is stable after launch)
    for pid, tty in active.items():
        if pid in _cc_proc_cache:
            continue
        try:
            r2 = subprocess.run(['lsof', '-a', '-d', 'cwd', '-p', pid],
                                 capture_output=True, text=True, timeout=2)
            for line in r2.stdout.strip().split('\n'):
                if line.startswith('COMMAND') or not line:
                    continue
                fields = line.split(None, 8)
                if len(fields) == 9:
                    _cc_proc_cache[pid] = (tty, fields[8])
                    break
        except Exception:
            pass

# Refresh tmux session state via one list-sessions call; no-op within 3s TTL
def _refresh_tmux_state(now: float) -> None:
    global _tmux_state_cache, _tmux_state_last_refresh
    if now - _tmux_state_last_refresh < _TMUX_REFRESH_INTERVAL:
        return
    _tmux_state_last_refresh = now
    try:
        r = subprocess.run(
            ['tmux', 'list-sessions', '-F', '#{session_name}'],
            capture_output=True, text=True, timeout=3)
        if r.returncode != 0:
            _tmux_state_cache = set()
            return
    except Exception:
        return
    _tmux_state_cache = {line.strip() for line in r.stdout.strip().split('\n') if line.strip()}

# True if session_name appears in the tmux state cache (= exists)
def _tmux_session_exists(session_name: str) -> bool:
    return session_name in _tmux_state_cache

# Return newest mtime of proxy logs matching opus_<project_key>; None if no match or dir missing
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

# Return hook state dict {session_id: {status, cwd, updated_ts}}; cached with _HOOK_REFRESH_INTERVAL TTL
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


# Return orchestrator-signal dict {tmux_session_name: send_unix_ts}; cached with _HOOK_REFRESH_INTERVAL TTL.
# Written by worker-cli (iterative-dev plugin) BEFORE each tmux send-keys. The menubar treats workers
# with `now - signal_ts < ORCHESTRATOR_SIGNAL_BUFFER_SECS` as 'working' for auto-abort decisions,
# eliminating the prompt-send → hook-fire race that previously killed Opus background timers.
def _read_orchestrator_signals(now: float) -> Dict[str, float]:
    global _orchestrator_signal_cache, _orchestrator_signal_last_read
    if now - _orchestrator_signal_last_read < _HOOK_REFRESH_INTERVAL:
        return _orchestrator_signal_cache
    _orchestrator_signal_last_read = now
    try:
        raw = json.loads(_ORCHESTRATOR_SIGNALS_FILE.read_text(encoding='utf-8'))
        _orchestrator_signal_cache = {k: float(v) for k, v in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
        _orchestrator_signal_cache = {}
    return _orchestrator_signal_cache
