# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# worker-cli spawn with 'opus' anywhere after the spawn subcommand (including as model arg)
_SPAWN_OPUS = re.compile(r'\bworker-cli\s+spawn\b.*\bopus\b', re.DOTALL)

_BLOCK_MESSAGE = "worker model must be sonnet, not opus: `worker-cli spawn <name> <prompt> <path> sonnet`\n"

# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if command spawns a worker with opus model
def block_worker_spawn_opus_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if _SPAWN_OPUS.search(stripped):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_worker_spawn_opus", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
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
    block_worker_spawn_opus_workflow()
