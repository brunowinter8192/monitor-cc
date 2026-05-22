# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active

# Recursive grep: -r or -R flag in combined or standalone short options
_RECURSIVE_FLAG = re.compile(r'(?:^|\s)-[a-zA-Z]*[rR][a-zA-Z]*(?:\s|$)')
# Already scoped: --include= or --include <pattern> present
_INCLUDE_SCOPE  = re.compile(r'--include[=\s]')
# Safe target: last non-whitespace token ends with a known code/text file extension
_FILE_EXT_SAFE  = re.compile(
    r'\S+\.(?:py|sh|md|json|jsonl|yaml|yml|toml|ts|js|go|rs|txt|cfg|ini|sql|html|css)\s*$',
    re.IGNORECASE,
)

_BLOCK_MESSAGE = (
    "BLOCKED: recursive grep without --include scope (Rule 3, tool-use.md).\n"
    "Unrestricted `-r` grep over a directory matches JSONL logs, node_modules, and\n"
    "vendored content — output can explode to 10MB+ and floods the context window.\n"
    "\n"
    "Fix options:\n"
    "  1. Add --include='*.py' (or the appropriate extension)\n"
    "  2. Use the Grep tool — it has safe scoping defaults\n"
    "  3. Target a specific file: grep -n <pattern> <specific_file.py>\n"
)

# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if recursive grep lacks --include and is not file-targeted
def block_broad_grep_workflow() -> None:
    command = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    segment = _grep_segment(stripped)
    if segment is None:
        sys.exit(0)
    if not _is_recursive(segment):
        sys.exit(0)
    if _has_include_scope(segment):
        sys.exit(0)
    if _is_file_targeted(segment):
        sys.exit(0)
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    sys.exit(2)

# FUNCTIONS

# Parse stdin JSON and return tool_input.command; return None on any error or missing field (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return cmd if isinstance(cmd, str) else None
    except Exception:
        return None

# Extract first standalone grep invocation up to first pipe or chain operator; skip 'git grep'
def _grep_segment(command: str):
    for m in re.finditer(r'\bgrep\b', command):
        start = m.start()
        if start >= 4 and command[start - 4:start] == 'git ':
            continue
        segment = command[start:]
        end = re.search(r'\s[|&;]', segment)
        return segment[:end.start()] if end else segment
    return None

# True if the grep segment contains a recursive flag (-r, -R, -rn, -nr, etc.)
def _is_recursive(segment: str) -> bool:
    return bool(_RECURSIVE_FLAG.search(segment))

# True if --include= or --include <pattern> is present in segment
def _has_include_scope(segment: str) -> bool:
    return bool(_INCLUDE_SCOPE.search(segment))

# True if the last non-whitespace token ends with a known code/text file extension
def _is_file_targeted(segment: str) -> bool:
    return bool(_FILE_EXT_SAFE.search(segment))


if __name__ == "__main__":
    block_broad_grep_workflow()
