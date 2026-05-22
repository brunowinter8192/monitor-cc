# INFRASTRUCTURE
import json
import re
import sys

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


# Sentinel raised by _strip_impl on unclosed constructs
class _StripError(Exception):
    pass


# Return command with heredoc bodies, single-quoted, double-quoted, and ANSI-C-quoted regions
# replaced by spaces. Command substitutions $(...) and backtick substitutions are kept
# shell-active (may contain real sleeps that should be blocked).
# Returns original command unchanged on any parse failure (fail-open).
def _strip_non_shell_active(command: str) -> str:
    try:
        return _strip_impl(command)
    except Exception:
        return command


_CMD_SUBST = '$('   # two-char command-substitution prefix used in _strip_impl checks

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
            if not marker:                            # unparseable marker — keep char, move on
                out.append(command[i])
                i += 1
                continue
            while i < j:                             # keep the <<MARKER redirect token itself
                out.append(command[i])
                i += 1
            while i < n and command[i] != '\n':      # keep rest of current line (shell-active)
                out.append(command[i])
                i += 1
            if i < n:
                out.append('\n')
                i += 1
            found_term = False
            while i < n:                             # consume body: replace lines with spaces
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
    block_chained_sleep_workflow()
