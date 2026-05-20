# INFRASTRUCTURE
import json
import os
import sys

_BLOCK_MESSAGE = (
    "BLOCKED: Read tool cannot read directories.\n"
    "Use Bash `ls <path>` to list directory contents instead.\n"
    "If you need a recursive listing: `find <path> -type f` or `ls -R <path>`.\n"
)

# ORCHESTRATOR

# Read Read tool_input from stdin; exit 2 + stderr if file_path points to a directory
def block_read_directory_workflow() -> None:
    path = _parse_path()
    if path is None:
        sys.exit(0)
    if _is_directory(path):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

# Parse stdin JSON and return tool_input.file_path; return None on any error or missing field (fail-open)
def _parse_path():
    try:
        payload = json.loads(sys.stdin.read())
        path = payload.get("tool_input", {}).get("file_path")
        return path if isinstance(path, str) else None
    except Exception:
        return None

# True if path resolves to a directory; False on any filesystem error (fail-open)
def _is_directory(path: str) -> bool:
    try:
        return os.path.isdir(path)
    except Exception:
        return False


if __name__ == "__main__":
    block_read_directory_workflow()
