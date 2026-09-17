# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_worker_wait_foreground.py"

CASES = [
    ("bare worker-cli wait, run_in_background true ALLOW",
     "worker-cli wait", True, 0),
    ("bare with project_path + --timeout, run_in_background true ALLOW",
     "worker-cli wait /path/to/project --timeout 600", True, 0),
    ("rewrite_background_sleep.py's own output, run_in_background true ALLOW",
     "worker-cli wait", True, 0),

    ("bare worker-cli wait, run_in_background false BLOCK",
     "worker-cli wait", False, 2),
    ("bare worker-cli wait, run_in_background omitted BLOCK",
     "worker-cli wait", None, 2),
    ("worker-cli wait with --timeout, run_in_background false BLOCK",
     "worker-cli wait --timeout 600", False, 2),
    ("cd ; worker-cli wait, run_in_background false BLOCK",
     "cd /tmp; worker-cli wait", False, 2),

    ("unrelated command, run_in_background false ALLOW",
     "echo hello world", False, 0),
    ("worker-cli wait mentioned only inside a quoted send message, "
     "run_in_background false ALLOW",
     'worker-cli send orchestrator "Do not run worker-cli wait in the foreground."', False, 0),
]


# ORCHESTRATOR

def test_block_worker_wait_foreground_workflow() -> None:
    failures = []
    for desc, cmd, rb, expected in CASES:
        got = _run_hook(cmd, rb)
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

def _run_hook(command: str, run_in_background) -> int:
    tool_input = {"command": command}
    if run_in_background is not None:
        tool_input["run_in_background"] = run_in_background
    payload = json.dumps({"tool_name": "Bash", "tool_input": tool_input})
    result = subprocess.run(
        ["python3", HOOK],
        input=payload.encode(),
        capture_output=True,
    )
    return result.returncode


if __name__ == "__main__":
    test_block_worker_wait_foreground_workflow()
