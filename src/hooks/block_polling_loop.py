# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# Matches: ps -p <literal-PID> — process-existence check with numeric PID
_PS_P_CHECK = re.compile(r'\bps\s+-p\s+\d+')
# Matches: tail -<N> <file> — log-read with inline line count (BSD/POSIX short form)
_TAIL_N_FILE = re.compile(r'\btail\s+-\d+\s+\S+')

_BLOCK_MESSAGE = "polling loop antipattern — use `wait $PID` then single `tail file` instead of repeated polls\n"


# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if command combines ps -p and tail -N (polling loop signature)
def block_polling_loop_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    if _is_blocked(command):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_polling_loop", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
        sys.exit(2)
    sys.exit(0)


# FUNCTIONS

# Parse stdin JSON; return (command, session_id); (None, None) on any error or missing field (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None

# Return True if command contains both ps -p <num> and tail -N <file> outside non-shell-active regions
def _is_blocked(command: str) -> bool:
    stripped = _strip_non_shell_active(command)
    return bool(_PS_P_CHECK.search(stripped) and _TAIL_N_FILE.search(stripped))


if __name__ == "__main__":
    block_polling_loop_workflow()
