# INFRASTRUCTURE
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

_CANONICAL_BG = re.compile(r'^\s*sleep\s+(\d+(?:\.\d+)?)\s*&&\s*echo\s+done\s*$')
_TARGET = "sleep 600 && echo done"


# ORCHESTRATOR

# Read Bash tool_input from stdin; rewrite sleep N → sleep 600 when background timer has N ≠ 600
def rewrite_background_sleep_workflow() -> None:
    command, run_in_background, session_id = _parse_input()
    if not run_in_background:
        sys.exit(0)
    if command is None:
        sys.exit(0)
    m = _CANONICAL_BG.match(command)
    if not m:
        sys.exit(0)
    if float(m.group(1)) == 600:
        sys.exit(0)
    output = _emit_rewrite()
    log_fire("rewrite_background_sleep", "rewrite", "Bash", command, rewritten=_TARGET, session_id=session_id)
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

# Build allow+updatedInput dict rewriting command to canonical 600s timer; return it (caller handles print)
def _emit_rewrite() -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {"command": _TARGET, "run_in_background": True},
        },
    }


if __name__ == "__main__":
    rewrite_background_sleep_workflow()
