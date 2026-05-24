# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# pkill with -f flag — anchored to command start or after shell separator
# (prevents false-positives when "pkill -f" appears inside a quoted argument)
_PKILL_F = re.compile(r'(?:^|[;&|\n])\s*pkill\s+(-[^\s]*\s+)*-f\b')
# pgrep -f piped into kill / xargs kill — same collateral risk as pkill -f
# Matches: pgrep -f X | xargs kill, pgrep -f X | xargs -r kill, etc.
_PGREP_F_KILL_PIPE = re.compile(r'(?:^|[;&|\n])\s*pgrep\s+(?:-[^\s]*\s+)*-f\b[^|]*\|.*\bkill\b', re.DOTALL)
# kill $(pgrep -f X) — command substitution variant
_KILL_PGREP_F_SUBST = re.compile(r'\bkill\s+(?:-[^\s]*\s+)*\$\(\s*pgrep\s+(?:-[^\s]*\s+)*-f\b')
# ps … | … grep … | … kill pipe chain — same anchor
_PS_GREP_KILL = re.compile(r'(?:^|[;&|\n])\s*ps\b[^|]*\|[^|]*\bgrep\b[^|]*\|.*\bkill\b', re.DOTALL)

_BLOCKED_PATTERNS = [_PKILL_F, _PGREP_F_KILL_PIPE, _KILL_PGREP_F_SUBST, _PS_GREP_KILL]

_BLOCK_MESSAGE = "pkill -f / pgrep -f|kill risk killing worker sessions — use `worker-cli kill <name>` or inspect PID first: `pgrep -f <pat>` then `kill <pid>`\n"


# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if command matches a dangerous kill pattern
def block_dangerous_kill_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    if _is_blocked(command):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_dangerous_kill", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
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

# Return True if command matches any blocked process-kill pattern (outside non-shell-active regions)
def _is_blocked(command: str) -> bool:
    stripped = _strip_non_shell_active(command)
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(stripped):
            return True
    return False


if __name__ == "__main__":
    block_dangerous_kill_workflow()
