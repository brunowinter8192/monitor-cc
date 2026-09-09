# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_LOOP_RE   = re.compile(r'\b(?:while|until)\b(.*?)\bdo\b(.*?)\bdone\b', re.DOTALL)
_BODY_SLEEP_ONLY = re.compile(r'^sleep\s+[\d.]+$')
_COND_STATUS = re.compile(r'\[|\b(?:ps|pgrep|kill|grep|egrep|fgrep|test|tail|head|cat|wc|ls|stat)\b')

_BLOCK_MESSAGE = (
    "Stop polling immediately. Do NOT loop-sleep waiting on a process, log, or file "
    "(`while`/`until <status-check>; do sleep N; done`). Run the full pipeline and wait for it to finish; "
    "if it is a background job, go idle and let the orchestrator read the output when it's done.\n"
)


# ORCHESTRATOR

def block_busywait_loop_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    for m in _LOOP_RE.finditer(stripped):
        cond, body = m.group(1), m.group(2)
        body_clean = body.strip(" \t\r\n;")
        if _BODY_SLEEP_ONLY.match(body_clean) and _COND_STATUS.search(cond):
            print(_BLOCK_MESSAGE, file=sys.stderr, end="")
            log_fire("block_busywait_loop", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
            sys.exit(2)
    sys.exit(0)


# FUNCTIONS

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


if __name__ == "__main__":
    block_busywait_loop_workflow()
