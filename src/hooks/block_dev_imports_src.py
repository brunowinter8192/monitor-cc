# INFRASTRUCTURE
import json
import re
import sys

# File path is under a dev/ directory
_DEV_PATH = re.compile(r'/dev/')
# Any line starting with `from src.` or `import src.` (the only ways to import the src package)
_SRC_IMPORT = re.compile(r'^(?:from\s+src\.|import\s+src\.)', re.MULTILINE)

_BLOCK_MESSAGE = (
    "BLOCKED: dev/ module importing from `src/`.\n"
    "dev/ scripts are self-contained — they do NOT import from src/. The purpose of\n"
    "dev/ is to be a migration candidate: a proven dev/ probe gets ported into src/ as\n"
    "a clean rewrite. Importing from src/ breaks this isolation: the probe no longer\n"
    "tests an alternative implementation, it extends the production code path.\n"
    "It also makes the dev/ script non-runnable in isolation (fails on any host without\n"
    "the full src/ tree installed).\n"
    "\n"
    "Fix: copy the needed logic directly into the dev/ module, or import from another\n"
    "pN_ module in the same dev/ pipeline stage.\n"
    "dev-convention.md Rule 5.\n"
)

# ORCHESTRATOR

# Read Write or Edit tool_input; exit 2 + stderr if a dev/ file introduces a src/ import
def block_dev_imports_src_workflow() -> None:
    file_path, content = _parse_targets()
    if file_path is None or content is None:
        sys.exit(0)
    if not _DEV_PATH.search(file_path):
        sys.exit(0)
    if _SRC_IMPORT.search(content):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

# Parse stdin JSON; return (file_path, content_to_check) for Write or Edit; (None, None) on error
def _parse_targets():
    try:
        payload = json.loads(sys.stdin.read())
        tool_name = payload.get("tool_name", "")
        inp = payload.get("tool_input", {})
        file_path = inp.get("file_path")
        if not isinstance(file_path, str):
            return None, None
        if tool_name == "Write":
            content = inp.get("content", "")
        elif tool_name == "Edit":
            content = inp.get("new_string", "")
        else:
            return None, None
        return file_path, content if isinstance(content, str) else None
    except Exception:
        return None, None


if __name__ == "__main__":
    block_dev_imports_src_workflow()
