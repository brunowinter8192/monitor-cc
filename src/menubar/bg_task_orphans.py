# INFRASTRUCTURE
import os
import signal
import subprocess
from typing import Dict, List, Tuple

from .proc_cache import _cc_proc_cache, bg_task_holder_pids_snapshot
from .menubar_log import log_menubar, log_menubar_change

_ANCESTRY_MAX_HOPS = 5
_ORPHAN_SCAN_INTERVAL = 10.0

_last_scan_ts: float = 0.0
_logged_orphan_pids: set = set()

# ORCHESTRATOR

def scan_bg_task_orphans(now: float) -> None:
    if not _scan_due(now):
        return
    _mark_scanned(now)
    holders = _collect_holder_pairs()
    if not holders:
        _forget_all_logged_orphans()
        return
    ppid_map = _build_ppid_map()
    orphans = _find_orphans(holders, ppid_map)
    _log_new_orphans(orphans)
    _kill_confirmed_orphans(orphans)

# FUNCTIONS

def _scan_due(now: float) -> bool:
    return now - _last_scan_ts >= _ORPHAN_SCAN_INTERVAL

def _mark_scanned(now: float) -> None:
    global _last_scan_ts
    _last_scan_ts = now

def _collect_holder_pairs() -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for path, pids in bg_task_holder_pids_snapshot().items():
        for pid in pids:
            pairs.append((pid, path))
    return pairs

def _forget_all_logged_orphans() -> None:
    _logged_orphan_pids.clear()

def _build_ppid_map() -> Dict[str, str]:
    try:
        r = subprocess.run(['ps', '-A', '-o', 'pid=,ppid='],
                            capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=3)
    except Exception as exc:
        log_menubar_change('bg_orphan', 'ps_ppid_map', f'ps failed err={exc!r}')
        return {}
    log_menubar_change('bg_orphan', 'ps_ppid_map', None)
    ppid_map: Dict[str, str] = {}
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            ppid_map[parts[0]] = parts[1]
    return ppid_map

def _find_orphans(pairs: List[Tuple[str, str]],
                   ppid_map: Dict[str, str]) -> List[Tuple[str, str]]:
    return [(pid, path) for pid, path in pairs
            if _classify_bg_task_holder(pid, ppid_map) == 'orphan']

def _classify_bg_task_holder(holder_pid: str, ppid_map: Dict[str, str]) -> str:
    ancestor_pid = holder_pid
    for _ in range(_ANCESTRY_MAX_HOPS):
        if ancestor_pid in _cc_proc_cache:
            return 'live'
        if ancestor_pid == '1':
            return 'orphan'
        parent_pid = ppid_map.get(ancestor_pid)
        if parent_pid is None:
            return 'unknown'
        ancestor_pid = parent_pid
    return 'unknown'

def _log_new_orphans(orphans: List[Tuple[str, str]]) -> None:
    current_pids = {pid for pid, _ in orphans}
    for pid, path in orphans:
        if pid not in _logged_orphan_pids:
            log_menubar('bg_orphan', f'orphan_detected pid={pid} file={path}')
    _logged_orphan_pids.clear()
    _logged_orphan_pids.update(current_pids)

def _kill_confirmed_orphans(orphans: List[Tuple[str, str]]) -> None:
    for pid, path in orphans:
        if _pid_still_holds_file(pid, path):
            _kill_orphan(pid, path)
        else:
            log_menubar('bg_orphan', f'kill_skipped pid={pid} file={path} reason=reconfirm_failed')

def _pid_still_holds_file(pid: str, expected_path: str) -> bool:
    try:
        r = subprocess.run(['lsof', '-p', pid, '-Fn'],
                            capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=2)
    except Exception:
        return False
    for line in r.stdout.splitlines():
        if line.startswith('n') and line[1:] == expected_path:
            return True
    return False

def _kill_orphan(pid: str, path: str) -> None:
    try:
        os.kill(int(pid), signal.SIGTERM)
    except (ProcessLookupError, ValueError, OSError) as e:
        log_menubar('bg_orphan', f'kill_failed pid={pid} file={path} err={repr(e)}')
        return
    log_menubar('bg_orphan', f'kill_action pid={pid} file={path}')
