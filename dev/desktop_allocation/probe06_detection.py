# INFRASTRUCTURE
import os
import sys
from typing import Dict, List, Optional, Set, Tuple

from probe06_bridge import _AS, _CG, _cf_at, _cf_count, _dict_long, _dict_str, _dict_val, _make_uint_array, _msgl

_CGS_SPACE_MASK    = 0x7
_CGW_LIST_ALL      = 0
_CGW_LIST_ONSCREEN = 1
_CGW_NULL_WID      = 0

# FUNCTIONS

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

def _wids(onscreen: bool = False) -> Set[int]:
    opt = _CGW_LIST_ONSCREEN if onscreen else _CGW_LIST_ALL
    arr = _CG.CGWindowListCopyWindowInfo(opt, _CGW_NULL_WID)
    out: Set[int] = set()
    for i in range(_cf_count(arr)):
        wid = _dict_long(_cf_at(arr, i), "kCGWindowNumber")
        if wid is not None:
            out.add(wid)
    return out

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

def _find_nonempty_nonactive_space(
    cid: int, active_space_id: int, space_map: Dict[int, Tuple[str, int]]
) -> Optional[int]:
    off_screen = _wids() - _wids(True)
    for wid in off_screen:
        sids = _spaces_for_wid(cid, wid)
        if sids and sids[0] != active_space_id and sids[0] in space_map:
            return sids[0]
    return None
