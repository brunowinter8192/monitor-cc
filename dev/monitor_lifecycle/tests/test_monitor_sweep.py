# INFRASTRUCTURE
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))
from dev.refactoring.strand_runner import strand_workflow
from src.monitor_janitor import list_monitor_sessions, sweep_sessions, _log_path

_OLD_NAME    = "monitor_cc_testold"
_NEW_NAME    = "monitor_cc_testnew"
_WORKER_NAME = "worker-testkeep"
_OLD_AGE_BACKDATE = 1000
_TEST_THRESHOLD   = 500
_STRAND_NAMES = ['_test_sweep_kills_old_spares_new_and_worker']
_TITLE = 'test_monitor_sweep'
_REPORT_PATH = Path(__file__).resolve().parents[1] / 'md' / 'test_monitor_sweep.md'

# ORCHESTRATOR

def test_monitor_sweep_workflow() -> None:
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))

# FUNCTIONS

def _test_sweep_kills_old_spares_new_and_worker() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="mcsw_", dir="/tmp"))
    try:
        with patch.dict(os.environ, _isolated_env(scratch)):
            os.environ.pop("TMUX", None)
            try:
                _run_checks()
            finally:
                _cleanup_fixtures()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

def _isolated_env(scratch: Path) -> dict:
    return {"TMUX_TMPDIR": str(scratch), "MONITOR_CC_ROOT": str(scratch)}

def _run_checks() -> None:
    old_pid = _create_fixture_session(_OLD_NAME)
    new_pid = _create_fixture_session(_NEW_NAME)
    worker_pid = _create_fixture_session(_WORKER_NAME)

    all_sessions = list_monitor_sessions()
    names = {name for name, _ in all_sessions}
    _check("enumeration includes testold", _OLD_NAME in names)
    _check("enumeration includes testnew", _NEW_NAME in names)
    _check("enumeration excludes worker-* session", _WORKER_NAME not in names)

    fixture_pair = [(n, c - _OLD_AGE_BACKDATE if n == _OLD_NAME else c)
                    for n, c in all_sessions if n in (_OLD_NAME, _NEW_NAME)]
    sweep_sessions(fixture_pair, _TEST_THRESHOLD)

    _check("testold session killed", not _session_exists(_OLD_NAME))
    _check("testnew session spared", _session_exists(_NEW_NAME))
    _check("worker-* session untouched", _session_exists(_WORKER_NAME))
    _check("testold pane process reaped (no orphan)", not _pid_alive(old_pid))
    _check("testnew pane process still alive", _pid_alive(new_pid))
    _check("worker-* pane process untouched", _pid_alive(worker_pid))
    _check("log recorded testold as KILLED", _log_has(_OLD_NAME, "KILLED"))
    _check("log recorded testnew as SPARED", _log_has(_NEW_NAME, "SPARED"))

def _check(desc: str, ok: bool) -> None:
    print(f"  [{'OK  ' if ok else 'FAIL'}] {desc}")
    if not ok:
        raise AssertionError(desc)

def _create_fixture_session(name: str) -> int:
    subprocess.run(["tmux", "new-session", "-d", "-s", name, "sleep 120"], check=True)
    pid_raw = subprocess.run(
        ["tmux", "list-panes", "-t", name, "-F", "#{pane_pid}"],
        capture_output=True, text=True
    ).stdout.strip()
    return int(pid_raw)

def _session_exists(name: str) -> bool:
    return subprocess.run(["tmux", "has-session", "-t", name], capture_output=True).returncode == 0

def _pid_alive(pid: int) -> bool:
    return subprocess.run(["ps", "-p", str(pid)], capture_output=True).returncode == 0

def _log_has(name: str, status: str) -> bool:
    log_path = _log_path()
    if not log_path.exists():
        return False
    lines = log_path.read_text(encoding='utf-8').splitlines()
    return any(f"{name} " in line and status in line for line in lines)

def _cleanup_fixtures() -> None:
    subprocess.run(["tmux", "kill-server"], capture_output=True)


if __name__ == "__main__":
    test_monitor_sweep_workflow()
