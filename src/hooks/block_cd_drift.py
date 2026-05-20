# INFRASTRUCTURE
import json
import os
import re
import sys

_CD_TARGET = re.compile(r'\bcd\s+(\S+)')
_WORKTREE_FRAGMENT = '.claude/worktrees/'

_BLOCK_MESSAGE = (
    "BLOCKED: `cd` into `.claude/worktrees/...` without a cd-back at the end of the chain.\n"
    "Bash tool calls share cwd across invocations — the next Bash call will inherit the\n"
    "worktree cwd and may write to the wrong tree.\n"
    "\n"
    "Required: the LAST statement must cd back to the main cwd, e.g.\n"
    "    cd <worktree> && git diff && cd <main-repo>\n"
    "OR avoid cd entirely:\n"
    "    git -C <worktree> diff      (and absolute paths throughout)\n"
    "Rule 16, tool-use.md.\n"
)


# ORCHESTRATOR

# Read Bash tool_input; exit 2 + stderr if a worktree cd lacks a cd-back, exit 0 otherwise.
# Skipped when the hook itself runs from inside a worktree (worker session — they live there).
def block_cd_drift_workflow() -> None:
    if _WORKTREE_FRAGMENT in os.getcwd():
        sys.exit(0)
    command = _parse_command()
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
        sys.exit(2)
    sys.exit(0)


# FUNCTIONS

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return cmd if isinstance(cmd, str) else None
    except Exception:
        return None


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
