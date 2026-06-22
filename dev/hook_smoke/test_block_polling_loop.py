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
    failures += _run_group_pipe_fed_tail(state_file)
    failures += _run_group_long_form_tail(state_file)
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
    r = _check("ps-p wins over tail-n when both present PASS",
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


# Pipe-fed tail: cmd | tail -N reads stdin — no file arg, never produces a poll target.
# The original false-positive: plugin-publish 2>&1 | tail -25\necho "done" repeated ≥3×
# extracted "echo;" as file target. All pipe-fed variants must PASS regardless of repetition.
def _run_group_pipe_fed_tail(state_file: str) -> list:
    failures = []
    sid = "pipe-fed"
    # Exact false-positive pattern: | tail -N\nnext-cmd repeated ≥3× — all must PASS
    cmd = "plugin-publish 2>&1 | tail -25\necho \"done\"; grep \"result\""
    r = _check("pipe-fed | tail newline-echo #1 PASS", _run_hook(cmd, state_file, sid), 0)
    if r: failures.append(r)
    r = _check("pipe-fed | tail newline-echo #2 PASS", _run_hook(cmd, state_file, sid), 0)
    if r: failures.append(r)
    r = _check("pipe-fed | tail newline-echo #3 PASS", _run_hook(cmd, state_file, sid), 0)
    if r: failures.append(r)
    # Same-line pipe variant: | tail -N ; echo (pipe + semicolon-separated next cmd)
    r = _check("pipe-fed | tail same-line semi PASS",
               _run_hook("cmd 2>&1 | tail -25 ; echo done", state_file, sid), 0)
    if r: failures.append(r)
    # stdin-only: cat f | tail -25 with no following command
    r = _check("cat | tail -25 no-file-arg PASS",
               _run_hook("cat /tmp/log.txt | tail -25", state_file, sid), 0)
    if r: failures.append(r)
    return failures


# Long-form tail: all GNU forms yield file target; offset-agnostic keying; pipe-fed long form passes
def _run_group_long_form_tail(state_file: str) -> list:
    failures = []
    # Worker's exact pattern: tail -n +N file | head with increasing offset, same file → blocks on 3rd
    sid = "long-tail-offset"
    r = _check("tail -n +58 | head offset #1 PASS",
               _run_hook("tail -n +58 /tmp/docling-reference_index.log | head -30", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("tail -n +88 | head offset #2 PASS",
               _run_hook("tail -n +88 /tmp/docling-reference_index.log | head -30", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("tail -n +118 | head offset #3 BLOCK",
               _run_hook("tail -n +118 /tmp/docling-reference_index.log | head -30", state_file, sid), 2)
    if r: failures.append(r)

    sid = "long-tail-n"
    r = _check("tail -n 30 #1 PASS", _run_hook("tail -n 30 /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("tail -n 30 #2 PASS", _run_hook("tail -n 30 /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("tail -n 30 #3 BLOCK", _run_hook("tail -n 30 /tmp/x.log", state_file, sid), 2)
    if r: failures.append(r)

    sid = "long-tail-lines"
    r = _check("tail --lines=30 #1 PASS", _run_hook("tail --lines=30 /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("tail --lines=30 #2 PASS", _run_hook("tail --lines=30 /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("tail --lines=30 #3 BLOCK", _run_hook("tail --lines=30 /tmp/x.log", state_file, sid), 2)
    if r: failures.append(r)

    # Pipe-fed long form: cmd | tail -n +58 → no target, always passes regardless of repetition
    sid = "pipe-fed-long"
    r = _check("pipe-fed | tail -n +58 #1 PASS",
               _run_hook("cmd | tail -n +58 /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("pipe-fed | tail -n +58 #2 PASS",
               _run_hook("cmd | tail -n +58 /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)
    r = _check("pipe-fed | tail -n +58 #3 PASS",
               _run_hook("cmd | tail -n +58 /tmp/x.log", state_file, sid), 0)
    if r: failures.append(r)

    # Single long-form read always passes (one-off)
    sid = "long-tail-single"
    r = _check("tail -n 20 single read PASS",
               _run_hook("tail -n 20 /tmp/single-long.log", state_file, sid), 0)
    if r: failures.append(r)

    # Attached forms (-nN and -n+N without space): pre-saturate 2×, use attached form as 3rd
    # → same file fingerprint → blocks (proves attached form detected and file-keyed)
    sid = "attached-n30"
    _run_hook("tail -n 30 /tmp/af-n.log", state_file, sid)
    _run_hook("tail -n 30 /tmp/af-n.log", state_file, sid)
    r = _check("tail -n30 no-space #3 BLOCK",
               _run_hook("tail -n30 /tmp/af-n.log", state_file, sid), 2)
    if r: failures.append(r)

    sid = "attached-nplus"
    _run_hook("tail -n +58 /tmp/af-np.log", state_file, sid)
    _run_hook("tail -n +88 /tmp/af-np.log", state_file, sid)
    r = _check("tail -n+118 no-space offset #3 BLOCK",
               _run_hook("tail -n+118 /tmp/af-np.log", state_file, sid), 2)
    if r: failures.append(r)

    return failures


if __name__ == "__main__":
    test_block_polling_loop_workflow()
