# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/rewrite_worker_wait.py"

CASES = [
    ("bare worker-cli wait, run_in_background true — already correct NO-OP",
     "worker-cli wait", True, 0, None, None),
    ("bare with --timeout, run_in_background true — already correct NO-OP",
     "worker-cli wait --timeout 600", True, 0, None, None),
    ("bare with project_path, run_in_background true — already correct NO-OP",
     "worker-cli wait /path/to/project", True, 0, None, None),
    ("bare with project_path + --timeout, run_in_background true — already "
     "correct NO-OP",
     "worker-cli wait /path/to/project --timeout 600", True, 0, None, None),
    ("rewrite_background_sleep.py's own output — already correct NO-OP",
     "worker-cli wait", True, 0, None, None),

    ("bare worker-cli wait, run_in_background false — flag forced REWRITE",
     "worker-cli wait", False, 0, "worker-cli wait", True),
    ("bare worker-cli wait, run_in_background omitted — flag forced REWRITE",
     "worker-cli wait", None, 0, "worker-cli wait", True),
    ("bare with --timeout, run_in_background false — flag forced, command "
     "unchanged REWRITE",
     "worker-cli wait --timeout 600", False, 0, "worker-cli wait --timeout 600", True),

    ("cd ; worker-cli wait, no path of its own — path injected, flag forced "
     "REWRITE (the actual incident shape)",
     "cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch; worker-cli wait",
     True, 0,
     "worker-cli wait /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch",
     True),
    ("cd && worker-cli wait, no path of its own — path injected REWRITE",
     "cd /tmp && worker-cli wait", True, 0, "worker-cli wait /tmp", True),
    ("cd ; worker-cli wait, run_in_background false too — both forced in one "
     "payload REWRITE",
     "cd /tmp; worker-cli wait", False, 0, "worker-cli wait /tmp", True),
    ("cd ; worker-cli wait --timeout 600, no path of its own — path injected "
     "before the flag REWRITE",
     "cd /tmp; worker-cli wait --timeout 600", True, 0,
     "worker-cli wait /tmp --timeout 600", True),
    ("cd ; worker-cli wait already has its own path — cd dropped as redundant "
     "REWRITE",
     "cd /tmp; worker-cli wait /other/project", True, 0,
     "worker-cli wait /other/project", True),
    ("cd \\n worker-cli wait (newline separator, real spawn-cd-prefix shape) "
     "REWRITE",
     "cd /tmp\nworker-cli wait", True, 0, "worker-cli wait /tmp", True),

    ("worker-cli wait && rag-cli index docs — trailing chain, unfixable "
     "BLOCK",
     "worker-cli wait && rag-cli index docs", True, 2, None, None),
    ("worker-cli wait ; echo done — trailing chain, unfixable BLOCK",
     "worker-cli wait ; echo done", True, 2, None, None),
    ("worker-cli wait piped — unfixable BLOCK",
     "worker-cli wait | tee /tmp/log", True, 2, None, None),
    ("cd /tmp && worker-cli wait && echo done — cd AND trailing chain, "
     "unfixable BLOCK",
     "cd /tmp && worker-cli wait && echo done", True, 2, None, None),

    ("worker-cli waitfoo — not a word-boundary match NO-OP",
     "worker-cli waitfoo", True, 0, None, None),
    ("unrelated command NO-OP",
     "echo hello world", False, 0, None, None),
    ("worker-cli wait mentioned only inside a quoted send message NO-OP",
     'worker-cli send orchestrator "Arm worker-cli wait after every dispatch."',
     False, 0, None, None),
    ("worker-cli wait mentioned only inside a heredoc body NO-OP",
     "cat <<'EOF' > /tmp/prompt.md\nRun worker-cli wait after you dispatch.\nEOF",
     False, 0, None, None),
]


# ORCHESTRATOR

def test_rewrite_worker_wait_workflow() -> None:
    failures = []
    for desc, cmd, rb, expected_exit, expected_cmd, expected_bg in CASES:
        got_cmd, got_bg, exit_code = _run_hook(cmd, rb)
        ok = (exit_code == expected_exit and got_cmd == expected_cmd
              and got_bg == expected_bg)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {desc}")
        if not ok:
            print(f"           want: exit={expected_exit} command={expected_cmd!r} "
                  f"run_in_background={expected_bg!r}")
            print(f"           got:  exit={exit_code} command={got_cmd!r} "
                  f"run_in_background={got_bg!r}")
            failures.append(desc)
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {len(CASES)} tests passed.")


# FUNCTIONS

def _run_hook(command: str, run_in_background):
    tool_input = {"command": command}
    if run_in_background is not None:
        tool_input["run_in_background"] = run_in_background
    payload = json.dumps({"tool_name": "Bash", "tool_input": tool_input})
    result = subprocess.run(
        ["python3", HOOK],
        input=payload.encode(),
        capture_output=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        try:
            data = json.loads(result.stdout)
            updated = data["hookSpecificOutput"]["updatedInput"]
            return updated["command"], updated["run_in_background"], result.returncode
        except (KeyError, json.JSONDecodeError):
            pass
    return None, None, result.returncode


if __name__ == "__main__":
    test_rewrite_worker_wait_workflow()
