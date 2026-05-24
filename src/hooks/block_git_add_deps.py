# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

# git add invocation (with optional -C path flag)
_GIT_ADD = re.compile(r'\bgit\s+(?:-C\s+\S+\s+)?add\b')
# Dependency directory names as explicit targets (with or without trailing slash)
_DEP_TARGET = re.compile(r'\b(?:venv|\.venv|node_modules)/?(?:\s|$)')

_BLOCK_MESSAGE = (
    "BLOCKED: `git add` targeting a dependency directory (venv/, .venv/, node_modules/).\n"
    "Worktrees contain symlinked dependency directories that point to the main repo's\n"
    "real directories. Staging these symlinks creates circular self-references when the\n"
    "branch is merged back — the symlinks in the merged result point at themselves.\n"
    "\n"
    "These directories must NEVER be staged or committed, even when `git status` shows\n"
    "them as untracked. Add them to .gitignore if they are not already excluded.\n"
    "worker-rules.md \u00a7 Never Commit Dependency Directories.\n"
)

# ORCHESTRATOR

# Read Bash tool_input; exit 2 + stderr if command stages a dependency directory
def block_git_add_deps_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_quoted(command)
    if _GIT_ADD.search(stripped) and _DEP_TARGET.search(stripped):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_git_add_deps", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
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

# Strip content inside single/double quotes to avoid matching quoted dependency dir names
def _strip_quoted(s: str) -> str:
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in ("'", '"'):
            quote, i = c, i + 1
            while i < n and s[i] != quote:
                if s[i] == "\\" and i + 1 < n:
                    i += 2
                else:
                    i += 1
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


if __name__ == "__main__":
    block_git_add_deps_workflow()
