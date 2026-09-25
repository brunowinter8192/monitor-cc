# INFRASTRUCTURE
import json
import sys
from case_strands import case_runners, report_case, run_case_strands
from hook_runner import run_hook

HOOK = "src/hooks/rewrite_worker_wait.py"

CASES = [
    ("bare worker-cli wait, run_in_background true — already correct NO-OP",
     "worker-cli wait", True, 0, None, None),
    ("bare with --timeout, run_in_background true — already correct NO-OP",
     "worker-cli wait --timeout 600", True, 0, None, None),
    ("bare with a path, run_in_background true — hook only normalises the flag, "
     "the CLI rejects the path NO-OP",
     "worker-cli wait /path/to/project", True, 0, None, None),
    ("bare with a path + --timeout, run_in_background true — hook only "
     "normalises the flag, the CLI rejects the path NO-OP",
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

    ("cd ; worker-cli wait (the actual incident shape) — leading cd, run "
     "from the project directory BLOCK",
     "cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch; worker-cli wait",
     True, 2, None, None),
    ("cd && worker-cli wait — leading cd BLOCK",
     "cd /tmp && worker-cli wait", True, 2, None, None),
    ("cd ; worker-cli wait, run_in_background false — leading cd BLOCK",
     "cd /tmp; worker-cli wait", False, 2, None, None),
    ("cd ; worker-cli wait --timeout 600 — leading cd BLOCK",
     "cd /tmp; worker-cli wait --timeout 600", True, 2, None, None),
    ("cd \\n worker-cli wait (newline separator) BLOCK",
     "cd /tmp\nworker-cli wait", True, 2, None, None),

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
    sys.exit(run_case_strands(globals(), __file__, case_runners(CASES, _check_case)))


# FUNCTIONS

def _check_case(case: tuple) -> None:
    desc, command, run_in_background, expected_exit, expected_cmd, expected_bg = case
    got_cmd, got_bg, exit_code = _run_hook(command, run_in_background)
    ok = exit_code == expected_exit and got_cmd == expected_cmd and got_bg == expected_bg
    want = f"exit={expected_exit} command={expected_cmd!r} run_in_background={expected_bg!r}"
    got = f"exit={exit_code} command={got_cmd!r} run_in_background={got_bg!r}"
    report_case(desc, ok, '' if ok else f'\n           want: {want}\n           got:  {got}')


def _run_hook(command: str, run_in_background):
    tool_input = {"command": command}
    if run_in_background is not None:
        tool_input["run_in_background"] = run_in_background
    payload = json.dumps({"tool_name": "Bash", "tool_input": tool_input})
    result = run_hook(HOOK, payload.encode())
    if result.returncode == 0 and result.stdout.strip():
        data = json.loads(result.stdout)
        updated = data["hookSpecificOutput"]["updatedInput"]
        return updated["command"], updated["run_in_background"], result.returncode
    return None, None, result.returncode


if __name__ == "__main__":
    test_rewrite_worker_wait_workflow()
