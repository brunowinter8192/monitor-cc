# INFRASTRUCTURE
import json
import sys
import tempfile
from pathlib import Path
from case_strands import case_runners, report_case, run_case_strands
from hook_runner import run_hook

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
HOOK = str(WORKTREE_ROOT / "src" / "hooks" / "rewrite_background_sleep.py")

CASES = [
    (
        "sleep 300 background timer → rewrite to worker-cli wait",
        "sleep 300 && echo done",
        True,
        "worker-cli wait",
        "orchestrator",
    ),
    (
        "sleep 5 background timer → rewrite to worker-cli wait",
        "sleep 5 && echo done",
        True,
        "worker-cli wait",
        "orchestrator",
    ),
    (
        "sleep 1200 background timer → rewrite to worker-cli wait",
        "sleep 1200 && echo done",
        True,
        "worker-cli wait",
        "orchestrator",
    ),
    (
        "old canonical sleep 3300 && echo done — also a stale habit now, rewrite",
        "sleep 3300 && echo done",
        True,
        "worker-cli wait",
        "orchestrator",
    ),
    (
        "bare sleep 300 — bare sleep, rewrite to worker-cli wait",
        "sleep 300",
        True,
        "worker-cli wait",
        "orchestrator",
    ),
    (
        "sleep 45 with custom echo text (fire-log actual incident) → rewrite",
        'sleep 45 && echo "bg-ack-probe done"',
        True,
        "worker-cli wait",
        "orchestrator",
    ),
    (
        "foreground sleep 300 — no background flag, no rewrite",
        "sleep 300 && echo done",
        False,
        None,
        "orchestrator",
    ),
    (
        "worker-cli wait bare — already canonical, no rewrite",
        "worker-cli wait",
        True,
        None,
        "orchestrator",
    ),
    (
        "worker-cli wait with project_path + --timeout — already canonical, no rewrite",
        "worker-cli wait /path/to/project --timeout 600",
        True,
        None,
        "orchestrator",
    ),
    (
        "rag-cli background — not canonical form, no rewrite",
        "rag-cli update_docs .",
        True,
        None,
        "orchestrator",
    ),
    (
        "sleep 300 && rag-cli — not echo done form, no rewrite",
        "sleep 300 && rag-cli server list",
        True,
        None,
        "orchestrator",
    ),
    (
        "bare sleep 300 from a WORKTREE cwd — orchestrator-only guard, no rewrite",
        "sleep 300",
        True,
        None,
        "worktree",
    ),
    (
        "sleep 3300 && echo done from a WORKTREE cwd — old canonical form, still no rewrite",
        "sleep 3300 && echo done",
        True,
        None,
        "worktree",
    ),
    (
        "foreground sleep from a WORKTREE cwd — no rewrite (already a no-op via the bg-flag gate)",
        "sleep 300 && echo done",
        False,
        None,
        "worktree",
    ),
]


# ORCHESTRATOR

def test_rewrite_background_sleep_workflow() -> None:
    sys.exit(run_case_strands(globals(), __file__, case_runners(CASES, _check_case)))


# FUNCTIONS

def _check_case(case: tuple) -> None:
    desc, command, run_in_background, expected_rewrite, cwd_kind = case
    with tempfile.TemporaryDirectory() as outer:
        exit_code, rewrite = _run_hook(command, run_in_background, _cwd_for_kind(cwd_kind, outer))
    ok = exit_code == 0 and rewrite == expected_rewrite
    want = repr(expected_rewrite) if expected_rewrite is not None else "None (no output)"
    got = repr(rewrite) if rewrite is not None else "None (no output)"
    report_case(desc, ok, '' if ok else f'\n           want: {want}\n           got:  {got} (exit={exit_code})')


def _run_hook(command: str, run_in_background: bool, cwd: str):
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command, "run_in_background": run_in_background},
    })
    result = run_hook(HOOK, payload.encode(), cwd=cwd)
    rewrite = None
    if result.returncode == 0 and result.stdout.strip():
        try:
            data   = json.loads(result.stdout)
            rewrite = data["hookSpecificOutput"]["updatedInput"]["command"]
        except (KeyError, json.JSONDecodeError):
            rewrite = None
    return result.returncode, rewrite


def _cwd_for_kind(cwd_kind: str, outer: str) -> str:
    if cwd_kind == "orchestrator":
        return outer
    worktree_cwd = Path(outer) / ".claude" / "worktrees" / "fake-worker"
    worktree_cwd.mkdir(parents=True)
    return str(worktree_cwd)


if __name__ == "__main__":
    test_rewrite_background_sleep_workflow()
