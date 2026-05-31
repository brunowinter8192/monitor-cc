# INFRASTRUCTURE
import ctypes
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_REPORTS_DIR = Path(__file__).parent / "04_reports"

_CG  = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
_OBJ = ctypes.CDLL('/usr/lib/libobjc.A.dylib')

_OBJ.sel_registerName.restype  = ctypes.c_void_p
_OBJ.sel_registerName.argtypes = [ctypes.c_char_p]
_OBJ.objc_getClass.restype     = ctypes.c_void_p
_OBJ.objc_getClass.argtypes    = [ctypes.c_char_p]

# Module-level CFUNCTYPE refs — GC of these corrupts the IMP pointer table
_FT_vv     = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_vvv    = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_vvcp   = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)
_FT_vvl    = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)
_FT_lvv    = ctypes.CFUNCTYPE(ctypes.c_long,   ctypes.c_void_p, ctypes.c_void_p)
_FT_pvv    = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_nvv    = ctypes.CFUNCTYPE(None,            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
# bridged-op:
_FT_0vv    = ctypes.CFUNCTYPE(None,            ctypes.c_void_p, ctypes.c_void_p)
_FT_vvvu64 = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                               ctypes.c_void_p, ctypes.c_uint64)

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


# FUNCTIONS

# --- objc bridge helpers (verbatim from 01_probe.py) ---

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
# initWithWindows:spaceID: (CGWindowID = uint32_t; verbatim from 01_probe.py)
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

# WIDs of all layer-0 named Ghostty terminal windows across all spaces.
# Requires kCGWindowName != None — excludes tab-bar strips (name=None, h=33px).
def _ghostty_wids_all() -> Set[int]:
    arr = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ALL, _CGW_NULL_WID)
    out: Set[int] = set()
    for i in range(_cf_count(arr)):
        d = _cf_at(arr, i)
        if _dict_long(d, "kCGWindowLayer") != 0:
            continue
        if _dict_str(d, "kCGWindowOwnerName") != "Ghostty":
            continue
        if _dict_str(d, "kCGWindowName") is None:
            continue
        wid = _dict_long(d, "kCGWindowNumber")
        if wid is not None:
            out.add(wid)
    return out

# Space IDs for a WID — used only to record original space before the move
# (not part of PASS/FAIL; CGSCopySpacesForWindows may lag after moves).
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

# SLSBridgedMoveWindowsToManagedSpaceOperation — DockDoor / yabai technique.
# Class hierarchy on 26.5: SLSBridgedMoveWindowsToManagedSpaceOperation
#   → SLSAsynchronousBridgedWindowManagementOperation (defines performWithWMBridgeDelegate)
# performWithWMBridgeDelegate returns void — success verified externally via on-screen list.
def _bridged_move(wids: List[int], target_space_id: int) -> None:
    cls = _OBJ.objc_getClass(b"SLSBridgedMoveWindowsToManagedSpaceOperation")
    if not cls:
        raise RuntimeError("SLSBridgedMoveWindowsToManagedSpaceOperation not found — requires macOS 26")
    allocated = ctypes.cast(_IMP, _FT_vv)(cls, _sel("alloc"))
    if not allocated:
        raise RuntimeError("alloc returned nil")
    ns_array  = _make_uint_array(wids)
    operation = ctypes.cast(_IMP, _FT_vvvu64)(
        allocated, _sel("initWithWindows:spaceID:"),
        ns_array, ctypes.c_uint64(target_space_id),
    )
    if not operation:
        raise RuntimeError("initWithWindows:spaceID: returned nil")
    ctypes.cast(_IMP, _FT_0vv)(operation, _sel("performWithWMBridgeDelegate"))

def _take_screenshot(path: Path) -> None:
    subprocess.run(["screencapture", "-x", str(path)], check=True, timeout=5)


# ORCHESTRATOR

def probe_workflow() -> None:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts  = time.strftime("%Y%m%d_%H%M%S")
    cid = _CG.CGSMainConnectionID()

    space_map, active_space = _build_space_map(cid)
    active_desktop = space_map.get(active_space, ('?', '?'))[1]

    # --- Preconditions ---
    if len(space_map) < 2:
        print(f"PRECONDITION NOT MET: only {len(space_map)} Mission Control space — need >= 2")
        return

    all_ghostty = _ghostty_wids_all()
    if not all_ghostty:
        print("PRECONDITION NOT MET: no named layer-0 Ghostty windows found")
        return

    onscreen_before    = _on_screen_wids()
    off_screen_ghostty = all_ghostty - onscreen_before

    if not off_screen_ghostty:
        print("PRECONDITION NOT MET: all Ghostty windows are on active space — "
              "move a Ghostty window to a different desktop and retry")
        return

    target_wid        = min(off_screen_ghostty)
    original_spaces   = _spaces_for_wid(cid, target_wid)
    original_space_id = original_spaces[0] if original_spaces else None
    original_desktop  = space_map.get(original_space_id, ('?', '?'))[1] if original_space_id else '?'

    print("=== Space-Move Probe (SLSBridgedMoveWindowsToManagedSpaceOperation) ===")
    print(f"  active_space  : {active_space}  desktop {active_desktop}")
    print(f"  target_wid    : {target_wid}")
    print(f"  orig_space    : {original_space_id}  desktop {original_desktop}")
    print(f"  direction     : space {original_space_id} -> {active_space}  (non-active -> active)")
    print(f"  all_spaces    : {sorted(space_map.keys())}")
    print()

    # --- BEFORE: snapshot + screenshot ---
    in_before   = target_wid in onscreen_before
    path_before = _REPORTS_DIR / f"04_before_move_{ts}.png"
    _take_screenshot(path_before)
    print(f"[BEFORE] wid {target_wid} in on-screen list : {in_before}  (expected: False)")
    print(f"[BEFORE] screenshot : {path_before.name}")

    # --- MOVE: non-active -> active via bridged-op ---
    print(f"\n  calling _bridged_move([{target_wid}], space={active_space}) ...")
    _bridged_move([target_wid], active_space)
    time.sleep(0.5)

    # --- AFTER: snapshot + screenshot ---
    onscreen_after = _on_screen_wids()
    in_after       = target_wid in onscreen_after
    path_after     = _REPORTS_DIR / f"04_after_move_{ts}.png"
    _take_screenshot(path_after)
    print(f"[AFTER]  wid {target_wid} in on-screen list : {in_after}  (expected: True)")
    print(f"[AFTER]  screenshot : {path_after.name}")
    print(f"[AFTER]  on-screen delta: added={sorted(onscreen_after - onscreen_before)}")

    # --- PASS/FAIL (grep-friendly) ---
    move_ok = (not in_before) and in_after
    print()
    if move_ok:
        print(f"RESULT: PASS -- wid {target_wid} absent-before={not in_before} present-after={in_after}")
    else:
        print(f"RESULT: FAIL -- wid {target_wid} absent-before={not in_before} present-after={in_after} "
              f"(expected both True)")

    # --- RESTORE ---
    print()
    restored = False
    if original_space_id is not None:
        print(f"  restoring wid {target_wid} -> space {original_space_id} ...")
        _bridged_move([target_wid], original_space_id)
        time.sleep(0.5)
        onscreen_restore = _on_screen_wids()
        in_restore       = target_wid in onscreen_restore
        restored         = not in_restore
        path_restore     = _REPORTS_DIR / f"04_after_restore_{ts}.png"
        _take_screenshot(path_restore)
        print(f"[RESTORE] wid {target_wid} in on-screen list : {in_restore}  (expected: False)")
        print(f"[RESTORE] screenshot : {path_restore.name}")
        print(f"[RESTORE] window returned to original space  : {restored}")
    else:
        print("WARNING: original_space_id unknown -- window left on active space")

    # --- Summary + on-screen dump ---
    print()
    print("=== Summary ===")
    print(f"  RESULT        : {'PASS' if move_ok else 'FAIL'}")
    print(f"  on-screen     : before={in_before} -> after={in_after}")
    print(f"  screenshots   : {path_before.name}  {path_after.name}")
    print(f"  restored      : {restored}")

    dump_path = _REPORTS_DIR / f"04_onscreen_dump_{ts}.txt"
    dump_path.write_text(
        f"active_space={active_space}  target_wid={target_wid}  orig_space={original_space_id}\n"
        f"before ({len(onscreen_before)} wids): {sorted(onscreen_before)}\n"
        f"after  ({len(onscreen_after)} wids): {sorted(onscreen_after)}\n"
        f"delta  added={sorted(onscreen_after - onscreen_before)}"
        f"  removed={sorted(onscreen_before - onscreen_after)}\n",
        encoding="utf-8",
    )
    print(f"  dump          : {dump_path.name}")


if __name__ == '__main__':
    probe_workflow()
