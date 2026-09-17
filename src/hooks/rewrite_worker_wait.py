# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_WAIT_MENTION_RE = re.compile(r'\bworker-cli\s+wait\b')
_WAIT_CANONICAL_RE = re.compile(r'^\s*worker-cli\s+wait\b([^;&|\n]*)$')
_CD_WAIT_RE = re.compile(r'^\s*cd\s+([^\s;&|\n]+)\s*(?:;|&&|\n)\s*worker-cli\s+wait\b([^;&|\n]*)$')

_BLOCK_MESSAGE = (
    "worker-cli wait cannot run chained with anything beyond a leading `cd` — a trailing "
    "`&& echo done`, a second command after it, or a pipe would be silently dropped or never "
    "run. Issue it as its own separate Bash call. To set the target directory, pass it as the "
    "positional argument instead of cd'ing there first: `worker-cli wait /path/to/project`.\n"
)


# ORCHESTRATOR

def rewrite_worker_wait_workflow() -> None:
    command, run_in_background, session_id = _parse_input()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if not _WAIT_MENTION_RE.search(stripped):
        sys.exit(0)
    cd_match = _CD_WAIT_RE.match(stripped)
    if cd_match:
        _emit_rewrite(_collapse_cd(cd_match), command, session_id)
    if _WAIT_CANONICAL_RE.match(stripped):
        if run_in_background:
            sys.exit(0)
        _emit_rewrite(command, command, session_id)
    _block(command, session_id)


# FUNCTIONS

def _parse_input():
    try:
        payload = json.loads(sys.stdin.read())
        tool_input = payload.get("tool_input", {})
        cmd = tool_input.get("command")
        bg = tool_input.get("run_in_background", False)
        cmd = cmd if isinstance(cmd, str) else None
        bg = bg if isinstance(bg, bool) else False
        return cmd, bg, payload.get("session_id")
    except Exception:
        return None, False, None

def _collapse_cd(cd_match) -> str:
    cd_path = cd_match.group(1)
    tail = cd_match.group(2).strip()
    tokens = tail.split()
    if tokens and not tokens[0].startswith('-'):
        return f"worker-cli wait {tail}"
    if tail:
        return f"worker-cli wait {cd_path} {tail}"
    return f"worker-cli wait {cd_path}"

def _emit_rewrite(corrected_command: str, original_command: str, session_id) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {
                "command": corrected_command,
                "run_in_background": True,
            },
        },
    }
    log_fire("rewrite_worker_wait", "rewrite", "Bash", original_command,
             rewritten=corrected_command, session_id=session_id)
    print(json.dumps(output))
    sys.exit(0)

def _block(command: str, session_id) -> None:
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("rewrite_worker_wait", "block", "Bash", command,
             reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)


if __name__ == "__main__":
    rewrite_worker_wait_workflow()
