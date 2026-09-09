# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_RECURSIVE_FLAG = re.compile(r'(?:^|\s)-[a-zA-Z]*[rR][a-zA-Z]*(?:\s|$)')
_INCLUDE_SCOPE  = re.compile(r'--include[=\s]')
_HEAD_PIPE      = re.compile(r'^\s*\|\s*head\b')
_FILE_EXT_SAFE  = re.compile(
    r'\S+\.(?:py|sh|md|json|jsonl|yaml|yml|toml|ts|js|go|rs|c|cc|cpp|cxx|h|hh|hpp|hxx|txt|cfg|ini|sql|html|css)\s*$',
    re.IGNORECASE,
)
_TRAILING_REDIRECT = re.compile(
    r'\s+(?:\d?>>?\s*&\s*\d|\d?>>?\s*\S+|&>>?\s*\S+|\d?<\s*\S+)\s*$'
)

_BLOCK_MESSAGE = "recursive grep needs scope: add --include='<glob>' OR target explicit files (grep -n <pattern> <file>)\n"

# ORCHESTRATOR

def block_broad_grep_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    segment, after = _grep_segment(stripped)
    if segment is None:
        sys.exit(0)
    if not _is_recursive(segment):
        sys.exit(0)
    if _has_include_scope(segment):
        sys.exit(0)
    if _is_file_targeted(segment):
        sys.exit(0)
    if _is_head_bounded(after):
        sys.exit(0)
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("block_broad_grep", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)

# FUNCTIONS

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None

def _grep_segment(command: str):
    for m in re.finditer(r'\bgrep\b', command):
        start = m.start()
        if start >= 4 and command[start - 4:start] == 'git ':
            continue
        segment_str = command[start:]
        end = re.search(r'\s[|&;]', segment_str)
        if end:
            return segment_str[:end.start()], command[start + end.start():]
        return segment_str, ""
    return None, None

def _is_recursive(segment: str) -> bool:
    return bool(_RECURSIVE_FLAG.search(segment))

def _has_include_scope(segment: str) -> bool:
    return bool(_INCLUDE_SCOPE.search(segment))

def _is_head_bounded(after: str) -> bool:
    return bool(_HEAD_PIPE.match(after))

def _is_file_targeted(segment: str) -> bool:
    cleaned = segment
    while True:
        new = _TRAILING_REDIRECT.sub('', cleaned)
        if new == cleaned:
            break
        cleaned = new
    return bool(_FILE_EXT_SAFE.search(cleaned))


if __name__ == "__main__":
    block_broad_grep_workflow()
