# INFRASTRUCTURE
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

_WORKTREE_FRAGMENT = '.claude/worktrees/'

_BLOCK_MESSAGE = (
    "BLOCKED: Read on a worktree path silently re-injects CLAUDE.md into context.\n"
    "Reading any file under `.claude/worktrees/...` via the Read tool injects the\n"
    "auto-loaded CLAUDE.md system-reminder again, bloating the context window and\n"
    "potentially duplicating the system prompt.\n"
    "\n"
    "Use Bash instead:\n"
    "    cat <worktree>/path/to/file              # full content\n"
    "    head -50 <worktree>/path/to/file         # first N lines\n"
    "    git -C <worktree> show HEAD:<relpath>    # specific revision\n"
    "    git -C <worktree> diff dev               # code review diff\n"
    "workers-2.md § Code Review.\n"
)


# ORCHESTRATOR

# Read Read tool_input from stdin; exit 2 + stderr if file_path is a foreign worktree path.
# Workers reading files inside their OWN worktree are allowed.
def block_read_worktree_workflow() -> None:
    path, session_id = _parse_path()
    if path is None:
        sys.exit(0)
    if _WORKTREE_FRAGMENT in path and not _is_own_worktree(path):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_read_worktree", "block", "Read", path, reason=_BLOCK_MESSAGE, session_id=session_id)
        sys.exit(2)
    sys.exit(0)


# FUNCTIONS

# Parse stdin JSON; return (file_path, session_id); (None, None) on any error (fail-open)
def _parse_path():
    try:
        payload = json.loads(sys.stdin.read())
        path = payload.get("tool_input", {}).get("file_path")
        return (path if isinstance(path, str) else None), payload.get("session_id")
    except Exception:
        return None, None

# True if file_path is inside the same worktree as the current session CWD.
# Hook subprocesses inherit the spawning CC session's CWD, so os.getcwd() is the session root.
# Returns False when called from a main session (CWD has no worktree fragment) — conservative.
def _is_own_worktree(file_path: str) -> bool:
    try:
        cwd = os.getcwd()
        if _WORKTREE_FRAGMENT not in cwd:
            return False  # main session — all worktree reads are foreign
        prefix, _, rest = cwd.partition('/' + _WORKTREE_FRAGMENT)
        wt_name = rest.split('/')[0]
        wt_root = f"{prefix}/{_WORKTREE_FRAGMENT}{wt_name}"
        return file_path.startswith(wt_root + '/')
    except Exception:
        return False  # fail-safe: unknown CWD → treat as foreign → block


if __name__ == "__main__":
    block_read_worktree_workflow()
