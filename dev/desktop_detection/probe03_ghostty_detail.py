# INFRASTRUCTURE
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from probe03_bridge import _cf_at, _cf_count, _dict_long, _dict_str
from probe03_windows import _dump_window_fields, _read_bounds

# FUNCTIONS

def _query_window_properties() -> Tuple[Optional[str], Optional[str], List[str]]:
    r_props = subprocess.run(
        ['osascript', '-e', 'tell application "Ghostty" to properties of window 1'],
        capture_output=True, text=True, timeout=6)
    if r_props.returncode == 0:
        raw = r_props.stdout.strip()
        keys = [kv.split(':')[0].strip() for kv in raw.split(',') if ':' in kv]
        return raw, None, keys
    return None, r_props.stderr.strip()[:300], []

def _query_window_bounds() -> Tuple[Optional[str], Optional[str]]:
    r_bounds = subprocess.run(
        ['osascript', '-e', 'tell application "Ghostty" to bounds of window 1'],
        capture_output=True, text=True, timeout=6)
    if r_bounds.returncode == 0:
        return r_bounds.stdout.strip(), None
    return None, r_bounds.stderr.strip()[:200]

def _query_window_position() -> Tuple[Optional[str], Optional[str]]:
    r_pos = subprocess.run(
        ['osascript', '-e', 'tell application "Ghostty" to position of window 1'],
        capture_output=True, text=True, timeout=6)
    if r_pos.returncode == 0:
        return r_pos.stdout.strip(), None
    return None, r_pos.stderr.strip()[:200]

def _determine_geometry_verdict(bounds_result: Optional[str], position_result: Optional[str]) -> str:
    if bounds_result is None and position_result is None:
        return 'AS_NOT_EXPOSED'
    elif bounds_result is not None:
        return 'AS_BOUNDS_AVAILABLE'
    else:
        return 'AS_PARTIAL'

def _collect_ghostty_as_window_properties() -> Dict[str, Any]:
    raw, prop_error, keys = _query_window_properties()
    bounds_result, bounds_error = _query_window_bounds()
    position_result, position_error = _query_window_position()
    return {
        'window_property_query':  'properties of window 1 of application "Ghostty"',
        'window_property_raw':    raw,
        'window_property_error':  prop_error,
        'discovered_keys':        keys,
        'bounds_query_tested':    'bounds of window 1 of application "Ghostty"',
        'bounds_result':          bounds_result,
        'bounds_error':           bounds_error,
        'position_query_tested':  'position of window 1 of application "Ghostty"',
        'position_result':        position_result,
        'position_error':         position_error,
        'geometry_verdict':       _determine_geometry_verdict(bounds_result, position_result),
    }

def _as_bounds_for_window_index(idx: int) -> Tuple[str, Optional[Any], Optional[str]]:
    method = f'bounds of window {idx} of application "Ghostty"'
    script = f'tell application "Ghostty" to bounds of window {idx}'
    r = subprocess.run(['osascript', '-e', script],
                       capture_output=True, text=True, timeout=6)
    if r.returncode == 0:
        return method, r.stdout.strip(), None
    return method, None, r.stderr.strip()[:200]

def _enumerate_ghostty_entries(ghostty_pid: int, raw) -> List[Dict[str, Any]]:
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
    return entries

def _query_as_bounds_pair(entries: List[Dict[str, Any]]):
    as_method_1, as_result_1, as_error_1 = _as_bounds_for_window_index(1)
    as_method_2 = None
    as_result_2 = None
    as_error_2  = None
    if len(entries) > 1:
        as_method_2, as_result_2, as_error_2 = _as_bounds_for_window_index(2)
    return as_method_1, as_result_1, as_error_1, as_method_2, as_result_2, as_error_2

def _attach_as_bounds(entries: List[Dict[str, Any]], as_data: tuple) -> None:
    as_method_1, as_result_1, as_error_1, as_method_2, as_result_2, as_error_2 = as_data
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

        if as_res and entry['cg_window_bounds']:
            try:
                parts = [int(p.strip()) for p in as_res.split(',')]
                cb = entry['cg_window_bounds']
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

def _collect_ghostty_windows_detailed(
    cid: int, ghostty_pid: int, raw
) -> List[Dict[str, Any]]:
    entries = _enumerate_ghostty_entries(ghostty_pid, raw)
    as_data = _query_as_bounds_pair(entries)
    _attach_as_bounds(entries, as_data)
    return entries
