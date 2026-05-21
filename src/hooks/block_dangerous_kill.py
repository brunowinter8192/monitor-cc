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
    "  - For Monitor_CC menubar restart — capture PID at launch and kill directly:\n"
    "      ./venv/bin/python -m src.menubar.workflow --mode menubar &\n"
    "      echo $! > /tmp/monitor_cc_menubar.pid\n"
    "      # later: kill $(cat /tmp/monitor_cc_menubar.pid)\n"
    "  - For your own background job: kill via PID from `Bash run_in_background=true` task ID\n"
)

# Sentinel raised by _strip_impl on unclosed constructs
class _StripError(Exception):
    pass

_CMD_SUBST = '$('   # two-char command-substitution prefix


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

# Return True if command matches any blocked process-kill pattern (outside non-shell-active regions)
def _is_blocked(command: str) -> bool:
    stripped = _strip_non_shell_active(command)
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(stripped):
            return True
    return False

# Return command with heredoc bodies, single-quoted, double-quoted, and ANSI-C-quoted regions
# replaced by spaces. Command substitutions $(...) and backtick substitutions are kept
# shell-active (may contain real dangerous kill patterns).
# Returns original command unchanged on any parse failure (fail-open).
def _strip_non_shell_active(command: str) -> str:
    try:
        return _strip_impl(command)
    except Exception:
        return command

# Single-pass character scanner: strip non-shell-active regions, keep shell-active ones.
def _strip_impl(command: str) -> str:  # noqa: C901
    out = []
    i = 0
    n = len(command)

    while i < n:

        # --- Heredoc: << (not <<<) ---
        if command[i:i+2] == '<<' and command[i:i+3] != '<<<':
            j = i + 2
            if j < n and command[j] == '-':
                j += 1                                # <<- strip-tabs variant
            while j < n and command[j] in (' ', '\t'):
                j += 1
            q = None
            if j < n and command[j] in ("'", '"'):    # quoted marker: <<'EOF' or <<"EOF"
                q = command[j]
                j += 1
            mk = []
            while j < n and command[j] not in ('\n', ' ', '\t'):
                if q and command[j] == q:
                    j += 1
                    break
                mk.append(command[j])
                j += 1
            marker = ''.join(mk)
            if not marker:
                out.append(command[i])
                i += 1
                continue
            while i < j:
                out.append(command[i])
                i += 1
            while i < n and command[i] != '\n':
                out.append(command[i])
                i += 1
            if i < n:
                out.append('\n')
                i += 1
            found_term = False
            while i < n:
                ls = i
                while i < n and command[i] != '\n':
                    i += 1
                line = command[ls:i]
                if i < n:
                    i += 1
                if line.strip() == marker:
                    out.append(line)
                    out.append('\n')
                    found_term = True
                    break
                out.append(' ' * len(line))
                out.append('\n')
            if not found_term:
                raise _StripError("unclosed heredoc")
            continue

        # --- ANSI-C quote: $'...' ---
        if command[i:i+2] == "$'":
            out.append('  ')
            i += 2
            closed = False
            while i < n:
                if command[i] == '\\' and i + 1 < n:
                    out.append('  ')
                    i += 2
                elif command[i] == "'":
                    out.append(' ')
                    i += 1
                    closed = True
                    break
                else:
                    out.append(' ')
                    i += 1
            if not closed:
                raise _StripError("unclosed ANSI-C quote")
            continue

        # --- Command substitution: $(...) — keep shell-active, track paren depth ---
        if command[i:i+2] == _CMD_SUBST:
            out.append(_CMD_SUBST)
            i += 2
            depth = 1
            while i < n and depth > 0:
                if command[i] == '(':
                    depth += 1
                elif command[i] == ')':
                    depth -= 1
                    if depth == 0:
                        out.append(')')
                        i += 1
                        break
                out.append(command[i])
                i += 1
            continue

        # --- Backtick substitution: `...` — keep shell-active ---
        if command[i] == '`':
            out.append('`')
            i += 1
            while i < n and command[i] != '`':
                out.append(command[i])
                i += 1
            if i < n:
                out.append('`')
                i += 1
            continue

        # --- Single-quoted string: '...' (no escape processing inside single-quotes) ---
        if command[i] == "'":
            out.append(' ')
            i += 1
            while i < n and command[i] != "'":
                out.append(' ')
                i += 1
            if i >= n:
                raise _StripError("unclosed single quote")
            out.append(' ')
            i += 1
            continue

        # --- Double-quoted string: "..." (\" escape handling) ---
        if command[i] == '"':
            out.append(' ')
            i += 1
            closed = False
            while i < n:
                if command[i] == '\\' and i + 1 < n:
                    out.append('  ')
                    i += 2
                elif command[i] == '"':
                    out.append(' ')
                    i += 1
                    closed = True
                    break
                else:
                    out.append(' ')
                    i += 1
            if not closed:
                raise _StripError("unclosed double quote")
            continue

        out.append(command[i])
        i += 1

    return ''.join(out)


if __name__ == "__main__":
    block_dangerous_kill_workflow()
