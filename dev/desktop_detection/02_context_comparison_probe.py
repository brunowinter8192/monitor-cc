# INFRASTRUCTURE
import argparse
import ctypes
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from Foundation import NSBundle

_SCRIPT_DIR    = Path(__file__).resolve().parent
_REPORTS_DIR   = _SCRIPT_DIR / '02_reports'
_APP_SUPPORT   = Path('~/Library/Application Support/com.brunowinter.monitor_cc_menubar').expanduser()
_CWD_UUID_FILE = _APP_SUPPORT / 'ghostty_cwd_uuid.json'
_TCC_DB        = Path('~/Library/Application Support/com.apple.TCC/TCC.db').expanduser()

_CGS_SPACE_MASK = 0x7
_CGW_LIST_ALL   = 0
_CGW_NULL_WID   = 0

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
_IMP     = ctypes.cast(_OBJ.objc_msgSend, ctypes.c_void_p).value

_CG.CGSMainConnectionID.argtypes          = []
_CG.CGSMainConnectionID.restype           = ctypes.c_int32
_CG.CGSGetActiveSpace.argtypes            = [ctypes.c_int32]
_CG.CGSGetActiveSpace.restype             = ctypes.c_uint64
_CG.CGSCopyManagedDisplaySpaces.argtypes  = [ctypes.c_int32]
_CG.CGSCopyManagedDisplaySpaces.restype   = ctypes.c_void_p
_CG.CGSCopySpacesForWindows.argtypes      = [ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p]
_CG.CGSCopySpacesForWindows.restype       = ctypes.c_void_p
_CG.CGWindowListCopyWindowInfo.argtypes   = [ctypes.c_uint32, ctypes.c_uint32]
_CG.CGWindowListCopyWindowInfo.restype    = ctypes.c_void_p

# proc_pidinfo flavor 58 = PROC_PIDT_RESPONSIBLE_PID
_LIBPROC               = ctypes.CDLL('/usr/lib/libproc.dylib')
_LIBPROC.proc_pidinfo.restype  = ctypes.c_int
_LIBPROC.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                   ctypes.c_void_p, ctypes.c_int]

# FUNCTIONS

def _sel(s):           return _OBJ.sel_registerName(s.encode())
def _msg1v(o, s, a):   return ctypes.cast(_IMP, _FT_vvv)(o, _sel(s), a)
def _msg1cp(o, s, a):  return ctypes.cast(_IMP, _FT_vvcp)(o, _sel(s), a)
def _msg1l(o, s, a):   return ctypes.cast(_IMP, _FT_vvl)(o, _sel(s), ctypes.c_long(a))
def _msgl(o, s):       return ctypes.cast(_IMP, _FT_lvv)(o, _sel(s))
def _msgp(o, s):       return ctypes.cast(_IMP, _FT_pvv)(o, _sel(s))

def _nsstr(s: str):
    return _msg1cp(_OBJ.objc_getClass(b"NSString"), "stringWithUTF8String:", s.encode())

def _cf_count(a) -> int:   return _msgl(a, "count")
def _cf_at(a, i: int):     return _msg1l(a, "objectAtIndex:", i)
def _dict_val(d, k: str):  return _msg1v(d, "objectForKey:", _nsstr(k))

def _dict_str(d, k: str) -> Optional[str]:
    v = _dict_val(d, k)
    r = _msgp(v, "UTF8String") if v else None
    return r.decode() if r else None

def _dict_long(d, k: str) -> Optional[int]:
    v = _dict_val(d, k)
    return _msgl(v, "intValue") if v else None

def _make_uint_array(vals: List[int]):
    NSA = _OBJ.objc_getClass(b"NSMutableArray")
    NSN = _OBJ.objc_getClass(b"NSNumber")
    arr = ctypes.cast(_IMP, _FT_vv)(NSA, _sel("array"))
    for v in vals:
        n = ctypes.cast(_IMP, _FT_vvl)(NSN, _sel("numberWithUnsignedInt:"), ctypes.c_long(v))
        ctypes.cast(_IMP, _FT_nvv)(arr, _sel("addObject:"), n)
    return arr

# Return TCC-identity diagnostics: codesign, NSBundle.mainBundle().bundleIdentifier(), env, responsible_pid
def _collect_context_diagnostics() -> Dict[str, Any]:
    own_pid    = os.getpid()
    parent_pid = os.getppid()
    rp = subprocess.run(['ps', '-p', str(parent_pid), '-o', 'comm='],
                        capture_output=True, text=True, timeout=3)
    parent_name = rp.stdout.strip() if rp.returncode == 0 else 'unknown'
    env_tcc = {k: os.environ.get(k)
               for k in ['__CFBundleIdentifier', 'XPC_SERVICE_NAME', 'LAUNCHD_SOCKET']}
    cs = subprocess.run(['codesign', '-dvvv', sys.executable],
                        capture_output=True, text=True, timeout=8)
    codesign_raw = (cs.stdout + cs.stderr).strip()
    codesign_id  = next(
        (l.split('=', 1)[1] for l in codesign_raw.splitlines() if l.startswith('Identifier=')),
        'unknown')
    bundle_id = NSBundle.mainBundle().bundleIdentifier()
    pv  = ctypes.c_int32(0)
    resp_pid  = int(pv.value) if _LIBPROC.proc_pidinfo(
        own_pid, 58, 0, ctypes.byref(pv), ctypes.sizeof(pv)) > 0 else None
    resp_name = None
    if resp_pid is not None:
        r2 = subprocess.run(['ps', '-p', str(resp_pid), '-o', 'comm='],
                             capture_output=True, text=True, timeout=3)
        resp_name = r2.stdout.strip() if r2.returncode == 0 else 'unknown'
    return {
        'own_pid': own_pid, 'executable_path': sys.executable,
        'parent_pid': parent_pid, 'parent_name': parent_name,
        'env_tcc_relevant': env_tcc,
        'codesign_identity': codesign_id, 'codesign_raw': codesign_raw,
        'bundle_id_nsbundle': bundle_id,
        'responsible_pid': resp_pid, 'responsible_name': resp_name,
    }

# Best-effort read of TCC.db ScreenCapture grants; returns error info if unreadable
def _collect_tcc_state() -> Dict[str, Any]:
    db_path = str(_TCC_DB)
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT service, client, auth_value FROM access "
            "WHERE service='kTCCServiceScreenCapture'"
        ).fetchall()
        conn.close()
        return {
            'db_path': db_path, 'readable': True,
            'screen_capture_rows': [{'service': r[0], 'client': r[1], 'auth_value': r[2]}
                                     for r in rows],
            'note': f'{len(rows)} rows found',
        }
    except Exception as e:
        return {'db_path': db_path, 'readable': False, 'screen_capture_rows': [],
                'note': f'unreadable: {e}'}

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

# Detection pipeline: cwd_uuid → AppleScript → CGWindowList (name-unique strategy only)
# Returns (sessions_list, skip_reason_or_None)
def _run_detection_pipeline(
    cid: int, ghostty_pid: int, smap: Dict
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if not _CWD_UUID_FILE.exists():
        return [], 'cwd_uuid_map_missing'
    try:
        cwd_uuid = json.loads(_CWD_UUID_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        return [], f'cwd_uuid_read_error:{e}'
    if not cwd_uuid:
        return [], 'cwd_uuid_map_empty'
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
        return [], f'applescript_failed:{ra.stderr.strip()[:200]}'
    uuid_to_win: Dict[str, str] = {}
    win_to_name: Dict[str, str] = {}
    for line in ra.stdout.strip().split('\n'):
        pts = line.strip().split('|||')
        if len(pts) == 3:
            uuid_to_win[pts[2]] = pts[0]
            win_to_name[pts[0]] = pts[1]
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
    rows: List[Dict[str, Any]] = []
    for cwd, uuid in sorted(cwd_uuid.items()):
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
        rows.append({'cwd': cwd, 'session_name': sname, 'uuid': uuid,
                     'cgwindow_id': cgw_id, 'strategy': strategy, 'space_id': space_id,
                     'desktop_no': desktop_no, 'win_name': win_name, 'diagnostic': diag})
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

# Write report JSON to _REPORTS_DIR/<tag>_<YYYYMMDD_HHMMSS>.json
def _write_report(
    tag: str, ctx: Dict, tcc: Dict, det: Dict, raw: List[Dict]
) -> Path:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = _REPORTS_DIR / f'{tag}_{ts}.json'
    path.write_text(
        json.dumps({'tag': tag, 'timestamp': datetime.now().isoformat(),
                    'context_diagnostics': ctx, 'tcc_state': tcc,
                    'detection_result': det, 'raw_windows': raw},
                   indent=2, default=str),
        encoding='utf-8')
    return path

# ORCHESTRATOR

def probe_workflow() -> None:
    ap = argparse.ArgumentParser(description='TCC context comparison probe — Monitor_CC Etappe 2')
    ap.add_argument('--tag', choices=['ccbash', 'launchd', 'bundle'], required=True)
    args = ap.parse_args()
    print(f'[probe02] tag={args.tag} pid={os.getpid()} exe={sys.executable}', flush=True)
    cid          = _CG.CGSMainConnectionID()
    ctx          = _collect_context_diagnostics()
    tcc          = _collect_tcc_state()
    smap, active = _build_space_map(cid)
    ghostty_pid  = _ghostty_pid()
    raw          = _collect_raw_windows(cid)
    det          = _collect_detection_result(cid, raw, ghostty_pid, smap, active)
    path         = _write_report(args.tag, ctx, tcc, det, raw)
    print(f'[probe02] report → {path}', flush=True)


if __name__ == '__main__':
    probe_workflow()
