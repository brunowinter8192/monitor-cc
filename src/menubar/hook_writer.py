# INFRASTRUCTURE
import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_APP_SUPPORT          = Path("~/Library/Application Support/com.brunowinter.monitor_cc_menubar").expanduser()
_HOOK_STATE_FILE      = _APP_SUPPORT / "hooks.json"
_HOOK_LOCK_FILE       = _APP_SUPPORT / "hooks.lock"
_QUEUE_FILE           = _APP_SUPPORT / "msg_queue.json"
_QUEUE_LOCK_FILE      = _APP_SUPPORT / "queue.lock"
_GHOSTTY_CWD_UUID_FILE = _APP_SUPPORT / "ghostty_cwd_uuid.json"

# Events that mark the session as actively working
_WORKING_EVENTS = {"UserPromptSubmit"}
# Events that mark the session as idle (turn complete or failed)
_IDLE_EVENTS = {"Stop", "StopFailure"}

# Entries older than this are pruned on each write (2 × ALIVE_WINDOW_SECS)
_PRUNE_AFTER_SECS = 7200

# ORCHESTRATOR

# Read hook payload from stdin, write status to shared hook state file
def hook_writer_workflow() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return
    event = payload.get("hook_event_name", "")
    if event in _WORKING_EVENTS:
        status = "working"
    elif event in _IDLE_EVENTS:
        status = "idle"
    else:
        return
    session_id = payload.get("session_id", "")
    cwd        = payload.get("cwd", "")
    if not session_id:
        return
    _write_state(session_id, status, cwd)
    if status == "idle":
        _maybe_deliver_queue(session_id, cwd)

# FUNCTIONS

# Atomically update the hook state file under exclusive file lock
def _write_state(session_id: str, status: str, cwd: str) -> None:
    now = time.time()
    _APP_SUPPORT.mkdir(parents=True, exist_ok=True)   # defensive: ensures dir exists if hook runs before main app
    try:
        with open(_HOOK_LOCK_FILE, "w") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            state = _load_state()
            # Prune stale entries before writing
            state = {
                sid: entry for sid, entry in state.items()
                if (now - entry.get("updated_ts", 0)) < _PRUNE_AFTER_SECS
            }
            state[session_id] = {"status": status, "cwd": cwd, "updated_ts": now}
            tmp = _HOOK_STATE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(state), encoding="utf-8")
            os.replace(tmp, _HOOK_STATE_FILE)
    except Exception:
        pass

# Read current hook state file; returns empty dict on missing or malformed file
def _load_state() -> dict:
    try:
        return json.loads(_HOOK_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

# Find first unsent message for session and deliver; on success mark sent_at in-place.
# On failure: leave sent_at=null so next Stop retries. Messages are never removed by the hook.
def _maybe_deliver_queue(session_id: str, cwd: str) -> None:
    msg_text, msg_idx = _queue_get_first_unsent(session_id)
    if msg_text is None:
        return
    success = _deliver_message(cwd, msg_text)
    if success:
        _queue_mark_sent(session_id, msg_idx)
    else:
        print(f"queue: delivery failed for session {session_id[:12]}", file=sys.stderr)

# Normalize a single queue entry: bare string → {text, sent_at: None}; dict passthrough
def _normalize_entry(e) -> dict:
    return e if isinstance(e, dict) else {"text": e, "sent_at": None}

# Atomically find first unsent entry for session_id; returns (text, idx) or (None, -1)
def _queue_get_first_unsent(session_id: str):
    try:
        with open(_QUEUE_LOCK_FILE, "w") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            q = _load_queue()
            for idx, entry in enumerate([_normalize_entry(e) for e in q.get(session_id, [])]):
                if entry.get("sent_at") is None:
                    return entry["text"], idx
    except Exception as e:
        print(f"queue: get_first_unsent error: {e}", file=sys.stderr)
    return None, -1

# Atomically set sent_at=now (UTC ISO) on msgs[idx] for session_id (in-place update)
def _queue_mark_sent(session_id: str, idx: int) -> None:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with open(_QUEUE_LOCK_FILE, "w") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            q = _load_queue()
            msgs = [_normalize_entry(e) for e in q.get(session_id, [])]
            if 0 <= idx < len(msgs):
                msgs[idx] = {**msgs[idx], "sent_at": now_iso}
                q[session_id] = msgs
                _save_queue(q)
    except Exception as e:
        print(f"queue: mark_sent error: {e}", file=sys.stderr)

# Focus Ghostty terminal for cwd and type message+Return via AppleScript
# Reads ghostty_cwd_uuid.json for UUID; falls back to cwd-based focus
def _deliver_message(cwd: str, msg: str) -> bool:
    uuid = _get_terminal_uuid(cwd)
    script = (
        f'tell application "Ghostty"\n'
        f'  focus terminal id "{_esc(uuid)}"\n'
        f'end tell\n'
        f'delay 0.1\n'
        f'tell application "System Events"\n'
        f'  keystroke "{_esc(msg)}"\n'
        f'  key code 36\n'
        f'end tell'
    ) if uuid else (
        f'tell application "Ghostty"\n'
        f'  activate\n'
        f'  try\n'
        f'    focus (first terminal whose working directory is "{_esc(cwd)}")\n'
        f'  on error\n'
        f'  end try\n'
        f'end tell\n'
        f'delay 0.1\n'
        f'tell application "System Events"\n'
        f'  keystroke "{_esc(msg)}"\n'
        f'  key code 36\n'
        f'end tell'
    )
    try:
        r = subprocess.run(['osascript', '-e', script], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False

# Read ghostty_cwd_uuid.json and return UUID for cwd; None on any error
def _get_terminal_uuid(cwd: str):
    try:
        return json.loads(_GHOSTTY_CWD_UUID_FILE.read_text(encoding="utf-8")).get(cwd)
    except Exception:
        return None

# Load msg_queue.json; returns {} on error
def _load_queue() -> dict:
    try:
        return json.loads(_QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

# Atomic write of queue dict to msg_queue.json
def _save_queue(q: dict) -> None:
    _APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    tmp = _QUEUE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(q), encoding="utf-8")
    os.replace(tmp, _QUEUE_FILE)

# Escape for AppleScript double-quoted string literal (only " needs escaping)
def _esc(s: str) -> str:
    return s.replace('"', '\\"')


if __name__ == "__main__":
    hook_writer_workflow()
