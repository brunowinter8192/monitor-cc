# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_chained_sleep.py"

CASES = [
    # (description, command, expected_exit_code)
    # --- canonical / allow cases ---
    ("canonical pass",               "sleep 5 && echo done",                                    0),
    ("canonical float pass",         "sleep 1.5 && echo done",                                  0),
    ("no sleep pass",                "ls -la",                                                  0),
    # --- real block cases ---
    ("chained before sleep BLOCK",   "cmd; sleep 5 && echo done",                               2),
    ("non-echo-done cont BLOCK",     "sleep 5 && ls",                                           2),
    ("real sleep after quoted BLOCK", 'echo "no sleep here"; sleep 3',                          2),
    # --- heredoc body stripped (PASS) ---
    ("heredoc quoted body PASS",     "cat > /tmp/x.sh <<'EOF'\n#!/bin/bash\nsleep 5\nEOF\n",    0),
    ("heredoc unquoted body PASS",   "cat <<EOF\nsleep 5\nEOF\n",                               0),
    # --- quoted strings stripped (PASS) ---
    ("single-quoted sleep PASS",     "echo 'sleep 5 seconds'",                                  0),
    ("double-quoted sleep PASS",     'echo "sleep 5 seconds"',                                  0),
    ("ANSI-C quote sleep PASS",      "echo $'sleep 5'",                                         0),
    # --- command substitutions kept shell-active (BLOCK) ---
    ("cmd-subst sleep BLOCK",        "echo $(sleep 5)",                                         2),
    ("backtick sleep BLOCK",         "echo `sleep 5`",                                          2),
]


# ORCHESTRATOR

def test_block_chained_sleep_workflow() -> None:
    failures = []
    for desc, cmd, expected in CASES:
        got = _run_hook(cmd)
        status = "OK  " if got == expected else "FAIL"
        print(f"  [{status}] {desc}: exit={got} (expected {expected})")
        if got != expected:
            failures.append(desc)
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {len(CASES)} tests passed.")


# FUNCTIONS

# Run hook with given command string; return exit code
def _run_hook(command: str) -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    result = subprocess.run(
        ["python3", HOOK],
        input=payload.encode(),
        capture_output=True,
    )
    return result.returncode


if __name__ == "__main__":
    test_block_chained_sleep_workflow()
