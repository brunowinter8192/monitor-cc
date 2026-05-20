# INFRASTRUCTURE
import json
import os
import sys

_SIZE_LIMIT_BYTES = 256 * 1024  # 256 KB — CC Read tool hard limit

_BLOCK_MESSAGE = (
    "BLOCKED: {path} is {size_kb:.0f}KB — exceeds the 256KB Read tool limit.\n"
    "Use grep to locate the target section first, then Read with offset + limit:\n"
    "\n"
    "    grep -n '<pattern>' {path}               # find the line number\n"
    "    Read(file_path='{path}', offset=N, limit=200)\n"
    "\n"
    "Or use `wc -l`, `head`, `tail` to orient before a targeted Read.\n"
)

# ORCHESTRATOR

# Read Read tool_input from stdin; exit 2 + stderr if file exceeds 256KB and no offset/limit/pages given
def block_read_oversize_workflow() -> None:
    path, already_scoped = _parse_input()
    if path is None or already_scoped:
        sys.exit(0)
    size = _file_size(path)
    if size is None:
        sys.exit(0)
    if size > _SIZE_LIMIT_BYTES:
        msg = _BLOCK_MESSAGE.format(path=path, size_kb=size / 1024)
        print(msg, file=sys.stderr, end="")
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

# Parse stdin JSON; return (file_path, already_scoped); default (None, False) on any error (fail-open)
def _parse_input():
    try:
        payload = json.loads(sys.stdin.read())
        tool_input = payload.get("tool_input", {})
        path = tool_input.get("file_path")
        path = path if isinstance(path, str) else None
        # User already scoped the read — offset, limit, or pages present
        already_scoped = any(k in tool_input for k in ("offset", "limit", "pages"))
        return path, already_scoped
    except Exception:
        return None, False

# Return file size in bytes; return None on any filesystem error (fail-open)
def _file_size(path: str):
    try:
        return os.path.getsize(path)
    except Exception:
        return None


if __name__ == "__main__":
    block_read_oversize_workflow()
