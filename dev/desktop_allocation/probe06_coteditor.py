# INFRASTRUCTURE
import subprocess
import time
from pathlib import Path
from typing import Optional

from probe06_bridge import _CG, _cf_at, _cf_count, _dict_str
from probe06_detection import _CGW_LIST_ALL, _CGW_NULL_WID, _method_a

# FUNCTIONS

def _ensure_coteditor_running() -> None:
    arr = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ALL, _CGW_NULL_WID)
    for i in range(_cf_count(arr)):
        if _dict_str(_cf_at(arr, i), "kCGWindowOwnerName") == "CotEditor":
            print("  CotEditor already running", flush=True)
            return
    print("  CotEditor not running — warm-launching...", flush=True)
    subprocess.run(["open", "-g", "-a", "CotEditor"], capture_output=True, timeout=10)
    time.sleep(2.0)
    print("  CotEditor warm-launch complete", flush=True)

def _open_coteditor_doc(token: str) -> None:
    path = Path(f"/tmp/probe06_{token}.txt")
    path.write_text(f"probe06 token={token}\n", encoding="utf-8")
    subprocess.run(
        ["open", "-g", "-a", "CotEditor", str(path)],
        capture_output=True, timeout=10,
    )

def _detect_coteditor_doc(token: str) -> Optional[int]:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        time.sleep(0.2)
        wid, _ = _method_a("CotEditor", token)
        if wid is not None:
            return wid
    return None

def _close_coteditor_doc(token: str) -> None:
    script = (
        f'tell application "CotEditor"\ntry\nrepeat with d in (get documents)\n'
        f'try\nif name of d contains "{token}" then close d saving no\n'
        'end try\nend repeat\nend try\nend tell'
    )
    subprocess.run(["osascript"], input=script.encode(), capture_output=True, timeout=10)
    Path(f"/tmp/probe06_{token}.txt").unlink(missing_ok=True)
