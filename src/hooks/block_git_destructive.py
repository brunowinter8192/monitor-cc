# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

# Each entry: (compiled pattern, label, suggestion). Patterns matched against quote-stripped command.
_PATTERNS = [
    (re.compile(r'\bgit\b[^|;&]*\bcommit\b[^|;&]*--amend\b'),
     "git commit --amend",
     "Never amend existing commits — create a new commit instead."),
    (re.compile(r'\bgit\b[^|;&]*\bpush\b[^|;&]*(?:--force\b|--force-with-lease\b)'),
     "git push --force / --force-with-lease",
     "Never force push — reset, recommit, or work on a new branch."),
    (re.compile(r'\bgit\b[^|;&]*\bpush\b[^|;&]*\s-f\b'),
     "git push -f",
     "Never force push — reset, recommit, or work on a new branch."),
    (re.compile(r'\bgit\b[^|;&]*\b(?:commit|push)\b[^|;&]*--no-verify\b'),
     "git --no-verify (skip hooks)",
     "Never skip hooks — fix the hook failure or run the check manually first."),
    (re.compile(r'\bgit\b[^|;&]*\bcommit\b[^|;&]*--allow-empty\b'),
     "git commit --allow-empty",
     "Never create empty commits — they add noise without value."),
]

# git config modify detection (separate from regex list — needs exclusion of read-only variants)
_GIT_CONFIG_RE = re.compile(r'\bgit\b(?:\s+-C\s+\S+)?\s+config\b([^|;&]*)')
_GIT_CONFIG_READONLY = re.compile(
    r'\s--(?:list|get|get-all|get-regexp|show-origin|show-scope|show-keys|help)\b'
)

_BLOCK_TEMPLATE = "`{label}` — {suggestion}\n"


# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if command matches a destructive git pattern.
def block_git_destructive_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_quoted(command)
    for pat, label, suggestion in _PATTERNS:
        if pat.search(stripped):
            reason = _BLOCK_TEMPLATE.format(label=label, suggestion=suggestion)
            print(reason, file=sys.stderr, end="")
            log_fire("block_git_destructive", "block", "Bash", command, reason=reason, session_id=session_id)
            sys.exit(2)
    m = _GIT_CONFIG_RE.search(stripped)
    if m and not _GIT_CONFIG_READONLY.search(m.group(1)):
        reason = _BLOCK_TEMPLATE.format(
            label="git config (modify)",
            suggestion="Never modify git config — config changes are deliberate user decisions, "
                       "not Opus-driven.")
        print(reason, file=sys.stderr, end="")
        log_fire("block_git_destructive", "block", "Bash", command, reason=reason, session_id=session_id)
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


# Strip content inside single/double quotes so quoted text (commit messages, descriptions) cannot
# trigger pattern matches. Not a full shell parser — handles balanced quotes with simple
# backslash-escape.
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
    block_git_destructive_workflow()
