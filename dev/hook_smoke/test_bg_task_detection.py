# INFRASTRUCTURE
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
from menubar import proc_cache

_SCRATCH = proc_cache._TASKS_BASE / '__test_bg_probe__'


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

def _case_match_true() -> tuple:
    proc_cache._bg_task_open_paths = {
        f'{proc_cache._TASKS_BASE_REAL}/enc1/sess1/tasks/abc.output'
    }
    got = proc_cache._has_active_bg('enc1', 'sess1')
    return got is True, f'want True, got {got}'


def _case_no_match_false() -> tuple:
    proc_cache._bg_task_open_paths = {
        f'{proc_cache._TASKS_BASE_REAL}/enc1/other_sess/tasks/abc.output'
    }
    got = proc_cache._has_active_bg('enc1', 'sess1')
    return got is False, f'want False, got {got}'


def _case_prefix_boundary() -> tuple:
    proc_cache._bg_task_open_paths = {
        f'{proc_cache._TASKS_BASE_REAL}/enc1/sess12/tasks/abc.output'
    }
    got = proc_cache._has_active_bg('enc1', 'sess1')
    return got is False, f'want False (no session-id prefix collision), got {got}'


def _case_real_lsof_roundtrip() -> tuple:
    tasks_dir = _SCRATCH / 'integration_sess' / 'tasks'
    tasks_dir.mkdir(parents=True, exist_ok=True)
    out_file = tasks_dir / 'probe.output'
    proc = subprocess.Popen(
        ['bash', '-c', f'exec > "{out_file}" 2>&1; for i in $(seq 1 20); do echo progress; sleep 0.5; done'],
        start_new_session=True)
    try:
        time.sleep(1.0)
        proc_cache._bg_task_last_refresh = 0.0
        proc_cache._refresh_bg_task_cache(time.time())
        during = proc_cache._has_active_bg('__test_bg_probe__', 'integration_sess')
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.wait(timeout=5)
        time.sleep(0.5)
        proc_cache._bg_task_last_refresh = 0.0
        proc_cache._refresh_bg_task_cache(time.time())
        after = proc_cache._has_active_bg('__test_bg_probe__', 'integration_sess')
        ok = during is True and after is False
        return ok, f'during={during} (want True), after={after} (want False)'
    finally:
        if proc.poll() is None:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        shutil.rmtree(_SCRATCH, ignore_errors=True)


def _case_fail_open() -> tuple:
    real_run = subprocess.run
    proc_cache._bg_task_open_paths = {'stale/should/stay'}
    proc_cache._bg_task_last_refresh = 0.0

    def _raising_run(*a, **kw):
        raise OSError('lsof unavailable (synthetic)')

    subprocess.run = _raising_run
    try:
        proc_cache._refresh_bg_task_cache(time.time())
        got = proc_cache._has_active_bg('enc1', 'sess1')
        stale_kept = proc_cache._bg_task_open_paths == {'stale/should/stay'}
        return (got is False and stale_kept), f'got={got} (want False), stale_kept={stale_kept} (want True)'
    finally:
        subprocess.run = real_run


def _case_ttl_gate() -> tuple:
    calls = []
    real_run = subprocess.run

    def _counting_run(*a, **kw):
        calls.append(1)
        return real_run(['true'], capture_output=True, text=True)

    subprocess.run = _counting_run
    try:
        now = time.time()
        proc_cache._bg_task_last_refresh = 0.0
        proc_cache._refresh_bg_task_cache(now)
        proc_cache._refresh_bg_task_cache(now + 0.1)
        return len(calls) == 1, f'lsof invocations={len(calls)} (want 1)'
    finally:
        subprocess.run = real_run


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
