# INFRASTRUCTURE
import json
import os
import sys
from case_strands import exit_code_runners, fail_open_runner, run_case_strands
from hook_runner import run_hook

HOOK = "src/hooks/block_rules_skills_edit.py"
HOME = os.path.expanduser("~")

CASES = [
    ("Edit under shared-rules BLOCK",
     f"{HOME}/.claude/shared-rules/global/tool-use.md", 2, "Edit"),
    ("Write of new file under shared-rules BLOCK",
     f"{HOME}/.claude/shared-rules/global/new_rule.md", 2, "Write"),
    ("Edit under ~/.claude/skills BLOCK",
     f"{HOME}/.claude/skills/some-skill/SKILL.md", 2, "Edit"),
    ("Write into iterative-dev skills directory BLOCK",
     f"{HOME}/Documents/ai/Meta/iterative-dev/skills/new-skill/SKILL.md", 2, "Write"),
    ("Edit on ordinary path PASS",
     f"{HOME}/Documents/ai/monitor-cc/src/hooks/block_po_read.py", 0, "Edit"),
    ("Read of skills path PASS",
     f"{HOME}/.claude/skills/some-skill/SKILL.md", 0, "Read"),
]


# ORCHESTRATOR

def test_block_rules_skills_edit_workflow() -> None:
    sys.exit(run_case_strands(globals(), __file__, _all_runners()))


# FUNCTIONS

def _all_runners() -> dict:
    runners = exit_code_runners(CASES, _run_hook)
    runners.update(fail_open_runner("parse-error fail-open PASS", _run_hook_raw, b"not valid json{{{"))
    return runners


def _run_hook(file_path: str, tool_name: str) -> int:
    payload = json.dumps({
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path, "content": "x"},
    })
    return _run_hook_raw(payload.encode())


def _run_hook_raw(stdin_bytes: bytes) -> int:
    return run_hook(HOOK, stdin_bytes).returncode


if __name__ == "__main__":
    test_block_rules_skills_edit_workflow()
