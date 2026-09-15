# INFRASTRUCTURE
import ctypes
import subprocess
import time
from pathlib import Path

from probe06_detection import _wids

_REPORTS_DIR = Path(__file__).parent / "06_reports"

# FUNCTIONS

# Set argtypes + restype on a ctypes function in one call
def _setup(fn, argtypes, restype):
    fn.argtypes = argtypes
    fn.restype  = restype

def _take_screenshot(path: Path) -> None:
    subprocess.run(["screencapture", "-x", str(path)], check=True, timeout=5)

# Return (fn, True) if symbol `name` resolves in `lib`, else (None, False)
def _try_sym(lib, name: str):
    try:
        ctypes.c_void_p.in_dll(lib, name)
        return getattr(lib, name), True
    except (OSError, ValueError):
        return None, False

# Measure one move attempt: baseline snapshot → call_fn() → post-snapshot → screenshots
def _run_primitive_trial(label: str, wid: int, call_fn, ts: str) -> dict:
    on_before   = _wids(True)
    in_before   = wid in on_before
    path_before = _REPORTS_DIR / f"06_{label}_before_{ts}.png"
    _take_screenshot(path_before)
    print(f"  [{label}] in_before={in_before}  wid={wid}", flush=True)

    call_fn()
    time.sleep(0.5)

    on_after   = _wids(True)
    in_after   = wid in on_after
    moved      = not in_after
    path_after = _REPORTS_DIR / f"06_{label}_after_{ts}.png"
    _take_screenshot(path_after)
    print(
        f"  [{label}] in_after={in_after}  moved={moved}"
        f"  shots: {path_before.name} → {path_after.name}",
        flush=True,
    )

    return {
        "label":       label,
        "wid":         wid,
        "in_before":   in_before,
        "in_after":    in_after,
        "moved":       moved,
        "shot_before": path_before.name,
        "shot_after":  path_after.name,
    }
