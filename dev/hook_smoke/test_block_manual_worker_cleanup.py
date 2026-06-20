# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_manual_worker_cleanup.py"

CASES = [
    # (description, command, expected_exit_code)
    # --- BLOCK: tmux kill-session on worker- target ---
    ("tmux kill-session full worker session name BLOCK",
     "tmux kill-session -t worker-monitor-cc-hook-docs", 2),
    ("tmux kill-session short worker name BLOCK",
     "tmux kill-session -t worker-foo", 2),
    ("tmux kill-session extra flag before -t BLOCK",
     "tmux kill-session -a -t worker-foo", 2),
    ("tmux kill-session no space after -t BLOCK",
     "tmux kill-session -tworker-foo", 2),
    # --- BLOCK: git worktree remove on .claude/worktrees/ ---
    ("git worktree remove relative path BLOCK",
     "git worktree remove .claude/worktrees/hook-docs", 2),
    ("git worktree remove absolute path BLOCK",
     "git worktree remove /abs/path/.claude/worktrees/hook-docs", 2),
    ("git -C worktree remove worker path BLOCK",
     "git -C /repo worktree remove .claude/worktrees/hook-docs", 2),
    ("git worktree remove --force BLOCK",
     "git worktree remove --force .claude/worktrees/hook-docs", 2),
    # --- ALLOW: recommended path ---
    ("worker-cli kill is allowed PASS",
     "worker-cli kill hook-docs", 0),
    # --- ALLOW: tmux non-worker sessions ---
    ("tmux kill-session non-worker session PASS",
     "tmux kill-session -t main", 0),
    ("tmux kill-session regular session name PASS",
     "tmux kill-session -t my-regular-session", 0),
    ("tmux kill-session no -t arg PASS",
     "tmux kill-session", 0),
    # --- ALLOW: git worktree non-.claude paths ---
    ("git worktree remove non-claude path PASS",
     "git worktree remove /some/other/path", 0),
    ("git worktree list PASS",
     "git worktree list", 0),
    ("git worktree add PASS",
     "git worktree add .claude/worktrees/foo -b foo", 0),
    # --- ALLOW: git branch -D excluded ---
    ("git branch -D allowed PASS",
     "git branch -D hook-docs", 0),
    # --- ALLOW: patterns in quoted strings (blanked by _strip_non_shell_active) ---
    ("tmux kill-session worker in single-quoted message PASS",
     "worker-cli send foo 'tmux kill-session -t worker-bar'", 0),
    ("git worktree remove in double-quoted message PASS",
     'worker-cli send foo "git worktree remove .claude/worktrees/foo"', 0),
    # --- ALLOW: separator tightening (new cases) ---
    ("tmux kill-session separator blocks bridge PASS",
     "tmux kill-session -t main ; echo -t worker-x", 0),
    ("git worktree remove separator blocks bridge PASS",
     "git worktree remove /other ; cat .claude/worktrees/x", 0),
    # --- ALLOW: shell comment residual (consistent with whole hook family) ---
    ("tmux kill-session worker in comment PASS",
     "tmux kill-session -t mysession # worker-cleanup", 0),
]


# ORCHESTRATOR

def test_block_manual_worker_cleanup_workflow() -> None:
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
    test_block_manual_worker_cleanup_workflow()
