# INFRASTRUCTURE
from typing import Dict, List, Optional, Set, Tuple

from probe05_bridge import _CG, _cf_at, _cf_count, _dict_long, _dict_str, _dict_val, _make_uint_array, _msgl

_CGS_SPACE_MASK    = 0x7
_CGW_LIST_ALL      = 0   # kCGWindowListOptionAll — all spaces
_CGW_LIST_ONSCREEN = 1   # kCGWindowListOptionOnScreenOnly — active space only
_CGW_NULL_WID      = 0

# Window type constants
_WIN_TMUX = "ghostty_tmux"
_WIN_OSC2 = "ghostty_osc2"
_WIN_COT  = "coteditor"

_OWNER = {_WIN_TMUX: "Ghostty", _WIN_OSC2: "Ghostty", _WIN_COT: "CotEditor"}

# require_name=True excludes unnamed intermediate windows; CotEditor document windows have names
_REQUIRE_NAME = {_WIN_TMUX: True, _WIN_OSC2: True, _WIN_COT: True}

_TOKEN_PREFIX = {_WIN_TMUX: "p05t", _WIN_OSC2: "p05g", _WIN_COT: "p05c"}

# FUNCTIONS

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
