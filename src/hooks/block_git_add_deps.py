# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.hooks._fire_log import log_fire
from src.hooks._shell_strip import _strip_non_shell_active

_SEGMENT_SPLIT = re.compile(r'&&|\|\||[;|\n]')
_GIT_ADD_DEP = re.compile(r'\bgit\s+(?:-C\s+\S+\s+)?add\b(?:\s+\S+)*?\s+(?:\./)?(?:venv|\.venv|node_modules)/?(?=\s|$)')

_BLOCK_MESSAGE = "venv/, .venv/, node_modules/ must never be staged — add to .gitignore if not already there\n"

# ORCHESTRATOR

def block_git_add_deps_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if _adds_dependency_dir(stripped):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_git_add_deps", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception as e:
        log_fire("block_git_add_deps", "trace", "Bash", "", reason=f"parse error: {type(e).__name__}: {e}")
        return None, None

def _adds_dependency_dir(stripped: str) -> bool:
    return any(_GIT_ADD_DEP.search(segment) for segment in _SEGMENT_SPLIT.split(stripped))


if __name__ == "__main__":
    block_git_add_deps_workflow()
