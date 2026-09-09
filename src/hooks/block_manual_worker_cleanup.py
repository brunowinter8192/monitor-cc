# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_TMUX_KILL_WORKER_RE = re.compile(r'\btmux\s+kill-session\b[^;&|\n]*\s-t\s*worker-')

_GIT_WORKTREE_REMOVE_RE = re.compile(
    r'\bgit\s+(?:-C\s+\S+\s+)?worktree\s+remove\b[^;&|\n]*\.claude/worktrees/'
)

_BLOCK_MESSAGE = (
    "BLOCKED: raw worker-cleanup command detected.\n"
    "`tmux kill-session -t worker-*` and `git worktree remove .claude/worktrees/*` leave orphaned\n"
    "state (dangling worktree, registry entry, or branch).\n"
    "Use: worker-cli kill <name>  "
    "— atomically kills session + removes worktree + deletes branch + clears registry.\n"
)


# ORCHESTRATOR

def block_manual_worker_cleanup_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if _TMUX_KILL_WORKER_RE.search(stripped) or _GIT_WORKTREE_REMOVE_RE.search(stripped):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_manual_worker_cleanup", "block", "Bash", command,
                 reason=_BLOCK_MESSAGE, session_id=session_id)
        sys.exit(2)
    sys.exit(0)


# FUNCTIONS

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


if __name__ == "__main__":
    block_manual_worker_cleanup_workflow()
