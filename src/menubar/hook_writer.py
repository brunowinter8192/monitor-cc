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

# Find first queued entry for session and deliver; on success set state="sent"+sent_at in-place.
# On failure: entry left unchanged so next Stop retries. Messages are never removed by the hook.
def _maybe_deliver_queue(session_id: str, cwd: str) -> None:
    msg_text, msg_idx = _queue_get_first_unsent(session_id)
    if msg_text is None:
        return
    uuid = _get_terminal_uuid(cwd)
    print(f"queue: delivering text={msg_text!r} cwd={cwd!r} uuid={uuid!r}", file=sys.stderr)
    success = _deliver_message(cwd, msg_text)
    print(f"queue: deliver returned success={success}", file=sys.stderr)
    if success:
        print(f"queue: mark_sent idx={msg_idx}", file=sys.stderr)
        _queue_mark_sent(session_id, msg_idx)
    else:
        print(f"queue: delivery failed for session {session_id[:12]}", file=sys.stderr)

# Normalize a single queue entry to the three-state format (mirrors queue.py).
# Stale guard: state=queued + sent_at set → treat as sent.
def _normalize_entry(e) -> dict:
    if isinstance(e, str):
        return {"text": e, "state": "queued", "sent_at": None}
    d = dict(e)
    if "state" not in d:
        d["state"] = "sent" if d.get("sent_at") else "queued"
    elif d["state"] == "queued" and d.get("sent_at") is not None:
        d["state"] = "sent"
    return d

# Atomically find first queued entry for session_id; returns (text, idx) or (None, -1).
# Skips drafts (state="draft") and already-sent entries (state="sent").
def _queue_get_first_unsent(session_id: str):
    try:
        with open(_QUEUE_LOCK_FILE, "w") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            q = _load_queue()
            for idx, entry in enumerate([_normalize_entry(e) for e in q.get(session_id, [])]):
                if entry.get("state") == "queued":
                    return entry["text"], idx
    except Exception as e:
        print(f"queue: get_first_unsent error: {e}", file=sys.stderr)
    return None, -1

# Atomically set state="sent" + sent_at=now (UTC ISO) on msgs[idx] for session_id (in-place update)
def _queue_mark_sent(session_id: str, idx: int) -> None:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with open(_QUEUE_LOCK_FILE, "w") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            q = _load_queue()
            msgs = [_normalize_entry(e) for e in q.get(session_id, [])]
            if 0 <= idx < len(msgs):
                msgs[idx] = {**msgs[idx], "state": "sent", "sent_at": now_iso}
                q[session_id] = msgs
                _save_queue(q)
    except Exception as e:
        print(f"queue: mark_sent error: {e}", file=sys.stderr)

# Deliver message to Ghostty terminal via native API (no System Events)
# UUID path: input text + send enter to terminal by id
# cwd fallback: find terminal by working directory, input text + send enter
def _deliver_message(cwd: str, msg: str) -> bool:
    uuid = _get_terminal_uuid(cwd)
    if uuid:
        script = (
            f'tell application "Ghostty"\n'
            f'  set t to first terminal whose id is "{_esc(uuid)}"\n'
            f'  input text "{_esc(msg)}" to t\n'
            f'  send key "enter" to t\n'
            f'end tell'
        )
    else:
        script = (
            f'tell application "Ghostty"\n'
            f'  set targets to (every terminal whose working directory is "{_esc(cwd)}")\n'
            f'  if (count of targets) > 0 then\n'
            f'    set t to item 1 of targets\n'
            f'    input text "{_esc(msg)}" to t\n'
            f'    send key "enter" to t\n'
            f'    return true\n'
            f'  end if\n'
            f'  return false\n'
            f'end tell'
        )
    try:
        r = subprocess.run(['osascript', '-e', script], capture_output=True, timeout=5)
        print(f"queue: osascript rc={r.returncode} stdout={r.stdout.decode(errors='replace')!r} stderr={r.stderr.decode(errors='replace')!r}", file=sys.stderr)
        if uuid:
            return r.returncode == 0
        return r.returncode == 0 and b'true' in r.stdout
    except Exception as exc:
        print(f"queue: osascript exception: {exc}", file=sys.stderr)
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
