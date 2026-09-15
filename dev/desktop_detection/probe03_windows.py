# INFRASTRUCTURE
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from probe03_bridge import _CG, _cf_at, _cf_count, _dict_all_keys, _dict_long, _dict_str, _dict_val, _make_uint_array, _msgl, _cf_describe

_CGS_SPACE_MASK = 0x7
_CGW_LIST_ALL   = 0
_CGW_NULL_WID   = 0

# FUNCTIONS

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
