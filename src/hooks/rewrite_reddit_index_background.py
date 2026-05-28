# INFRASTRUCTURE
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# Match invocation of the reddit indexer CLI (wrapper or raw python cli.py)
# Examples matched:
#   reddit-cli index_subreddits "query" sub1 sub2
#   ./venv/bin/python cli.py index_subreddits "query" sub1
#   cd /path/to/reddit && reddit-cli index_subreddits "query" sub1
_INDEXER_RE = re.compile(r'\b(reddit-cli|cli\.py)\s+index_subreddits\b')


# ORCHESTRATOR

# Read Bash tool_input from stdin; force run_in_background=true for reddit-cli index_subreddits invocations
def rewrite_reddit_index_background_workflow() -> None:
    command, run_in_background, session_id = _parse_input()
    if command is None:
        sys.exit(0)
    if run_in_background:
        sys.exit(0)  # already backgrounded, nothing to do
    stripped = _strip_non_shell_active(command)
    if not _INDEXER_RE.search(stripped):
        sys.exit(0)  # not the indexer command
    output = _emit_rewrite(command)
    log_fire("rewrite_reddit_index_background", "rewrite", "Bash", command,
             rewritten="run_in_background: false → true (long-running indexer ~75-100s)",
             session_id=session_id)
    print(json.dumps(output))
    sys.exit(0)


# FUNCTIONS

# Parse stdin JSON; return (command, run_in_background, session_id); (None, False, None) on error (fail-open)
def _parse_input():
    try:
        payload = json.loads(sys.stdin.read())
        tool_input = payload.get("tool_input", {})
        cmd = tool_input.get("command")
        bg = tool_input.get("run_in_background", False)
        cmd = cmd if isinstance(cmd, str) else None
        bg = bg if isinstance(bg, bool) else False
        return cmd, bg, payload.get("session_id")
    except Exception:
        return None, False, None


# Build allow+updatedInput dict flipping run_in_background to true; return it (caller handles print)
def _emit_rewrite(command: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {
                "command": command,
                "run_in_background": True,
            },
        },
    }


if __name__ == "__main__":
    rewrite_reddit_index_background_workflow()
