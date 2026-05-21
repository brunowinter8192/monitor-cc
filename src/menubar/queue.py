# INFRASTRUCTURE
import json
import os
import subprocess
from typing import Optional

from .paths import QUEUE_FILE, QUEUE_LOCK, GHOSTTY_CWD_UUID_FILE

# FUNCTIONS

# Normalize a single queue entry: bare string → {text, sent_at: None}; dict passthrough
def _normalize_entry(e) -> dict:
    return e if isinstance(e, dict) else {"text": e, "sent_at": None}

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

# Deliver via Ghostty terminal UUID: focus terminal id → System Events keystroke + Return
def _deliver_via_uuid(uuid: str, message: str) -> bool:
    script = (
        f'tell application "Ghostty"\n'
        f'  focus terminal id "{_esc(uuid)}"\n'
        f'end tell\n'
        f'delay 0.1\n'
        f'tell application "System Events"\n'
        f'  keystroke "{_esc(message)}"\n'
        f'  key code 36\n'
        f'end tell'
    )
    try:
        r = subprocess.run(['osascript', '-e', script], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False

# Deliver via cwd-based focus fallback (when UUID unknown; limited: uses PTY initial cwd)
def _deliver_via_cwd(cwd: str, message: str) -> bool:
    script = (
        f'tell application "Ghostty"\n'
        f'  activate\n'
        f'  try\n'
        f'    focus (first terminal whose working directory is "{_esc(cwd)}")\n'
        f'  on error\n'
        f'  end try\n'
        f'end tell\n'
        f'delay 0.1\n'
        f'tell application "System Events"\n'
        f'  keystroke "{_esc(message)}"\n'
        f'  key code 36\n'
        f'end tell'
    )
    try:
        r = subprocess.run(['osascript', '-e', script], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False
