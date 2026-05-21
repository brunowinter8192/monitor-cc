# INFRASTRUCTURE
import json
import os
import subprocess
import sys

HOOK = "src/hooks/block_read_worktree.py"

# Derive the current worktree root (tests run from inside the hook-heredoc worktree)
_CWD = os.getcwd()
_WT_ROOT = _CWD if '.claude/worktrees/' in _CWD else None  # e.g. /path/.../worktrees/hook-heredoc

CASES = [
    # (description, file_path, expected_exit_code)
    # --- foreign worktree reads → BLOCK ---
    ("cross-worktree read BLOCK",
     "/fake/project/.claude/worktrees/other-worker/src/foo.py", 2),
    # --- main-project path (no worktrees fragment) → PASS ---
    ("main project path PASS",
     "/Users/x/project/src/hooks/block_read_worktree.py", 0),
    # --- own worktree read → PASS (only testable when running inside a worktree) ---
    ("own worktree read PASS",
     _WT_ROOT + "/src/hooks/block_read_worktree.py" if _WT_ROOT else None, 0),
    # --- path without worktree fragment → PASS ---
    ("plain path PASS", "/tmp/some_file.py", 0),
    # --- empty / None field → PASS (fail-open) ---
    ("missing file_path PASS", None, 0),
]


# ORCHESTRATOR

def test_block_read_worktree_workflow() -> None:
    failures = []
    for desc, path, expected in CASES:
        if path is None and expected == 0:
            # missing file_path field — send payload without it
            got = _run_hook_raw(json.dumps({"tool_name": "Read", "tool_input": {}}))
        elif path is None:
            got = _run_hook(path)
        else:
            got = _run_hook(path)
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
    print(f"All {len([c for c in CASES if c[1] is not None or c[2] == 0])} tests passed.")


# FUNCTIONS

# Run hook with given file_path string; return exit code
def _run_hook(file_path: str) -> int:
    payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": file_path}})
    return _run_hook_raw(payload)

# Run hook with raw JSON payload; return exit code
def _run_hook_raw(payload: str) -> int:
    result = subprocess.run(
        ["python3", HOOK],
        input=payload.encode(),
        capture_output=True,
    )
    return result.returncode


if __name__ == "__main__":
    test_block_read_worktree_workflow()
