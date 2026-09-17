# INFRASTRUCTURE
import json
import re
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_WAIT_MENTION_RE = re.compile(r'\bworker-cli\s+wait\b')

_BLOCK_MESSAGE = (
    "BLOCKED: `worker-cli wait` without run_in_background=true.\n"
    "wait polls the target project's worker status in-process and only returns on a state\n"
    "transition or its timeout ceiling — running it in the foreground blocks this session\n"
    "directly instead of letting it poll out of band. Re-issue it as its own Bash call with\n"
    "run_in_background: true.\n"
)


# ORCHESTRATOR

def block_worker_wait_foreground_workflow() -> None:
    command, run_in_background, session_id = _parse_input()
    if command is None or run_in_background:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if not _WAIT_MENTION_RE.search(stripped):
        sys.exit(0)
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("block_worker_wait_foreground", "block", "Bash", command,
             reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)


# FUNCTIONS

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
    block_worker_wait_foreground_workflow()
