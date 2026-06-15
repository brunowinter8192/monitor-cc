# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# worker-cli send invocation in shell-active code (the fire-once, must-confirm action)
_WORKER_SEND = re.compile(r'\bworker-cli\s+send\b')

_BLOCK_MESSAGE = (
    "BLOCKED: `worker-cli send` with run_in_background=true.\n"
    "Send is a fire-once, must-confirm action — backgrounding means it is not awaited and can be\n"
    "SIGTERM-killed before delivering (exit 143, silent message loss). Issue the send as its own\n"
    "foreground Bash call; dispatch any timer separately as `sleep N && echo done`.\n"
)


# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if a backgrounded command contains worker-cli send
def block_worker_send_background_workflow() -> None:
    command, run_in_background, session_id = _parse_input()
    if command is None or not run_in_background:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if not _WORKER_SEND.search(stripped):
        sys.exit(0)
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("block_worker_send_background", "block", "Bash", command,
             reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)


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


if __name__ == "__main__":
    block_worker_send_background_workflow()
