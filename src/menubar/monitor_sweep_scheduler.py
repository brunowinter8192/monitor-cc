# INFRASTRUCTURE
import json
import os
import threading

from .paths import MONITOR_SWEEP_STATE_FILE, MONITOR_CC_ROOT
from .menubar_log import log_menubar

SWEEP_INTERVAL_SECS = 24 * 3600

_last_sweep_ts = None
_sweep_in_progress = False

# ORCHESTRATOR

def maybe_run_sweep_workflow(now: float) -> None:
    global _last_sweep_ts, _sweep_in_progress
    if _sweep_in_progress:
        return
    if _last_sweep_ts is None:
        _last_sweep_ts = _read_last_sweep_ts()
    if not _is_sweep_due(_last_sweep_ts, now):
        return
    _last_sweep_ts = now
    _write_last_sweep_ts(now)
    _sweep_in_progress = True
    threading.Thread(target=_run_sweep, name='monitor-sweep', daemon=True).start()

# FUNCTIONS

def _is_sweep_due(last_ts: float, now: float) -> bool:
    return now - last_ts >= SWEEP_INTERVAL_SECS

def _read_last_sweep_ts() -> float:
    try:
        return float(json.loads(MONITOR_SWEEP_STATE_FILE.read_text(encoding='utf-8'))['last_run_ts'])
    except Exception:
        return 0.0

def _write_last_sweep_ts(ts: float) -> None:
    try:
        tmp = MONITOR_SWEEP_STATE_FILE.with_name(MONITOR_SWEEP_STATE_FILE.name + '.tmp')
        tmp.write_text(json.dumps({'last_run_ts': ts}), encoding='utf-8')
        os.replace(tmp, MONITOR_SWEEP_STATE_FILE)
    except Exception as e:
        log_menubar('monitor_sweep', f'state-write FAILED {e}')

def _run_sweep() -> None:
    global _sweep_in_progress
    try:
        os.environ.setdefault('MONITOR_CC_ROOT', str(MONITOR_CC_ROOT))
        from ..monitor_janitor import sweep_workflow
        results = sweep_workflow()
        killed = sum(1 for r in results if r['killed'])
        log_menubar('monitor_sweep',
                     f'ran sessions={len(results)} killed={killed} spared={len(results) - killed}')
    except Exception as e:
        log_menubar('monitor_sweep', f'FAILED {e}')
    finally:
        _sweep_in_progress = False
