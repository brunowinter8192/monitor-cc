# INFRASTRUCTURE
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from src.menubar import monitor_sweep_scheduler as sched

_NOW = 1_000_000_000.0

# ORCHESTRATOR

def test_monitor_sweep_scheduler_workflow() -> None:
    failures = []
    _test_pure_gate_boundaries(failures)
    _test_fresh_state_runs(failures)
    _test_run_1h_ago_does_not_run(failures)
    _test_run_25h_ago_runs(failures)
    _test_reentry_guard_blocks_concurrent_trigger(failures)
    _test_attempt_timestamp_persisted_before_sweep_completes(failures)

    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for desc in failures:
            print(f"  - {desc}")
        sys.exit(1)
    print("All checks passed.")

# FUNCTIONS

def _check(failures: list, desc: str, ok: bool) -> None:
    print(f"  [{'OK  ' if ok else 'FAIL'}] {desc}")
    if not ok:
        failures.append(desc)

def _test_pure_gate_boundaries(failures: list) -> None:
    _check(failures, "fresh state (last_ts=0.0) is due",
          sched._is_sweep_due(0.0, _NOW))
    _check(failures, "a run 1h ago is NOT due",
          not sched._is_sweep_due(_NOW - 3600, _NOW))
    _check(failures, "a run 25h ago IS due",
          sched._is_sweep_due(_NOW - 25 * 3600, _NOW))
    _check(failures, "exactly 24h ago IS due (>= boundary, not >)",
          sched._is_sweep_due(_NOW - sched.SWEEP_INTERVAL_SECS, _NOW))

def _test_fresh_state_runs(failures: list) -> None:
    fired = _invoke_with_isolated_state(seed_last_run_ts=None, now=_NOW)
    _check(failures, "fresh state (no state file) triggers a sweep attempt", fired)

def _test_run_1h_ago_does_not_run(failures: list) -> None:
    fired = _invoke_with_isolated_state(seed_last_run_ts=_NOW - 3600, now=_NOW)
    _check(failures, "a run 1h ago does NOT trigger a sweep attempt", not fired)

def _test_run_25h_ago_runs(failures: list) -> None:
    fired = _invoke_with_isolated_state(seed_last_run_ts=_NOW - 25 * 3600, now=_NOW)
    _check(failures, "a run 25h ago DOES trigger a sweep attempt", fired)

def _test_reentry_guard_blocks_concurrent_trigger(failures: list) -> None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="monitor_sweep_gate_"))
    state_file = tmp_dir / "monitor_sweep_state.json"
    orig_state_file, orig_last_ts, orig_in_progress = (
        sched.MONITOR_SWEEP_STATE_FILE, sched._last_sweep_ts, sched._sweep_in_progress)
    sched.MONITOR_SWEEP_STATE_FILE = state_file
    sched._last_sweep_ts = None
    release = threading.Event()
    calls = []
    sched._sweep_in_progress = False

    def _blocking_stub():
        calls.append(1)
        release.wait(timeout=3)
        sched._sweep_in_progress = False

    orig_run_sweep = sched._run_sweep
    sched._run_sweep = _blocking_stub
    try:
        sched.maybe_run_sweep_workflow(_NOW)
        time.sleep(0.1)
        sched.maybe_run_sweep_workflow(_NOW + 1)
        _check(failures, "a concurrent tick while a sweep is in-progress does not re-trigger",
              len(calls) == 1)
    finally:
        release.set()
        _wait_until(lambda: not sched._sweep_in_progress, timeout=3)
        sched._run_sweep = orig_run_sweep
        sched.MONITOR_SWEEP_STATE_FILE, sched._last_sweep_ts, sched._sweep_in_progress = (
            orig_state_file, orig_last_ts, orig_in_progress)

def _test_attempt_timestamp_persisted_before_sweep_completes(failures: list) -> None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="monitor_sweep_gate_"))
    state_file = tmp_dir / "monitor_sweep_state.json"
    orig_state_file, orig_last_ts, orig_in_progress = (
        sched.MONITOR_SWEEP_STATE_FILE, sched._last_sweep_ts, sched._sweep_in_progress)
    sched.MONITOR_SWEEP_STATE_FILE = state_file
    sched._last_sweep_ts = None
    sched._sweep_in_progress = False
    release = threading.Event()

    def _slow_stub():
        release.wait(timeout=3)
        sched._sweep_in_progress = False

    orig_run_sweep = sched._run_sweep
    sched._run_sweep = _slow_stub
    try:
        sched.maybe_run_sweep_workflow(_NOW)
        time.sleep(0.1)
        recorded = json.loads(state_file.read_text(encoding='utf-8'))['last_run_ts']
        _check(failures, "attempt timestamp is on disk before the sweep itself finishes",
              recorded == _NOW)
    finally:
        release.set()
        _wait_until(lambda: not sched._sweep_in_progress, timeout=3)
        sched._run_sweep = orig_run_sweep
        sched.MONITOR_SWEEP_STATE_FILE, sched._last_sweep_ts, sched._sweep_in_progress = (
            orig_state_file, orig_last_ts, orig_in_progress)

def _invoke_with_isolated_state(seed_last_run_ts, now: float) -> bool:
    tmp_dir = Path(tempfile.mkdtemp(prefix="monitor_sweep_gate_"))
    state_file = tmp_dir / "monitor_sweep_state.json"
    if seed_last_run_ts is not None:
        state_file.write_text(json.dumps({"last_run_ts": seed_last_run_ts}), encoding="utf-8")

    orig_state_file, orig_last_ts, orig_in_progress, orig_run_sweep = (
        sched.MONITOR_SWEEP_STATE_FILE, sched._last_sweep_ts, sched._sweep_in_progress,
        sched._run_sweep)
    sched.MONITOR_SWEEP_STATE_FILE = state_file
    sched._last_sweep_ts = None
    sched._sweep_in_progress = False
    fired = threading.Event()

    def _fast_stub():
        fired.set()
        sched._sweep_in_progress = False

    sched._run_sweep = _fast_stub
    try:
        sched.maybe_run_sweep_workflow(now)
        return fired.wait(timeout=2)
    finally:
        sched._run_sweep = orig_run_sweep
        sched.MONITOR_SWEEP_STATE_FILE, sched._last_sweep_ts, sched._sweep_in_progress = (
            orig_state_file, orig_last_ts, orig_in_progress)

def _wait_until(predicate, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)


if __name__ == "__main__":
    test_monitor_sweep_scheduler_workflow()
