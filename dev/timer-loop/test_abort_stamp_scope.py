#!/usr/bin/env python3
# INFRASTRUCTURE
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from dev.refactoring.strand_runner import strand_workflow

_bg_timer_mod = importlib.import_module('src.menubar.bg_timer')
_abort_bg_sleep_timers = _bg_timer_mod._abort_bg_sleep_timers
_resolve_pid_output_file = _bg_timer_mod._resolve_pid_output_file
_menubar_log_mod = importlib.import_module('src.menubar.menubar_log')

_HOLD_DURATION = 20
_POLL_DEADLINE_SECS = 10.0
_POLL_INTERVAL_SECS = 0.05
_STRAND_NAMES = ['_test_abort_stamps_only_own_file']
_TITLE = 'test_abort_stamp_scope'
_REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'test_abort_stamp_scope.md'


# ORCHESTRATOR

def test_abort_stamp_scope_workflow() -> None:
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))


# FUNCTIONS

def _test_abort_stamps_only_own_file() -> None:
    tmp = Path(tempfile.mkdtemp(prefix='abort_stamp_scope_'))
    proc_killed = None
    proc_live = None
    scratch_log = tmp / 'menubar.log'
    try:
        with patch.object(_menubar_log_mod, 'MENUBAR_LOG', scratch_log):
            paths, proc_killed, proc_live = _spawn_test_fixtures(tmp)
            _run_abort_and_checks(proc_killed, proc_live, paths, scratch_log)
    finally:
        _teardown_fixtures(tmp, proc_killed, proc_live)

def _check(desc: str, ok: bool, detail: str) -> None:
    status = "OK  " if ok else "FAIL"
    print(f"  [{status}] {desc}: {detail}")
    if not ok:
        raise AssertionError(desc)

def _spawn_holding_output(output_path: Path):
    fh = open(output_path, 'wb')
    proc = subprocess.Popen(['sleep', str(_HOLD_DURATION)], stdout=fh, stderr=fh)
    fh.close()
    return proc


def _spawn_test_fixtures(tmp: Path):
    killed_file = tmp / 'bkilledtask1.output'
    foreign_file = tmp / 'bforeigntask2.output'
    live_file = tmp / 'blivetask3.output'
    foreign_file.write_text('')

    proc_killed = _spawn_holding_output(killed_file)
    proc_live = _spawn_holding_output(live_file)
    _wait_until_resolvable(proc_killed.pid)
    _wait_until_resolvable(proc_live.pid)

    paths = {'killed_file': killed_file, 'foreign_file': foreign_file, 'live_file': live_file}
    return paths, proc_killed, proc_live


def _wait_until_resolvable(pid: int) -> None:
    deadline = time.monotonic() + _POLL_DEADLINE_SECS
    while time.monotonic() < deadline:
        if _resolve_pid_output_file(pid) is not None:
            return
        time.sleep(_POLL_INTERVAL_SECS)
    raise RuntimeError(f'output file of pid {pid} not visible to lsof within {_POLL_DEADLINE_SECS}s')


def _run_abort_and_checks(proc_killed, proc_live, paths, scratch_log):
    killed_file = paths['killed_file']
    foreign_file = paths['foreign_file']
    live_file = paths['live_file']

    killed_count = _abort_bg_sleep_timers([proc_killed.pid])

    _check("killed PID's own file gets stamped",
           killed_count == 1 and killed_file.read_text() == 'aborted\n',
           f"killed_count={killed_count} content={killed_file.read_text()!r}")

    proc_killed.wait(timeout=3)
    _check("killed PID's process actually terminated",
           proc_killed.poll() is not None, f"poll={proc_killed.poll()}")

    _check("foreign 0-byte file (no associated PID) NOT stamped",
           foreign_file.read_text() == '', f"content={foreign_file.read_text()!r}")

    _check("live wait's file in another session untouched (content)",
           live_file.read_text() == '', f"content={live_file.read_text()!r}")
    _check("live wait's process in another session still alive",
           proc_live.poll() is None, f"poll={proc_live.poll()}")

    new_log_tail = scratch_log.read_text() if scratch_log.exists() else ''
    _check("[abort] log line lists only the stamped file",
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


if __name__ == "__main__":
    test_abort_stamp_scope_workflow()
