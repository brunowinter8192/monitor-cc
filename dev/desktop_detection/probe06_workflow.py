# INFRASTRUCTURE
import ctypes
import secrets
import time
from pathlib import Path
from typing import Dict, List, Optional

from probe06_bridge import _CG, _SL, _make_uint64_array, _make_uint_array
from probe06_coteditor import _close_coteditor_doc, _detect_coteditor_doc, _ensure_coteditor_running, _open_coteditor_doc
from probe06_detection import _build_space_map, _check_permissions, _find_nonempty_nonactive_space
from probe06_primitives import _REPORTS_DIR, _run_primitive_trial, _setup, _try_sym

_COMPAT_ID = 42   # arbitrary int32 for SLSSpaceSetCompatID / SLSSetWindowListWorkspace

# FUNCTIONS

def _setup_probe():
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cid = _CG.CGSMainConnectionID()

    ax, sc = _check_permissions()

    space_map, active_space = _build_space_map(cid)
    active_desktop = space_map.get(active_space, ('?', '?'))[1]

    print("=== Move Sweep Probe 06 ===")
    print(f"  active_space={active_space}  desktop={active_desktop}")
    print(f"  spaces: {sorted(space_map.keys())}")
    print()

    return cid, ax, sc, space_map, active_space

def _validate_preconditions(cid: int, space_map: Dict, active_space: int) -> Optional[int]:
    if len(space_map) < 2:
        print(f"PRECONDITION NOT MET: only {len(space_map)} space — need >= 2")
        return None

    target_space = _find_nonempty_nonactive_space(cid, active_space, space_map)
    if target_space is None:
        print("PRECONDITION NOT MET: no non-active Space with existing windows found")
        print("  Move at least one window to a non-active Space and retry")
        return None
    target_desktop = space_map.get(target_space, ('?', '?'))[1]
    print(f"  target_space={target_space}  desktop={target_desktop}")
    print()
    return target_space

def _load_primitive_symbols() -> dict:
    # Load symbols for all 4 primitives
    fn_a,     a_ok     = _try_sym(_CG, "CGSMoveWindowsToManagedSpace")
    fn_b,     b_ok     = _try_sym(_SL, "SLSMoveWindowsToManagedSpace")
    fn_c_add, c_add_ok = _try_sym(_CG, "CGSAddWindowsToSpaces")
    fn_c_rem, c_rem_ok = _try_sym(_CG, "CGSRemoveWindowsFromSpaces")
    fn_d_set, d_set_ok = _try_sym(_SL, "SLSSpaceSetCompatID")
    fn_d_ws,  d_ws_ok  = _try_sym(_SL, "SLSSetWindowListWorkspace")
    c_ok = c_add_ok and c_rem_ok
    d_ok = d_set_ok and d_ws_ok

    _i32v64 = [ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint64]
    _i32vv  = [ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p]
    _i32u64i= [ctypes.c_int32, ctypes.c_uint64, ctypes.c_int32]
    _i32vi  = [ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32]
    if a_ok:     _setup(fn_a,     _i32v64, ctypes.c_int32)
    if b_ok:     _setup(fn_b,     _i32v64, ctypes.c_int32)
    if c_add_ok: _setup(fn_c_add, _i32vv,  ctypes.c_int32)
    if c_rem_ok: _setup(fn_c_rem, _i32vv,  ctypes.c_int32)
    if d_set_ok: _setup(fn_d_set, _i32u64i, None)
    if d_ws_ok:  _setup(fn_d_ws,  _i32vi,  None)

    print(f"  A CGSMoveWindowsToManagedSpace  : {'loaded' if a_ok else 'MISSING'}")
    print(f"  B SLSMoveWindowsToManagedSpace  : {'loaded' if b_ok else 'MISSING'}")
    c_detail = 'loaded' if c_ok else f'MISSING (add={c_add_ok} rem={c_rem_ok})'
    d_detail = 'loaded' if d_ok else f'MISSING (set={d_set_ok} ws={d_ws_ok})'
    print(f"  C CGSAddWindowsToSpaces+Remove  : {c_detail}")
    print(f"  D SLSSpaceSetCompatID+Workspace : {d_detail}")
    print()

    return {
        'fn_a': fn_a, 'a_ok': a_ok, 'fn_b': fn_b, 'b_ok': b_ok,
        'fn_c_add': fn_c_add, 'c_add_ok': c_add_ok, 'fn_c_rem': fn_c_rem, 'c_rem_ok': c_rem_ok,
        'fn_d_set': fn_d_set, 'd_set_ok': d_set_ok, 'fn_d_ws': fn_d_ws, 'd_ws_ok': d_ws_ok,
        'c_ok': c_ok, 'd_ok': d_ok,
    }

def _build_call_fn(label: str, syms: dict, wid: int, cid: int, target_space: int, active_space: int):
    if label == "A":
        def call_fn(w=wid, c=cid, t=target_space):
            return syms['fn_a'](c, _make_uint_array([w]), ctypes.c_uint64(t))
    elif label == "B":
        def call_fn(w=wid, c=cid, t=target_space):
            return syms['fn_b'](c, _make_uint_array([w]), ctypes.c_uint64(t))
    elif label == "C":
        def call_fn(w=wid, c=cid, t=target_space, s=active_space):
            syms['fn_c_add'](c, _make_uint_array([w]), _make_uint64_array([t]))
            syms['fn_c_rem'](c, _make_uint_array([w]), _make_uint64_array([s]))
    elif label == "D":
        def call_fn(w=wid, c=cid, t=target_space):
            syms['fn_d_set'](c, ctypes.c_uint64(t), ctypes.c_int32(_COMPAT_ID))
            syms['fn_d_ws'](c, _make_uint_array([w]), ctypes.c_int32(_COMPAT_ID))
            syms['fn_d_set'](c, ctypes.c_uint64(t), ctypes.c_int32(0))
    return call_fn

def _run_single_primitive(
    label: str, sym_ok: bool, cid: int, target_space: int, active_space: int, syms: dict
) -> dict:
    print(f"--- Primitive {label} ---")
    if not sym_ok:
        print(f"  SKIP — symbol not loaded")
        result = {"label": label, "sym_ok": False, "moved": None, "shot_after": "-"}
        print()
        return result

    trial_ts = time.strftime("%Y%m%d_%H%M%S")
    token    = f"p06{label.lower()}" + secrets.token_hex(3)
    print(f"  opening CotEditor doc  token={token}", flush=True)
    _open_coteditor_doc(token)
    wid = _detect_coteditor_doc(token)
    if wid is None:
        print("  FAIL — detect timeout (5s), skipping")
        result = {"label": label, "sym_ok": True, "moved": None,
                  "shot_after": "-", "error": "detect_timeout"}
        _close_coteditor_doc(token)
        print()
        return result
    print(f"  detected wid={wid}", flush=True)
    time.sleep(0.3)

    call_fn = _build_call_fn(label, syms, wid, cid, target_space, active_space)

    r = _run_primitive_trial(label, wid, call_fn, trial_ts)
    r["sym_ok"] = True

    _close_coteditor_doc(token)
    time.sleep(1.0)
    print()
    return r

def _run_all_primitives(cid: int, target_space: int, active_space: int, syms: dict) -> List[dict]:
    results = []
    for label, sym_ok in [("A", syms['a_ok']), ("B", syms['b_ok']), ("C", syms['c_ok']), ("D", syms['d_ok'])]:
        results.append(_run_single_primitive(label, sym_ok, cid, target_space, active_space, syms))
    return results
