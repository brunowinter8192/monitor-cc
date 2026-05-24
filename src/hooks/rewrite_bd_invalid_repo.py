# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

# Matches --repo= or --repo<spaces> followed by: double-quoted, single-quoted, or unquoted path.
# Unquoted path terminates at shell metachars (space, quote, ; & | < > ( ) ` $ \).
_REPO_TOKEN_RE = re.compile(
    r'--repo(?:=| +)'
    r'(?:'
    r'"(?:[^"\\]|\\.)*"'        # double-quoted path (escape-aware)
    r"|'[^']*'"                  # single-quoted path
    r'|[^\s\'";&|<>()`$\\]+'    # unquoted path
    r')'
)

# Shell metachars that make a path unresolvable at hook time (env vars, globs, subst)
_SHELL_META_RE = re.compile(r'[$`\\*?{]')

# Quick check: command contains 'bd' at all
_BD_PRESENT_RE = re.compile(r'\bbd\b')


# ORCHESTRATOR

# Read Bash tool_input; strip invalid --repo <path> tokens; emit updatedInput JSON if any stripped
def rewrite_bd_invalid_repo_workflow() -> None:
    try:
        command, session_id = _parse_command()
        if command is None or not _BD_PRESENT_RE.search(command):
            sys.exit(0)

        matches = list(_REPO_TOKEN_RE.finditer(command))
        if not matches:
            sys.exit(0)

        invalid_spans = []
        invalid_paths = []
        for m in matches:
            path = _extract_path(m.group(0))
            if path is None:
                continue
            if _has_shell_meta(path):
                continue  # unresolvable — let through
            if not _is_valid_beads_path(path):
                invalid_spans.append((m.start(), m.end()))
                invalid_paths.append(path)

        if not invalid_spans:
            sys.exit(0)

        rewritten = _rewrite_command(command, invalid_spans)
        output = _emit_rewrite(rewritten, invalid_paths)
        log_fire("rewrite_bd_invalid_repo", "rewrite", "Bash", command, rewritten=rewritten, session_id=session_id)
        print(json.dumps(output))
    except Exception:
        sys.exit(0)  # fail-open — never block the command
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

# Extract the bare path string from a --repo token (strip --repo= / --repo<spaces> and quotes)
def _extract_path(token: str):
    m = re.match(r'--repo(?:=| +)(.*)', token, re.DOTALL)
    if not m:
        return None
    raw = m.group(1).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        raw = raw[1:-1]
    return raw if raw else None

# True if path contains shell metachars that make it unresolvable at hook time
def _has_shell_meta(path: str) -> bool:
    return bool(_SHELL_META_RE.search(path))

# True if path resolves to a directory that contains a .beads/ subdirectory
def _is_valid_beads_path(path: str) -> bool:
    try:
        resolved = os.path.abspath(os.path.expanduser(path))
        return os.path.isdir(resolved) and os.path.isdir(os.path.join(resolved, '.beads'))
    except Exception:
        return False

# Return command with the given (start, end) spans removed
def _rewrite_command(command: str, spans: list) -> str:
    parts, prev = [], 0
    for start, end in sorted(spans):
        parts.append(command[prev:start])
        prev = end
    parts.append(command[prev:])
    return ''.join(parts)

# Build hookSpecificOutput + systemMessage dict; return it (caller handles print)
def _emit_rewrite(rewritten: str, invalid_paths: list) -> dict:
    cwd = os.getcwd()
    paths_str = ', '.join(f'`{p}`' for p in invalid_paths)
    message = (
        f"Hook rewrote bd command: stripped --repo {paths_str} "
        f"— that path has no .beads/ dir. "
        f"Using cwd={cwd} (which has .beads/) instead. "
        f"If you meant a different project, supply the correct --repo path. "
        f"Use --repo only when targeting a project OTHER than cwd."
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {"command": rewritten},
        },
        "systemMessage": message,
    }


if __name__ == "__main__":
    rewrite_bd_invalid_repo_workflow()
