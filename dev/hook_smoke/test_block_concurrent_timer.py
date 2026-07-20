# INFRASTRUCTURE
import datetime
import json
import os
import subprocess
import sys
import tempfile

HOOK = "src/hooks/block_concurrent_timer.py"
SESSION = "test-session-timer-a"
SESSION_OTHER = "test-session-timer-b"
TIMER_CMD = "sleep 600 && echo done"


# ORCHESTRATOR

# Run all cases and print results; exit 1 if any fail
def test_block_concurrent_timer_workflow() -> None:
    failures = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = os.path.join(tmp_dir, "timer_state.jsonl")
        fire_log = os.path.join(tmp_dir, "hook_firing.jsonl")
        env = {
            **os.environ,
            "MONITOR_CC_TIMER_STATE": state_file,
            "MONITOR_CC_HOOK_FIRING_LOG": fire_log,
        }

        # (a) first timer for a session → ALLOWED
        _clear(state_file)
        ec, _ = _run_timer(SESSION, env)
        _check("(a) first timer for session → ALLOWED", ec == 0, f"exit={ec}", failures)

        # (b) second timer for the SAME session immediately after → BLOCKED
        ec, stderr = _run_timer(SESSION, env)
        _check("(b) second timer, same session, still running → BLOCKED",
               ec == 2 and "already running" in stderr, f"exit={ec} stderr={stderr!r:.120}", failures)

        # (c) timer for a DIFFERENT session → ALLOWED (independent)
        ec, _ = _run_timer(SESSION_OTHER, env)
        _check("(c) timer for a different session → ALLOWED (independent)",
               ec == 0, f"exit={ec}", failures)

        # (d) non-timer command → ALLOWED, no state written
        _clear(state_file)
        ec, _ = _run_non_timer(SESSION, "ls", env)
        _check("(d) non-timer command → ALLOWED", ec == 0, f"exit={ec}", failures)
        _check("(d-verify) non-timer command does not write state",
               not os.path.exists(state_file), f"state_file exists={os.path.exists(state_file)}", failures)

        # (e) expired stored timer → next timer request is ALLOWED
        _clear(state_file)
        _inject_expiry(state_file, SESSION, datetime.timedelta(seconds=-1))
        ec, _ = _run_timer(SESSION, env)
        _check("(e) expired stored timer → next timer ALLOWED", ec == 0, f"exit={ec}", failures)

        # (f) IO error reading state file → fail-open ALLOW
        # Point state env var at a directory — open(dir, 'r') raises IsADirectoryError → _READ_ERROR → exit 0
        env_error = {**env, "MONITOR_CC_TIMER_STATE": tmp_dir}
        ec, _ = _run_timer(SESSION, env_error)
        _check("(f) IO error on state read → fail-open ALLOW", ec == 0, f"exit={ec}", failures)

    print()
    total = 7
    passed = total - len(failures)
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {passed} tests passed.")


# FUNCTIONS

# Remove state file if it exists
def _clear(state_file: str) -> None:
    if os.path.exists(state_file):
        os.remove(state_file)

# Hand-write a stored timer expiry for session (now + delta); overwrites the state file
def _inject_expiry(state_file: str, session_id: str, delta: "datetime.timedelta") -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    entry = {
        'ts': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'session_id': session_id,
        'expiry': (now + delta).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    with open(state_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps(entry) + '\n')

# Run hook with the canonical background sleep timer; return (exit_code, stderr_text)
def _run_timer(session_id: str, env: dict):
    payload = json.dumps({
        "tool_name": "Bash",
        "session_id": session_id,
        "tool_input": {"command": TIMER_CMD, "run_in_background": True},
    })
    result = subprocess.run(["python3", HOOK], input=payload.encode(), capture_output=True, env=env)
    return result.returncode, result.stderr.decode()

# Run hook with a non-timer command; return (exit_code, stderr_text)
def _run_non_timer(session_id: str, command: str, env: dict):
    payload = json.dumps({
        "tool_name": "Bash",
        "session_id": session_id,
        "tool_input": {"command": command, "run_in_background": False},
    })
    result = subprocess.run(["python3", HOOK], input=payload.encode(), capture_output=True, env=env)
    return result.returncode, result.stderr.decode()

# Print result line; append description to failures list on failure
def _check(desc: str, ok: bool, detail: str, failures: list) -> None:
    status = "OK  " if ok else "FAIL"
    print(f"  [{status}] {desc}")
    if not ok:
        print(f"           got: {detail}")
        failures.append(desc)


if __name__ == "__main__":
    test_block_concurrent_timer_workflow()
