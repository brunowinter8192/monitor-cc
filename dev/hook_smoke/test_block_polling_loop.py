# INFRASTRUCTURE
import json
import os
import subprocess
import sys
import tempfile

HOOK = "src/hooks/block_polling_loop.py"

# Stateful test: each group uses its own session_id so counts are isolated.
# All calls within a group run fast enough (<30 s combined) to stay in the window.


# ORCHESTRATOR

def test_block_polling_loop_workflow() -> None:
    fd, state_file = tempfile.mkstemp(suffix='.jsonl')
    os.close(fd)
    failures = []
    failures += _run_group_frequency(state_file)
    failures += _run_group_different_target(state_file)
    failures += _run_group_single_checks(state_file)
    failures += _run_group_no_target(state_file)
    failures += _run_group_session_isolation(state_file)
    os.unlink(state_file)
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for desc in failures:
            print(f"  - {desc}")
        sys.exit(1)
    print("All tests passed.")


# FUNCTIONS

# Run hook with given command string and session_id; return exit code
def _run_hook(command: str, state_file: str, session_id: str = "test-session-001") -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "session_id": session_id,
    })
    env = {**os.environ, "MONITOR_CC_POLLING_STATE": state_file}
    result = subprocess.run(
        ["python3", HOOK],
        input=payload.encode(),
        capture_output=True,
        env=env,
    )
    return result.returncode

# Check one case; print result; return desc if failed
def _check(desc: str, got: int, expected: int) -> str:
    status = "OK  " if got == expected else "FAIL"
    print(f"  [{status}] {desc}: exit={got} (expected {expected})")
    return "" if got == expected else desc

# Frequency group: 1st and 2nd poll pass, 3rd blocks (same session + target within 30 s)
def _run_group_frequency(state_file: str) -> list:
    failures = []
    sid = "freq-ps"
    r = _check("ps -p poll #1 PASS", _run_hook("ps -p 12345 > /dev/null 2>&1", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("ps -p poll #2 PASS", _run_hook("ps -p 12345 > /dev/null 2>&1", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("ps -p poll #3 BLOCK", _run_hook("ps -p 12345 > /dev/null 2>&1", state_file, sid), 2)
    if r: failures.append(r)

    sid = "freq-tail"
    r = _check("tail poll #1 PASS", _run_hook("tail -18 /tmp/sweep.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("tail poll #2 PASS", _run_hook("tail -18 /tmp/sweep.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("tail poll #3 BLOCK", _run_hook("tail -18 /tmp/sweep.log", state_file, sid), 2)
    if r: failures.append(r)
    return failures

# Different target: after 3 blocks on pid:12345, a different pid or file passes freely
def _run_group_different_target(state_file: str) -> list:
    failures = []
    sid = "diff-target"
    # saturate pid:12345
    for _ in range(3):
        _run_hook("ps -p 12345", state_file, sid)
    r = _check("different pid after saturation PASS",
               _run_hook("ps -p 99999", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("different file after saturation PASS",
               _run_hook("tail -5 /tmp/other.log", state_file, sid), 0)
    if r: failures.append(r)
    return failures

# Single checks: one-off ps -p or tail call always passes
def _run_group_single_checks(state_file: str) -> list:
    failures = []
    sid = "single"
    r = _check("ps -p single check PASS",
               _run_hook("ps -p 55555", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("tail single check PASS",
               _run_hook("tail -10 /tmp/unique.log", state_file, sid), 0)
    if r: failures.append(r)
    return failures

# No-target commands: commands without ps -p or tail -N always pass
def _run_group_no_target(state_file: str) -> list:
    failures = []
    sid = "no-target"
    r = _check("git status no target PASS",
               _run_hook("git status && ls -la", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("tail -n long-form no target PASS",
               _run_hook("ps -p 555; tail -n 20 /tmp/file.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("ps aux no -p PASS",
               _run_hook("ps aux | grep python", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("ps -p in single-quoted string PASS",
               _run_hook("echo 'ps -p 123 && tail -18 /tmp/log'", state_file, sid), 0)
    if r: failures.append(r)
    return failures

# Session isolation: counts are per-session — session B saturating a target does not affect session A
def _run_group_session_isolation(state_file: str) -> list:
    failures = []
    sid_a = "iso-session-A"
    sid_b = "iso-session-B"
    # session B saturates pid:77777
    for _ in range(3):
        _run_hook("ps -p 77777", state_file, sid_b)
    # session A's first poll on the same target should still pass
    r = _check("session A unaffected by session B saturation PASS",
               _run_hook("ps -p 77777", state_file, sid_a), 0)
    if r: failures.append(r)
    return failures


if __name__ == "__main__":
    test_block_polling_loop_workflow()
