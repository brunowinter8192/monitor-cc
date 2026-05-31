# INFRASTRUCTURE
import ctypes
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_REPORTS_DIR = Path(__file__).parent / "06_reports"

_CG  = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
_OBJ = ctypes.CDLL('/usr/lib/libobjc.A.dylib')
_SL  = ctypes.CDLL('/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight')
_AS  = ctypes.CDLL('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')

_OBJ.sel_registerName.restype  = ctypes.c_void_p
_OBJ.sel_registerName.argtypes = [ctypes.c_char_p]
_OBJ.objc_getClass.restype     = ctypes.c_void_p
_OBJ.objc_getClass.argtypes    = [ctypes.c_char_p]

# Module-level CFUNCTYPE refs — GC of these corrupts the IMP pointer table
_FT_vv    = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_vvv   = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_vvcp  = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)
_FT_vvl   = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)
_FT_vvU64 = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64)
_FT_lvv   = ctypes.CFUNCTYPE(ctypes.c_long,   ctypes.c_void_p, ctypes.c_void_p)
_FT_pvv   = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_nvv   = ctypes.CFUNCTYPE(None,            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

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

_AS.AXIsProcessTrusted.argtypes             = []
_AS.AXIsProcessTrusted.restype              = ctypes.c_bool
_CG.CGPreflightScreenCaptureAccess.argtypes = []
_CG.CGPreflightScreenCaptureAccess.restype  = ctypes.c_bool

_CGS_SPACE_MASK    = 0x7
_CGW_LIST_ALL      = 0
_CGW_LIST_ONSCREEN = 1
_CGW_NULL_WID      = 0

_COMPAT_ID = 42   # arbitrary int32 for SLSSpaceSetCompatID / SLSSetWindowListWorkspace


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

# Build NSMutableArray of NSNumber(uint32) — window ID arrays
def _make_uint_array(values: List[int]):
    NSMutableArray = _OBJ.objc_getClass(b"NSMutableArray")
    NSNumber       = _OBJ.objc_getClass(b"NSNumber")
    arr = ctypes.cast(_IMP, _FT_vv)(NSMutableArray, _sel("array"))
    for v in values:
        n = ctypes.cast(_IMP, _FT_vvl)(NSNumber, _sel("numberWithUnsignedInt:"), ctypes.c_long(v))
        ctypes.cast(_IMP, _FT_nvv)(arr, _sel("addObject:"), n)
    return arr

# Build NSMutableArray of NSNumber(uint64) — space ID arrays
def _make_uint64_array(values: List[int]):
    NSMutableArray = _OBJ.objc_getClass(b"NSMutableArray")
    NSNumber       = _OBJ.objc_getClass(b"NSNumber")
    arr = ctypes.cast(_IMP, _FT_vv)(NSMutableArray, _sel("array"))
    for v in values:
        n = ctypes.cast(_IMP, _FT_vvU64)(NSNumber, _sel("numberWithUnsignedLongLong:"), ctypes.c_uint64(v))
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

# WIDs from CGWindowList; onscreen=True → active space only, False → all spaces
def _wids(onscreen: bool = False) -> Set[int]:
    opt = _CGW_LIST_ONSCREEN if onscreen else _CGW_LIST_ALL
    arr = _CG.CGWindowListCopyWindowInfo(opt, _CGW_NULL_WID)
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

# First layer-0 window of `owner` whose kCGWindowName contains token
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

# Ensure CotEditor is running before trials to prevent cold-launch session restore
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

# Print AX + ScreenCapture + binary identity; return (ax_trusted, sc_trusted)
def _check_permissions() -> Tuple[bool, bool]:
    ax  = bool(_AS.AXIsProcessTrusted())
    sc  = bool(_CG.CGPreflightScreenCaptureAccess())
    exe = sys.executable
    rp  = os.path.realpath(exe)
    print("=== Permission Self-Check ===")
    print(f"  AXIsProcessTrusted()             : {ax}")
    print(f"  CGPreflightScreenCaptureAccess() : {sc}")
    print(f"  sys.executable                   : {exe}")
    print(f"  realpath(executable)             : {rp}")
    print()
    return ax, sc

# First non-active space in space_map that has at least one off-screen window
def _find_nonempty_nonactive_space(
    cid: int, active_space_id: int, space_map: Dict[int, Tuple[str, int]]
) -> Optional[int]:
    off_screen = _wids() - _wids(True)
    for wid in off_screen:
        sids = _spaces_for_wid(cid, wid)
        if sids and sids[0] != active_space_id and sids[0] in space_map:
            return sids[0]
    return None

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

# Write tmpfile and open CotEditor doc for token; always -g (no focus steal, no -n)
def _open_coteditor_doc(token: str) -> None:
    path = Path(f"/tmp/probe06_{token}.txt")
    path.write_text(f"probe06 token={token}\n", encoding="utf-8")
    subprocess.run(
        ["open", "-g", "-a", "CotEditor", str(path)],
        capture_output=True, timeout=10,
    )

# Poll CGWindowList until CotEditor window with token appears in title (≤5s)
def _detect_coteditor_doc(token: str) -> Optional[int]:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        time.sleep(0.2)
        wid, _ = _method_a("CotEditor", token)
        if wid is not None:
            return wid
    return None

# Close CotEditor doc by token via AppleScript — works regardless of which Space it's on
def _close_coteditor_doc(token: str) -> None:
    script = (
        f'tell application "CotEditor"\ntry\nrepeat with d in (get documents)\n'
        f'try\nif name of d contains "{token}" then close d saving no\n'
        'end try\nend repeat\nend try\nend tell'
    )
    subprocess.run(["osascript"], input=script.encode(), capture_output=True, timeout=10)
    Path(f"/tmp/probe06_{token}.txt").unlink(missing_ok=True)

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


# ORCHESTRATOR

def probe_workflow() -> None:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cid = _CG.CGSMainConnectionID()

    ax, sc = _check_permissions()

    space_map, active_space = _build_space_map(cid)
    active_desktop = space_map.get(active_space, ('?', '?'))[1]

    print("=== Move Sweep Probe 06 ===")
    print(f"  active_space={active_space}  desktop={active_desktop}")
    print(f"  spaces: {sorted(space_map.keys())}")
    print()

    if len(space_map) < 2:
        print(f"PRECONDITION NOT MET: only {len(space_map)} space — need >= 2")
        return

    target_space = _find_nonempty_nonactive_space(cid, active_space, space_map)
    if target_space is None:
        print("PRECONDITION NOT MET: no non-active Space with existing windows found")
        print("  Move at least one window to a non-active Space and retry")
        return
    target_desktop = space_map.get(target_space, ('?', '?'))[1]
    print(f"  target_space={target_space}  desktop={target_desktop}")
    print()

    _ensure_coteditor_running()
    print()

    # Load symbols for all 4 primitives
    fn_a,     a_ok     = _try_sym(_CG, "CGSMoveWindowsToManagedSpace")
    fn_b,     b_ok     = _try_sym(_SL, "SLSMoveWindowsToManagedSpace")
    fn_c_add, c_add_ok = _try_sym(_CG, "CGSAddWindowsToSpaces")
    fn_c_rem, c_rem_ok = _try_sym(_CG, "CGSRemoveWindowsFromSpaces")
    fn_d_set, d_set_ok = _try_sym(_SL, "SLSSpaceSetCompatID")
    fn_d_ws,  d_ws_ok  = _try_sym(_SL, "SLSSetWindowListWorkspace")
    c_ok = c_add_ok and c_rem_ok
    d_ok = d_set_ok and d_ws_ok

    _i32v64 = [ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint64]
    _i32vv  = [ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p]
    _i32u64i= [ctypes.c_int32, ctypes.c_uint64, ctypes.c_int32]
    _i32vi  = [ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32]
    if a_ok:     _setup(fn_a,     _i32v64, ctypes.c_int32)
    if b_ok:     _setup(fn_b,     _i32v64, ctypes.c_int32)
    if c_add_ok: _setup(fn_c_add, _i32vv,  ctypes.c_int32)
    if c_rem_ok: _setup(fn_c_rem, _i32vv,  ctypes.c_int32)
    if d_set_ok: _setup(fn_d_set, _i32u64i, None)
    if d_ws_ok:  _setup(fn_d_ws,  _i32vi,  None)

    print(f"  A CGSMoveWindowsToManagedSpace  : {'loaded' if a_ok else 'MISSING'}")
    print(f"  B SLSMoveWindowsToManagedSpace  : {'loaded' if b_ok else 'MISSING'}")
    c_detail = 'loaded' if c_ok else f'MISSING (add={c_add_ok} rem={c_rem_ok})'
    d_detail = 'loaded' if d_ok else f'MISSING (set={d_set_ok} ws={d_ws_ok})'
    print(f"  C CGSAddWindowsToSpaces+Remove  : {c_detail}")
    print(f"  D SLSSpaceSetCompatID+Workspace : {d_detail}")
    print()

    results = []

    for label, sym_ok in [("A", a_ok), ("B", b_ok), ("C", c_ok), ("D", d_ok)]:
        print(f"--- Primitive {label} ---")
        if not sym_ok:
            print(f"  SKIP — symbol not loaded")
            results.append({"label": label, "sym_ok": False, "moved": None, "shot_after": "-"})
            print()
            continue

        trial_ts = time.strftime("%Y%m%d_%H%M%S")
        token    = f"p06{label.lower()}" + secrets.token_hex(3)
        print(f"  opening CotEditor doc  token={token}", flush=True)
        _open_coteditor_doc(token)
        wid = _detect_coteditor_doc(token)
        if wid is None:
            print("  FAIL — detect timeout (5s), skipping")
            results.append({"label": label, "sym_ok": True, "moved": None,
                            "shot_after": "-", "error": "detect_timeout"})
            _close_coteditor_doc(token)
            print()
            continue
        print(f"  detected wid={wid}", flush=True)
        time.sleep(0.3)

        if label == "A":
            def call_fn(w=wid, c=cid, t=target_space):
                return fn_a(c, _make_uint_array([w]), ctypes.c_uint64(t))
        elif label == "B":
            def call_fn(w=wid, c=cid, t=target_space):
                return fn_b(c, _make_uint_array([w]), ctypes.c_uint64(t))
        elif label == "C":
            def call_fn(w=wid, c=cid, t=target_space, s=active_space):
                fn_c_add(c, _make_uint_array([w]), _make_uint64_array([t]))
                fn_c_rem(c, _make_uint_array([w]), _make_uint64_array([s]))
        elif label == "D":
            def call_fn(w=wid, c=cid, t=target_space):
                fn_d_set(c, ctypes.c_uint64(t), ctypes.c_int32(_COMPAT_ID))
                fn_d_ws(c, _make_uint_array([w]), ctypes.c_int32(_COMPAT_ID))
                fn_d_set(c, ctypes.c_uint64(t), ctypes.c_int32(0))

        r = _run_primitive_trial(label, wid, call_fn, trial_ts)
        r["sym_ok"] = True
        results.append(r)

        _close_coteditor_doc(token)
        time.sleep(1.0)
        print()

    # --- Summary table ---
    print("=== Per-Primitive Result Table ===")
    hdr = f"{'Prim':<5}  {'Symbol':>6}  {'Moved':>5}  {'in_after':>8}  Shot_after"
    print(hdr)
    print("-" * 60)
    for r in results:
        sym_s    = "yes"  if r.get("sym_ok")           else "no"
        moved_s  = "yes"  if r.get("moved") is True    else ("no" if r.get("moved") is False else "-")
        iafter_s = str(r["in_after"]) if "in_after" in r else "-"
        shot_s   = r.get("shot_after", "-")
        print(f"{r['label']:<5}  {sym_s:>6}  {moved_s:>5}  {iafter_s:>8}  {shot_s}")
    print()

    # --- HEADLINE ---
    moved_labels = [r["label"] for r in results if r.get("moved")]
    if moved_labels:
        print(f"HEADLINE: primitive(s) {', '.join(moved_labels)} MOVED the window"
              f"  |  AX={ax}  ScreenCapture={sc}")
    else:
        print(f"HEADLINE: NO primitive moved the window  |  AX={ax}  ScreenCapture={sc}")


if __name__ == '__main__':
    probe_workflow()
