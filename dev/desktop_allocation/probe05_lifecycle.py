# INFRASTRUCTURE
import subprocess
import time
from pathlib import Path
from typing import Optional, Set

from probe05_bridge import _CG, _cf_at, _cf_count, _dict_str
from probe05_detection import _CGW_LIST_ALL, _CGW_NULL_WID, _WIN_COT, _WIN_OSC2, _WIN_TMUX, _wid_exists, _wid_info

# FUNCTIONS

def _open_window(win_type: str, token: str, foreground: bool) -> None:
    fg_flag = [] if foreground else ["-g"]
    if win_type == _WIN_TMUX:
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", token, "sleep 60"],
            check=True, capture_output=True, timeout=10,
        )
        subprocess.run(
            ["open", "-n"] + fg_flag + ["-a", "Ghostty",
             "--args", "--command", f"tmux attach-session -t {token}"],
            capture_output=True, timeout=10,
        )
    elif win_type == _WIN_OSC2:
        subprocess.run(
            ["open", "-n"] + fg_flag + ["-a", "Ghostty",
             "--args", "--command",
             f"bash -c 'printf \"\\033]2;{token}\\007\"; sleep 60'"],
            capture_output=True, timeout=10,
        )
    elif win_type == _WIN_COT:
        Path(f"/tmp/probe05_{token}.txt").write_text(
            f"probe05 token={token}\n", encoding="utf-8"
        )
        subprocess.run(
            ["open", "-g", "-a", "CotEditor", f"/tmp/probe05_{token}.txt"],
            capture_output=True, timeout=10,
        )

def _close_window_for_type(win_type: str, token: str) -> None:
    if win_type == _WIN_TMUX:
        subprocess.run(
            ["tmux", "kill-session", "-t", token],
            capture_output=True, timeout=5,
        )
    elif win_type == _WIN_OSC2:
        script = f'''tell application "Ghostty"
    try
        repeat with w in (get windows)
            try
                if name of w contains "{token}" then close w
            end try
        end repeat
    end try
end tell'''
        subprocess.run(["osascript"], input=script.encode(), capture_output=True, timeout=10)
    elif win_type == _WIN_COT:
        script = f'''tell application "CotEditor"
    try
        repeat with d in (get documents)
            try
                if name of d contains "{token}" then close d saving no
            end try
        end repeat
    end try
end tell'''
        subprocess.run(["osascript"], input=script.encode(), capture_output=True, timeout=10)
        Path(f"/tmp/probe05_{token}.txt").unlink(missing_ok=True)

def _wait_for_wid_gone(wid: int, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _wid_exists(wid):
            return True
        time.sleep(0.3)
    return False

def _force_kill_if_new_pid(wid: int, pids_before: Set[int]) -> bool:
    _, wid_pid = _wid_info(wid)
    if wid_pid is not None and wid_pid not in pids_before:
        subprocess.run(["kill", "-15", str(wid_pid)], capture_output=True)
        time.sleep(0.8)
        return not _wid_exists(wid)
    return False

def _cleanup_window(
    win_type: str, token: str, wid: Optional[int], pids_before: Set[int]
) -> bool:
    _close_window_for_type(win_type, token)

    if wid is None:
        return True

    if _wait_for_wid_gone(wid):
        return True

    return _force_kill_if_new_pid(wid, pids_before)

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
