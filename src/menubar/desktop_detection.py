# INFRASTRUCTURE
import ctypes
import os
import subprocess
import time
from typing import Dict, List, Optional, Set, Tuple

from .menubar_log import log_menubar

_GHOSTTY_DET_PREFIX = '__DET_'
_CGS_SPACE_MASK     = 0x7
_CGW_LIST_ALL       = 0
_CGW_NULL_WID       = 0
_DET_CACHE_TTL      = 10.0

_CG  = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
_OBJ = ctypes.CDLL('/usr/lib/libobjc.A.dylib')

_OBJ.sel_registerName.restype  = ctypes.c_void_p
_OBJ.sel_registerName.argtypes = [ctypes.c_char_p]
_OBJ.objc_getClass.restype     = ctypes.c_void_p
_OBJ.objc_getClass.argtypes    = [ctypes.c_char_p]

_FT_vv   = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_vvv  = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_vvcp = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)
_FT_vvl  = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)
_FT_lvv  = ctypes.CFUNCTYPE(ctypes.c_long,   ctypes.c_void_p, ctypes.c_void_p)
_FT_pvv  = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_nvv  = ctypes.CFUNCTYPE(None,            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

_IMP = ctypes.cast(_OBJ.objc_msgSend, ctypes.c_void_p).value

_CG.CGSMainConnectionID.argtypes           = []
_CG.CGSMainConnectionID.restype            = ctypes.c_int32
_CG.CGSCopyManagedDisplaySpaces.argtypes   = [ctypes.c_int32]
_CG.CGSCopyManagedDisplaySpaces.restype    = ctypes.c_void_p
_CG.CGSCopySpacesForWindows.argtypes       = [ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p]
_CG.CGSCopySpacesForWindows.restype        = ctypes.c_void_p
_CG.CGWindowListCopyWindowInfo.argtypes    = [ctypes.c_uint32, ctypes.c_uint32]
_CG.CGWindowListCopyWindowInfo.restype     = ctypes.c_void_p
_CG.CGSCopyWindowProperty.argtypes        = [ctypes.c_int32, ctypes.c_uint32,
                                              ctypes.c_void_p,
                                              ctypes.POINTER(ctypes.c_void_p)]
_CG.CGSCopyWindowProperty.restype         = ctypes.c_int32

_det_cache: Dict[str, Optional[int]] = {}
_det_cache_ts: float = 0.0
_det_cache_cwds: frozenset = frozenset()
_cgw_title_diag_logged: bool = False
_last_result: Dict[str, Optional[int]] = {}
_cwd_desktop_lkg: Dict[str, dict] = {}

# ORCHESTRATOR

def detect_main_desktop_numbers(
    cwd_uuid_map: Dict[str, str],
    cwd_tty_map:  Dict[str, str],
    now: float,
) -> Dict[str, Optional[int]]:
    global _det_cache, _det_cache_ts, _det_cache_cwds, _cgw_title_diag_logged
    _cgw_title_diag_logged = False
    cwds = frozenset(cwd_uuid_map.keys())
    if cwds == _det_cache_cwds and (now - _det_cache_ts) < _DET_CACHE_TTL:
        return _det_cache
    result, cwd_ctx = _resolve_cwds_to_desktops(cwd_uuid_map, cwd_tty_map)
    _log_transitions(result, cwd_ctx)
    _det_cache = result
    _det_cache_ts = now
    _det_cache_cwds = cwds
    return result

# FUNCTIONS

def _resolve_cwds_to_desktops(
    cwd_uuid_map: Dict[str, str],
    cwd_tty_map:  Dict[str, str],
) -> Tuple[Dict[str, Optional[int]], Dict[str, dict]]:
    cwds = frozenset(cwd_uuid_map.keys())
    result: Dict[str, Optional[int]] = {cwd: None for cwd in cwds}
    for gone in [c for c in _cwd_desktop_lkg if c not in cwds]:
        del _cwd_desktop_lkg[gone]
    cwd_ctx: Dict[str, dict] = {}
    try:
        ghostty_pid_int = _ghostty_pid_int()
        if ghostty_pid_int is not None:
            uuid_to_win, win_to_name = _applescript_uuid_window_map()
            cid              = _CG.CGSMainConnectionID()
            cgwindow_by_name = _cgwindow_list_ghostty(ghostty_pid_int, cid)
            space_map = _build_space_map(cid)
            claimed: Set[int] = set()
            for cwd, uuid in sorted(cwd_uuid_map.items()):
                ghostty_win_id = uuid_to_win.get(uuid, '')
                win_name       = win_to_name.get(ghostty_win_id, '') if ghostty_win_id else ''
                tty            = cwd_tty_map.get(cwd)
                cgwindow_id    = _resolve_cgwindow_id(win_name, cgwindow_by_name, claimed,
                                                      cid, tty, ghostty_pid_int)
                cwd_ctx[cwd]  = {'win': win_name,
                                   'n_cand': len(cgwindow_by_name.get(win_name, []))}
                if cgwindow_id is not None:
                    spaces = _spaces_for_wid(cid, cgwindow_id)
                    if spaces:
                        space_id = spaces[0]
                        info = space_map.get(space_id)
                        if info:
                            _, desktop_no = info
                            result[cwd] = desktop_no
                            claimed.add(space_id)
                            _cwd_desktop_lkg[cwd] = {"space_id": space_id, "desktop_no": desktop_no}
            if cwds and all(v is None for v in result.values()):
                log_menubar('detection', f'all_failed n_mains={len(cwds)} reason=all_no_match')
        else:
            log_menubar('detection', f'all_failed n_mains={len(cwds)} reason=ghostty_not_running')
    except Exception as exc:
        reason = repr(exc)[:80].replace('\n', ' ')
        log_menubar('detection', f'all_failed n_mains={len(cwds)} reason=error:{reason}')
    return result, cwd_ctx

def _log_transitions(result: Dict[str, Optional[int]], cwd_ctx: Dict[str, dict]) -> None:
    global _last_result
    for cwd, new_no in result.items():
        old_no = _last_result.get(cwd)
        if new_no == old_no:
            continue
        label  = os.path.basename(os.path.dirname(cwd)) + '/' + os.path.basename(cwd)
        ctx    = cwd_ctx.get(cwd, {})
        detail = f'win={repr(ctx.get("win", ""))[:40]} n_cand={ctx.get("n_cand", "?")}'
        log_menubar('detection', f'transition {label} {old_no}->{new_no} {detail}')
    _last_result = dict(result)

def _sel(s: str):                      return _OBJ.sel_registerName(s.encode())
def _msg1v(obj, s: str, a):            return ctypes.cast(_IMP, _FT_vvv)(obj, _sel(s), a)
def _msg1cp(obj, s: str, a: bytes):    return ctypes.cast(_IMP, _FT_vvcp)(obj, _sel(s), a)
def _msg1l(obj, s: str, a: int):       return ctypes.cast(_IMP, _FT_vvl)(obj, _sel(s), ctypes.c_long(a))
def _msgl(obj, s: str) -> int:         return ctypes.cast(_IMP, _FT_lvv)(obj, _sel(s))
def _msgp(obj, s: str):                return ctypes.cast(_IMP, _FT_pvv)(obj, _sel(s))

def _nsstr(s: str):
    cls = _OBJ.objc_getClass(b"NSString")
    return _msg1cp(cls, "stringWithUTF8String:", s.encode())

def _normalize_window_title(t: Optional[str]) -> Optional[str]:
    if t is None or len(t) < 2:
        return t
    if t[1] == ' ' and not (t[0].isascii() and (t[0].isalnum() or t[0] in '/-_.')):
        return t[2:]
    return t

def _cf_count(arr) -> int:         return _msgl(arr, "count")
def _cf_at(arr, i: int):           return _msg1l(arr, "objectAtIndex:", i)
def _dict_val(d, key: str):        return _msg1v(d, "objectForKey:", _nsstr(key))

def _dict_str(d, key: str) -> Optional[str]:
    v = _dict_val(d, key)
    if not v:
        return None
    r = _msgp(v, "UTF8String")
    return r.decode() if r else None

def _dict_long(d, key: str) -> Optional[int]:
    v = _dict_val(d, key)
    return _msgl(v, "intValue") if v else None

def _make_uint_array(values: List[int]):
    NSMutableArray = _OBJ.objc_getClass(b"NSMutableArray")
    NSNumber       = _OBJ.objc_getClass(b"NSNumber")
    arr = ctypes.cast(_IMP, _FT_vv)(NSMutableArray, _sel("array"))
    for v in values:
        n = ctypes.cast(_IMP, _FT_vvl)(NSNumber, _sel("numberWithUnsignedInt:"), ctypes.c_long(v))
        ctypes.cast(_IMP, _FT_nvv)(arr, _sel("addObject:"), n)
    return arr

def _ghostty_pid_int() -> Optional[int]:
    r = subprocess.run(['ps', '-A', '-o', 'pid=,command='],
                       capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=2)
    for line in r.stdout.splitlines():
        if 'Ghostty.app/Contents/MacOS' in line:
            pid_str = line.split(None, 1)[0].strip()
            if pid_str.isdigit():
                return int(pid_str)
    return None

def _applescript_uuid_window_map() -> Tuple[Dict[str, str], Dict[str, str]]:
    osa = (
        'tell application "Ghostty"\n'
        '  set out to ""\n'
        '  repeat with w in every window\n'
        '    set wid to (id of w) as text\n'
        '    set wname to (name of w) as text\n'
        '    repeat with t in every tab of w\n'
        '      try\n'
        '        set termid to id of terminal of t\n'
        '        set out to out & wid & "|||" & wname & "|||" & termid & ASCII character 10\n'
        '      end try\n'
        '    end repeat\n'
        '  end repeat\n'
        '  return out\n'
        'end tell'
    )
    r = subprocess.run(['osascript', '-e', osa], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=6)
    if r.returncode != 0:
        raise RuntimeError(f'osascript rc={r.returncode} {r.stderr.strip()!r:.80}')
    uuid_to_win: Dict[str, str] = {}
    win_to_name: Dict[str, str] = {}
    for line in r.stdout.strip().split('\n'):
        parts = line.strip().split('|||')
        if len(parts) == 3:
            win_id, win_name, uuid = parts
            uuid_to_win[uuid] = win_id
            win_to_name[win_id] = _normalize_window_title(win_name)
    return uuid_to_win, win_to_name

def _cgwindow_title(cid: int, wid: int) -> Optional[str]:
    global _cgw_title_diag_logged
    out_ref = ctypes.c_void_p(0)
    key_ns  = _nsstr("kCGSWindowTitle")
    rc = _CG.CGSCopyWindowProperty(cid, wid, key_ns, ctypes.byref(out_ref))
    if rc != 0 or not out_ref.value:
        if not _cgw_title_diag_logged:
            log_menubar('detection', f'cgw_title_first_fail wid={wid} rc={rc} '
                                     f'out_ptr={out_ref.value}')
            _cgw_title_diag_logged = True
        return None
    s = _msgp(out_ref.value, "UTF8String")
    return s.decode() if s else None

def _cgwindow_list_ghostty(ghostty_pid_int: int, cid: int) -> Dict[str, List[int]]:
    arr   = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ALL, _CGW_NULL_WID)
    count = _cf_count(arr)
    by_name: Dict[str, List[int]] = {}
    for i in range(count):
        d = _cf_at(arr, i)
        if _dict_long(d, "kCGWindowOwnerPID") != ghostty_pid_int:
            continue
        if _dict_long(d, "kCGWindowLayer") != 0:
            continue
        wid = _dict_long(d, "kCGWindowNumber")
        if wid is None:
            continue
        name = _normalize_window_title(_cgwindow_title(cid, wid))
        if name is None:
            continue
        by_name.setdefault(name, []).append(wid)
    if not by_name:
        log_menubar('detection', f'cgw_list_empty pid={ghostty_pid_int} iterated={count} '
                                 f'no_names_returned')
    return by_name

def _build_space_map(cid: int) -> Dict[int, Tuple[str, int]]:
    dsp_arr    = _CG.CGSCopyManagedDisplaySpaces(cid)
    n_displays = _cf_count(dsp_arr)
    space_map: Dict[int, Tuple[str, int]] = {}
    for di in range(n_displays):
        d_dict     = _cf_at(dsp_arr, di)
        disp_id    = (_dict_str(d_dict, 'Display Identifier') or
                      _dict_str(d_dict, 'DisplayIdentifier') or 'unknown')
        abbrev     = disp_id[:8]
        spaces_val = _dict_val(d_dict, 'Spaces') or _dict_val(d_dict, 'spaces')
        if not spaces_val:
            continue
        for si in range(_cf_count(spaces_val)):
            sp_dict = _cf_at(spaces_val, si)
            sid = (_dict_long(sp_dict, 'ManagedSpaceID') or
                   _dict_long(sp_dict, 'id') or
                   _dict_long(sp_dict, 'ID'))
            if sid is not None:
                space_map[sid] = (abbrev, si + 1)
    return space_map

def _spaces_for_wid(cid: int, wid: int) -> List[int]:
    wid_arr    = _make_uint_array([wid])
    result_arr = _CG.CGSCopySpacesForWindows(cid, _CGS_SPACE_MASK, wid_arr)
    if not result_arr:
        return []
    spaces = []
    for i in range(_cf_count(result_arr)):
        ns_num = _cf_at(result_arr, i)
        sid    = _msgl(ns_num, "intValue") if ns_num else None
        if sid is not None:
            spaces.append(sid)
    return spaces

def _osc2_inject_match(tty: str, ghostty_pid_int: int, candidates: List[int], cid: int) -> Optional[int]:
    marker = f'{_GHOSTTY_DET_PREFIX}{os.urandom(4).hex()}'
    try:
        with open(f'/dev/{tty}', 'wb', buffering=0) as fh:
            fh.write(f'\033]2;{marker}\007'.encode())
    except OSError as e:
        log_menubar('detection', f'osc2_write_failed tty={tty} err={repr(e)[:80]}')
        return None
    time.sleep(0.5)
    by_name = _cgwindow_list_ghostty(ghostty_pid_int, cid)
    matched = by_name.get(marker, [])
    try:
        with open(f'/dev/{tty}', 'wb', buffering=0) as fh:
            fh.write(b'\033]2;\007')
    except OSError as e:
        log_menubar('detection', f'osc2_restore_failed tty={tty} err={repr(e)[:80]}')
    if not matched:
        log_menubar('detection', f'osc2_no_marker tty={tty} (write may have been ignored, or tab not focused)')
        return None
    if len(matched) == 1:
        log_menubar('detection', f'osc2_match tty={tty} wid={matched[0]}')
        return matched[0]
    overlap = [w for w in matched if w in candidates]
    if len(overlap) == 1:
        log_menubar('detection', f'osc2_overlap tty={tty} wid={overlap[0]}')
        return overlap[0]
    log_menubar('detection', f'osc2_ambiguous tty={tty} matched={matched} overlap={overlap}')
    return None

def _resolve_cgwindow_id(
    window_name: str,
    cgwindow_by_name: Dict[str, List[int]],
    claimed_space_ids: Set[int],
    cid: int,
    tty: Optional[str],
    ghostty_pid_int: int,
) -> Optional[int]:
    candidates = cgwindow_by_name.get(window_name, [])
    if not candidates:
        log_menubar('detection', f'resolve_no_name_match window_name={repr(window_name)[:60]}')
        return None
    if len(candidates) == 1:
        return candidates[0]
    unclaimed: List[int] = []
    for wid in candidates:
        spaces = _spaces_for_wid(cid, wid)
        if spaces and not set(spaces).intersection(claimed_space_ids):
            unclaimed.append(wid)
    if len(unclaimed) == 1:
        return unclaimed[0]
    if tty:
        return _osc2_inject_match(tty, ghostty_pid_int, candidates, cid)
    log_menubar('detection', f'resolve_no_tty candidates={len(candidates)} unclaimed={len(unclaimed)}')
    return None
