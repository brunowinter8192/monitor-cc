# INFRASTRUCTURE
import argparse
import ctypes
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from Foundation import NSBundle

_SCRIPT_DIR  = Path(__file__).resolve().parent
_REPORTS_DIR = _SCRIPT_DIR / '03_reports'
_TCC_DB      = Path('~/Library/Application Support/com.apple.TCC/TCC.db').expanduser()

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

_CG.CGSMainConnectionID.argtypes         = []
_CG.CGSMainConnectionID.restype          = ctypes.c_int32
_CG.CGSCopySpacesForWindows.argtypes     = [ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p]
_CG.CGSCopySpacesForWindows.restype      = ctypes.c_void_p
_CG.CGWindowListCopyWindowInfo.argtypes  = [ctypes.c_uint32, ctypes.c_uint32]
_CG.CGWindowListCopyWindowInfo.restype   = ctypes.c_void_p

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

# Return human-readable string description of any NSObject via [obj description] → UTF8String
def _cf_describe(v) -> Optional[str]:
    if not v:
        return None
    ns = ctypes.cast(_IMP, _FT_vv)(v, _sel("description"))
    if not ns:
        return None
    r = _msgp(ns, "UTF8String")
    return r.decode('utf-8', errors='replace') if r else None

# Return all string keys from a CF/NS dictionary via [d allKeys]
def _dict_all_keys(d) -> List[str]:
    arr = ctypes.cast(_IMP, _FT_vv)(d, _sel("allKeys"))
    if not arr:
        return []
    result = []
    for i in range(_cf_count(arr)):
        k = _cf_at(arr, i)
        r = _msgp(k, "UTF8String")
        if r:
            result.append(r.decode('utf-8', errors='replace'))
    return result

# Dump all key/value pairs from a CGWindow dict; kCGWindowBounds handled as nested dict
def _dump_window_fields(d) -> Dict[str, Any]:
    keys = _dict_all_keys(d)
    out: Dict[str, Any] = {}
    for k in keys:
        v = _dict_val(d, k)
        if not v:
            out[k] = None
            continue
        if k == 'kCGWindowBounds':
            out[k] = {kk: _dict_long(v, kk) for kk in ('X', 'Y', 'Width', 'Height')}
        else:
            s = _cf_describe(v)
            if s is None:
                out[k] = None
            else:
                try:
                    out[k] = int(s)
                except ValueError:
                    try:
                        out[k] = float(s)
                    except ValueError:
                        out[k] = s
    return out

# Return kCGWindowBounds sub-dict as {X,Y,Width,Height} or None
def _read_bounds(d) -> Optional[Dict[str, Optional[int]]]:
    bv = _dict_val(d, 'kCGWindowBounds')
    if not bv:
        return None
    result = {kk: _dict_long(bv, kk) for kk in ('X', 'Y', 'Width', 'Height')}
    return result if any(v is not None for v in result.values()) else None

# Build field_availability_summary across all windows
def _build_availability_summary(
    all_fields: List[Dict[str, Any]],
    all_keys: List[str],
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for k in all_keys:
        populated = 0
        null_count = 0
        sample = None
        for fields in all_fields:
            v = fields.get(k)
            if v is None:
                null_count += 1
            else:
                populated += 1
                if sample is None:
                    sample = v
        summary[k] = {
            'populated_count': populated,
            'null_count':      null_count,
            'sample_value':    sample,
        }
    return summary

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

# Collect TCC-identity diagnostics: codesign, NSBundle.mainBundle(), env, responsible_pid
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
    pv       = ctypes.c_int32(0)
    resp_pid = int(pv.value) if _LIBPROC.proc_pidinfo(
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

# Best-effort read of TCC.db ScreenCapture grants
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

# One-shot AS query: properties of window 1 — discover what Ghostty exposes at window level
def _collect_ghostty_as_window_properties() -> Dict[str, Any]:
    result: Dict[str, Any] = {
        'window_property_query':  'properties of window 1 of application "Ghostty"',
        'window_property_raw':    None,
        'window_property_error':  None,
        'discovered_keys':        [],
        'bounds_query_tested':    'bounds of window 1 of application "Ghostty"',
        'bounds_result':          None,
        'bounds_error':           None,
        'position_query_tested':  'position of window 1 of application "Ghostty"',
        'position_result':        None,
        'position_error':         None,
        'geometry_verdict':       'UNKNOWN',
    }
    # Property discovery
    r_props = subprocess.run(
        ['osascript', '-e', 'tell application "Ghostty" to properties of window 1'],
        capture_output=True, text=True, timeout=6)
    if r_props.returncode == 0:
        raw = r_props.stdout.strip()
        result['window_property_raw'] = raw
        result['discovered_keys'] = [kv.split(':')[0].strip() for kv in raw.split(',') if ':' in kv]
    else:
        result['window_property_error'] = r_props.stderr.strip()[:300]

    # Bounds query
    r_bounds = subprocess.run(
        ['osascript', '-e', 'tell application "Ghostty" to bounds of window 1'],
        capture_output=True, text=True, timeout=6)
    if r_bounds.returncode == 0:
        result['bounds_result'] = r_bounds.stdout.strip()
    else:
        result['bounds_error'] = r_bounds.stderr.strip()[:200]

    # Position query
    r_pos = subprocess.run(
        ['osascript', '-e', 'tell application "Ghostty" to position of window 1'],
        capture_output=True, text=True, timeout=6)
    if r_pos.returncode == 0:
        result['position_result'] = r_pos.stdout.strip()
    else:
        result['position_error'] = r_pos.stderr.strip()[:200]

    # Verdict
    if result['bounds_result'] is None and result['position_result'] is None:
        result['geometry_verdict'] = 'AS_NOT_EXPOSED'
    elif result['bounds_result'] is not None:
        result['geometry_verdict'] = 'AS_BOUNDS_AVAILABLE'
    else:
        result['geometry_verdict'] = 'AS_PARTIAL'

    return result

# Attempt AS bounds for a specific window index; returns (method_str, result_or_None, error_or_None)
def _as_bounds_for_window_index(idx: int) -> Tuple[str, Optional[Any], Optional[str]]:
    method = f'bounds of window {idx} of application "Ghostty"'
    script = f'tell application "Ghostty" to bounds of window {idx}'
    r = subprocess.run(['osascript', '-e', script],
                       capture_output=True, text=True, timeout=6)
    if r.returncode == 0:
        return method, r.stdout.strip(), None
    return method, None, r.stderr.strip()[:200]

# Collect per-Ghostty-window detail: CG fields + AS bounds attempt
def _collect_ghostty_windows_detailed(
    cid: int, ghostty_pid: int, raw: ctypes.c_void_p
) -> List[Dict[str, Any]]:
    # Enumerate Ghostty windows in order (layer=0 only)
    entries = []
    for i in range(_cf_count(raw)):
        d   = _cf_at(raw, i)
        pid = _dict_long(d, 'kCGWindowOwnerPID')
        if pid != ghostty_pid:
            continue
        layer = _dict_long(d, 'kCGWindowLayer')
        if layer != 0:
            continue
        wid    = _dict_long(d, 'kCGWindowNumber')
        fields = _dump_window_fields(d)
        bounds = _read_bounds(d)
        entries.append({
            'window_id':          wid,
            'owner_pid':          pid,
            'cg_window_name':     _dict_str(d, 'kCGWindowName'),
            'cg_window_bounds':   bounds,
            'cg_window_all_fields': fields,
        })

    # AS bounds: attempt once for window index 1 (covers all — Ghostty has one CGWindow per window)
    # and once for window index 2 (second window if present), then reuse the single error result
    as_method_1, as_result_1, as_error_1 = _as_bounds_for_window_index(1)
    as_method_2 = None
    as_result_2 = None
    as_error_2  = None
    if len(entries) > 1:
        as_method_2, as_result_2, as_error_2 = _as_bounds_for_window_index(2)

    # Attach AS bounds info to each entry
    for idx, entry in enumerate(entries):
        if idx == 0:
            method, as_res, as_err = as_method_1, as_result_1, as_error_1
        elif idx == 1:
            method, as_res, as_err = as_method_2, as_result_2, as_error_2
        else:
            method = f'bounds of window {idx + 1} of application "Ghostty"'
            as_res, as_err = None, 'skipped (only first two windows queried)'

        entry['as_bounds_method'] = method
        entry['as_bounds_result'] = as_res
        entry['as_bounds_error']  = as_err

        # Rect comparison (N/A when AS side returns no bounds)
        if as_res and entry['cg_window_bounds']:
            # Parse AS result like "0, 25, 1512, 1220" → [x1,y1,x2,y2]
            try:
                parts = [int(p.strip()) for p in as_res.split(',')]
                cb = entry['cg_window_bounds']
                # AS: x1,y1,x2,y2 → CG: X,Y,Width,Height
                as_x1, as_y1 = parts[0], parts[1]
                as_w = parts[2] - parts[0] if len(parts) == 4 else None
                as_h = parts[3] - parts[1] if len(parts) == 4 else None
                diff = [
                    as_x1 - (cb['X'] or 0),
                    as_y1 - (cb['Y'] or 0),
                    (as_w or 0) - (cb['Width'] or 0),
                    (as_h or 0) - (cb['Height'] or 0),
                ]
                entry['rect_match'] = all(abs(d) <= 2 for d in diff)
                entry['rect_diff']   = diff
            except Exception:
                entry['rect_match'] = None
                entry['rect_diff']  = None
        else:
            entry['rect_match'] = None
            entry['rect_diff']  = None

    return entries

# Full CGWindow dump: all windows, all keys, build field_availability_summary
def _collect_full_cgwindow_data(
    cid: int, ghostty_pid: Optional[int]
) -> Tuple[List[str], Dict[str, Any], List[Dict]]:
    raw = _CG.CGWindowListCopyWindowInfo(_CGW_LIST_ALL, _CGW_NULL_WID)
    all_field_dumps: List[Dict[str, Any]] = []
    all_keys_seen: List[str] = []
    keys_set: set = set()
    ghostty_raw_ptr = raw  # reuse same list for Ghostty-detail pass

    for i in range(_cf_count(raw)):
        d = _cf_at(raw, i)
        fields = _dump_window_fields(d)
        all_field_dumps.append(fields)
        for k in fields:
            if k not in keys_set:
                keys_set.add(k)
                all_keys_seen.append(k)

    summary = _build_availability_summary(all_field_dumps, all_keys_seen)
    return all_keys_seen, summary, ghostty_raw_ptr

# Write report JSON to _REPORTS_DIR/<tag>_<YYYYMMDD_HHMMSS>.json
def _write_report(payload: Dict) -> Path:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = _REPORTS_DIR / f'{payload["tag"]}_{ts}.json'
    path.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
    return path

# ORCHESTRATOR

def probe_workflow() -> None:
    ap = argparse.ArgumentParser(description='CGWindow field availability probe — Monitor_CC probe03')
    ap.add_argument('--tag', choices=['ccbash', 'launchd', 'bundle'], required=True)
    args = ap.parse_args()
    print(f'[probe03] tag={args.tag} pid={os.getpid()} exe={sys.executable}', flush=True)

    cid         = _CG.CGSMainConnectionID()
    ctx         = _collect_context_diagnostics()
    tcc         = _collect_tcc_state()
    ghostty_pid = _ghostty_pid()

    all_keys, field_summary, raw_ptr = _collect_full_cgwindow_data(cid, ghostty_pid)

    ghostty_detail: List[Dict] = []
    if ghostty_pid:
        ghostty_detail = _collect_ghostty_windows_detailed(cid, ghostty_pid, raw_ptr)

    as_props = _collect_ghostty_as_window_properties()

    payload = {
        'tag':                       args.tag,
        'timestamp':                 datetime.now().isoformat(),
        'context_diagnostics':       ctx,
        'tcc_state':                 tcc,
        'ghostty_pid':               ghostty_pid,
        'all_field_keys_observed':   all_keys,
        'field_availability_summary': field_summary,
        'ghostty_windows_detailed':  ghostty_detail,
        'ghostty_as_window_properties': as_props,
    }

    path = _write_report(payload)
    print(f'[probe03] report → {path}', flush=True)


if __name__ == '__main__':
    probe_workflow()
