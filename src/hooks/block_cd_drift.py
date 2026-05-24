# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

_CD_TARGET = re.compile(r'\bcd\s+(\S+)')
_WORKTREE_FRAGMENT = '.claude/worktrees/'

_BLOCK_MESSAGE = "use `git -C <worktree> diff` instead of `cd <worktree>`\n"


# ORCHESTRATOR

# Read Bash tool_input; exit 2 + stderr if a worktree cd lacks a cd-back, exit 0 otherwise.
# Skipped when the hook itself runs from inside a worktree (worker session — they live there).
def block_cd_drift_workflow() -> None:
    if _WORKTREE_FRAGMENT in os.getcwd():
        sys.exit(0)
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_quoted(command)
    cd_targets = _CD_TARGET.findall(stripped)
    if not cd_targets:
        sys.exit(0)
    worktree_cds = [t for t in cd_targets if _WORKTREE_FRAGMENT in t]
    if not worktree_cds:
        sys.exit(0)
    if _WORKTREE_FRAGMENT in cd_targets[-1]:
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_cd_drift", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
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


# Strip content inside single/double quotes so quoted text cannot trigger pattern matches.
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
    block_cd_drift_workflow()
