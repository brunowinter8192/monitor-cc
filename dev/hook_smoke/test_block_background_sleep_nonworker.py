# INFRASTRUCTURE
import json
import os
import subprocess
import sys
import tempfile

HOOK = "src/hooks/block_background_sleep_nonworker.py"
SESSION = "test-session-idle-timer"
TIMER_CMD = "sleep 600 && echo done"


# ORCHESTRATOR

# Run all cases and print results; exit 1 if any fail
def test_block_background_sleep_nonworker_workflow() -> None:
    failures = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = os.path.join(tmp_dir, "last_cmd_state.jsonl")
        fire_log = os.path.join(tmp_dir, "hook_firing.jsonl")
        env = {
            **os.environ,
            "MONITOR_CC_LAST_CMD_STATE": state_file,
            "MONITOR_CC_HOOK_FIRING_LOG": fire_log,
        }

        # (a) last cmd rag-cli index → timer BLOCKED
        _clear(state_file)
        _inject_cmd(SESSION, "rag-cli index --collection x > /tmp/out.txt 2>&1", env)
        ec, stderr = _run_timer(SESSION, env)
        _check("(a) last cmd rag-cli index → timer BLOCKED",
               ec == 2 and "Go idle" in stderr, f"exit={ec} stderr={stderr!r:.80}", failures)

        # (b) last cmd worker-cli spawn → timer ALLOWED
        _clear(state_file)
        _inject_cmd(SESSION, 'worker-cli spawn foo "task prompt" /path sonnet', env)
        ec, _ = _run_timer(SESSION, env)
        _check("(b) last cmd worker-cli spawn → timer ALLOWED",
               ec == 0, f"exit={ec}", failures)

        # (c) last cmd worker-cli status → timer ALLOWED
        _clear(state_file)
        _inject_cmd(SESSION, "worker-cli status foo", env)
        ec, _ = _run_timer(SESSION, env)
        _check("(c) last cmd worker-cli status → timer ALLOWED",
               ec == 0, f"exit={ec}", failures)

        # (d) no prior cmd → timer BLOCKED
        _clear(state_file)
        ec, stderr = _run_timer(SESSION, env)
        _check("(d) no prior cmd → timer BLOCKED",
               ec == 2 and "Go idle" in stderr, f"exit={ec} stderr={stderr!r:.80}", failures)

        # (g) cd ; worker-cli spawn → timer ALLOWED (semicolon separator)
        _clear(state_file)
        _inject_cmd(SESSION, 'cd /some/path ; worker-cli spawn foo /tmp/p.md . sonnet', env)
        ec, _ = _run_timer(SESSION, env)
        _check("(g) cd ; worker-cli spawn → timer ALLOWED",
               ec == 0, f"exit={ec}", failures)

        # (h) cd && worker-cli status → timer ALLOWED (ampersand separator)
        _clear(state_file)
        _inject_cmd(SESSION, 'cd /some/path && worker-cli status foo', env)
        ec, _ = _run_timer(SESSION, env)
        _check("(h) cd && worker-cli status → timer ALLOWED",
               ec == 0, f"exit={ec}", failures)

        # (i) cd newline worker-cli spawn → timer ALLOWED (exact live-repro form)
        _clear(state_file)
        _inject_cmd(SESSION, 'cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli\nworker-cli spawn doccheck-verify /tmp/p.md . sonnet', env)
        ec, _ = _run_timer(SESSION, env)
        _check("(i) cd\\nworker-cli spawn → timer ALLOWED (live-repro form)",
               ec == 0, f"exit={ec}", failures)

        # (e) non-timer bg cmd → hook exits 0 (state updated, not blocked by this hook)
        _clear(state_file)
        ec, _ = _run_non_timer_bg(SESSION, "rag-cli index --collection x", env)
        _check("(e) non-timer bg cmd → exits 0 (not blocked)",
               ec == 0, f"exit={ec}", failures)

        # (e-verify) state was written → subsequent timer is BLOCKED (rag-cli recorded)
        ec, _ = _run_timer(SESSION, env)
        _check("(e-verify) state written by non-timer bg → next timer BLOCKED",
               ec == 2, f"exit={ec}", failures)

        # (f) IO error reading state file → fail-open ALLOW
        # Point state env var at a directory — open(dir, 'r') raises IsADirectoryError → _READ_ERROR → exit 0
        env_error = {**env, "MONITOR_CC_LAST_CMD_STATE": tmp_dir}
        ec, _ = _run_timer(SESSION, env_error)
        _check("(f) IO error on state read → fail-open ALLOW",
               ec == 0, f"exit={ec}", failures)

    print()
    total = 10
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

# Run hook with a foreground (non-timer) command to set last-cmd state; ignore exit code
def _inject_cmd(session_id: str, command: str, env: dict) -> None:
    payload = json.dumps({
        "tool_name": "Bash",
        "session_id": session_id,
        "tool_input": {"command": command, "run_in_background": False},
    })
    subprocess.run(["python3", HOOK], input=payload.encode(), capture_output=True, env=env)

# Run hook with the canonical background sleep timer; return (exit_code, stderr_text)
def _run_timer(session_id: str, env: dict):
    payload = json.dumps({
        "tool_name": "Bash",
        "session_id": session_id,
        "tool_input": {"command": TIMER_CMD, "run_in_background": True},
    })
    result = subprocess.run(["python3", HOOK], input=payload.encode(), capture_output=True, env=env)
    return result.returncode, result.stderr.decode()

# Run hook with a non-timer command that has run_in_background=True; return (exit_code, stderr_text)
def _run_non_timer_bg(session_id: str, command: str, env: dict):
    payload = json.dumps({
        "tool_name": "Bash",
        "session_id": session_id,
        "tool_input": {"command": command, "run_in_background": True},
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
    test_block_background_sleep_nonworker_workflow()
