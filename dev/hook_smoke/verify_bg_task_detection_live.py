# INFRASTRUCTURE
import os
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.menubar import proc_cache

_POLL_DEADLINE_SECS = 10.0
_POLL_INTERVAL_SECS = 0.05


# ORCHESTRATOR

def verify_bg_task_detection_live_workflow() -> None:
    detected, cleared = _run_live_roundtrip()
    print_detected_while_open(detected, cleared)
    print_verdict(detected, cleared)
    exit_with_status(detected, cleared)


# FUNCTIONS

def _run_live_roundtrip() -> tuple:
    with _scratch_tasks_base() as base:
        tasks_dir = base / 'enc_probe' / 'sess_probe' / 'tasks'
        tasks_dir.mkdir(parents=True)
        out_file = tasks_dir / 'probe.output'
        proc = subprocess.Popen(
            ['bash', '-c', f'exec > "{out_file}" 2>&1; for i in $(seq 1 100); do echo progress; sleep 0.5; done'],
            start_new_session=True)
        try:
            during = _wait_until(lambda: _refreshed_active_bg('enc_probe', 'sess_probe'), _POLL_DEADLINE_SECS)
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait(timeout=5)
            after = _wait_until(lambda: not _refreshed_active_bg('enc_probe', 'sess_probe'), _POLL_DEADLINE_SECS)
        finally:
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait(timeout=5)
    return during, after


@contextmanager
def _scratch_tasks_base():
    with tempfile.TemporaryDirectory(prefix='bg_probe_') as tmp:
        base = Path(tmp).resolve()
        with patch.object(proc_cache, '_TASKS_BASE', base), \
                patch.object(proc_cache, '_TASKS_BASE_REAL', str(base)), \
                patch.object(proc_cache, '_bg_task_open_paths', set()), \
                patch.object(proc_cache, '_bg_task_holder_pids', {}), \
                patch.object(proc_cache, '_bg_task_last_refresh', 0.0):
            yield base


def _wait_until(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(_POLL_INTERVAL_SECS)
    return predicate()


def _refreshed_active_bg(encoded_dir: str, session_id: str) -> bool:
    proc_cache._bg_task_last_refresh = 0.0
    proc_cache._refresh_bg_task_cache(time.time())
    return proc_cache._has_active_bg(encoded_dir, session_id)


def print_detected_while_open(detected, cleared):
    print(f"detected_while_open={detected} (want True), cleared_after_close={cleared} (want True)")


def print_verdict(detected, cleared):
    print("VERDICT: " + ("PASS" if detected and cleared else "FAIL"))


def exit_with_status(detected, cleared):
    sys.exit(0 if detected and cleared else 1)


if __name__ == "__main__":
    verify_bg_task_detection_live_workflow()
