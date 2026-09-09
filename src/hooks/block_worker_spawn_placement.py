# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_WORKTREE_FRAGMENT = '.claude/worktrees/'

_SPAWN_RE       = re.compile(r'\bworker-cli\s+spawn\s+(\S+)\s+(\S+)\s+(\S+)', re.DOTALL)
_NO_WORKTREE_RE = re.compile(r'\bworker-cli\s+spawn\b.*--no-worktree\b', re.DOTALL)

_WRONG_PROJECT_MSG  = (
    "BLOCKED: worker-cli spawn targets a different project than the current session.\n"
    "Use: worker-cli spawn <name> <prompt_file> c   (worktree in the CURRENT project).\n"
    "For cross-project work: spawn here with 'c', then set up the target project with\n"
    "worker-cli worktree <name> <target_repo> — this creates AND registers the target\n"
    "worktree so worker-cli kill cleans it up later — and have the worker operate there.\n"
    "Never --no-worktree.\n"
)
_NO_WORKTREE_MSG    = (
    "BLOCKED: worker-cli spawn with --no-worktree.\n"
    "Use: worker-cli spawn <name> <prompt_file> <project_path>   (always spawns into a worktree).\n"
)

# ORCHESTRATOR

def block_worker_spawn_placement_workflow() -> None:
    if _WORKTREE_FRAGMENT in os.getcwd():
        sys.exit(0)
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    spawn_match = _SPAWN_RE.search(stripped)
    if not spawn_match:
        sys.exit(0)
    if _NO_WORKTREE_RE.search(stripped):
        print(_NO_WORKTREE_MSG, file=sys.stderr, end="")
        log_fire("block_worker_spawn_placement", "block", "Bash", command, reason=_NO_WORKTREE_MSG, session_id=session_id)
        sys.exit(2)
    project_path_arg = spawn_match.group(3)
    if project_path_arg in ('c', '.'):
        sys.exit(0)
    spawn_root = _resolve_project_root(project_path_arg)
    if spawn_root is None:
        sys.exit(0)
    current_root = _resolve_project_root(os.getcwd())
    if current_root is None:
        sys.exit(0)
    if spawn_root.lower() != current_root.lower():
        print(_WRONG_PROJECT_MSG, file=sys.stderr, end="")
        log_fire("block_worker_spawn_placement", "block", "Bash", command, reason=_WRONG_PROJECT_MSG, session_id=session_id)
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


def _resolve_project_root(path: str) -> str | None:
    p = os.path.abspath(os.path.expanduser(path))
    idx = p.find('/' + _WORKTREE_FRAGMENT)
    if idx >= 0:
        p = p[:idx]
    p = os.path.realpath(p)
    return _find_git_root(p)


def _find_git_root(start: str) -> str | None:
    p = start
    while True:
        if os.path.isdir(os.path.join(p, '.git')):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent


if __name__ == "__main__":
    block_worker_spawn_placement_workflow()
