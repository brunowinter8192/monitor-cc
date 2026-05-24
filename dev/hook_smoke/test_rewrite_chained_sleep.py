# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/rewrite_chained_sleep.py"

# (description, command, expected_rewrite_or_None)
# None = no rewrite expected (hook should emit nothing and exit 0)
CASES = [
    # --- positive: trivial-sync echo before sleep → strip ---
    (
        "echo marker then sleep then tmux — strip sleep",
        "echo \"marker\"; sleep 8; tmux display-message -t ccwrap-phase1 -p '#{pane_title}'",
        "echo \"marker\"; tmux display-message -t ccwrap-phase1 -p '#{pane_title}'",
    ),
    (
        "echo X && sleep then bd — strip sleep",
        'echo "X" && sleep 6 && bd comments add --description "impl"',
        'echo "X" && bd comments add --description "impl"',
    ),
    (
        "true guard before sleep then bd — strip sleep",
        "worker-cli kill X || true; sleep 2; bd list -s open",
        "worker-cli kill X || true; bd list -s open",
    ),
    # --- negative: load-bearing cmd_before → no rewrite ---
    (
        "kill before sleep — load-bearing, no strip",
        "kill $PID 2>&1; sleep 3; check_status",
        None,
    ),
    (
        "launchctl before sleep — load-bearing, no strip",
        "launchctl bootout gui/501/com.example; sleep 1; pgrep -f workflow",
        None,
    ),
    # --- negative: sleep inside loop body → no rewrite ---
    (
        "sleep inside for...done loop — no strip",
        "for i in $(seq 1 30); do echo check; sleep 20; done",
        None,
    ),
    # --- negative: sleep-first (canonical or intent) → no rewrite ---
    (
        "canonical sleep N && echo done — no strip",
        "sleep 5 && echo done",
        None,
    ),
    (
        "sleep-first leading timer intent — no strip",
        "sleep 15 && rag-cli server list",
        None,
    ),
]


# ORCHESTRATOR

# Run all cases and print results; exit 1 if any fail
def test_rewrite_chained_sleep_workflow() -> None:
    failures = []
    for desc, cmd, expected_rewrite in CASES:
        exit_code, rewrite = _run_hook(cmd)
        ok = exit_code == 0 and rewrite == expected_rewrite
        status = "OK  " if ok else "FAIL"
        want = repr(expected_rewrite) if expected_rewrite is not None else "None (no output)"
        got  = repr(rewrite) if rewrite is not None else "None (no output)"
        print(f"  [{status}] {desc}")
        if not ok:
            print(f"           want: {want}")
            print(f"           got:  {got} (exit={exit_code})")
            failures.append(desc)
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {len(CASES)} tests passed.")


# FUNCTIONS

# Run hook with given command; return (exit_code, rewritten_command_or_None)
def _run_hook(command: str):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result  = subprocess.run(
        ["python3", HOOK],
        input=payload.encode(),
        capture_output=True,
    )
    rewrite = None
    if result.returncode == 0 and result.stdout.strip():
        try:
            data    = json.loads(result.stdout)
            rewrite = data["hookSpecificOutput"]["updatedInput"]["command"]
        except (KeyError, json.JSONDecodeError):
            rewrite = None
    return result.returncode, rewrite


if __name__ == "__main__":
    test_rewrite_chained_sleep_workflow()
