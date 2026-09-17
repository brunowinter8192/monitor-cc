# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_unauthorized_background.py"

CASES = [
    ("sleep N && echo done — sleep-only form ALLOW",
     "sleep 300 && echo done", True, None),
    ("sleep N bare — sleep-only form ALLOW",
     "sleep 300", True, None),
    ("sleep N with custom echo text (fire-log actual) ALLOW",
     'sleep 45 && echo "bg-ack-probe done"', True, None),

    ("worker-cli wait bare ALLOW",
     "worker-cli wait", True, None),
    ("worker-cli wait with project_path ALLOW",
     "worker-cli wait /path/to/project", True, None),
    ("worker-cli wait with --timeout ALLOW",
     "worker-cli wait --timeout 600", True, None),
    ("worker-cli wait with project_path + --timeout ALLOW",
     "worker-cli wait /path/to/project --timeout 600", True, None),

    ("reddit-cli index_subreddits — foreground-forced FORCE",
     "reddit-cli index_subreddits", True, False),
    ("workflow.py index-dir — foreground-forced FORCE",
     "workflow.py index-dir", True, False),

    ("./venv/bin/python script.py — non-canonical background FORCE",
     "./venv/bin/python script.py", True, False),
    ("rag-cli update_docs — original triggering incident FORCE",
     "rag-cli update_docs .", True, False),
    ("worker-cli waitfoo — not a word-boundary match on 'wait' FORCE",
     "worker-cli waitfoo", True, False),

    ("worker-cli wait && rag-cli index — mentions wait, this hook has no "
     "opinion (rewrite_worker_wait.py decides instead) NO-OP",
     "worker-cli wait && rag-cli index docs", True, None),
    ("cd /tmp; worker-cli wait — mentions wait, this hook has no opinion NO-OP",
     "cd /tmp; worker-cli wait", True, None),
    ("worker-cli wait mentioned only inside a quoted echo argument does NOT "
     "exempt an unrelated non-canonical command FORCE",
     'echo "worker-cli wait" && ./venv/bin/python script.py', True, False),

    ("./venv/bin/python script.py foreground — no output PASS",
     "./venv/bin/python script.py", False, None),
]


# ORCHESTRATOR

def test_block_unauthorized_background_workflow() -> None:
    failures = []
    for desc, cmd, rb, expected_bg in CASES:
        got_bg = _run_hook(cmd, rb)
        ok = got_bg == expected_bg
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {desc}: rewritten_bg={got_bg!r} (expected {expected_bg!r})")
        if not ok:
            failures.append(desc)
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {len(CASES)} tests passed.")


# FUNCTIONS

def _run_hook(command: str, run_in_background: bool):
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command, "run_in_background": run_in_background},
    })
    result = subprocess.run(
        ["python3", HOOK],
        input=payload.encode(),
        capture_output=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        try:
            data = json.loads(result.stdout)
            return data["hookSpecificOutput"]["updatedInput"]["run_in_background"]
        except (KeyError, json.JSONDecodeError):
            pass
    return None


if __name__ == "__main__":
    test_block_unauthorized_background_workflow()
