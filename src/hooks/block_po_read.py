# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# Persisted-output export path schema (verified across 822 real proxy-log cases):
# contains "/.claude/" AND ends in ".txt" — no other .txt file under any .claude/ dir
# is ever legitimately read via shell.
_PO_PATH_RE = re.compile(r'\S*/\.claude/\S*\.txt\b')
# Reader tools that consume file content as INPUT (block_log_read reader set, plus rg + cut)
_READ_TOOL_RE = re.compile(
    r'\b(?:head|tail|grep|egrep|fgrep|rg|sed|awk|cut|less|more|cat|tac|nl|zcat)\b'
)
# Output redirect targets to strip before checking for a PO-path input arg:
# > file, >> file, N> file, N>> file, &> file, &>> file, 2>&1, 1>&2 (no path in fd-forms)
_REDIRECT_STRIP = re.compile(r'\s*(?:\d?>>?|&>>?)\s*\S+')
# Split command into pipeline/chain segments for per-segment classification
_SEGMENT_SPLIT = re.compile(r'\s*(?:&&|\|\||\||\n|;)\s*')

_BLOCK_MSG = (
    "BLOCKED: this path is a Claude Code persisted-output export (contains /.claude/, ends .txt) — "
    "it MUST be read IN FULL via the Read tool, never partially via head/tail/grep/sed/etc. "
    "Read supports offset/limit to page through large exports.\n"
)


# ORCHESTRATOR

# Read Bash tool_input from stdin; per-segment: reader tool + persisted-output input path → block
def block_po_read_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    segments = [s for s in _SEGMENT_SPLIT.split(stripped) if s.strip()]
    for seg in segments:
        if _is_po_read_segment(seg):
            print(_BLOCK_MSG, file=sys.stderr, end="")
            log_fire("block_po_read", "block", "Bash", command, reason=_BLOCK_MSG, session_id=session_id)
            sys.exit(2)
    sys.exit(0)


# FUNCTIONS

# Parse stdin JSON; return (command, session_id); (None, None) on any error or missing field (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None

# True when segment has a read tool AND a persisted-output path that is not a redirect output target
def _is_po_read_segment(seg: str) -> bool:
    cleaned = _strip_redirects(seg)
    return bool(_READ_TOOL_RE.search(cleaned) and _PO_PATH_RE.search(cleaned))

# Strip output redirect targets iteratively: > f, >> f, N> f, N>> f, &> f, &>> f, 2>&1 etc.
def _strip_redirects(seg: str) -> str:
    cleaned = seg
    while True:
        new = _REDIRECT_STRIP.sub(' ', cleaned)
        if new == cleaned:
            break
        cleaned = new
    return cleaned


if __name__ == "__main__":
    block_po_read_workflow()
