# INFRASTRUCTURE
import fcntl
import json
import os
import sys
import time
from pathlib import Path

_HOOK_STATE_FILE = Path("~/.monitor_cc_menubar_hooks.json").expanduser()
_HOOK_LOCK_FILE  = Path("~/.monitor_cc_menubar_hooks.lock").expanduser()

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

# FUNCTIONS

# Atomically update the hook state file under exclusive file lock
def _write_state(session_id: str, status: str, cwd: str) -> None:
    now = time.time()
    _HOOK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _HOOK_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
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


if __name__ == "__main__":
    hook_writer_workflow()
