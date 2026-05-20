# INFRASTRUCTURE
import json
import re
import sys

# canonical allowed background form: sleep N && echo done (optional whitespace/float)
_CANONICAL = re.compile(r'^\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*$')

_BLOCK_MESSAGE = (
    "BLOCKED: `run_in_background=true` on a non-canonical command.\n"
    "The only command allowed in background is:\n"
    "\n"
    "    sleep N && echo done\n"
    "\n"
    "Everything else must run in the foreground so output is visible live (Rule 12,\n"
    "tool-use.md). Background mode hides stdout/stderr until the command finishes,\n"
    "making long-running tools (rag-cli, python scripts, builds) unmonitorable.\n"
    "Remove run_in_background=true and let the Bash call run normally.\n"
)

# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if run_in_background=true on non-canonical command
def block_unauthorized_background_workflow() -> None:
    command, run_in_background = _parse_input()
    if not run_in_background:
        sys.exit(0)
    if command is None:
        sys.exit(0)
    if not _is_canonical(command):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

# Parse stdin JSON; return (command, run_in_background); default (None, False) on any error (fail-open)
def _parse_input():
    try:
        payload = json.loads(sys.stdin.read())
        tool_input = payload.get("tool_input", {})
        cmd = tool_input.get("command")
        bg = tool_input.get("run_in_background", False)
        cmd = cmd if isinstance(cmd, str) else None
        bg = bg if isinstance(bg, bool) else False
        return cmd, bg
    except Exception:
        return None, False

# True if command is exactly the canonical background timer form and nothing else
def _is_canonical(command: str) -> bool:
    return bool(_CANONICAL.match(command))


if __name__ == "__main__":
    block_unauthorized_background_workflow()
