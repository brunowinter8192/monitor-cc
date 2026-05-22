# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active

# word-boundary sleep token — detects any sleep usage in shell-active code
_SLEEP_TOKEN = re.compile(r'\bsleep\s+\d+(?:\.\d+)?\b')
# canonical allowed form: sleep N && echo done (optional leading/trailing whitespace, optional float)
_CANONICAL = re.compile(r'^\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*$')
_SLEEP_N = re.compile(r'\bsleep\s+(\d+(?:\.\d+)?)\b')
_LOOP_RE = re.compile(r'\b(until|while|for)\b')
_SIDE_EFFECT_RE = re.compile(
    r'\b(pkill|launchctl|kickstart|bootout|worker-cli\s+kill|systemctl)\b|kill\s+-\d'
)

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
    payload = _parse_payload()
    if payload is None:
        sys.exit(0)
    command, run_in_background = payload
    stripped = _strip_non_shell_active(command)
    if not _sleep_detected(stripped) or _is_canonical(command):
        sys.exit(0)
    if _is_settling_time_allow(stripped, run_in_background):
        sys.exit(0)
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    sys.exit(2)


# FUNCTIONS

# Parse stdin JSON and return (command, run_in_background); return None on any error or missing field
def _parse_payload():
    try:
        data = json.loads(sys.stdin.read())
        ti = data.get("tool_input", {})
        cmd = ti.get("command")
        if not isinstance(cmd, str):
            return None
        return cmd, bool(ti.get("run_in_background", False))
    except Exception:
        return None

# True if command contains a sleep token in shell-active code
def _sleep_detected(command: str) -> bool:
    return bool(_SLEEP_TOKEN.search(command))

# True if command is exactly the canonical form and nothing else
def _is_canonical(command: str) -> bool:
    return bool(_CANONICAL.match(command))

# True when sleep is short settling-time after a side-effect command (foreground, not in a loop)
def _is_settling_time_allow(stripped: str, run_in_background: bool) -> bool:
    if run_in_background:
        return False
    if _LOOP_RE.search(stripped):
        return False
    m = _SLEEP_N.search(stripped)
    if m is None:
        return False
    n = float(m.group(1))
    if n > 10:
        return False
    return n <= 5 and bool(_SIDE_EFFECT_RE.search(stripped))


if __name__ == "__main__":
    block_chained_sleep_workflow()
