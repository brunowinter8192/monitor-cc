# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.hooks._shell_strip import _strip_non_shell_active
from src.hooks._fire_log import log_fire

_WORKTREE_FRAGMENT = '.claude/worktrees/'

_SPAWN_RE       = re.compile(r'\bworker-cli\s+spawn\s+(\S+)\s+(\S+)', re.DOTALL)
_NO_WORKTREE_RE = re.compile(r'\bworker-cli\s+spawn\b.*--no-worktree\b', re.DOTALL)

_NO_WORKTREE_MSG    = (
    "BLOCKED: worker-cli spawn with --no-worktree.\n"
    "Use: worker-cli spawn <name> <prompt_file>   (always spawns into a worktree of the current project).\n"
)

# ORCHESTRATOR

def block_worker_spawn_placement_workflow() -> None:
    if _WORKTREE_FRAGMENT in os.getcwd():
        sys.exit(0)
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if not _SPAWN_RE.search(stripped):
        sys.exit(0)
    if _NO_WORKTREE_RE.search(stripped):
        print(_NO_WORKTREE_MSG, file=sys.stderr, end="")
        log_fire("block_worker_spawn_placement", "block", "Bash", command, reason=_NO_WORKTREE_MSG, session_id=session_id)
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception as e:
        log_fire("block_worker_spawn_placement", "trace", "Bash", "", reason=f"parse error: {type(e).__name__}: {e}")
        return None, None


if __name__ == "__main__":
    block_worker_spawn_placement_workflow()
