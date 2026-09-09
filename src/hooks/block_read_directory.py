# INFRASTRUCTURE
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

_BLOCK_MESSAGE = "Read cannot read directories — use `ls <path>` instead\n"

# ORCHESTRATOR

def block_read_directory_workflow() -> None:
    path, session_id = _parse_path()
    if path is None:
        sys.exit(0)
    if _is_directory(path):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_read_directory", "block", "Read", path, reason=_BLOCK_MESSAGE, session_id=session_id)
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

def _parse_path():
    try:
        payload = json.loads(sys.stdin.read())
        path = payload.get("tool_input", {}).get("file_path")
        return (path if isinstance(path, str) else None), payload.get("session_id")
    except Exception:
        return None, None

def _is_directory(path: str) -> bool:
    try:
        return os.path.isdir(path)
    except Exception:
        return False


if __name__ == "__main__":
    block_read_directory_workflow()
