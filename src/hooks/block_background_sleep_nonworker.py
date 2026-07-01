# INFRASTRUCTURE
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# Mirrors _SLEEP_ONLY_BG in rewrite_background_sleep.py — same signature triggers the block check.
_SLEEP_ONLY_BG = re.compile(r'^\s*sleep\s+\d+(?:\.\d+)?\s*(?:&&\s*echo\b[^;&|\n]*)?\s*$')
_WORKER_CLI_RE = re.compile(r'(?:^|[;&|\n])\s*worker-cli\b')
_PRUNE_SECS = 86400  # 24 hours — sessions never outlast this

_STATE_FILE = os.environ.get(
    "MONITOR_CC_LAST_CMD_STATE",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'logs', 'last_cmd_state.jsonl',
    ),
)

_BLOCK_MESSAGE = (
    "Go idle immediately. Stop whatever you are doing and go idle. "
    "A background Bash task self-notifies via its completion notice — "
    "do NOT set a timer to wait for it. Timers are ONLY for polling a worker "
    "you just spawned/messaged (worker-cli).\n"
)

# Sentinel returned by _get_last_cmd on IO/parse failure → fail-open (distinct from None = not found)
_READ_ERROR = object()


# ORCHESTRATOR

# Read Bash tool_input from stdin; block sleep-only background timers unless the last non-timer command was worker-cli
def block_background_sleep_nonworker_workflow() -> None:
    command, run_in_background, session_id = _parse_input()
    if command is None:
        sys.exit(0)
    is_timer = run_in_background and bool(_SLEEP_ONLY_BG.match(command))
    if not is_timer:
        _record_last_cmd(session_id or "", command)
        sys.exit(0)
    last_cmd = _get_last_cmd(session_id or "")
    if last_cmd is _READ_ERROR:
        sys.exit(0)
    if _is_worker_cli(last_cmd):
        sys.exit(0)
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("block_background_sleep_nonworker", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)


# FUNCTIONS

# Parse stdin JSON; return (command, run_in_background, session_id); (None, False, None) on error (fail-open)
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

# True if shell-stripped cmd starts with worker-cli (any subcommand); False for None/empty
def _is_worker_cli(cmd) -> bool:
    if not cmd:
        return False
    stripped = _strip_non_shell_active(cmd)
    return bool(_WORKER_CLI_RE.search(stripped))

# Return stored last non-timer command for session; None if not found; _READ_ERROR on IO/parse failure
def _get_last_cmd(session_id: str):
    try:
        if not os.path.exists(_STATE_FILE):
            return None
        with open(_STATE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get('session_id') == session_id:
                        return entry.get('cmd')
                except Exception:
                    continue
        return None
    except Exception:
        return _READ_ERROR

# Read state file entries not older than cutoff and not belonging to exclude_session; returns list (skips malformed)
def _read_existing_entries(cutoff: datetime.datetime, exclude_session: str) -> list:
    if not os.path.exists(_STATE_FILE):
        return []
    entries = []
    try:
        with open(_STATE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = datetime.datetime.fromisoformat(entry.get('ts', '').replace('Z', '+00:00'))
                    if ts >= cutoff and entry.get('session_id') != exclude_session:
                        entries.append(entry)
                except Exception:
                    continue
    except Exception:
        return []
    return entries

# Write command as latest entry for session; prune entries older than _PRUNE_SECS; fail-silent on any error
def _record_last_cmd(session_id: str, command: str) -> None:
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(seconds=_PRUNE_SECS)
        entries = _read_existing_entries(cutoff, session_id)
        entries.append({
            'ts': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'session_id': session_id,
            'cmd': command,
        })
        state_dir = os.path.dirname(_STATE_FILE)
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)
        with open(_STATE_FILE, 'w', encoding='utf-8') as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        return


if __name__ == "__main__":
    block_background_sleep_nonworker_workflow()
