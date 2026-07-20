# INFRASTRUCTURE
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

# Mirrors _SLEEP_ONLY_BG in rewrite_background_sleep.py — same signature triggers the block check.
_SLEEP_ONLY_BG = re.compile(r'^\s*sleep\s+\d+(?:\.\d+)?\s*(?:&&\s*echo\b[^;&|\n]*)?\s*$')
_TIMER_SECS = 600  # rewrite_background_sleep.py normalizes every sleep timer to exactly 600s
_PRUNE_SECS = 86400  # 24 hours — stale entries never outlast this

_STATE_FILE = os.environ.get(
    "MONITOR_CC_TIMER_STATE",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'logs', 'timer_state.jsonl',
    ),
)

# Sentinel returned by _get_expiry on IO/parse failure → fail-open (distinct from None = no timer stored)
_READ_ERROR = object()


# ORCHESTRATOR

# Read Bash tool_input from stdin; block a background sleep-timer if one is already running for this session
def block_concurrent_timer_workflow() -> None:
    command, run_in_background, session_id = _parse_input()
    if command is None:
        sys.exit(0)
    if not (run_in_background and _SLEEP_ONLY_BG.match(command)):
        sys.exit(0)
    now = datetime.datetime.now(datetime.timezone.utc)
    stored_expiry = _get_expiry(session_id or "")
    if stored_expiry is _READ_ERROR:
        sys.exit(0)
    if stored_expiry is not None and now < stored_expiry:
        message = _block_message(stored_expiry)
        print(message, file=sys.stderr, end="")
        log_fire("block_concurrent_timer", "block", "Bash", command, reason=message, session_id=session_id)
        sys.exit(2)
    _record_expiry(session_id or "", now + datetime.timedelta(seconds=_TIMER_SECS))
    sys.exit(0)


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

# Build the block message telling the agent a timer is already running until the given expiry
def _block_message(expiry: datetime.datetime) -> str:
    return (
        "A background timer is already running for this session "
        f"(expires {expiry.strftime('%Y-%m-%dT%H:%M:%SZ')}). Only one timer may run at a time — "
        "wait for its completion notice before setting a new one.\n"
    )

# Return stored timer expiry for session as datetime; None if not found; _READ_ERROR on IO/parse failure
def _get_expiry(session_id: str):
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
                        return datetime.datetime.fromisoformat(entry.get('expiry', '').replace('Z', '+00:00'))
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

# Write the new timer expiry as latest entry for session; prune entries older than _PRUNE_SECS; fail-silent on any error
def _record_expiry(session_id: str, expiry: datetime.datetime) -> None:
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(seconds=_PRUNE_SECS)
        entries = _read_existing_entries(cutoff, session_id)
        entries.append({
            'ts': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'session_id': session_id,
            'expiry': expiry.strftime('%Y-%m-%dT%H:%M:%SZ'),
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
    block_concurrent_timer_workflow()
