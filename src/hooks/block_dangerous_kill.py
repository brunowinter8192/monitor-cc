# INFRASTRUCTURE
import json
import re
import sys

# pkill with -f flag anywhere in the argument list
_PKILL_F = re.compile(r'\bpkill\s+(-[^\s]*\s+)*-f\b')
# ps ... | ... grep ... | ... kill pipe chain (targets process via text match)
_PS_GREP_KILL = re.compile(r'\bps\b.+\|.+\bgrep\b.+\|.+\bkill\b', re.DOTALL)

_BLOCKED_PATTERNS = [_PKILL_F, _PS_GREP_KILL]

_BLOCK_MESSAGE = (
    "BLOCKED: `pkill -f <pattern>` matches arbitrary cmdline substrings and frequently kills the wrong\n"
    "process (e.g., Claude Code worker sessions whose prompts contain the pattern as text).\n"
    "\n"
    "Safer alternatives:\n"
    "  - `pgrep -f <pattern>` first to see what would match, then `kill <pid>` on the specific PID\n"
    "  - `pkill -x <exact_name>` (exact process name match, no substring)\n"
    "  - For worker management: `worker-cli kill <name>`\n"
    "  - For a known script: kill via PID from a PID file or `pgrep -f` output\n"
)

# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if command matches a dangerous kill pattern
def block_dangerous_kill_workflow() -> None:
    command = _parse_command()
    if command is None:
        sys.exit(0)
    if _is_blocked(command):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

# Parse stdin JSON and return tool_input.command; return None on any error or missing field
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return cmd if isinstance(cmd, str) else None
    except Exception:
        return None

# Return True if command matches any blocked process-kill pattern
def _is_blocked(command: str) -> bool:
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(command):
            return True
    return False


if __name__ == "__main__":
    block_dangerous_kill_workflow()
