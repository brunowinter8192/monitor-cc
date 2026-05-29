# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

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

# Explicit literal allowlist for pkill -f arguments that are safe to pass through.
# Safe = this string can never appear in a claude-worker process cmdline.
# Rationale per entry:
#   "dolt sql-server" — bd Beads SQL backend forced restart. bd's own orphan-cleanup
#     SIGKILLs any process whose cmdline contains this string, so no worker prompt can
#     safely carry it (carrying it = the worker gets killed by bd cleanup). Therefore
#     pkill -f with exactly this pattern cannot collaterally kill any worker session.
_PKILL_F_ALLOWLIST: tuple = (
    "dolt sql-server",
)
# Extract pkill -f <arg> from original command (handles single-quoted, double-quoted, unquoted)
_PKILL_F_ARG_RE = re.compile(
    r'(?:^|[;&|\n])\s*pkill\b[^|&;\n]*?-f\s+(?:\'([^\']+)\'|"([^"]+)"|(\S+))'
)

_BLOCK_MESSAGE = "pkill -f / pgrep -f|kill risk killing worker sessions — use `worker-cli kill <name>` or inspect PID first: `pgrep -f <pat>` then `kill <pid>`\n"


# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if command matches a dangerous kill pattern
def block_dangerous_kill_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    if _is_blocked(command):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_dangerous_kill", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
        sys.exit(2)
    sys.exit(0)


# FUNCTIONS

# Parse stdin JSON; return (command, session_id); (None, None) on any error or missing field (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None

# Return True if command matches any blocked process-kill pattern (outside non-shell-active regions)
def _is_blocked(command: str) -> bool:
    stripped = _strip_non_shell_active(command)
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(stripped):
            if pattern is _PKILL_F and _pkill_f_is_allowlisted(command):
                continue
            return True
    return False

# Return True if every pkill -f occurrence in command targets only an allowlisted pattern.
# Checked against original (un-stripped) command — stripped form blanks quoted args.
# Conservative: any unrecognised argument or no argument found → False (block).
def _pkill_f_is_allowlisted(command: str) -> bool:
    found = _PKILL_F_ARG_RE.findall(command)
    if not found:
        return False
    for sq, dq, uq in found:
        arg = sq or dq or uq
        if arg not in _PKILL_F_ALLOWLIST:
            return False
    return True


if __name__ == "__main__":
    block_dangerous_kill_workflow()
