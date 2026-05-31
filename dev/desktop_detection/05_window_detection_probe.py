# INFRASTRUCTURE
import ctypes
import json
import os
import secrets
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_REPORTS_DIR = Path(__file__).parent / "05_reports"

_CG  = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
_OBJ = ctypes.CDLL('/usr/lib/libobjc.A.dylib')

_OBJ.sel_registerName.restype  = ctypes.c_void_p
_OBJ.sel_registerName.argtypes = [ctypes.c_char_p]
_OBJ.objc_getClass.restype     = ctypes.c_void_p
_OBJ.objc_getClass.argtypes    = [ctypes.c_char_p]

# Module-level CFUNCTYPE refs — GC of these corrupts the IMP pointer table
_FT_vv   = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_vvv  = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_vvcp = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)
_FT_vvl  = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)
_FT_lvv  = ctypes.CFUNCTYPE(ctypes.c_long,   ctypes.c_void_p, ctypes.c_void_p)
_FT_pvv  = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_nvv  = ctypes.CFUNCTYPE(None,            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

_IMP = ctypes.cast(_OBJ.objc_msgSend, ctypes.c_void_p).value

_CG.CGSMainConnectionID.argtypes         = []
_CG.CGSMainConnectionID.restype          = ctypes.c_int32
_CG.CGSGetActiveSpace.argtypes           = [ctypes.c_int32]
_CG.CGSGetActiveSpace.restype            = ctypes.c_uint64
_CG.CGSCopyManagedDisplaySpaces.argtypes = [ctypes.c_int32]
_CG.CGSCopyManagedDisplaySpaces.restype  = ctypes.c_void_p
_CG.CGSCopySpacesForWindows.argtypes     = [ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p]
_CG.CGSCopySpacesForWindows.restype      = ctypes.c_void_p
_CG.CGWindowListCopyWindowInfo.argtypes  = [ctypes.c_uint32, ctypes.c_uint32]
_CG.CGWindowListCopyWindowInfo.restype   = ctypes.c_void_p

_CGS_SPACE_MASK    = 0x7
_CGW_LIST_ALL      = 0   # kCGWindowListOptionAll — all spaces
_CGW_LIST_ONSCREEN = 1   # kCGWindowListOptionOnScreenOnly — active space only
_CGW_NULL_WID      = 0

# Window type constants
_WIN_TMUX = "ghostty_tmux"
_WIN_OSC2 = "ghostty_osc2"
_WIN_COT  = "coteditor"

_OWNER = {_WIN_TMUX: "Ghostty", _WIN_OSC2: "Ghostty", _WIN_COT: "CotEditor"}

# require_name=True excludes Ghostty tab-bar strips (name=None, h=33px); False for CotEditor
_REQUIRE_NAME = {_WIN_TMUX: True, _WIN_OSC2: True, _WIN_COT: False}

_TOKEN_PREFIX = {_WIN_TMUX: "p05t", _WIN_OSC2: "p05g", _WIN_COT: "p05c"}


# FUNCTIONS

# --- ObjC bridge helpers (verbatim from 04_space_move_probe.py) ---

def _sel(s: str):
    return _OBJ.sel_registerName(s.encode())

def _msg1v(obj, s: str, a):
    return ctypes.cast(_IMP, _FT_vvv)(obj, _sel(s), a)

def _msg1cp(obj, s: str, a: bytes):
    return ctypes.cast(_IMP, _FT_vvcp)(obj, _sel(s), a)

def _msg1l(obj, s: str, a: int):
    return ctypes.cast(_IMP, _FT_vvl)(obj, _sel(s), ctypes.c_long(a))

def _msgl(obj, s: str) -> int:
    return ctypes.cast(_IMP, _FT_lvv)(obj, _sel(s))

def _msgp(obj, s: str):
    return ctypes.cast(_IMP, _FT_pvv)(obj, _sel(s))

def _nsstr(s: str):
    cls = _OBJ.objc_getClass(b"NSString")
    return _msg1cp(cls, "stringWithUTF8String:", s.encode())

def _cf_count(arr) -> int:
    return _msgl(arr, "count")

def _cf_at(arr, i: int):
    return _msg1l(arr, "objectAtIndex:", i)

def _dict_val(d, key: str):
    return _msg1v(d, "objectForKey:", _nsstr(key))

def _dict_str(d, key: str) -> Optional[str]:
    v = _dict_val(d, key)
    if not v:
        return None
    r = _msgp(v, "UTF8String")
    return r.decode() if r else None

def _dict_long(d, key: str) -> Optional[int]:
    v = _dict_val(d, key)
    return _msgl(v, "intValue") if v else None

# Build NSMutableArray of NSNumber(numberWithUnsignedInt:) — correct shape for
# CGSCopySpacesForWindows (CGWindowID = uint32_t; verbatim from 04)
def _make_uint_array(values: List[int]):
    NSMutableArray = _OBJ.objc_getClass(b"NSMutableArray")
    NSNumber       = _OBJ.objc_getClass(b"NSNumber")
    arr = ctypes.cast(_IMP, _FT_vv)(NSMutableArray, _sel("array"))
    for v in values:
        n = ctypes.cast(_IMP, _FT_vvl)(NSNumber, _sel("numberWithUnsignedInt:"), ctypes.c_long(v))
        ctypes.cast(_IMP, _FT_nvv)(arr, _sel("addObject:"), n)
    return arr

# Returns ({space_id: (display_abbrev, desktop_no_1based)}, active_space_id)
def _build_space_map(cid: int) -> Tuple[Dict[int, Tuple[str, int]], int]:
    active  = _CG.CGSGetActiveSpace(cid)
    dsp_arr = _CG.CGSCopyManagedDisplaySpaces(cid)
    smap: Dict[int, Tuple[str, int]] = {}
    for di in range(_cf_count(dsp_arr)):
        d_dict  = _cf_at(dsp_arr, di)
        disp_id = (_dict_str(d_dict, 'Display Identifier') or
                   _dict_str(d_dict, 'DisplayIdentifier') or
                   _dict_str(d_dict, 'Display ID') or 'unknown')
        abbrev  = disp_id[:8]
        spc_val = _dict_val(d_dict, 'Spaces') or _dict_val(d_dict, 'spaces')
        if not spc_val:
            continue
        for si in range(_cf_count(spc_val)):
            sp  = _cf_at(spc_val, si)
            sid = (_dict_long(sp, 'ManagedSpaceID') or
                   _dict_long(sp, 'id') or _dict_long(sp, 'ID'))
            if sid is not None:
                smap[sid] = (abbrev, si + 1)
    return smap, active

# WIDs of every window visible on the currently-active space
def _on_screen_wids() -> Set[int]:
    arr = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ONSCREEN, _CGW_NULL_WID)
    out: Set[int] = set()
    for i in range(_cf_count(arr)):
        wid = _dict_long(_cf_at(arr, i), "kCGWindowNumber")
        if wid is not None:
            out.add(wid)
    return out

# Space IDs for a single WID via CGSCopySpacesForWindows
def _spaces_for_wid(cid: int, wid: int) -> List[int]:
    result_arr = _CG.CGSCopySpacesForWindows(cid, _CGS_SPACE_MASK, _make_uint_array([wid]))
    if not result_arr:
        return []
    spaces = []
    for i in range(_cf_count(result_arr)):
        ns_num = _cf_at(result_arr, i)
        sid    = _msgl(ns_num, "intValue") if ns_num else None
        if sid is not None:
            spaces.append(sid)
    return spaces

# WIDs of all layer-0 windows of `owner`; require_name=True excludes name=None entries
def _owner_wids_layer0(owner: str, require_name: bool = False) -> Set[int]:
    arr = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ALL, _CGW_NULL_WID)
    out: Set[int] = set()
    for i in range(_cf_count(arr)):
        d = _cf_at(arr, i)
        if _dict_long(d, "kCGWindowLayer") != 0:
            continue
        if _dict_str(d, "kCGWindowOwnerName") != owner:
            continue
        if require_name and _dict_str(d, "kCGWindowName") is None:
            continue
        wid = _dict_long(d, "kCGWindowNumber")
        if wid is not None:
            out.add(wid)
    return out

# PIDs of all processes owning windows attributed to `owner`
def _owner_pids(owner: str) -> Set[int]:
    arr = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ALL, _CGW_NULL_WID)
    pids: Set[int] = set()
    for i in range(_cf_count(arr)):
        d = _cf_at(arr, i)
        if _dict_str(d, "kCGWindowOwnerName") == owner:
            pid = _dict_long(d, "kCGWindowOwnerPID")
            if pid is not None:
                pids.add(pid)
    return pids

# kCGWindowName + kCGWindowOwnerPID for a given WID (single CGWindowList scan)
def _wid_info(wid: int) -> Tuple[Optional[str], Optional[int]]:
    arr = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ALL, _CGW_NULL_WID)
    for i in range(_cf_count(arr)):
        d = _cf_at(arr, i)
        if _dict_long(d, "kCGWindowNumber") == wid:
            return _dict_str(d, "kCGWindowName"), _dict_long(d, "kCGWindowOwnerPID")
    return None, None

# True if wid appears anywhere in CGWindowList (all spaces)
def _wid_exists(wid: int) -> bool:
    arr = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ALL, _CGW_NULL_WID)
    for i in range(_cf_count(arr)):
        if _dict_long(_cf_at(arr, i), "kCGWindowNumber") == wid:
            return True
    return False

# Method A — title-match: first layer-0 window of owner whose name contains token
def _method_a(owner: str, token: str) -> Tuple[Optional[int], Optional[str]]:
    arr = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ALL, _CGW_NULL_WID)
    for i in range(_cf_count(arr)):
        d = _cf_at(arr, i)
        if _dict_long(d, "kCGWindowLayer") != 0:
            continue
        if _dict_str(d, "kCGWindowOwnerName") != owner:
            continue
        name = _dict_str(d, "kCGWindowName")
        if name and token in name:
            wid = _dict_long(d, "kCGWindowNumber")
            if wid is not None:
                return wid, name
    return None, None

# Method B — frontmost: first layer-0 window of owner in CGWindowList front-to-back order
def _method_b(owner: str, require_name: bool) -> Optional[int]:
    arr = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ALL, _CGW_NULL_WID)
    for i in range(_cf_count(arr)):
        d = _cf_at(arr, i)
        if _dict_long(d, "kCGWindowLayer") != 0:
            continue
        if _dict_str(d, "kCGWindowOwnerName") != owner:
            continue
        if require_name and _dict_str(d, "kCGWindowName") is None:
            continue
        wid = _dict_long(d, "kCGWindowNumber")
        if wid is not None:
            return wid
    return None

# Launch a new window of the given type; foreground=False uses open -g
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
            ["open", "-n"] + fg_flag + ["-a", "CotEditor",
             f"/tmp/probe05_{token}.txt"],
            capture_output=True, timeout=10,
        )

# Close window and clean up per-type side-effects.
# pids_before: app PIDs pre-trial; a new PID is safe to SIGTERM as cleanup fallback.
# Returns True if wid is gone from CGWindowList within 3s.
def _cleanup_window(
    win_type: str, token: str, wid: Optional[int], pids_before: Set[int]
) -> bool:
    if win_type == _WIN_TMUX:
        # Killing tmux session exits tmux-attach → Ghostty closes the terminal window
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

    if wid is None:
        return True

    # Poll until WID gone from CGWindowList (max 3s)
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if not _wid_exists(wid):
            return True
        time.sleep(0.3)

    # Fallback: SIGTERM the owning process if it is a new one (safe: separate -n instance)
    _, wid_pid = _wid_info(wid)
    if wid_pid is not None and wid_pid not in pids_before:
        subprocess.run(["kill", "-15", str(wid_pid)], capture_output=True)
        time.sleep(0.8)
        return not _wid_exists(wid)

    return False

# Run one trial: open window, detect via ground-truth + methods A/B, measure space signals.
def _run_trial(
    cid: int, space_map: Dict[int, Tuple[str, int]],
    win_type: str, trial_n: int, foreground: bool,
) -> dict:
    owner    = _OWNER[win_type]
    req_name = _REQUIRE_NAME[win_type]
    token    = _TOKEN_PREFIX[win_type] + secrets.token_hex(3)
    ts       = time.strftime("%Y%m%d_%H%M%S")
    fg_label = "fg" if foreground else "bg"

    print(f"  [{win_type} trial {trial_n} {fg_label}] token={token}", flush=True)

    # S1: active space snapshotted STRICTLY before open
    s1_space_id = int(_CG.CGSGetActiveSpace(cid))
    s1_desktop  = space_map.get(s1_space_id, ("?", "?"))[1]

    # Ground truth: before snapshot, then poll until delta non-empty
    pids_before = _owner_pids(owner)
    before      = _owner_wids_layer0(owner, req_name)

    _open_window(win_type, token, foreground)

    wid_gt     = None
    poll_start = time.monotonic()
    while time.monotonic() - poll_start < 5.0:
        time.sleep(0.2)
        after = _owner_wids_layer0(owner, req_name)
        delta = after - before
        if delta:
            wid_gt = min(delta)
            break
    poll_elapsed = round(time.monotonic() - poll_start, 2)

    title_observed  = None
    s2_on_screen    = None
    s3_space_id     = None
    s3_desktop      = None
    space_all_agree = None
    ma_wid          = None
    ma_name         = None
    ma_agrees       = None
    mb_wid          = None
    mb_agrees       = None

    if wid_gt is not None:
        time.sleep(0.5)   # let title settle after detection (OSC-2 late-set, tmux title)

        title_observed, _ = _wid_info(wid_gt)

        # Method A — title-match
        ma_wid, ma_name = _method_a(owner, token)
        ma_agrees = (ma_wid == wid_gt)

        # Method B — frontmost among owner layer-0 windows
        mb_wid    = _method_b(owner, req_name)
        mb_agrees = (mb_wid == wid_gt)

        # Space signals
        s2_on_screen = wid_gt in _on_screen_wids()
        s3_spaces    = _spaces_for_wid(cid, wid_gt)
        s3_space_id  = s3_spaces[0] if s3_spaces else None
        if s3_space_id is not None:
            s3_desktop = space_map.get(s3_space_id, ("?", "?"))[1]

        s1_s3_agree     = (s1_space_id == s3_space_id) if s3_space_id is not None else False
        space_all_agree = s1_s3_agree and (s2_on_screen is True)

    print(
        f"    gt={wid_gt}  title={repr(title_observed)}"
        f"  A={'agree' if ma_agrees else 'DISAGREE'}"
        f"  B={'agree' if mb_agrees else 'DISAGREE'}"
        f"  desktop={s3_desktop}  space_agree={space_all_agree}",
        flush=True,
    )

    cleanup_ok = _cleanup_window(win_type, token, wid_gt, pids_before)
    time.sleep(1.0)   # stabilize between trials

    result = {
        "type":           win_type,
        "trial":          trial_n,
        "foreground":     foreground,
        "token":          token,
        "gt_wid":         wid_gt,
        "gt_found":       wid_gt is not None,
        "poll_elapsed_s": poll_elapsed,
        "title_observed": title_observed,
        "method_a": {
            "wid":          ma_wid,
            "matched_name": ma_name,
            "agrees":       ma_agrees,
        },
        "method_b": {
            "wid":    mb_wid,
            "agrees": mb_agrees,
        },
        "space": {
            "s1_space_id":  s1_space_id,
            "s1_desktop":   s1_desktop,
            "s2_on_screen": s2_on_screen,
            "s3_space_id":  s3_space_id,
            "s3_desktop":   s3_desktop,
            "all_agree":    space_all_agree,
        },
        "cleanup_ok": cleanup_ok,
    }

    json_path = _REPORTS_DIR / f"trial_{win_type}_{trial_n}_{ts}.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"    -> {json_path.name}", flush=True)

    return result

# Format and print per-trial results as aligned summary table
def _print_summary(results: List[dict]) -> None:
    print("=== Summary Table ===")
    hdr = (
        f"{'type':<16} {'tr':>2} {'fg/bg':>5}  {'gt_wid':>7}"
        f"  {'A_agree':>7}  {'B_agree':>7}  {'desktop':>7}  {'space_agree':>11}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        fg_str    = "fg" if r["foreground"] else "bg"
        gt_str    = str(r["gt_wid"]) if r["gt_wid"] is not None else "N/A"
        a_str     = str(r["method_a"]["agrees"])
        b_str     = str(r["method_b"]["agrees"])
        desktop   = r["space"]["s3_desktop"] or r["space"]["s1_desktop"]
        space_str = str(desktop) if desktop is not None else "?"
        sa_str    = str(r["space"]["all_agree"])
        print(
            f"{r['type']:<16} {r['trial']:>2} {fg_str:>5}  {gt_str:>7}"
            f"  {a_str:>7}  {b_str:>7}  {space_str:>7}  {sa_str:>11}"
        )


# ORCHESTRATOR

def probe_workflow() -> None:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cid = _CG.CGSMainConnectionID()
    space_map, active_space = _build_space_map(cid)
    active_desktop = space_map.get(active_space, ("?", "?"))[1]

    print("=== Window Detection Probe 05 ===")
    print(f"  active_space={active_space}  desktop={active_desktop}")
    print(f"  spaces: {sorted(space_map.keys())}")
    print(f"  reports: {_REPORTS_DIR}")
    print()

    win_types      = [_WIN_TMUX, _WIN_OSC2, _WIN_COT]
    trial_schedule = [(1, True), (2, True), (3, False)]

    all_results: List[dict] = []
    for win_type in win_types:
        print(f"--- {win_type} ---")
        for trial_n, foreground in trial_schedule:
            r = _run_trial(cid, space_map, win_type, trial_n, foreground)
            all_results.append(r)
        print()

    _print_summary(all_results)


if __name__ == "__main__":
    probe_workflow()
