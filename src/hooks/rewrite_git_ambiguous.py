# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active

# git diff/log/show with ..-range token (e.g. dev..HEAD, main..feature)
_GIT_SUBCMD       = re.compile(r'\bgit\b.*?(?<!-)\b(diff|log|show)\b', re.DOTALL)
# Range token: <name>..<name> or <name>.. or ..<name>
_RANGE_TOKEN      = re.compile(r'[\w./:-]+\.\.[\w./:-]*|\.\.[\w./:-]+')
# Capture text after the subcommand for bare-ref inspection
_SUBCOMMAND_AFTER = re.compile(r'\b(?:diff|log|show)\b(.+)', re.DOTALL)
# Bare ref: alphanumeric + underscore/hyphen/slash, no dots (branch/commit ref name shape)
_BARE_REF         = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_/\-]*$')
# Standalone -- path separator surrounded by whitespace/boundary (excludes --flag like --stat)
_HAS_PATH_SEP     = re.compile(r'(?:^|\s)--(?:\s|$)')
# Unquoted chain operators / redirects that end the git subcommand arg scope
_CHAIN_OP_RE      = re.compile(r'&&|\|\||[|><;]')


# ORCHESTRATOR

# Read Bash tool_input from stdin; auto-rewrite git command with -- if ambiguity detected
def rewrite_git_ambiguous_workflow() -> None:
    command = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if not _is_git_diff_log(stripped):
        sys.exit(0)
    if _has_path_separator(stripped):
        sys.exit(0)
    if not (_has_range_token(stripped) or _has_bare_ref_token(stripped)):
        sys.exit(0)
    _emit_rewrite(command, stripped)
    sys.exit(0)


# FUNCTIONS

# Parse stdin JSON and return tool_input.command; return None on any error or missing field (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return cmd if isinstance(cmd, str) else None
    except Exception:
        return None

# True if command contains 'git' followed (anywhere) by diff, log, or show
def _is_git_diff_log(command: str) -> bool:
    return bool(_GIT_SUBCMD.search(command))

# True if command contains a ..-range token (e.g. dev..HEAD, dev.., ..HEAD)
def _has_range_token(command: str) -> bool:
    return bool(_RANGE_TOKEN.search(command))

# True if the first non-flag token after diff/log/show looks like a bare ref name
def _has_bare_ref_token(command: str) -> bool:
    m = _SUBCOMMAND_AFTER.search(command)
    if not m:
        return False
    for token in m.group(1).split():
        if token.startswith('-'):
            continue
        return bool(_BARE_REF.match(token)) and '..' not in token
    return False

# True if command already contains a standalone -- path separator (not --flag like --stat)
def _has_path_separator(command: str) -> bool:
    return bool(_HAS_PATH_SEP.search(command))

# Insert ' -- ' before the first unquoted chain operator / redirect, or append at end
def _insert_path_separator(command: str, stripped: str) -> str:
    m = _CHAIN_OP_RE.search(stripped)
    if m:
        pos = m.start()
        while pos > 0 and stripped[pos - 1] in (' ', '\t'):
            pos -= 1
        return command[:pos] + ' --' + command[pos:]
    return command.rstrip() + ' --'

# Emit allow+updatedInput JSON to rewrite the command in-place
def _emit_rewrite(command: str, stripped: str) -> None:
    rewritten = _insert_path_separator(command, stripped)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {"command": rewritten},
        },
        "systemMessage": (
            f"Hook rewrote git command: inserted -- to disambiguate ref/range from path. "
            f"Original: `{command}`. Rewritten: `{rewritten}`."
        ),
    }
    print(json.dumps(output))


if __name__ == "__main__":
    rewrite_git_ambiguous_workflow()
