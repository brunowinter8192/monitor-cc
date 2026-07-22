# INFRASTRUCTURE
import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# Anchor for the rag-cli search invocation. Only `search` is in scope —
# `read_document`, `list_documents`, `list_collections`, etc. remain untouched.
_RAG_RE = re.compile(r'\brag-cli\s+search\b')

# Segment-end operators: terminate the rag-cli logical command (same set as
# rewrite_rag_cli_search_noise.py's chain-boundary detection).
_SEGMENT_END_RE = re.compile(r'&&|\|\||[;)\n]|(?<!>)&(?![&>])')

# Noise inside the segment: pipes (excluding `||`) and redirects. First match
# position also bounds the segment — a piped/redirected search must not
# pull unrelated trailing tokens into the argument scan.
_NOISE_RE = re.compile(r'2>&1|2>|&>|>>|<<|>|<|(?<!\|)\|(?!\|)')

_LAYER_FILTER_FLAGS = ("--document", "--exclude")

_BLOCK_MESSAGE = (
    "rag-cli search on a *-docs collection must carry a --document or --exclude "
    "filter whose value contains 'process-docs' — this scopes the search to one layer. "
    "Use --document 'process-docs/%' (or 'process-docs/<area>/%') for process-history "
    "search, or --exclude 'process-docs/%' for code-module search.\n"
)


# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if a rag-cli search call
# targets a *-docs collection without a --document/--exclude filter naming
# 'process-docs'. Fail-open on any parse error.
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

# Parse stdin JSON; return (command, session_id); (None, None) on any error (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


# Return end index of the logical rag-cli segment starting after the search
# match, bounded by the first chain operator or the first pipe/redirect noise token.
def _segment_end(stripped: str, rag_end: int) -> int:
    end_m = _SEGMENT_END_RE.search(stripped, rag_end)
    seg_end = end_m.start() if end_m else len(stripped)
    noise_m = _NOISE_RE.search(stripped, rag_end, seg_end)
    if noise_m is not None:
        seg_end = min(seg_end, noise_m.start())
    return seg_end


# Return True if this rag-cli search segment targets a *-docs collection
# without a --document/--exclude filter whose value contains 'process-docs'.
# Fail-open (False) on any tokenization error or unexpected shape.
def _segment_violates(original_segment: str) -> bool:
    try:
        tokens = shlex.split(original_segment)
    except ValueError:
        return False
    collection = _find_collection(tokens)
    if collection is None or not collection.endswith('-docs'):
        return False
    return not _has_layer_filter(tokens)


# Return the collection token (two positions after 'search'), or None
def _find_collection(tokens: list) -> str | None:
    for i, tok in enumerate(tokens):
        if tok == 'search' and i + 2 < len(tokens):
            return tokens[i + 2]
    return None


# Return True if tokens contain a --document/--exclude flag whose value
# contains the substring 'process-docs' (space-separated or --flag=value form)
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
