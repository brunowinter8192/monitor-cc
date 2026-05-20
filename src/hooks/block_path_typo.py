# INFRASTRUCTURE
import json
import re
import sys

# Two typo classes from Rule 13 (tool-use.md):
#   `.claire/`   — tokenizer typo of `.claude/`
#   `..letter`   — double-dot immediately followed by lowercase letter (in path context)
_CLAIRE_PATTERN = re.compile(r'\.claire/')
_DOTDOT_PATTERN = re.compile(r'(?:^|/|\s|=)\.\.[a-z]')

_BLOCK_MESSAGE_CLAIRE = (
    "BLOCKED: path contains `.claire/` — tokenizer typo of `.claude/`.\n"
    "Worktrees and config live under `.claude/worktrees/...` and `~/.claude/`. There is no\n"
    "`.claire/` directory anywhere. Rewrite the path with `.claude/` and retry.\n"
    "Rule 13, tool-use.md.\n"
)
_BLOCK_MESSAGE_DOTDOT = (
    "BLOCKED: path contains `..<letter>` (two dots immediately followed by a lowercase letter).\n"
    "Valid relative-parent traversal is `../` (two dots + slash). Forms like `..claude/`,\n"
    "`..bin/`, `..src/` are typos with overwhelming probability. Rewrite the path correctly.\n"
    "Rule 13 same-class, tool-use.md.\n"
)


# ORCHESTRATOR

# Read tool_input from stdin; exit 2 + stderr if a path-typo pattern fires; exit 0 otherwise.
def block_path_typo_workflow() -> None:
    targets = _parse_targets()
    for s in targets:
        stripped = _strip_quoted(s)
        if _CLAIRE_PATTERN.search(stripped):
            print(_BLOCK_MESSAGE_CLAIRE, file=sys.stderr, end="")
            sys.exit(2)
        if _DOTDOT_PATTERN.search(stripped):
            print(_BLOCK_MESSAGE_DOTDOT, file=sys.stderr, end="")
            sys.exit(2)
    sys.exit(0)


# FUNCTIONS

# Parse stdin JSON; return list of strings to check (command or file_path); [] on any error.
def _parse_targets():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return []
    tool_name = payload.get("tool_name", "")
    inp = payload.get("tool_input", {})
    if tool_name == "Bash":
        cmd = inp.get("command")
        return [cmd] if isinstance(cmd, str) else []
    if tool_name in ("Read", "Write", "Edit"):
        fp = inp.get("file_path")
        return [fp] if isinstance(fp, str) else []
    return []


# Strip content inside single/double quotes so quoted regex/text cannot trigger pattern matches.
# Not a full shell parser — handles balanced quotes with simple backslash-escape.
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
            i += 1   # skip closing quote (or step past end if unbalanced)
        else:
            out.append(c)
            i += 1
    return "".join(out)


if __name__ == "__main__":
    block_path_typo_workflow()
