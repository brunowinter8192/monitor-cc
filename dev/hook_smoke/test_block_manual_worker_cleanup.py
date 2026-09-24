# INFRASTRUCTURE
import json
from hook_runner import abort_if_failed, run_hook

HOOK = "src/hooks/block_manual_worker_cleanup.py"

CASES = [
    ("tmux kill-session full worker session name BLOCK",
     "tmux kill-session -t worker-monitor-cc-hook-docs", 2),
    ("tmux kill-session short worker name BLOCK",
     "tmux kill-session -t worker-foo", 2),
    ("tmux kill-session extra flag before -t BLOCK",
     "tmux kill-session -a -t worker-foo", 2),
    ("tmux kill-session no space after -t BLOCK",
     "tmux kill-session -tworker-foo", 2),
    ("git worktree remove relative path BLOCK",
     "git worktree remove .claude/worktrees/hook-docs", 2),
    ("git worktree remove absolute path BLOCK",
     "git worktree remove /abs/path/.claude/worktrees/hook-docs", 2),
    ("git -C worktree remove worker path BLOCK",
     "git -C /repo worktree remove .claude/worktrees/hook-docs", 2),
    ("git worktree remove --force BLOCK",
     "git worktree remove --force .claude/worktrees/hook-docs", 2),
    ("worker-cli kill is allowed PASS",
     "worker-cli kill hook-docs", 0),
    ("tmux kill-session non-worker session PASS",
     "tmux kill-session -t main", 0),
    ("tmux kill-session regular session name PASS",
     "tmux kill-session -t my-regular-session", 0),
    ("tmux kill-session no -t arg PASS",
     "tmux kill-session", 0),
    ("git worktree remove non-claude path PASS",
     "git worktree remove /some/other/path", 0),
    ("git worktree list PASS",
     "git worktree list", 0),
    ("git worktree add PASS",
     "git worktree add .claude/worktrees/foo -b foo", 0),
    ("git branch -D allowed PASS",
     "git branch -D hook-docs", 0),
    ("tmux kill-session worker in single-quoted message PASS",
     "worker-cli send foo 'tmux kill-session -t worker-bar'", 0),
    ("git worktree remove in double-quoted message PASS",
     'worker-cli send foo "git worktree remove .claude/worktrees/foo"', 0),
    ("tmux kill-session separator blocks bridge PASS",
     "tmux kill-session -t main ; echo -t worker-x", 0),
    ("git worktree remove separator blocks bridge PASS",
     "git worktree remove /other ; cat .claude/worktrees/x", 0),
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
            abort_if_failed(failures)
    print()
    print(f"All {len(CASES)} tests passed.")


# FUNCTIONS

def _run_hook(command: str) -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    result = run_hook(HOOK, payload.encode())
    return result.returncode


if __name__ == "__main__":
    test_block_manual_worker_cleanup_workflow()
