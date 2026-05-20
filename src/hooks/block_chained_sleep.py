# INFRASTRUCTURE
import json
import re
import sys

# word-boundary sleep token with optional float seconds — detects any sleep usage
_SLEEP_TOKEN = re.compile(r'\bsleep\s+\d+(?:\.\d+)?\b')
# canonical allowed form: sleep N && echo done (optional leading/trailing whitespace, optional float)
_CANONICAL = re.compile(r'^\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*$')

_BLOCK_MESSAGE = (
    "BLOCKED: `sleep` detected in a Bash command that is not the canonical orchestration timer.\n"
    "The only allowed form is:\n"
    "\n"
    "    sleep N && echo done          (dispatched with run_in_background=true)\n"
    "\n"
    "Chained forms like `cmd_before; sleep N && echo done` or `sleep N && other_cmd` are\n"
    "forbidden (Rule 12, tool-use.md). When the menubar auto-abort fires SIGTERM on the sleep\n"
    "PID, the entire chained shell exits with code 143 and output from pre-sleep commands is\n"
    "lost. Restructure: put pre-sleep commands in a separate Bash call, then dispatch the\n"
    "timer as a standalone `sleep N && echo done` with run_in_background=true.\n"
)

# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if sleep appears in non-canonical form
def block_chained_sleep_workflow() -> None:
    command = _parse_command()
    if command is None:
        sys.exit(0)
    if _sleep_detected(command) and not _is_canonical(command):
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

# True if command contains a sleep token (word-boundary, avoids substrings like "overslept")
def _sleep_detected(command: str) -> bool:
    return bool(_SLEEP_TOKEN.search(command))

# True if command is exactly the canonical form and nothing else
def _is_canonical(command: str) -> bool:
    return bool(_CANONICAL.match(command))


if __name__ == "__main__":
    block_chained_sleep_workflow()
