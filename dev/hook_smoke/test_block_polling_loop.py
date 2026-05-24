# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_polling_loop.py"

CASES = [
    # (description, command, expected_exit_code)
    # --- true positives: must block ---
    ("exact incident pattern BLOCK",
     "ps -p 12345 > /dev/null 2>&1 && echo still running || echo done; "
     "wc -l /tmp/sweep.log; tail -18 /tmp/sweep.log", 2),
    ("ps -p + tail -N same chain BLOCK",
     "ps -p 9876; tail -50 /tmp/out.log", 2),
    ("ps -p + tail -N with redirect BLOCK",
     "ps -p 42 && tail -5 /tmp/build.log", 2),
    # --- false positive fixes: must pass ---
    ("ps -p alone PASS",
     "ps -p 12345 > /dev/null 2>&1 && echo running || echo done", 0),
    ("tail -N alone PASS",
     "tail -18 /tmp/cross_sweep_output.log", 0),
    ("ps -p + tail -N in single-quoted string PASS",
     "echo 'ps -p 123 && tail -18 /tmp/log'", 0),
    ("ps -p + tail -N in heredoc body PASS",
     "python3 <<'EOF'\ncmd = 'ps -p 123; tail -10 /tmp/log'\nEOF", 0),
    ("ps aux no -p flag PASS",
     "ps aux | grep python", 0),
    ("tail -n N long form PASS",
     "ps -p 555; tail -n 20 /tmp/file.log", 0),
    ("unrelated command PASS",
     "git status && ls -la", 0),
]


# ORCHESTRATOR

def test_block_polling_loop_workflow() -> None:
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
    test_block_polling_loop_workflow()
