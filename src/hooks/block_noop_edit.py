# INFRASTRUCTURE
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

_BLOCK_MESSAGE = "old_string == new_string — re-read the file first before retrying (content may have changed)\n"

# ORCHESTRATOR

# Read Edit tool_input from stdin; exit 2 + stderr if old_string == new_string
def block_noop_edit_workflow() -> None:
    old_string, new_string, file_path, session_id = _parse_input()
    if old_string is None or new_string is None:
        sys.exit(0)
    if old_string == new_string:
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_noop_edit", "block", "Edit", file_path or "", reason=_BLOCK_MESSAGE, session_id=session_id)
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

# Parse stdin JSON; return (old_string, new_string, file_path, session_id); (None, None, None, None) on error (fail-open)
def _parse_input():
    try:
        payload = json.loads(sys.stdin.read())
        tool_input = payload.get("tool_input", {})
        old = tool_input.get("old_string")
        new = tool_input.get("new_string")
        fp = tool_input.get("file_path")
        old = old if isinstance(old, str) else None
        new = new if isinstance(new, str) else None
        fp = fp if isinstance(fp, str) else None
        return old, new, fp, payload.get("session_id")
    except Exception:
        return None, None, None, None


if __name__ == "__main__":
    block_noop_edit_workflow()
