# INFRASTRUCTURE
import json
import re
import sys

# git diff/log/show with ..-range token (e.g. dev..HEAD, main..feature)
_GIT_SUBCMD       = re.compile(r'\bgit\b.*?\b(diff|log|show)\b', re.DOTALL)
# Range token: <name>..<name> or <name>.. or ..<name>
_RANGE_TOKEN      = re.compile(r'[\w./:-]+\.\.[\w./:-]*|\.\.[\w./:-]+')
# Capture text after the subcommand for bare-ref inspection
_SUBCOMMAND_AFTER = re.compile(r'\b(?:diff|log|show)\b(.+)', re.DOTALL)
# Bare ref: alphanumeric + underscore/hyphen/slash, no dots (branch/commit ref name shape)
_BARE_REF         = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_/\-]*$')
# Standalone -- path separator surrounded by whitespace/boundary (excludes --flag like --stat)
_HAS_PATH_SEP     = re.compile(r'(?:^|\s)--(?:\s|$)')

_SYSTEM_MESSAGE = "Added -- separator to disambiguate branch name from path."


# ORCHESTRATOR

# Read Bash tool_input from stdin; emit updatedInput JSON if git diff/log/show ambiguity detected
def rewrite_git_ambiguous_workflow() -> None:
    command = _parse_command()
    if command is None:
        sys.exit(0)
    if not _is_git_diff_log(command):
        sys.exit(0)
    if _has_path_separator(command):
        sys.exit(0)
    if not (_has_range_token(command) or _has_bare_ref_token(command)):
        sys.exit(0)
    _emit_block_hint(command)
    sys.exit(2)


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

# Print block hint: detection found but auto-rewrite path not supported by CC API.
# Surface a one-line stderr so the model retries with -- appended manually.
# For piped commands the `--` belongs BEFORE the pipe/redirect (right after the
# git subcommand args), not at the very end of the chain.
def _emit_block_hint(command: str) -> None:
    print(
        "BLOCKED: git diff/log/show with bare ref or ..-range — append ' -- ' "
        "after the git subcommand args (before any pipe or redirect) to "
        "disambiguate branch/ref from path.",
        file=sys.stderr,
        end="",
    )
    # Originally designed as `hookSpecificOutput.updatedInput` auto-rewrite (per
    # anthropics/claude-code SKILL.md). Empirically refuted (2026-05-22): per CC
    # CHANGELOG line 1324, allow+updatedInput in PreToolUse only satisfies the
    # AskUserQuestion tool, not Bash. For general Bash rewrite, only `ask`
    # decision works (CHANGELOG line 2629) — rejected by user as workflow tax.
    # Fallback: exit 2 + one-line hint, model retries with -- appended.


if __name__ == "__main__":
    rewrite_git_ambiguous_workflow()
