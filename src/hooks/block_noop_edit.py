# INFRASTRUCTURE
import json
import sys

_BLOCK_MESSAGE = (
    "BLOCKED: old_string and new_string are identical — this Edit is a no-op.\n"
    "CC will reject it with 'No changes to make: old_string and new_string are exactly the same.'\n"
    "Re-read the file first to confirm what's actually there before retrying.\n"
    "Common cause: file was modified externally, or assumed indentation/whitespace differs.\n"
)

# ORCHESTRATOR

# Read Edit tool_input from stdin; exit 2 + stderr if old_string == new_string
def block_noop_edit_workflow() -> None:
    old_string, new_string = _parse_input()
    if old_string is None or new_string is None:
        sys.exit(0)
    if old_string == new_string:
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

# Parse stdin JSON; return (old_string, new_string); default (None, None) on any error (fail-open)
def _parse_input():
    try:
        payload = json.loads(sys.stdin.read())
        tool_input = payload.get("tool_input", {})
        old = tool_input.get("old_string")
        new = tool_input.get("new_string")
        old = old if isinstance(old, str) else None
        new = new if isinstance(new, str) else None
        return old, new
    except Exception:
        return None, None


if __name__ == "__main__":
    block_noop_edit_workflow()
