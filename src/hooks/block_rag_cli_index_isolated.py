# INFRASTRUCTURE
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.hooks._shell_strip import _strip_non_shell_active
from src.hooks._fire_log import log_fire

_RAG_INDEX_RE = re.compile(r'\brag-cli\s+index\b')
_ASSIGN_TOKEN = r'[A-Za-z_][A-Za-z0-9_]*=\S*'
_ASSIGN_PREFIX = rf'(?:{_ASSIGN_TOKEN}\s+)*'
_RAG_INDEX_SEGMENT_RE = re.compile(rf'^{_ASSIGN_PREFIX}rag-cli\s+index\b')
_CD_SEGMENT_RE = re.compile(r'^cd\b')
_ASSIGNMENT_ONLY_SEGMENT_RE = re.compile(rf'^(?:{_ASSIGN_TOKEN}\s*)+$')
_SEPARATOR_RE = re.compile(r'&&|\|\||;|\n|\||(?<![&>])&(?![&>])')
_LINE_CONTINUATION_RE = re.compile(r'\\\n')
_SUBSHELL_RE = re.compile(r'\$\(|`|<\(|>\(')

_BLOCK_MESSAGE = (
    "rag-cli index must run alone in the Bash invocation — no other commands before, after, or "
    "piped to it, and no command/process substitution ($(...), `...`, <(...), >(...)) anywhere "
    "in it. Only shell variable assignments, a `cd`, and the rag-cli index call itself "
    "(optionally env-var-prefixed, with output redirection) may accompany it. Run log checks or "
    "other commands in a separate Bash call.\n"
)


# ORCHESTRATOR

def block_rag_cli_index_isolated_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    if _is_violation(command):
        _block(command, session_id)
    sys.exit(0)

# FUNCTIONS

def _is_violation(command: str) -> bool:
    stripped = _strip_non_shell_active(command)
    joined = _LINE_CONTINUATION_RE.sub(' ', stripped)
    if not _RAG_INDEX_RE.search(joined):
        return False
    if _SUBSHELL_RE.search(command):
        return True
    segments = [s.strip() for s in _SEPARATOR_RE.split(joined) if s.strip()]
    index_segments = [s for s in segments if _RAG_INDEX_SEGMENT_RE.match(s)]
    if not index_segments:
        return False
    if len(index_segments) > 1:
        return True
    return any(not _is_allowed_segment(seg) for seg in segments)

def _is_allowed_segment(seg: str) -> bool:
    return bool(_RAG_INDEX_SEGMENT_RE.match(seg) or _CD_SEGMENT_RE.match(seg)
                or _ASSIGNMENT_ONLY_SEGMENT_RE.match(seg))

def _block(command: str, session_id: str) -> None:
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("block_rag_cli_index_isolated", "block", "Bash", command,
             reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)


def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception as e:
        log_fire("block_rag_cli_index_isolated", "trace", "Bash", "", reason=f"parse error: {type(e).__name__}: {e}")
        return None, None


if __name__ == "__main__":
    block_rag_cli_index_isolated_workflow()
