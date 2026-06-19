# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_WORKTREE_FRAGMENT = '.claude/worktrees/'

# 3rd positional after 'spawn': worker-cli spawn <name> <prompt_file> <project_path> [model] [--no-worktree]
_SPAWN_RE       = re.compile(r'\bworker-cli\s+spawn\s+(\S+)\s+(\S+)\s+(\S+)', re.DOTALL)
_NO_WORKTREE_RE = re.compile(r'\bworker-cli\s+spawn\b.*--no-worktree\b', re.DOTALL)

_WRONG_PROJECT_MSG  = (
    "worker spawn nur im aktuellen projekt — nutze 'c' (worktree im aktuellen projekt). "
    "Für cross-project arbeit: mit 'c' spawnen, dann im zielprojekt selbst ein worktree bauen "
    "(git -C <zielprojekt> worktree add .claude/worktrees/<name> -b <name>) und den worker DORT arbeiten lassen "
    "— oder, wenn die zieldateien gitignored sind, direkt im source des zielprojekts. Nie --no-worktree.\n"
)
_NO_WORKTREE_MSG    = "worker spawn immer im worktree — kein --no-worktree\n"

# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if spawn targets a different project or uses --no-worktree.
# Skipped entirely when the hook runs from inside a worktree (worker sessions don't spawn workers).
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

# Parse stdin JSON; return (command, session_id); (None, None) on any error (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


# Resolve path to its git-root after stripping any /.claude/worktrees/<name> suffix.
# Applies os.path.realpath to normalise symlink components (/Users vs /System/Volumes/Data/Users).
# Returns None when no .git root is found (caller treats as fail-open).
def _resolve_project_root(path: str) -> str | None:
    p = os.path.abspath(os.path.expanduser(path))
    idx = p.find('/' + _WORKTREE_FRAGMENT)
    if idx >= 0:
        p = p[:idx]
    p = os.path.realpath(p)
    return _find_git_root(p)


# Walk up from start until a directory containing .git is found; return that directory or None.
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
