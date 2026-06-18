# INFRASTRUCTURE
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# Match a gh-cli index_issues / index_discussions invocation anywhere in the command
_INDEX_RE = re.compile(r'\bgh-cli\s+index_(?:issues|discussions)\b')
# A segment is allowed only if it IS such a call (starts with it, after whitespace)
_INDEX_SEGMENT_RE = re.compile(r'^gh-cli\s+index_(?:issues|discussions)\b')
# Shell command separators: && || ; newline | (single, after ||) and space-bounded
# background &. Order matters — && before single, || before |. `2>&1` / `>&` not matched
# (no whitespace before &, no |/;/&& token).
_SEPARATOR_RE = re.compile(r'&&|\|\||;|\n|\||\s&(?=\s|$)')

_BLOCK_MESSAGE = (
    "index_issues / index_discussions must run STANDALONE — only multiple index_* calls "
    "may be combined in one Bash. Remove the chained command(s) (echo, grep, rag-cli, etc.) "
    "and run indexing as its own step.\n"
)


# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if an index_issues/index_discussions
# call is chained with any non-index segment. Multiple index_* calls in one Bash = allowed.
def block_index_issues_chained_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if not _INDEX_RE.search(stripped):
        sys.exit(0)
    for segment in _SEPARATOR_RE.split(stripped):
        seg = segment.strip()
        if not seg:
            continue
        if not _INDEX_SEGMENT_RE.match(seg):
            print(_BLOCK_MESSAGE, file=sys.stderr, end="")
            log_fire("block_index_issues_chained", "block", "Bash", command,
                     reason=_BLOCK_MESSAGE, session_id=session_id)
            sys.exit(2)
    sys.exit(0)


# FUNCTIONS

# Parse stdin JSON; return (command, session_id); (None, None) on any error (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


if __name__ == "__main__":
    block_index_issues_chained_workflow()
