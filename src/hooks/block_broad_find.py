# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# Global options that may appear before find paths (single-token forms)
_FIND_GLOBAL_OPTS = frozenset({'-H', '-L', '-P'})
# -O<level> optimisation flag (single token: -O, -O1, -O2, -O3)
_GLOBAL_OPT_O_RE  = re.compile(r'^-O\d*$')
# Head-bounded: find output piped immediately to `head` — no context-flood risk
_HEAD_PIPE        = re.compile(r'^\s*\|\s*head\b')
# maxdepth predicate present in the find expression
_MAXDEPTH_RE      = re.compile(r'(?:^|\s)-maxdepth(?:\s|$)')

_HOME      = os.path.normpath(os.path.expanduser("~"))
_CLAUDE    = os.path.normpath(os.path.join(_HOME, ".claude"))

_BLOCK_MESSAGE = (
    "broad find needs scope: add -maxdepth N, OR pipe to | head N, "
    "OR scope to a specific subdirectory instead of a broad root "
    "(~, ~/, /, ~/.claude)\n"
)

# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if find is broad/unbounded
def block_broad_find_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    segment, after = _find_segment(stripped)
    if segment is None:
        sys.exit(0)
    roots = _extract_roots(segment)
    if not any(_is_broad_root(r) for r in roots):
        sys.exit(0)
    if _has_maxdepth(segment):
        sys.exit(0)
    if _is_head_bounded(after):
        sys.exit(0)
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("block_broad_find", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)

# FUNCTIONS

# Parse stdin JSON; return (command, session_id); (None, None) on any error or missing field (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None

# Extract first standalone find invocation up to first pipe or chain operator.
# Returns (segment, after_segment); (None, None) when no qualifying find found.
def _find_segment(command: str):
    for m in re.finditer(r'\bfind\b', command):
        segment_str = command[m.start():]
        end = re.search(r'\s[|&;]', segment_str)
        if end:
            return segment_str[:end.start()], command[m.start() + end.start():]
        return segment_str, ""
    return None, None

# Extract path roots from a find segment: skip leading global options (-H/-L/-P/-Olevel/-D debugopts),
# collect non-predicate tokens until the first token starting with -, (, !, or ,
def _extract_roots(segment: str) -> list:
    tokens = segment.split()
    if not tokens or tokens[0] != 'find':
        return []
    i = 1
    roots = []
    while i < len(tokens):
        tok = tokens[i]
        if tok in _FIND_GLOBAL_OPTS:
            i += 1
            continue
        if _GLOBAL_OPT_O_RE.match(tok):
            i += 1
            continue
        if tok == '-D':
            i += 2
            continue
        if tok and tok[0] in ('-', '(', '!', ','):
            break
        roots.append(tok)
        i += 1
    return roots

# Resolve a root token to a normalised absolute path.
# Handles ~, ~/, ~/path, $HOME, ${HOME} and all their subpath forms (e.g. $HOME/.claude).
# Strategy: replace $HOME/${HOME} prefix with ~ so that expanduser covers all subpaths uniformly.
# Falls back to the token itself on any error (fail-open).
def _resolve_root(token: str) -> str:
    try:
        if token.startswith('${HOME}'):
            token = '~' + token[7:]
        elif token.startswith('$HOME'):
            token = '~' + token[5:]
        return os.path.normpath(os.path.expanduser(token))
    except Exception:
        return token

# True if the resolved root is broad: home dir, filesystem root, or the .claude subtree
def _is_broad_root(token: str) -> bool:
    resolved = _resolve_root(token)
    if resolved in (_HOME, '/'):
        return True
    if resolved == _CLAUDE or resolved.startswith(_CLAUDE + '/'):
        return True
    return False

# True if -maxdepth appears as a predicate in the segment
def _has_maxdepth(segment: str) -> bool:
    return bool(_MAXDEPTH_RE.search(segment))

# True if after_segment (the portion after the find segment) starts with `| head` — output bounded
def _is_head_bounded(after: str) -> bool:
    return bool(_HEAD_PIPE.match(after))


if __name__ == "__main__":
    block_broad_find_workflow()
