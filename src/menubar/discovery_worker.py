# INFRASTRUCTURE
import threading
import time
from typing import Dict, List, NamedTuple

from .discover import list_alive_sessions, get_last_session_timings, SessionInfo
from .bg_timer import _scan_bg_sleep_timers, BgSleepInfo
from .bg_task_orphans import scan_bg_task_orphans
from .menubar_log import log_menubar, log_menubar_change

REFRESH_INTERVAL = 1.5
BG_REFRESH_LATENCY_THRESHOLD_MS = 200

class DiscoverySnapshot(NamedTuple):
    sessions:      List[SessionInfo]
    bg_by_project: Dict[str, BgSleepInfo]
    ts:            float

_lock = threading.Lock()
_snapshot = DiscoverySnapshot(sessions=[], bg_by_project={}, ts=0.0)
_started = False

# ORCHESTRATOR

def start_discovery_worker() -> None:
    global _started
    if _started:
        return
    _started = True
    t = threading.Thread(target=_worker_loop, name='discovery-worker', daemon=True)
    t.start()

def get_latest_snapshot() -> DiscoverySnapshot:
    with _lock:
        return _snapshot

# FUNCTIONS

def _worker_loop() -> None:
    global _snapshot
    while True:
        cycle_t0 = time.monotonic()
        try:
            sessions = list_alive_sessions()
            cwd_to_project = {s.cwd: s.project_name for s in sessions if not s.is_worker and s.cwd}
            bg_by_project = _scan_bg_sleep_timers(cwd_to_project)
            scan_bg_task_orphans(time.time())
            with _lock:
                _snapshot = DiscoverySnapshot(sessions=sessions, bg_by_project=bg_by_project,
                                               ts=time.time())
            _log_if_slow(cycle_t0)
            log_menubar_change('discovery', 'worker_cycle', None)
        except Exception as e:
            log_menubar_change('discovery', 'worker_cycle', f'worker cycle error err={e!r}')
        elapsed = time.monotonic() - cycle_t0
        time.sleep(max(0.0, REFRESH_INTERVAL - elapsed))

def _log_if_slow(cycle_t0: float) -> None:
    total_ms = (time.monotonic() - cycle_t0) * 1000
    if total_ms > BG_REFRESH_LATENCY_THRESHOLD_MS:
        phases = get_last_session_timings()
        breakdown = ' '.join(f'{k}={v * 1000:.0f}ms' for k, v in phases.items())
        log_menubar('latency', f'bg_refresh total={total_ms:.0f}ms {breakdown}')
