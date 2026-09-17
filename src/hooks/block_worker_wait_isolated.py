# INFRASTRUCTURE
import json
import re
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_WAIT_MENTION_RE = re.compile(r'\bworker-cli\s+wait\b')
_WAIT_CANONICAL_RE = re.compile(r'^\s*worker-cli\s+wait\b[^;&|\n]*$')

_BLOCK_MESSAGE = (
    "worker-cli wait must run alone in the Bash invocation — no cd prefix, no chaining with "
    "; or && or |, nothing before or after it. Point it at the target project directly instead "
    "of cd'ing there first: `worker-cli wait /path/to/project` (optionally with "
    "--timeout SECONDS). Issue any other command as its own separate Bash call.\n"
)


# ORCHESTRATOR

def block_worker_wait_isolated_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if not _WAIT_MENTION_RE.search(stripped):
        sys.exit(0)
    if _WAIT_CANONICAL_RE.match(stripped):
        sys.exit(0)
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("block_worker_wait_isolated", "block", "Bash", command,
             reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)


# FUNCTIONS

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


if __name__ == "__main__":
    block_worker_wait_isolated_workflow()
