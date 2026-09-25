# INFRASTRUCTURE
import json
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))
from dev.refactoring.live_log_isolation import isolate_home

_HOME_SANDBOX = isolate_home("test_monitor_sweep_sched_")

from dev.refactoring.strand_runner import strand_workflow
from src.menubar import monitor_sweep_scheduler as sched

_NOW = 1_000_000_000.0
_WAIT_DEADLINE_SECS = 3.0
_WAIT_INTERVAL_SECS = 0.01
_SWEEP_THREAD_NAME = 'monitor-sweep'
_STRAND_NAMES = [
    '_test_pure_gate_boundaries',
    '_test_fresh_state_runs',
    '_test_run_1h_ago_does_not_run',
    '_test_run_25h_ago_runs',
    '_test_reentry_guard_blocks_concurrent_trigger',
    '_test_attempt_timestamp_persisted_before_sweep_completes',
]
_TITLE = 'test_monitor_sweep_scheduler'
_REPORT_PATH = Path(__file__).resolve().parents[1] / 'md' / 'test_monitor_sweep_scheduler.md'

# ORCHESTRATOR

def test_monitor_sweep_scheduler_workflow() -> None:
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))

# FUNCTIONS

def _check(desc: str, ok: bool) -> None:
    print(f"  [{'OK  ' if ok else 'FAIL'}] {desc}")
    if not ok:
        raise AssertionError(desc)

@contextmanager
def _isolated_scheduler(run_sweep_stub, seed_last_run_ts=None):
    with tempfile.TemporaryDirectory(prefix="monitor_sweep_gate_") as tmp:
        state_file = Path(tmp) / "monitor_sweep_state.json"
        if seed_last_run_ts is not None:
            state_file.write_text(json.dumps({"last_run_ts": seed_last_run_ts}), encoding="utf-8")
        with patch.object(sched, 'MONITOR_SWEEP_STATE_FILE', state_file), \
                patch.object(sched, '_last_sweep_ts', None), \
                patch.object(sched, '_sweep_in_progress', False), \
                patch.object(sched, '_run_sweep', run_sweep_stub):
            try:
                yield state_file
            finally:
                _wait_until(lambda: not _sweep_threads(), _WAIT_DEADLINE_SECS)

def _sweep_threads() -> list:
    return [t for t in threading.enumerate() if t.name == _SWEEP_THREAD_NAME]

def _wait_until(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(_WAIT_INTERVAL_SECS)
    return predicate()

def _test_pure_gate_boundaries() -> None:
    _check("fresh state (last_ts=0.0) is due",
          sched._is_sweep_due(0.0, _NOW))
    _check("a run 1h ago is NOT due",
          not sched._is_sweep_due(_NOW - 3600, _NOW))
    _check("a run 25h ago IS due",
          sched._is_sweep_due(_NOW - 25 * 3600, _NOW))
    _check("exactly 24h ago IS due (>= boundary, not >)",
          sched._is_sweep_due(_NOW - sched.SWEEP_INTERVAL_SECS, _NOW))

def _test_fresh_state_runs() -> None:
    fired = _invoke_with_isolated_state(seed_last_run_ts=None, now=_NOW)
    _check("fresh state (no state file) triggers a sweep attempt", fired)

def _test_run_1h_ago_does_not_run() -> None:
    fired = _invoke_with_isolated_state(seed_last_run_ts=_NOW - 3600, now=_NOW)
    _check("a run 1h ago does NOT trigger a sweep attempt", not fired)

def _test_run_25h_ago_runs() -> None:
    fired = _invoke_with_isolated_state(seed_last_run_ts=_NOW - 25 * 3600, now=_NOW)
    _check("a run 25h ago DOES trigger a sweep attempt", fired)

def _test_reentry_guard_blocks_concurrent_trigger() -> None:
    release = threading.Event()
    calls = []

    def _blocking_stub():
        calls.append(1)
        release.wait(timeout=_WAIT_DEADLINE_SECS)
        sched._sweep_in_progress = False

    with _isolated_scheduler(_blocking_stub):
        try:
            sched.maybe_run_sweep_workflow(_NOW)
            _wait_until(lambda: len(calls) == 1, _WAIT_DEADLINE_SECS)
            sched.maybe_run_sweep_workflow(_NOW + 1)
            _check("a concurrent tick while a sweep is in-progress does not re-trigger",
                  len(calls) == 1 and len(_sweep_threads()) == 1)
        finally:
            release.set()

def _test_attempt_timestamp_persisted_before_sweep_completes() -> None:
    release = threading.Event()

    def _slow_stub():
        release.wait(timeout=_WAIT_DEADLINE_SECS)
        sched._sweep_in_progress = False

    with _isolated_scheduler(_slow_stub) as state_file:
        try:
            sched.maybe_run_sweep_workflow(_NOW)
            recorded = json.loads(state_file.read_text(encoding='utf-8'))['last_run_ts']
            _check("attempt timestamp is on disk before the sweep itself finishes",
                  recorded == _NOW and bool(_sweep_threads()))
        finally:
            release.set()

def _invoke_with_isolated_state(seed_last_run_ts, now: float) -> bool:
    fired = threading.Event()

    def _fast_stub():
        fired.set()
        sched._sweep_in_progress = False

    with _isolated_scheduler(_fast_stub, seed_last_run_ts):
        sched.maybe_run_sweep_workflow(now)
        return _sweep_fired(fired)

def _sweep_fired(fired: threading.Event) -> bool:
    for thread in _sweep_threads():
        thread.join(timeout=_WAIT_DEADLINE_SECS)
    return fired.is_set()


if __name__ == "__main__":
    test_monitor_sweep_scheduler_workflow()
