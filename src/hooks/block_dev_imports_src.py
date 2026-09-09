# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

_DEV_PATH = re.compile(r'/dev/')
_SRC_IMPORT = re.compile(r'^(?:from\s+src\.|import\s+src\.)', re.MULTILINE)
_TEST_DIR = re.compile(r'/tests/')
_TEST_FILENAME = re.compile(r'/(?:test_[^/]+\.py|[^/]+_test\.py|conftest\.py)$')

_BLOCK_MESSAGE = "dev/ scripts may not import from src/ — copy the logic into the dev/ module or import from another pN_ module\n"

# ORCHESTRATOR

def block_dev_imports_src_workflow() -> None:
    file_path, content, session_id = _parse_targets()
    if file_path is None or content is None:
        sys.exit(0)
    if not _DEV_PATH.search(file_path):
        sys.exit(0)
    if _is_regression_test_file(file_path):
        sys.exit(0)
    if _SRC_IMPORT.search(content):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_dev_imports_src", "block", "Write/Edit", file_path, reason=_BLOCK_MESSAGE, session_id=session_id)
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

def _is_regression_test_file(file_path: str) -> bool:
    return bool(_TEST_DIR.search(file_path) and _TEST_FILENAME.search(file_path))

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
