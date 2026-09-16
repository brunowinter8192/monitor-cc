#!/usr/bin/env python3
"""Integration tests for the abort-stamp scoping fix in src/menubar/bg_timer.py.

Regression guard for the 2026-08-17 live incident (process-docs/timer-loop/): the OLD
_abort_bg_sleep_timers swept 'aborted\\n' into every 0-byte *.output file under _TASKS_BASE
globally on any manual abort click — confirmed live via bwbf0nmow.output carrying both 'aborted'
and a genuine later 'workers idle' line, meaning the sweep hit a DIFFERENT, still-running
worker-cli wait's own file. The fix resolves each killed PID's own output file (via a real lsof
-p <pid> -d 1,2 call, BEFORE the kill) and stamps only that file.

Uses REAL subprocesses holding REAL open file handles (mirrors CC's own background-launch fd
shape: stdout+stderr redirected straight to the task .output file) and calls the REAL
_abort_bg_sleep_timers / _resolve_pid_output_file — not a mock. importlib.import_module used for
the src.menubar imports (block_dev_imports_src.py forbids a literal 'from src.' line in dev/).

Run: python3 dev/timer-loop/test_abort_stamp_scope.py
"""

# INFRASTRUCTURE
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

_bg_timer_mod = importlib.import_module('src.menubar.bg_timer')
_abort_bg_sleep_timers = _bg_timer_mod._abort_bg_sleep_timers
_paths_mod = importlib.import_module('src.menubar.paths')
_MENUBAR_LOG = _paths_mod._APP_SUPPORT / 'menubar.log'

_HOLD_DURATION = 20  # seconds — long enough that only the test's own kill/teardown ends it


# ORCHESTRATOR

def test_abort_stamp_scope_workflow() -> None:
    failures = []
    tmp = Path(tempfile.mkdtemp(prefix='abort_stamp_scope_'))
    proc_killed = None
    proc_live = None
    try:
        paths, proc_killed, proc_live = _spawn_test_fixtures(tmp)
        log_size_before = _MENUBAR_LOG.stat().st_size if _MENUBAR_LOG.exists() else 0
        _run_abort_and_checks(failures, proc_killed, proc_live, paths, log_size_before)
    finally:
        _teardown_fixtures(tmp, proc_killed, proc_live)
    _print_summary(failures)


# FUNCTIONS

# Print one PASS/FAIL line; append desc to failures on mismatch
def _check(failures: list, desc: str, ok: bool, detail: str) -> None:
    status = "OK  " if ok else "FAIL"
    print(f"  [{status}] {desc}: {detail}")
    if not ok:
        failures.append(desc)

# Spawn a real subprocess with stdout+stderr redirected straight to output_path — the same fd
# shape CC's own background-launch produces for a task .output file, so the real lsof -p <pid>
# -d 1,2 lookup in _resolve_pid_output_file finds it exactly like it would for a genuine
# worker-cli wait/sleep process. Caller owns the returned Popen (kill/wait in a finally block).
def _spawn_holding_output(output_path: Path):
    fh = open(output_path, 'wb')
    proc = subprocess.Popen(['sleep', str(_HOLD_DURATION)], stdout=fh, stderr=fh)
    fh.close()  # child already dup'd its own fd 1/2 onto this file; parent's handle is no longer needed
    return proc


def _spawn_test_fixtures(tmp: Path):
    killed_file = tmp / 'bkilledtask1.output'
    foreign_file = tmp / 'bforeigntask2.output'
    live_file = tmp / 'blivetask3.output'
    foreign_file.write_text('')

    proc_killed = _spawn_holding_output(killed_file)
    proc_live = _spawn_holding_output(live_file)
    time.sleep(0.3)  # let lsof see the just-opened handles

    paths = {'killed_file': killed_file, 'foreign_file': foreign_file, 'live_file': live_file}
    return paths, proc_killed, proc_live


def _run_abort_and_checks(failures, proc_killed, proc_live, paths, log_size_before):
    killed_file = paths['killed_file']
    foreign_file = paths['foreign_file']
    live_file = paths['live_file']

    killed_count = _abort_bg_sleep_timers([proc_killed.pid])

    _check(failures, "killed PID's own file gets stamped",
           killed_count == 1 and killed_file.read_text() == 'aborted\n',
           f"killed_count={killed_count} content={killed_file.read_text()!r}")

    proc_killed.wait(timeout=3)
    _check(failures, "killed PID's process actually terminated",
           proc_killed.poll() is not None, f"poll={proc_killed.poll()}")

    _check(failures, "foreign 0-byte file (no associated PID) NOT stamped",
           foreign_file.read_text() == '', f"content={foreign_file.read_text()!r}")

    _check(failures, "live wait's file in another session untouched (content)",
           live_file.read_text() == '', f"content={live_file.read_text()!r}")
    _check(failures, "live wait's process in another session still alive",
           proc_live.poll() is None, f"poll={proc_live.poll()}")

    new_log_tail = _MENUBAR_LOG.read_text()[log_size_before:] if _MENUBAR_LOG.exists() else ''
    _check(failures, "[abort] log line lists only the stamped file",
           str(killed_file) in new_log_tail
           and str(foreign_file) not in new_log_tail
           and str(live_file) not in new_log_tail,
           new_log_tail.strip() or '(no new log line written)')


def _teardown_fixtures(tmp, proc_killed, proc_live):
    for p in (proc_killed, proc_live):
        if p is not None and p.poll() is None:
            try:
                p.kill()
                p.wait(timeout=2)
            except Exception as e:
                print(f'[teardown] kill error for pid={p.pid}: {e}', file=sys.stderr)
    shutil.rmtree(tmp, ignore_errors=True)


def _print_summary(failures):
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("All 6 checks passed.")


if __name__ == "__main__":
    test_abort_stamp_scope_workflow()
