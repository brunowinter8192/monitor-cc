# INFRASTRUCTURE
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from probe02_bridge import _CG, _cf_at, _cf_count, _dict_long, _dict_str, _dict_val, _make_uint_array, _msgl

_APP_SUPPORT   = Path('~/Library/Application Support/com.brunowinter.monitor_cc_menubar').expanduser()
_CWD_UUID_FILE = _APP_SUPPORT / 'ghostty_cwd_uuid.json'

_CGS_SPACE_MASK = 0x7
_CGW_LIST_ALL   = 0
_CGW_NULL_WID   = 0

# FUNCTIONS

# Return PID of running Ghostty.app, or None
def _ghostty_pid() -> Optional[int]:
    r = subprocess.run(['ps', '-A', '-o', 'pid=,command='],
                       capture_output=True, text=True, timeout=3)
    for line in r.stdout.splitlines():
        if 'Ghostty.app/Contents/MacOS' in line:
            p = line.split(None, 1)[0].strip()
            if p.isdigit():
                return int(p)
    return None

# Return space_ids for a single CGWindowID
def _spaces_for_wid(cid: int, wid: int) -> List[int]:
    arr = _CG.CGSCopySpacesForWindows(cid, _CGS_SPACE_MASK, _make_uint_array([wid]))
    if not arr:
        return []
    result = []
    for i in range(_cf_count(arr)):
        ns = _cf_at(arr, i)
        if ns:
            result.append(_msgl(ns, "intValue"))
    return result

# Return (space_map {sid: (disp_abbrev, desktop_no)}, active_space_id)
def _build_space_map(cid: int) -> Tuple[Dict[int, Tuple[str, int]], int]:
    active = _CG.CGSGetActiveSpace(cid)
    dsp    = _CG.CGSCopyManagedDisplaySpaces(cid)
    smap: Dict[int, Tuple[str, int]] = {}
    for di in range(_cf_count(dsp)):
        dd  = _cf_at(dsp, di)
        did = (_dict_str(dd, 'Display Identifier') or _dict_str(dd, 'DisplayIdentifier') or 'unknown')
        sv  = _dict_val(dd, 'Spaces') or _dict_val(dd, 'spaces')
        if not sv:
            continue
        for si in range(_cf_count(sv)):
            sd  = _cf_at(sv, si)
            sid = (_dict_long(sd, 'ManagedSpaceID') or _dict_long(sd, 'id') or _dict_long(sd, 'ID'))
            if sid is not None:
                smap[sid] = (did[:8], si + 1)
    return smap, int(active)

# Return all windows; space_ids only for layer=0 (key TCC comparison signal)
def _collect_raw_windows(cid: int) -> List[Dict[str, Any]]:
    raw = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ALL, _CGW_NULL_WID)
    result = []
    for i in range(_cf_count(raw)):
        d     = _cf_at(raw, i)
        layer = _dict_long(d, "kCGWindowLayer")
        wid   = _dict_long(d, "kCGWindowNumber")
        result.append({
            'owner_name':  _dict_str(d, "kCGWindowOwnerName"),
            'owner_pid':   _dict_long(d, "kCGWindowOwnerPID"),
            'window_name': _dict_str(d, "kCGWindowName"),
            'window_id':   wid,
            'layer':       layer,
            'space_ids':   _spaces_for_wid(cid, wid) if layer == 0 and wid else None,
        })
    return result

# Read cwd_uuid map; returns (map, None) or (None, skip_reason)
def _load_cwd_uuid_map() -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    if not _CWD_UUID_FILE.exists():
        return None, 'cwd_uuid_map_missing'
    try:
        cwd_uuid = json.loads(_CWD_UUID_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        return None, f'cwd_uuid_read_error:{e}'
    if not cwd_uuid:
        return None, 'cwd_uuid_map_empty'
    return cwd_uuid, None

# AppleScript one-call: returns ({ghostty_win_id: uuid}, {ghostty_win_id: win_name})
def _applescript_window_map() -> Tuple[Dict[str, str], Dict[str, str]]:
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
    ra = subprocess.run(['osascript', '-e', osa],
                        capture_output=True, text=True, timeout=6)
    if ra.returncode != 0:
        raise RuntimeError(f'applescript_failed:{ra.stderr.strip()[:200]}')
    uuid_to_win: Dict[str, str] = {}
    win_to_name: Dict[str, str] = {}
    for line in ra.stdout.strip().split('\n'):
        pts = line.strip().split('|||')
        if len(pts) == 3:
            uuid_to_win[pts[2]] = pts[0]
            win_to_name[pts[0]] = pts[1]
    return uuid_to_win, win_to_name

# Return {window_name: [wid, ...]} for all layer-0 named Ghostty CGWindows
def _cgwindow_name_map(ghostty_pid: int) -> Dict[str, List[int]]:
    cgw = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ALL, _CGW_NULL_WID)
    by_name: Dict[str, List[int]] = {}
    for i in range(_cf_count(cgw)):
        d = _cf_at(cgw, i)
        if _dict_long(d, "kCGWindowOwnerPID") != ghostty_pid or \
           _dict_long(d, "kCGWindowLayer") != 0:
            continue
        wid = _dict_long(d, "kCGWindowNumber")
        nm  = _dict_str(d, "kCGWindowName")
        if nm and wid:
            by_name.setdefault(nm, []).append(wid)
    return by_name

# Build one pipeline row (name-unique strategy only)
def _build_pipeline_row(
    cwd: str, uuid: str, uuid_to_win: Dict[str, str], win_to_name: Dict[str, str],
    by_name: Dict[str, List[int]], cid: int, smap: Dict,
) -> Dict[str, Any]:
    sname    = os.path.basename(cwd.rstrip('/'))
    g_win    = uuid_to_win.get(uuid, '')
    win_name = win_to_name.get(g_win, '') if g_win else ''
    cands    = by_name.get(win_name, [])
    cgw_id   = cands[0] if len(cands) == 1 else None
    strategy = 'name-unique' if cgw_id else 'no-match'
    diag     = ('' if cgw_id else
                f'no CGWindow name={repr(win_name)}' if not cands
                else f'{len(cands)} candidates (name-unique failed; space-elim/OSC-2 not run in probe)')
    space_id = desktop_no = None
    if cgw_id is not None:
        sids = _spaces_for_wid(cid, cgw_id)
        if sids:
            space_id = sids[0]
            info = smap.get(space_id)
            if info:
                desktop_no = info[1]
    return {'cwd': cwd, 'session_name': sname, 'uuid': uuid,
            'cgwindow_id': cgw_id, 'strategy': strategy, 'space_id': space_id,
            'desktop_no': desktop_no, 'win_name': win_name, 'diagnostic': diag}

# Detection pipeline: cwd_uuid → AppleScript → CGWindowList (name-unique strategy only)
# Returns (sessions_list, skip_reason_or_None)
def _run_detection_pipeline(
    cid: int, ghostty_pid: int, smap: Dict
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    cwd_uuid, skip = _load_cwd_uuid_map()
    if skip:
        return [], skip
    try:
        uuid_to_win, win_to_name = _applescript_window_map()
    except RuntimeError as e:
        return [], str(e)
    by_name = _cgwindow_name_map(ghostty_pid)
    rows = [
        _build_pipeline_row(cwd, uuid, uuid_to_win, win_to_name, by_name, cid, smap)
        for cwd, uuid in sorted(cwd_uuid.items())
    ]
    return rows, None

# Collect detection_result section: window stats + pipeline
def _collect_detection_result(
    cid: int, raw_windows: List[Dict[str, Any]],
    ghostty_pid: Optional[int], smap: Dict, active_space: int
) -> Dict[str, Any]:
    owner_ctr = Counter(w['owner_name'] or '__null__' for w in raw_windows)
    g_wins    = [w for w in raw_windows
                 if w['owner_pid'] == ghostty_pid and w['layer'] == 0] if ghostty_pid else []
    sessions  = []
    skip      = None
    if ghostty_pid:
        try:
            sessions, skip = _run_detection_pipeline(cid, ghostty_pid, smap)
        except Exception as e:
            skip  = f'pipeline_exception:{type(e).__name__}:{e}'
            sessions = []
    else:
        skip = 'ghostty_not_running'
    return {
        'cid': cid,
        'total_window_count': len(raw_windows),
        'windows_by_owner': dict(owner_ctr.most_common()),
        'ghostty_pid': ghostty_pid,
        'ghostty_windows_found': len(g_wins),
        'space_map': {str(sid): {'display_abbrev': d, 'desktop_no': n}
                      for sid, (d, n) in smap.items()},
        'active_space_id': int(active_space),
        'mains_detected': not bool(skip),
        'detection_skip_reason': skip,
        'main_sessions': sessions,
    }
