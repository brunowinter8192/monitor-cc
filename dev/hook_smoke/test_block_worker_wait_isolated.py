# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_worker_wait_isolated.py"

CASES = [
    ("bare worker-cli wait ALLOW",
     "worker-cli wait", 0),
    ("bare with --timeout ALLOW",
     "worker-cli wait --timeout 600", 0),
    ("bare with project_path ALLOW",
     "worker-cli wait /path/to/project", 0),
    ("bare with project_path + --timeout ALLOW",
     "worker-cli wait /path/to/project --timeout 600", 0),
    ("rewrite_background_sleep.py's own output ALLOW",
     "worker-cli wait", 0),

    ("cd ; worker-cli wait — the actual incident shape BLOCK",
     "cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch; worker-cli wait", 2),
    ("cd && worker-cli wait BLOCK",
     "cd /tmp && worker-cli wait", 2),
    ("worker-cli wait && rag-cli index docs — chained after BLOCK",
     "worker-cli wait && rag-cli index docs", 2),
    ("worker-cli wait ; echo done — chained after with ; BLOCK",
     "worker-cli wait ; echo done", 2),
    ("worker-cli wait piped BLOCK",
     "worker-cli wait | tee /tmp/log", 2),

    ("worker-cli waitfoo — not a word-boundary match ALLOW",
     "worker-cli waitfoo", 0),
    ("unrelated command ALLOW",
     "echo hello world", 0),
    ("worker-cli wait mentioned only inside a quoted send message ALLOW",
     'worker-cli send orchestrator "Arm worker-cli wait after every dispatch."', 0),
    ("worker-cli wait mentioned only inside a heredoc body ALLOW",
     "cat <<'EOF' > /tmp/prompt.md\nRun worker-cli wait after you dispatch.\nEOF", 0),
]


# ORCHESTRATOR

def test_block_worker_wait_isolated_workflow() -> None:
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
    test_block_worker_wait_isolated_workflow()
