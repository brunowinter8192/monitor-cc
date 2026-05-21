# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_dangerous_kill.py"

CASES = [
    # (description, command, expected_exit_code)
    # --- true positives: must block ---
    ("pkill -f pattern BLOCK",
     'pkill -f "workflow.py --mode menubar"', 2),
    ("pkill -f at start BLOCK",
     "pkill -f some_script.py", 2),
    ("pgrep -f pipe kill BLOCK",
     "pgrep -f some_proc | xargs kill", 2),
    ("kill $(pgrep -f X) BLOCK",
     "kill $(pgrep -f myapp)", 2),
    ("ps grep kill chain BLOCK",
     "ps aux | grep myapp | xargs kill", 2),
    # --- false positive fixes: must pass ---
    ("pkill -f in single-quoted string PASS",
     "echo 'pkill -f pattern is blocked'", 0),
    ("pkill -f in double-quoted string PASS",
     'echo "pkill -f pattern is blocked"', 0),
    ("pkill -f in heredoc body PASS",
     "python3 <<'EOF'\ntest = 'pkill -f myapp'\nEOF", 0),
    ("pkill -f in heredoc unquoted PASS",
     "cat <<EOF\npkill -f example\nEOF", 0),
    # --- safe patterns: must pass ---
    ("pkill -x exact name PASS",
     "pkill -x myapp", 0),
    ("pkill no -f PASS",
     "pkill myapp", 0),
    ("kill numeric pid PASS",
     "kill 12345", 0),
    ("kill signal pid PASS",
     "kill -9 12345", 0),
    ("worker-cli kill PASS",
     "worker-cli kill my-worker", 0),
    ("no kill at all PASS",
     "ls -la && git status", 0),
]


# ORCHESTRATOR

def test_block_dangerous_kill_workflow() -> None:
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
    test_block_dangerous_kill_workflow()
