# INFRASTRUCTURE
import ctypes
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_APP_SUPPORT = Path("~/Library/Application Support/com.brunowinter.monitor_cc_menubar").expanduser()
_CWD_UUID_FILE = _APP_SUPPORT / "ghostty_cwd_uuid.json"

_GHOSTTY_DET_PREFIX = '__DET_'
_CGS_SPACE_MASK = 0x7           # works for all regular spaces
_CGW_LIST_ALL   = 0             # kCGWindowListOptionAll — all windows incl. off-screen spaces
_CGW_NULL_WID   = 0             # kCGNullWindowID

_CG  = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
_OBJ = ctypes.CDLL('/usr/lib/libobjc.A.dylib')

_OBJ.sel_registerName.restype  = ctypes.c_void_p
_OBJ.sel_registerName.argtypes = [ctypes.c_char_p]
_OBJ.objc_getClass.restype     = ctypes.c_void_p
_OBJ.objc_getClass.argtypes    = [ctypes.c_char_p]

# CFUNCTYPE refs at module level — GC-safe (GC'ing these corrupts the IMP pointer table)
_FT_vv   = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_vvv  = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_vvcp = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)
_FT_vvl  = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)
_FT_lvv  = ctypes.CFUNCTYPE(ctypes.c_long,   ctypes.c_void_p, ctypes.c_void_p)
_FT_pvv  = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_nvv  = ctypes.CFUNCTYPE(None,            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

_IMP = ctypes.cast(_OBJ.objc_msgSend, ctypes.c_void_p).value

# CGS / CGWindow function signatures (set once at module load)
_CG.CGSMainConnectionID.argtypes           = []
_CG.CGSMainConnectionID.restype            = ctypes.c_int32
_CG.CGSGetActiveSpace.argtypes             = [ctypes.c_int32]
_CG.CGSGetActiveSpace.restype              = ctypes.c_uint64
_CG.CGSCopyManagedDisplaySpaces.argtypes   = [ctypes.c_int32]
_CG.CGSCopyManagedDisplaySpaces.restype    = ctypes.c_void_p
_CG.CGSCopySpacesForWindows.argtypes       = [ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p]
_CG.CGSCopySpacesForWindows.restype        = ctypes.c_void_p
_CG.CGWindowListCopyWindowInfo.argtypes    = [ctypes.c_uint32, ctypes.c_uint32]
_CG.CGWindowListCopyWindowInfo.restype     = ctypes.c_void_p

# FUNCTIONS

# --- objc bridge helpers ---

def _sel(s: str):                       return _OBJ.sel_registerName(s.encode())
def _msg1v(obj, s: str, a):            return ctypes.cast(_IMP, _FT_vvv)(obj, _sel(s), a)
def _msg1cp(obj, s: str, a: bytes):    return ctypes.cast(_IMP, _FT_vvcp)(obj, _sel(s), a)
def _msg1l(obj, s: str, a: int):       return ctypes.cast(_IMP, _FT_vvl)(obj, _sel(s), ctypes.c_long(a))
def _msgl(obj, s: str) -> int:         return ctypes.cast(_IMP, _FT_lvv)(obj, _sel(s))
def _msgp(obj, s: str):                return ctypes.cast(_IMP, _FT_pvv)(obj, _sel(s))

def _nsstr(s: str):
    cls = _OBJ.objc_getClass(b"NSString")
    return _msg1cp(cls, "stringWithUTF8String:", s.encode())

def _cf_count(arr) -> int:          return _msgl(arr, "count")
def _cf_at(arr, i: int):            return _msg1l(arr, "objectAtIndex:", i)
def _dict_val(d, key: str):         return _msg1v(d, "objectForKey:", _nsstr(key))

def _dict_str(d, key: str) -> Optional[str]:
    v = _dict_val(d, key)
    if not v:
        return None
    r = _msgp(v, "UTF8String")
    return r.decode() if r else None

def _dict_long(d, key: str) -> Optional[int]:
    v = _dict_val(d, key)
    return _msgl(v, "intValue") if v else None

# Build NSMutableArray of unsigned-int values (for CGSCopySpacesForWindows window list)
def _make_uint_array(values: List[int]):
    NSMutableArray = _OBJ.objc_getClass(b"NSMutableArray")
    NSNumber = _OBJ.objc_getClass(b"NSNumber")
    arr = ctypes.cast(_IMP, _FT_vv)(NSMutableArray, _sel("array"))
    for v in values:
        n = ctypes.cast(_IMP, _FT_vvl)(NSNumber, _sel("numberWithUnsignedInt:"), ctypes.c_long(v))
        ctypes.cast(_IMP, _FT_nvv)(arr, _sel("addObject:"), n)
    return arr

# --- data gathering ---

# Return PID int of running Ghostty.app process, or None
def _ghostty_pid() -> Optional[int]:
    r = subprocess.run(['ps', '-A', '-o', 'pid=,command='],
                       capture_output=True, text=True, timeout=2)
    for line in r.stdout.splitlines():
        if 'Ghostty.app/Contents/MacOS' in line:
            pid_str = line.split(None, 1)[0].strip()
            if pid_str.isdigit():
                return int(pid_str)
    return None

# Read ghostty_cwd_uuid.json → {cwd: uuid}; None if file missing (menubar not running)
def _read_cwd_uuid_map() -> Optional[Dict[str, str]]:
    if not _CWD_UUID_FILE.exists():
        return None
    return json.loads(_CWD_UUID_FILE.read_text(encoding='utf-8'))

# Build {cwd: tty} for all CC processes (command contains 'claude', tty != '??')
# One ps call + lsof per CC pid; mirrors proc_cache.py _refresh_cc_proc_cache pattern
def _build_cwd_tty_map() -> Dict[str, str]:
    r = subprocess.run(['ps', '-A', '-o', 'pid=,tty=,command='],
                       capture_output=True, text=True, timeout=3)
    pid_tty: Dict[str, str] = {}
    for line in r.stdout.strip().split('\n'):
        parts = line.split(None, 2)
        if len(parts) == 3 and 'claude' in parts[2].lower() and parts[1] != '??':
            pid_tty[parts[0].strip()] = parts[1].strip()
    result: Dict[str, str] = {}
    for pid, tty in pid_tty.items():
        r2 = subprocess.run(['lsof', '-a', '-d', 'cwd', '-p', pid],
                            capture_output=True, text=True, timeout=2)
        for line in r2.stdout.strip().split('\n'):
            if line.startswith('COMMAND') or not line:
                continue
            fields = line.split(None, 8)
            if len(fields) == 9:
                cwd = fields[8]
                if cwd not in result:
                    result[cwd] = tty
                break
    return result

# AppleScript one-call: returns ({uuid: ghostty_win_id}, {ghostty_win_id: win_name})
# Traverses all windows → tabs → terminal; one round-trip to Ghostty
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
    r = subprocess.run(['osascript', '-e', osa],
                       capture_output=True, text=True, timeout=6)
    if r.returncode != 0:
        raise RuntimeError(f'Ghostty AppleScript failed: {r.stderr.strip()}')
    uuid_to_win: Dict[str, str] = {}
    win_to_name: Dict[str, str] = {}
    for line in r.stdout.strip().split('\n'):
        parts = line.strip().split('|||')
        if len(parts) == 3:
            win_id, win_name, uuid = parts
            uuid_to_win[uuid] = win_id
            win_to_name[win_id] = win_name
    return uuid_to_win, win_to_name

# Return {window_name: [wid, ...]} for all layer-0 named Ghostty-owned CGWindows (all spaces)
def _cgwindow_list_ghostty(ghostty_pid_int: int) -> Dict[str, List[int]]:
    arr = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ALL, _CGW_NULL_WID)
    count = _cf_count(arr)
    by_name: Dict[str, List[int]] = {}
    for i in range(count):
        d = _cf_at(arr, i)
        if _dict_long(d, "kCGWindowOwnerPID") != ghostty_pid_int:
            continue
        if _dict_long(d, "kCGWindowLayer") != 0:
            continue
        wid  = _dict_long(d, "kCGWindowNumber")
        name = _dict_str(d, "kCGWindowName")
        if name is None or wid is None:
            continue
        by_name.setdefault(name, []).append(wid)
    return by_name

# Return (space_map, active_space_id)
# space_map: {space_id: (display_id_abbrev, desktop_no_1based)}
# Defensive: probes multiple key names for display identifier and space id
def _build_space_map(cid: int) -> Tuple[Dict[int, Tuple[str, int]], int]:
    active = _CG.CGSGetActiveSpace(cid)
    dsp_arr = _CG.CGSCopyManagedDisplaySpaces(cid)
    n_displays = _cf_count(dsp_arr)
    space_map: Dict[int, Tuple[str, int]] = {}
    for di in range(n_displays):
        d_dict = _cf_at(dsp_arr, di)
        disp_id = (_dict_str(d_dict, 'Display Identifier') or
                   _dict_str(d_dict, 'DisplayIdentifier') or
                   _dict_str(d_dict, 'Display ID') or 'unknown')
        disp_abbrev = disp_id[:8]
        spaces_val = _dict_val(d_dict, 'Spaces') or _dict_val(d_dict, 'spaces')
        if not spaces_val:
            continue
        n_spaces = _cf_count(spaces_val)
        for si in range(n_spaces):
            sp_dict = _cf_at(spaces_val, si)
            sid = (_dict_long(sp_dict, 'ManagedSpaceID') or
                   _dict_long(sp_dict, 'id') or
                   _dict_long(sp_dict, 'ID'))
            if sid is not None:
                space_map[sid] = (disp_abbrev, si + 1)
    return space_map, active

# Return list of space_ids for a single CGWindowID via CGSCopySpacesForWindows
def _spaces_for_wid(cid: int, wid: int) -> List[int]:
    wid_arr = _make_uint_array([wid])
    result_arr = _CG.CGSCopySpacesForWindows(cid, _CGS_SPACE_MASK, wid_arr)
    if not result_arr:
        return []
    n = _cf_count(result_arr)
    spaces = []
    for i in range(n):
        ns_num = _cf_at(result_arr, i)
        sid = _msgl(ns_num, "intValue") if ns_num else None
        if sid is not None:
            spaces.append(sid)
    return spaces

# OSC-2 fallback: inject unique marker to tty, re-check kCGWindowName after 150ms
# Effective only when the injected terminal is the focused tab in its Ghostty window
def _osc2_inject_match(tty: str, ghostty_pid_int: int,
                        candidates: List[int]) -> Optional[int]:
    marker = f'{_GHOSTTY_DET_PREFIX}{os.urandom(4).hex()}'
    with open(f'/dev/{tty}', 'wb', buffering=0) as fh:
        fh.write(f'\033]2;{marker}\007'.encode())
    time.sleep(0.15)
    by_name = _cgwindow_list_ghostty(ghostty_pid_int)
    matched_wids = by_name.get(marker, [])
    with open(f'/dev/{tty}', 'wb', buffering=0) as fh:   # restore shell-default title
        fh.write(b'\033]2;\007')
    if len(matched_wids) == 1:
        return matched_wids[0]
    overlap = [w for w in matched_wids if w in candidates]
    return overlap[0] if len(overlap) == 1 else None

# Resolve CGWindowID for one Main session via three strategies (in order):
# 1) Unique kCGWindowName match  2) Space-based elimination  3) OSC-2 injection
# Returns (cgwindow_id, strategy_used, diagnostic_note)
def _resolve_cgwindow_id(
    window_name: str,
    cgwindow_by_name: Dict[str, List[int]],
    claimed_space_ids: set,
    cid: int,
    tty: Optional[str],
    ghostty_pid_int: int,
) -> Tuple[Optional[int], str, str]:
    candidates = cgwindow_by_name.get(window_name, [])
    if not candidates:
        return None, 'no-match', f'no CGWindow with kCGWindowName={repr(window_name)}'

    if len(candidates) == 1:
        return candidates[0], 'name-unique', ''

    # Space-based elimination: find candidates not on spaces claimed by other mains
    unclaimed: List[Tuple[int, List[int]]] = []
    for wid in candidates:
        spaces = _spaces_for_wid(cid, wid)
        if spaces and not set(spaces).intersection(claimed_space_ids):
            unclaimed.append((wid, spaces))
    if len(unclaimed) == 1:
        return unclaimed[0][0], 'space-elimination', ''

    if len(unclaimed) > 1:
        diag = (f'{len(candidates)} candidates, {len(unclaimed)} unclaimed-space — '
                f'ambiguous wids={[w for w,_ in unclaimed]}')
    else:
        diag = f'{len(candidates)} candidates, all on claimed spaces'

    # OSC-2 injection: only effective when the CC tab is the focused tab in its window
    if tty:
        wid = _osc2_inject_match(tty, ghostty_pid_int, candidates)
        if wid is not None:
            return wid, 'osc2-injection', ''
        diag += f'; OSC-2 on tty={tty} no match (tab likely not focused)'
    else:
        diag += '; no tty available for OSC-2 fallback'

    return None, 'no-match', diag

# ORCHESTRATOR

def probe_workflow() -> None:
    cwd_uuid = _read_cwd_uuid_map()
    if cwd_uuid is None:
        print("WARNING: ghostty_cwd_uuid.json missing — Menubar not running. "
              "Start Menubar and wait ~3s for map to populate.")
        return
    if not cwd_uuid:
        print("WARNING: ghostty_cwd_uuid.json is empty — no active Main sessions found.")
        return

    ghostty_pid_int = _ghostty_pid()
    if not ghostty_pid_int:
        print("ERROR: Ghostty not running.")
        return

    cwd_tty = _build_cwd_tty_map()
    uuid_to_win, win_to_name = _applescript_uuid_window_map()
    cgwindow_by_name = _cgwindow_list_ghostty(ghostty_pid_int)

    cid = _CG.CGSMainConnectionID()

    space_map, active_space = _build_space_map(cid)

    # Process mains; accumulate claimed space_ids progressively for disambiguation
    claimed_space_ids: set = set()
    rows = []

    for cwd, uuid in sorted(cwd_uuid.items()):
        session_name = os.path.basename(cwd.rstrip('/'))
        tty = cwd_tty.get(cwd)
        ghostty_win_id = uuid_to_win.get(uuid, '')
        win_name = win_to_name.get(ghostty_win_id, '') if ghostty_win_id else ''

        cgwindow_id, strategy, diagnostic = _resolve_cgwindow_id(
            win_name, cgwindow_by_name, claimed_space_ids,
            cid, tty, ghostty_pid_int)

        space_id: Optional[int] = None
        desktop_no: Optional[int] = None
        display_abbrev = ''
        if cgwindow_id is not None:
            spaces = _spaces_for_wid(cid, cgwindow_id)
            if spaces:
                space_id = spaces[0]
                info = space_map.get(space_id)
                if info:
                    display_abbrev, desktop_no = info
                claimed_space_ids.add(space_id)

        rows.append({
            'session_name': session_name,
            'cwd': cwd,
            'uuid': uuid,
            'tty': tty or '',
            'cgwindow_id': cgwindow_id,
            'strategy': strategy,
            'space_id': space_id,
            'display_id': display_abbrev,
            'desktop_no': desktop_no,
            'diagnostic': diagnostic,
            'win_name': win_name,
        })

    H = '{:<20} {:<38} {:<9} {:<8} {:<12} {:<8} {:<9} {:<10}'
    print(H.format('session_name', 'cwd', 'tty', 'uuid[:8]', 'cgwindow_id', 'space_id', 'display', 'desktop_no'))
    print('-' * 120)
    for r in rows:
        cd = ('...' + r['cwd'][-35:]) if len(r['cwd']) > 38 else r['cwd']
        ns = lambda v: str(v) if v is not None else 'None'
        print(H.format(r['session_name'][:20], cd, r['tty'], r['uuid'][:8],
                       ns(r['cgwindow_id']), ns(r['space_id']),
                       r['display_id'], ns(r['desktop_no'])))

    print(f'\n=== Active Space: {active_space}  '
          f'(desktop {space_map.get(active_space, ("?","?"))[1]})')

    print('\n=== All Spaces per Display (ordered by desktop_no):')
    by_display: Dict[str, List[Tuple[int, int]]] = {}
    for sid, (disp, dno) in sorted(space_map.items(), key=lambda x: x[1][1]):
        by_display.setdefault(disp, []).append((sid, dno))
    for disp, spc in by_display.items():
        print(f'  Display {disp}...: space_ids=[{", ".join(str(s) for s,_ in spc)}]'
              f'  desktops=[{", ".join(str(d) for _,d in spc)}]')

    n_matched = sum(1 for r in rows if r['cgwindow_id'] is not None)
    print(f'\n=== Detected Mains: {len(rows)}   With CGWindowID: {n_matched}   Without: {len(rows)-n_matched}')

    misses = [r for r in rows if r['cgwindow_id'] is None]
    if misses:
        print('\n=== Mains without CGWindowID match:')
        for r in misses:
            print(f'  - {r["session_name"]}: win_name={repr(r["win_name"])} diag={r["diagnostic"]}')

    by_strategy: Dict[str, int] = {}
    for r in rows:
        by_strategy[r['strategy']] = by_strategy.get(r['strategy'], 0) + 1
    print('\n=== Strategy breakdown: ' + '  '.join(f'{s}:{c}' for s, c in sorted(by_strategy.items())))


if __name__ == '__main__':
    probe_workflow()
