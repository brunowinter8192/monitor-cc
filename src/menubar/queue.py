# INFRASTRUCTURE
import json
import os
import subprocess
import sys
from typing import Optional

from .paths import QUEUE_FILE, QUEUE_LOCK, GHOSTTY_CWD_UUID_FILE

# FUNCTIONS

# Normalize a single queue entry to the three-state format.
# bare string → queued; dict missing state: sent_at set → sent, else → queued.
# Stale inconsistency guard: state=queued + sent_at set → treat as sent (old code wrote sent_at without flipping state).
def _normalize_entry(e) -> dict:
    if isinstance(e, str):
        return {"text": e, "state": "queued", "sent_at": None}
    d = dict(e)
    if "state" not in d:
        d["state"] = "sent" if d.get("sent_at") else "queued"
    elif d["state"] == "queued" and d.get("sent_at") is not None:
        d["state"] = "sent"
    return d

# Load msg_queue.json; normalizes bare-string entries to dict form for backward compat.
# Returns {} on any error (missing file, parse error, corrupt).
def load_queue() -> dict:
    try:
        raw = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        return {sid: [_normalize_entry(e) for e in msgs] for sid, msgs in raw.items()}
    except Exception:
        return {}

# Atomic write of queue dict; silent on write failure (non-critical storage)
def save_queue(q: dict) -> None:
    try:
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = QUEUE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(q), encoding="utf-8")
        os.replace(tmp, QUEUE_FILE)
    except Exception:
        return

# Focus Ghostty terminal for cwd and deliver message+Return via AppleScript
# Tries UUID-based focus first (from ghostty_cwd_uuid.json), falls back to cwd-match
# Returns True on successful osascript call (not a delivery confirmation)
def deliver_message(cwd: str, message: str) -> bool:
    uuid = _get_terminal_uuid(cwd)
    print(f"queue: deliver_message cwd={cwd!r} uuid={uuid!r}", file=sys.stderr)
    if uuid:
        return _deliver_via_uuid(uuid, message)
    return _deliver_via_cwd(cwd, message)

# Read cwd→UUID from ghostty_cwd_uuid.json; None on any error or missing entry
def _get_terminal_uuid(cwd: str) -> Optional[str]:
    try:
        return json.loads(GHOSTTY_CWD_UUID_FILE.read_text(encoding="utf-8")).get(cwd)
    except Exception:
        return None

# Escape text for use inside AppleScript double-quoted string literal
def _esc(s: str) -> str:
    return s.replace('"', '\\"')

# Deliver via Ghostty terminal UUID: input text + send enter via Ghostty native API (no System Events)
def _deliver_via_uuid(uuid: str, message: str) -> bool:
    script = (
        f'tell application "Ghostty"\n'
        f'  set t to first terminal whose id is "{_esc(uuid)}"\n'
        f'  input text "{_esc(message)}" to t\n'
        f'  send key "enter" to t\n'
        f'end tell'
    )
    try:
        r = subprocess.run(['osascript', '-e', script], capture_output=True, timeout=5)
        print(f"queue: osascript(uuid) rc={r.returncode} stderr={r.stderr.decode(errors='replace')!r}", file=sys.stderr)
        return r.returncode == 0
    except Exception as exc:
        print(f"queue: osascript(uuid) exception: {exc}", file=sys.stderr)
        return False

# Deliver via cwd-match fallback (when UUID unknown): input text + send enter via Ghostty native API
def _deliver_via_cwd(cwd: str, message: str) -> bool:
    script = (
        f'tell application "Ghostty"\n'
        f'  set targets to (every terminal whose working directory is "{_esc(cwd)}")\n'
        f'  if (count of targets) > 0 then\n'
        f'    set t to item 1 of targets\n'
        f'    input text "{_esc(message)}" to t\n'
        f'    send key "enter" to t\n'
        f'    return true\n'
        f'  end if\n'
        f'  return false\n'
        f'end tell'
    )
    try:
        r = subprocess.run(['osascript', '-e', script], capture_output=True, timeout=5)
        print(f"queue: osascript(cwd) rc={r.returncode} stderr={r.stderr.decode(errors='replace')!r}", file=sys.stderr)
        return r.returncode == 0 and b'true' in r.stdout
    except Exception as exc:
        print(f"queue: osascript(cwd) exception: {exc}", file=sys.stderr)
        return False
