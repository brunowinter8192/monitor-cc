# INFRASTRUCTURE
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# Fast-path anchor: skip commands with no rag-cli token at all
_RAG_CLI_RE = re.compile(r'\brag-cli\b')
# Shell command separators: && || ; newline | (single, after ||) and space-bounded &.
# Order matters — && before single &, || before |. `2>&1` / `>&` not matched
# (no whitespace before &, no |/;/&& token).
_SEPARATOR_RE = re.compile(r'&&|\|\||;|\n|\||\s&(?=\s|$)')

_BLOCK_MESSAGE = (
    "rag-cli calls must not be followed by non-rag-cli commands in the same Bash invocation. "
    "After the first rag-cli segment, every subsequent segment must also start with rag-cli. "
    "Commands BEFORE the first rag-cli (e.g. cd, guards) are unrestricted. "
    "Use output redirection (>) to capture rag-cli output instead of piping.\n"
)


# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if a rag-cli call is followed by any
# non-rag-cli segment. Segments before the first rag-cli are unrestricted. Fail-open on errors.
def block_rag_cli_chained_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if not _RAG_CLI_RE.search(stripped):
        sys.exit(0)
    segments = [s.strip() for s in _SEPARATOR_RE.split(stripped) if s.strip()]
    first_rag_idx = _find_first_rag_segment(segments)
    if first_rag_idx is None:
        sys.exit(0)
    for seg in segments[first_rag_idx + 1:]:
        if not seg.startswith('rag-cli'):
            print(_BLOCK_MESSAGE, file=sys.stderr, end="")
            log_fire("block_rag_cli_chained", "block", "Bash", command,
                     reason=_BLOCK_MESSAGE, session_id=session_id)
            sys.exit(2)
    sys.exit(0)


# FUNCTIONS

# Return index of first segment that starts with 'rag-cli', or None if absent
def _find_first_rag_segment(segments: list) -> int | None:
    for i, seg in enumerate(segments):
        if seg.startswith('rag-cli'):
            return i
    return None


# Parse stdin JSON; return (command, session_id); (None, None) on any error (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


if __name__ == "__main__":
    block_rag_cli_chained_workflow()
