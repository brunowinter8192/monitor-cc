# INFRASTRUCTURE
import json
import sys
from case_strands import case_runners, report_case, run_case_strands
from hook_runner import run_hook

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
    sys.exit(run_case_strands(globals(), __file__, case_runners(CASES, _check_case)))


# FUNCTIONS

def _check_case(case: tuple) -> None:
    desc, command, run_in_background, expected_bg = case
    got_bg = _run_hook(command, run_in_background)
    report_case(desc, got_bg == expected_bg, f': rewritten_bg={got_bg!r} (expected {expected_bg!r})')


def _run_hook(command: str, run_in_background: bool):
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command, "run_in_background": run_in_background},
    })
    result = run_hook(HOOK, payload.encode())
    if result.returncode == 0 and result.stdout.strip():
        data = json.loads(result.stdout)
        return data["hookSpecificOutput"]["updatedInput"]["run_in_background"]
    return None


if __name__ == "__main__":
    test_block_unauthorized_background_workflow()
