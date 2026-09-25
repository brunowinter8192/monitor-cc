# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.hooks._shell_strip import _strip_non_shell_active
from src.hooks._fire_log import log_fire

_PO_PATH_RE = re.compile(r'\S*/\.claude/\S*\.txt\b')
_READ_TOOL_RE = re.compile(
    r'\b(?:head|tail|grep|egrep|fgrep|rg|sed|awk|cut|less|more|cat|tac|nl|zcat|split|dd)\b'
)
_REDIRECT_STRIP = re.compile(r'\s*(?:\d?>>?|&>>?)\s*\S+')
_SEGMENT_SPLIT = re.compile(r'\s*(?:&&|\|\||\||\n|;)\s*')
_TOKEN_PREFIX_RE = re.compile(r'^\w+=(.*)$')

POREAD_MAX_BYTES = 50_000

_BLOCK_MSG = (
    "BLOCKED: this path is a Claude Code persisted-output export (contains /.claude/, ends .txt) — "
    "read it via `poread <path>` instead of partially.\n"
)


# ORCHESTRATOR

def block_po_read_workflow() -> None:
    command, session_id, cwd = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    segments = [s for s in _SEGMENT_SPLIT.split(stripped) if s.strip()]
    for seg in segments:
        if _is_po_read_segment(seg, cwd):
            print(_BLOCK_MSG, file=sys.stderr, end="")
            log_fire("block_po_read", "block", "Bash", command, reason=_BLOCK_MSG, session_id=session_id)
            sys.exit(2)
    sys.exit(0)


# FUNCTIONS

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id"), payload.get("cwd")
    except Exception as e:
        log_fire("block_po_read", "trace", "Bash", "", reason=f"parse error: {type(e).__name__}: {e}")
        return None, None, None

def _is_po_read_segment(seg: str, cwd) -> bool:
    cleaned = _strip_redirects(seg)
    if not _READ_TOOL_RE.search(cleaned):
        return False
    match = _PO_PATH_RE.search(cleaned)
    if not match:
        return False
    size = _po_export_size(match.group(0), cwd)
    if size is None:
        log_fire("block_po_read", "trace", "Bash", seg, reason=f"size unknown, blocking: {match.group(0)}")
        return True
    return size <= POREAD_MAX_BYTES

def _strip_redirects(seg: str) -> str:
    cleaned = seg
    while True:
        new = _REDIRECT_STRIP.sub(' ', cleaned)
        if new == cleaned:
            break
        cleaned = new
    return cleaned

def _resolve_po_path(token: str, cwd) -> str:
    prefix_match = _TOKEN_PREFIX_RE.match(token)
    path = prefix_match.group(1) if prefix_match else token
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        base = cwd if isinstance(cwd, str) and cwd else os.getcwd()
        path = os.path.join(base, path)
    return path

def _po_export_size(token: str, cwd):
    path = _resolve_po_path(token, cwd)
    try:
        return os.path.getsize(path)
    except OSError:
        return None


if __name__ == "__main__":
    block_po_read_workflow()
