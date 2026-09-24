# INFRASTRUCTURE
import os
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.menubar import proc_cache

_POLL_DEADLINE_SECS = 10.0
_POLL_INTERVAL_SECS = 0.05


# ORCHESTRATOR

def test_bg_task_detection_workflow() -> None:
    failures = []
    for desc, fn in CASES:
        ok, detail = fn()
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {desc}")
        if not ok:
            print(f"           {detail}")
            failures.append(desc)
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for desc in failures:
            print(f"  - {desc}")
        sys.exit(1)
    print(f"All {len(CASES)} tests passed.")


# FUNCTIONS

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


def _case_match_true() -> tuple:
    with _scratch_tasks_base():
        proc_cache._bg_task_open_paths = {
            f'{proc_cache._TASKS_BASE_REAL}/enc1/sess1/tasks/abc.output'
        }
        got = proc_cache._has_active_bg('enc1', 'sess1')
    return got is True, f'want True, got {got}'


def _case_no_match_false() -> tuple:
    with _scratch_tasks_base():
        proc_cache._bg_task_open_paths = {
            f'{proc_cache._TASKS_BASE_REAL}/enc1/other_sess/tasks/abc.output'
        }
        got = proc_cache._has_active_bg('enc1', 'sess1')
    return got is False, f'want False, got {got}'


def _case_prefix_boundary() -> tuple:
    with _scratch_tasks_base():
        proc_cache._bg_task_open_paths = {
            f'{proc_cache._TASKS_BASE_REAL}/enc1/sess12/tasks/abc.output'
        }
        got = proc_cache._has_active_bg('enc1', 'sess1')
    return got is False, f'want False (no session-id prefix collision), got {got}'


def _case_real_lsof_roundtrip() -> tuple:
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
    return during and after, f'detected_while_open={during} (want True), cleared_after_close={after} (want True)'


def _case_fail_open() -> tuple:
    def _raising_run(*a, **kw):
        raise OSError('lsof unavailable (synthetic)')

    with _scratch_tasks_base(), patch.object(proc_cache, 'subprocess', SimpleNamespace(run=_raising_run)):
        proc_cache._bg_task_open_paths = {'stale/should/stay'}
        proc_cache._bg_task_last_refresh = 0.0
        proc_cache._refresh_bg_task_cache(time.time())
        got = proc_cache._has_active_bg('enc1', 'sess1')
        stale_kept = proc_cache._bg_task_open_paths == {'stale/should/stay'}
    return (got is False and stale_kept), f'got={got} (want False), stale_kept={stale_kept} (want True)'


def _case_ttl_gate() -> tuple:
    calls = []

    def _counting_run(*a, **kw):
        calls.append(1)
        return SimpleNamespace(stdout='', returncode=0)

    with _scratch_tasks_base(), patch.object(proc_cache, 'subprocess', SimpleNamespace(run=_counting_run)):
        now = time.time()
        proc_cache._bg_task_last_refresh = 0.0
        proc_cache._refresh_bg_task_cache(now)
        proc_cache._refresh_bg_task_cache(now + 0.1)
    return len(calls) == 1, f'lsof invocations={len(calls)} (want 1)'


CASES = [
    ('open path under session tasks dir -> True',            _case_match_true),
    ('no open path for session -> False',                     _case_no_match_false),
    ('session-id prefix collision does not false-positive',   _case_prefix_boundary),
    ('real subprocess writer: detected while open, not after', _case_real_lsof_roundtrip),
    ('lsof failure fails open, keeps prior snapshot',         _case_fail_open),
    ('TTL gate: second call inside window is a no-op',        _case_ttl_gate),
]


if __name__ == "__main__":
    test_bg_task_detection_workflow()
