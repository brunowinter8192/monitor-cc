# INFRASTRUCTURE
import json
import re
import sys

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

_BLOCK_MESSAGE = (
    "BLOCKED: `pkill -f` and `pgrep -f | kill` chains match arbitrary cmdline substrings and kill\n"
    "the wrong process. Claude Code worker sessions are spawned via `claude \"$(cat prompt.md)\"` —\n"
    "the ENTIRE prompt content lives in the claude process argv. Any file path or substring you grep\n"
    "for that also appears in a worker prompt will match (and kill) that worker's claude process.\n"
    "Path-like patterns (containing `/`) are NOT safer — they are the most common kill-the-worker case.\n"
    "\n"
    "Safer alternatives:\n"
    "  - `pgrep -f <pattern>` as a STANDALONE command, inspect output, then `kill <pid>` on the\n"
    "    specific PID after confirming the match is not a claude / tmux / worker process\n"
    "  - `pkill -x <exact_name>` (exact process name match, no argv substring)\n"
    "  - For worker management: `worker-cli kill <name>`\n"
    "  - For your own background job: kill via PID from `Bash run_in_background=true` task ID\n"
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

# Strip content inside single/double quotes so quoted text cannot trigger pattern matches.
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

# Return True if command matches any blocked process-kill pattern (outside quoted regions)
def _is_blocked(command: str) -> bool:
    stripped = _strip_quoted(command)
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(stripped):
            return True
    return False


if __name__ == "__main__":
    block_dangerous_kill_workflow()
