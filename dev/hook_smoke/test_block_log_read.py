# INFRASTRUCTURE
import json
import os
import subprocess
import sys
import tempfile

HOOK = "src/hooks/block_log_read.py"

# Stateful test: each group uses its own session_id so counts are isolated.
# Branch A counts are per (session_id, file) — different session IDs prevent cross-group contamination.


# ORCHESTRATOR

def test_block_log_read_workflow() -> None:
    fd, state_file = tempfile.mkstemp(suffix='.jsonl')
    os.close(fd)
    failures = []
    failures += _run_group_branch_b_block(state_file)
    failures += _run_group_branch_b_pass(state_file)
    failures += _run_group_branch_a_frequency(state_file)
    failures += _run_group_logread_line_count(state_file)
    failures += _run_group_file_independence(state_file)
    failures += _run_group_shell_strip(state_file)
    failures += _run_group_non_log(state_file)
    failures += _run_group_evasion(state_file)
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
    env = {**os.environ, "MONITOR_CC_LOGREAD_STATE": state_file}
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

# Branch B — read tools with .log input arg → BLOCK
def _run_group_branch_b_block(state_file: str) -> list:
    failures = []
    sid = "b2-block"
    print("Branch B — read tools BLOCK:")
    r = _check("tail -n +58 x.log | head -30 BLOCK",
               _run_hook("tail -n +58 /tmp/x.log | head -30", state_file, sid), 2)
    if r: failures.append(r)
    r = _check("cat /tmp/x.log BLOCK",
               _run_hook("cat /tmp/x.log", state_file, sid), 2)
    if r: failures.append(r)
    r = _check("grep err /tmp/x.log BLOCK",
               _run_hook("grep err /tmp/x.log", state_file, sid), 2)
    if r: failures.append(r)
    r = _check("less /var/log/y.log BLOCK",
               _run_hook("less /var/log/y.log", state_file, sid), 2)
    if r: failures.append(r)
    r = _check("sed -n '1,5p' a.log BLOCK",
               _run_hook("sed -n '1,5p' a.log", state_file, sid), 2)
    if r: failures.append(r)
    return failures

# Branch B — write redirects and tee → PASS
def _run_group_branch_b_pass(state_file: str) -> list:
    failures = []
    sid = "b2-pass"
    print("Branch B — write targets PASS:")
    r = _check("echo done > /tmp/x.log PASS",
               _run_hook("echo done > /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("cmd >> /tmp/x.log PASS",
               _run_hook("cmd >> /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("cmd 2>> /tmp/x.log PASS",
               _run_hook("cmd 2>> /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("tee /tmp/x.log PASS",
               _run_hook("tee /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("echo x | tee /tmp/x.log PASS",
               _run_hook("echo x | tee /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)
    return failures

# Branch A — logread 1st + 2nd PASS, 3rd BLOCK on same file in same session
def _run_group_branch_a_frequency(state_file: str) -> list:
    failures = []
    sid = "a1-freq"
    print("Branch A — frequency cap:")
    r = _check("logread /tmp/x.log #1 PASS",
               _run_hook("logread /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("logread /tmp/x.log #2 PASS",
               _run_hook("logread /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("logread /tmp/x.log #3 BLOCK",
               _run_hook("logread /tmp/x.log", state_file, sid), 2)
    if r: failures.append(r)
    return failures

# Branch A — logread x N counts as file x (2nd arg is line count, not file)
def _run_group_logread_line_count(state_file: str) -> list:
    failures = []
    sid = "a1-linecnt"
    print("Branch A — line-count arg is not the file:")
    r = _check("logread /tmp/z.log (plain) #1 PASS",
               _run_hook("logread /tmp/z.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("logread /tmp/z.log 50 (with N) #2 PASS — same file as plain",
               _run_hook("logread /tmp/z.log 50", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("logread /tmp/z.log 100 #3 BLOCK — counts as same file",
               _run_hook("logread /tmp/z.log 100", state_file, sid), 2)
    if r: failures.append(r)
    return failures

# Branch A — different files are independent counters
def _run_group_file_independence(state_file: str) -> list:
    failures = []
    sid = "a1-indep"
    print("Branch A — file independence:")
    r = _check("logread /tmp/a.log #1 PASS",
               _run_hook("logread /tmp/a.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("logread /tmp/b.log #1 PASS (different file)",
               _run_hook("logread /tmp/b.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("logread /tmp/a.log #2 PASS (independent of b.log count)",
               _run_hook("logread /tmp/a.log", state_file, sid), 0)
    if r: failures.append(r)
    return failures

# Shell-strip — .log read inside a quoted worker-cli send message → PASS
def _run_group_shell_strip(state_file: str) -> list:
    failures = []
    sid = "strip"
    print("Shell-strip — quoted .log read:")
    r = _check("worker-cli send worker \"tail x.log | head\" PASS",
               _run_hook('worker-cli send worker "tail /tmp/x.log | head"', state_file, sid), 0)
    if r: failures.append(r)
    return failures

# Non-.log file read — cat /tmp/x.txt → PASS (scope is .log only)
def _run_group_non_log(state_file: str) -> list:
    failures = []
    sid = "non-log"
    print("Non-.log file:")
    r = _check("cat /tmp/x.txt PASS",
               _run_hook("cat /tmp/x.txt", state_file, sid), 0)
    if r: failures.append(r)
    return failures

# Evasion case: logread presence in ONE segment must NOT disable Branch B in another segment.
# 'tail /tmp/x.log ; logread /tmp/y.log' — the tail segment blocks regardless of logread elsewhere.
def _run_group_evasion(state_file: str) -> list:
    failures = []
    sid = "evasion"
    print("Evasion case — per-segment precedence:")
    r = _check("tail x.log ; logread y.log BLOCK (tail segment)",
               _run_hook("tail /tmp/x.log ; logread /tmp/y.log", state_file, sid), 2)
    if r: failures.append(r)
    return failures


if __name__ == "__main__":
    test_block_log_read_workflow()
