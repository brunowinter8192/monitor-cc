# INFRASTRUCTURE
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# Match a reddit-cli / cli.py search_subreddits invocation
_SEARCH_RE = re.compile(r'\b(reddit-cli|cli\.py)\s+search_subreddits\b')
# Match a --limit flag (--limit, --limit N, --limit=N) appearing after the subcommand
_LIMIT_RE = re.compile(r'--limit\b')

_BLOCK_MESSAGE = (
    "reddit-cli search_subreddits: --limit is not permitted. Subreddit discovery must "
    "not be capped — drop the --limit flag and pick 3-5 subreddits from the full result set.\n"
)


# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if a search_subreddits call carries --limit
def block_search_subreddits_limit_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    m = _SEARCH_RE.search(stripped)
    if not m:
        sys.exit(0)
    if not _LIMIT_RE.search(stripped, m.end()):
        sys.exit(0)
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("block_search_subreddits_limit", "block", "Bash", command,
             reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)


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
    block_search_subreddits_limit_workflow()
