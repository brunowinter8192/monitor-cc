# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

_WORKTREE_FRAGMENT = '.claude/worktrees/'
# Any bd invocation: `bd <subcommand|flag>` at statement start or after a chain operator
_BD_INVOCATION = re.compile(r'(?:^|[;&|\n])\s*bd\s+(?:--?\w|\w)', re.MULTILINE)

_BLOCK_MESSAGE = (
    "BLOCKED: `bd` CLI command from inside a worker session.\n"
    "Bead operations are Opus's responsibility exclusively. Workers MUST NOT run bd\n"
    "commands — worktrees contain a copy of `.beads/` state, and bd writes from inside\n"
    "a worktree go to the worktree copy, NOT the main repo, silently corrupting bead\n"
    "data when the branch is later merged or the worktree is removed.\n"
    "\n"
    "Do NOT: bd create / bd close / bd comments add / bd export\n"
    "Do: report the needed bead operation in your Completion Checklist; Opus handles it.\n"
    "worker-rules.md \u00a7 What NOT to Do.\n"
)

# ORCHESTRATOR

# Read Bash tool_input; exit 2 + stderr if running inside a worktree and command invokes bd
def block_bd_cli_worker_workflow() -> None:
    if _WORKTREE_FRAGMENT not in os.getcwd():
        sys.exit(0)
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_quoted(command)
    if _BD_INVOCATION.search(stripped):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_bd_cli_worker", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

# Parse stdin JSON; return (command, session_id); (None, None) on any error (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None

# Strip content inside single/double quotes so quoted bd examples cannot trigger pattern matches
def _strip_quoted(s: str) -> str:
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in ("'", '"'):
            quote, i = c, i + 1
            while i < n and s[i] != quote:
                if s[i] == "\\" and i + 1 < n:
                    i += 2
                else:
                    i += 1
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


if __name__ == "__main__":
    block_bd_cli_worker_workflow()
