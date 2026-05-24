# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

# canonical allowed background form: sleep N && echo done (optional whitespace/float)
_CANONICAL = re.compile(r'^\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*$')

# ORCHESTRATOR

# Read Bash tool_input from stdin; silently rewrite run_in_background=true → false for non-canonical commands
def block_unauthorized_background_workflow() -> None:
    command, run_in_background, session_id = _parse_input()
    if not run_in_background:
        sys.exit(0)
    if command is None:
        sys.exit(0)
    if _is_canonical(command):
        sys.exit(0)
    output = _emit_rewrite(command)
    log_fire("block_unauthorized_background", "rewrite", "Bash", command,
             rewritten="run_in_background: true → false", session_id=session_id)
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

# True if command is exactly the canonical background timer form and nothing else
def _is_canonical(command: str) -> bool:
    return bool(_CANONICAL.match(command))

# Build allow+updatedInput dict flipping run_in_background to false; return it (caller handles print)
def _emit_rewrite(command: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {
                "command": command,
                "run_in_background": False,
            },
        },
    }


if __name__ == "__main__":
    block_unauthorized_background_workflow()
