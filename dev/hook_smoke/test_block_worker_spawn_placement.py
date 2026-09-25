# INFRASTRUCTURE
import json
import sys
import tempfile
from pathlib import Path
from case_strands import case_runners, report_case, run_case_strands
from hook_runner import run_hook

HOOK = "src/hooks/block_worker_spawn_placement.py"

CASES = [
    ("spawn with --no-worktree BLOCK",
     "worker-cli spawn mytask /tmp/prompt.md --no-worktree", 2),
    ("spawn with --no-worktree before the prompt file BLOCK",
     "worker-cli spawn mytask --no-worktree /tmp/prompt.md", 2),
    ("spawn in the new form NO-OP",
     "worker-cli spawn mytask /tmp/prompt.md", 0),
    ("spawn in the old form with a project path — the CLI rejects it NO-OP",
     "worker-cli spawn mytask /tmp/prompt.md /some/other/project", 0),
    ("spawn in the old form with c — the CLI rejects it NO-OP",
     "worker-cli spawn mytask /tmp/prompt.md c", 0),
    ("worker-cli worktree with a target repo NO-OP",
     "worker-cli worktree mytask /some/target/repo", 0),
    ("--no-worktree mentioned only inside a quoted send message NO-OP",
     'worker-cli send orchestrator "never spawn with --no-worktree"', 0),
    ("worker-cli spawn mentioned only inside a heredoc body NO-OP",
     "cat <<'EOF' > /tmp/note.md\nworker-cli spawn a b --no-worktree\nEOF", 0),
    ("unrelated command NO-OP",
     "echo hello world", 0),
    ("spawn with --no-worktree from a WORKTREE cwd — guard skipped NO-OP",
     "worker-cli spawn mytask /tmp/prompt.md --no-worktree", 0, True),
]


# ORCHESTRATOR

def test_block_worker_spawn_placement_workflow() -> None:
    sys.exit(run_case_strands(globals(), __file__, case_runners(CASES, _check_case)))


# FUNCTIONS

def _check_case(case: tuple) -> None:
    desc, command, expected_exit, *rest = case
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    with tempfile.TemporaryDirectory(prefix="spawn_placement_") as outer:
        cwd = Path(outer) / ".claude" / "worktrees" / "fake-worker" if rest else Path(outer)
        cwd.mkdir(parents=True, exist_ok=True)
        result = run_hook(HOOK, payload.encode(), cwd=cwd)
    ok = result.returncode == expected_exit
    report_case(desc, ok, '' if ok else f'\n           want: exit={expected_exit}\n           got:  exit={result.returncode}')


if __name__ == "__main__":
    test_block_worker_spawn_placement_workflow()
