# INFRASTRUCTURE
import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_RAG_RE = re.compile(r'\brag-cli\s+search\b')

_SEGMENT_END_RE = re.compile(r'&&|\|\||[;)\n]|(?<!>)&(?![&>])')

_NOISE_RE = re.compile(r'2>&1|2>|&>|>>|<<|>|<|(?<!\|)\|(?!\|)')

_LAYER_FILTER_FLAGS = ("--document", "--exclude")

_BLOCK_MESSAGE = (
    "rag-cli search on a *-docs collection must carry a --document or --exclude "
    "filter whose value contains 'process-docs' — this scopes the search to one layer. "
    "Use --document 'process-docs/%' (or 'process-docs/<area>/%') for process-history "
    "search, or --exclude 'process-docs/%' for code-module search.\n"
)


# ORCHESTRATOR

def block_rag_docs_layer_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    matches = list(_RAG_RE.finditer(stripped))
    if not matches:
        sys.exit(0)

    for m in matches:
        seg_end = _segment_end(stripped, m.end())
        original_segment = command[m.start():seg_end]
        if _segment_violates(original_segment):
            print(_BLOCK_MESSAGE, file=sys.stderr, end="")
            log_fire("block_rag_docs_layer", "block", "Bash", command,
                     reason=_BLOCK_MESSAGE, session_id=session_id)
            sys.exit(2)
    sys.exit(0)


# FUNCTIONS

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


def _segment_end(stripped: str, rag_end: int) -> int:
    end_m = _SEGMENT_END_RE.search(stripped, rag_end)
    seg_end = end_m.start() if end_m else len(stripped)
    noise_m = _NOISE_RE.search(stripped, rag_end, seg_end)
    if noise_m is not None:
        seg_end = min(seg_end, noise_m.start())
    return seg_end


def _segment_violates(original_segment: str) -> bool:
    try:
        tokens = shlex.split(original_segment)
    except ValueError:
        return False
    collection = _find_collection(tokens)
    if collection is None or not collection.endswith('-docs'):
        return False
    return not _has_layer_filter(tokens)


def _find_collection(tokens: list) -> str | None:
    for i, tok in enumerate(tokens):
        if tok == 'search' and i + 2 < len(tokens):
            return tokens[i + 2]
    return None


def _has_layer_filter(tokens: list) -> bool:
    for i, tok in enumerate(tokens):
        if tok in _LAYER_FILTER_FLAGS:
            if i + 1 < len(tokens) and 'process-docs' in tokens[i + 1]:
                return True
        for flag in _LAYER_FILTER_FLAGS:
            if tok.startswith(flag + '=') and 'process-docs' in tok.split('=', 1)[1]:
                return True
    return False


if __name__ == "__main__":
    block_rag_docs_layer_workflow()
