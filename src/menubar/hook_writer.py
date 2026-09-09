# INFRASTRUCTURE
import fcntl
import json
import os
import sys
import time
from pathlib import Path

_APP_SUPPORT     = Path("~/Library/Application Support/com.brunowinter.monitor-cc-menubar").expanduser()
_HOOK_STATE_FILE = _APP_SUPPORT / "hooks.json"
_HOOK_LOCK_FILE  = _APP_SUPPORT / "hooks.lock"

_WORKING_EVENTS = {"UserPromptSubmit"}
_IDLE_EVENTS = {"Stop", "StopFailure"}

_PRUNE_AFTER_SECS = 7200

# ORCHESTRATOR

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

def _write_state(session_id: str, status: str, cwd: str) -> None:
    now = time.time()
    _APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    try:
        with open(_HOOK_LOCK_FILE, "w") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            state = _load_state()
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

def _load_state() -> dict:
    try:
        return json.loads(_HOOK_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

if __name__ == "__main__":
    hook_writer_workflow()
