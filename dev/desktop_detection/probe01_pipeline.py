# INFRASTRUCTURE
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from probe01_bridge import _CG, _cf_at, _cf_count, _dict_long, _dict_str, _dict_val, _make_uint_array, _msgl

_APP_SUPPORT = Path("~/Library/Application Support/com.brunowinter.monitor_cc_menubar").expanduser()
_CWD_UUID_FILE = _APP_SUPPORT / "ghostty_cwd_uuid.json"

_GHOSTTY_DET_PREFIX = '__DET_'
_CGS_SPACE_MASK = 0x7
_CGW_LIST_ALL   = 0
_CGW_NULL_WID   = 0

# FUNCTIONS


def _ghostty_pid() -> Optional[int]:
    r = subprocess.run(['ps', '-A', '-o', 'pid=,command='],
                       capture_output=True, text=True, timeout=2)
    for line in r.stdout.splitlines():
        if 'Ghostty.app/Contents/MacOS' in line:
            pid_str = line.split(None, 1)[0].strip()
            if pid_str.isdigit():
                return int(pid_str)
    return None

def _read_cwd_uuid_map() -> Optional[Dict[str, str]]:
    if not _CWD_UUID_FILE.exists():
        return None
    return json.loads(_CWD_UUID_FILE.read_text(encoding='utf-8'))

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

def _osc2_inject_match(tty: str, ghostty_pid_int: int,
                        candidates: List[int]) -> Optional[int]:
    marker = f'{_GHOSTTY_DET_PREFIX}{os.urandom(4).hex()}'
    with open(f'/dev/{tty}', 'wb', buffering=0) as fh:
        fh.write(f'\033]2;{marker}\007'.encode())
    time.sleep(0.15)
    by_name = _cgwindow_list_ghostty(ghostty_pid_int)
    matched_wids = by_name.get(marker, [])
    with open(f'/dev/{tty}', 'wb', buffering=0) as fh:
        fh.write(b'\033]2;\007')
    if len(matched_wids) == 1:
        return matched_wids[0]
    overlap = [w for w in matched_wids if w in candidates]
    return overlap[0] if len(overlap) == 1 else None

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

    if tty:
        wid = _osc2_inject_match(tty, ghostty_pid_int, candidates)
        if wid is not None:
            return wid, 'osc2-injection', ''
        diag += f'; OSC-2 on tty={tty} no match (tab likely not focused)'
    else:
        diag += '; no tty available for OSC-2 fallback'

    return None, 'no-match', diag

def _build_session_row(
    cwd: str, uuid: str, cwd_tty: Dict[str, str],
    uuid_to_win: Dict[str, str], win_to_name: Dict[str, str],
    cgwindow_by_name: Dict[str, List[int]], claimed_space_ids: set,
    cid: int, ghostty_pid_int: int, space_map: Dict[int, Tuple[str, int]],
) -> dict:
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

    return {
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
    }

def _collect_session_rows(
    cid: int, cwd_uuid: Dict[str, str], ghostty_pid_int: int,
) -> Tuple[List[dict], Dict[int, Tuple[str, int]], int]:
    cwd_tty = _build_cwd_tty_map()
    uuid_to_win, win_to_name = _applescript_uuid_window_map()
    cgwindow_by_name = _cgwindow_list_ghostty(ghostty_pid_int)

    space_map, active_space = _build_space_map(cid)

    claimed_space_ids: set = set()
    rows = []
    for cwd, uuid in sorted(cwd_uuid.items()):
        rows.append(_build_session_row(
            cwd, uuid, cwd_tty, uuid_to_win, win_to_name,
            cgwindow_by_name, claimed_space_ids, cid, ghostty_pid_int, space_map))

    return rows, space_map, active_space
