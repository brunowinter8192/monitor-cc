# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

# Timer form: `sleep N && echo <anything>` standalone. Matches strict canonical
# (`echo done`) AND the looser variants Opus actually emits (`echo "8min check"`).
_TIMER_FORM = re.compile(r'^\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+\S.*$')

_BLOCK_MESSAGE = (
    "two-Bash-in-one-response with sleep-timer detected — second Bash gets SIGTERM'd silently. "
    "Split: dispatch the timer alone in its own response.\n"
)


# ORCHESTRATOR

# Read PreToolUse Bash payload; block when latest assistant message has ≥2 Bash tool_uses AND ≥1 is timer-form
def block_parallel_bash_timer_workflow() -> None:
    command, transcript_path, session_id = _parse_input()
    if command is None or transcript_path is None:
        sys.exit(0)
    bashes = _read_latest_assistant_bashes(transcript_path)
    if len(bashes) < 2:
        sys.exit(0)
    if not any(_is_timer_form(b) for b in bashes):
        sys.exit(0)
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("block_parallel_bash_timer", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)


# FUNCTIONS

# Parse stdin JSON; return (command, transcript_path, session_id); (None, None, None) on any error (fail-open)
def _parse_input():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        tp = payload.get("transcript_path")
        return (
            cmd if isinstance(cmd, str) else None,
            tp if isinstance(tp, str) else None,
            payload.get("session_id"),
        )
    except Exception:
        return None, None, None


# Return list of Bash tool_use command-strings in the latest assistant message of the transcript
def _read_latest_assistant_bashes(transcript_path: str) -> list:
    try:
        with open(transcript_path) as f:
            lines = f.readlines()
    except Exception:
        return []
    latest = None
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except Exception:
            continue
        if entry.get("type") == "assistant":
            latest = entry
            break
    if latest is None:
        return []
    content = latest.get("message", {}).get("content", [])
    if not isinstance(content, list):
        return []
    cmds = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_use" or block.get("name") != "Bash":
            continue
        cmd = block.get("input", {}).get("command")
        if isinstance(cmd, str):
            cmds.append(cmd)
    return cmds


# True if cmd matches the loose timer form (sleep N && echo <anything>)
def _is_timer_form(cmd: str) -> bool:
    return bool(_TIMER_FORM.match(cmd))


if __name__ == "__main__":
    block_parallel_bash_timer_workflow()
