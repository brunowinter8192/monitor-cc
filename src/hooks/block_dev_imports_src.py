# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

# File path is under a dev/ directory
_DEV_PATH = re.compile(r'/dev/')
# Any line starting with `from src.` or `import src.` (the only ways to import the src package)
_SRC_IMPORT = re.compile(r'^(?:from\s+src\.|import\s+src\.)', re.MULTILINE)

_BLOCK_MESSAGE = "dev/ scripts may not import from src/ — copy the logic into the dev/ module or import from another pN_ module\n"

# ORCHESTRATOR

# Read Write or Edit tool_input; exit 2 + stderr if a dev/ file introduces a src/ import
def block_dev_imports_src_workflow() -> None:
    file_path, content, session_id = _parse_targets()
    if file_path is None or content is None:
        sys.exit(0)
    if not _DEV_PATH.search(file_path):
        sys.exit(0)
    if _SRC_IMPORT.search(content):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_dev_imports_src", "block", "Write/Edit", file_path, reason=_BLOCK_MESSAGE, session_id=session_id)
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

# Parse stdin JSON; return (file_path, content_to_check, session_id); (None, None, None) on error
def _parse_targets():
    try:
        payload = json.loads(sys.stdin.read())
        tool_name = payload.get("tool_name", "")
        inp = payload.get("tool_input", {})
        file_path = inp.get("file_path")
        sid = payload.get("session_id")
        if not isinstance(file_path, str):
            return None, None, None
        if tool_name == "Write":
            content = inp.get("content", "")
        elif tool_name == "Edit":
            content = inp.get("new_string", "")
        else:
            return None, None, None
        return file_path, (content if isinstance(content, str) else None), sid
    except Exception:
        return None, None, None


if __name__ == "__main__":
    block_dev_imports_src_workflow()
