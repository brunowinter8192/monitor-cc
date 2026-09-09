# INFRASTRUCTURE
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_SCRAPER_RE = re.compile(r'-m\s+src\.crawler\.pipe_scraper\b')
_ASSIGN_TOKEN = r'[A-Za-z_][A-Za-z0-9_]*=\S*'
_ASSIGN_PREFIX = rf'(?:{_ASSIGN_TOKEN}\s+)*'
_SCRAPER_SEGMENT_RE = re.compile(
    rf'^{_ASSIGN_PREFIX}(?:\S+/)?python3?\s+-m\s+src\.crawler\.pipe_scraper\b'
)
_CD_SEGMENT_RE = re.compile(r'^cd\b')
_ASSIGNMENT_ONLY_SEGMENT_RE = re.compile(rf'^(?:{_ASSIGN_TOKEN}\s*)+$')
_SEPARATOR_RE = re.compile(r'&&|\|\||;|\n|\||(?<![&>])&(?![&>])')
_LINE_CONTINUATION_RE = re.compile(r'\\\n')
_SUBSHELL_RE = re.compile(r'\$\(|`|<\(|>\(')

_BLOCK_MESSAGE = (
    "python -m src.crawler.pipe_scraper must run alone in the Bash invocation — no other "
    "commands before, after, or piped to it, and no command/process substitution ($(...), "
    "`...`, <(...), >(...)) anywhere in it. Only shell variable assignments, a `cd`, and the "
    "pipe_scraper call itself (optionally env-var-prefixed, with output redirection) may "
    "accompany it. This lets the long-running scraper auto-background instead of blocking the "
    "worker on a poll chained into the same call. Run log checks or other commands in a "
    "separate Bash call.\n"
)


# ORCHESTRATOR

def block_pipe_scraper_isolated_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    joined = _LINE_CONTINUATION_RE.sub(' ', stripped)
    if not _SCRAPER_RE.search(joined):
        sys.exit(0)
    if _SUBSHELL_RE.search(command):
        _block(command, session_id)
    segments = [s.strip() for s in _SEPARATOR_RE.split(joined) if s.strip()]
    scraper_segments = [s for s in segments if _SCRAPER_SEGMENT_RE.match(s)]
    if not scraper_segments:
        sys.exit(0)
    if len(scraper_segments) > 1:
        _block(command, session_id)
    for seg in segments:
        if (_SCRAPER_SEGMENT_RE.match(seg) or _CD_SEGMENT_RE.match(seg)
                or _ASSIGNMENT_ONLY_SEGMENT_RE.match(seg)):
            continue
        _block(command, session_id)
    sys.exit(0)


# FUNCTIONS

def _block(command: str, session_id: str) -> None:
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("block_pipe_scraper_isolated", "block", "Bash", command,
              reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)


def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


if __name__ == "__main__":
    block_pipe_scraper_isolated_workflow()
