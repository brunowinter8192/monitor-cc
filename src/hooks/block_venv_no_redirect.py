# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# Match: optional `cd && ` prefix, then `./venv/bin/python <X>.py` or `venv/bin/python <X>.py`
_VENV_SCRIPT = re.compile(r'\.?\.?/?venv/bin/python\s+\S+\.py\b')
# Any file redirect counts: > /tmp/x.md, >> file, > x.log, etc.
_REDIRECT = re.compile(r'>\s*\S+')
# `| tee FILE` also captures output to disk — treat as compliant
_TEE = re.compile(r'\|\s*tee\b')

_BLOCK_MESSAGE = (
    "BLOCKED: `./venv/bin/python <script>.py` without file redirect.\n"
    "Dev scripts are noisy — verbose output floods the context window.\n"
    "Required form:\n"
    "\n"
    "    ./venv/bin/python dev/<area>/<script>.py > /tmp/<name>.md 2>&1\n"
    "    tail -20 /tmp/<name>.md\n"
    "\n"
    "Alternative: pipe through `| tee /tmp/<name>.md` if you need live + file output.\n"
    "Rule 4, tool-use.md.\n"
)


# ORCHESTRATOR

# Read Bash tool_input; exit 2 + stderr if venv-python script call has no file redirect.
def block_venv_no_redirect_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if not _VENV_SCRIPT.search(stripped):
        sys.exit(0)
    if _REDIRECT.search(stripped) or _TEE.search(stripped):
        sys.exit(0)
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("block_venv_no_redirect", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)


# FUNCTIONS

# Parse stdin JSON; return (command, session_id); (None, None) on any error (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


if __name__ == "__main__":
    block_venv_no_redirect_workflow()
