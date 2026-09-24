# INFRASTRUCTURE
import ctypes
import time

from .desktop_detection import _build_space_map

_CG = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')

_TAP_SESSION = 1
_FLAG_CONTROL = 1 << 18
_DESKTOP_KEYCODES = {1: 18, 2: 19, 3: 20, 4: 21, 5: 23, 6: 22, 7: 26, 8: 28, 9: 25}
_POLL_INTERVAL = 0.02
_SWITCH_TIMEOUT = 3.0

_CG.CGSMainConnectionID.restype = ctypes.c_int32
_CG.CGSMainConnectionID.argtypes = []
_CG.CGSGetActiveSpace.restype = ctypes.c_uint64
_CG.CGSGetActiveSpace.argtypes = [ctypes.c_int32]
_CG.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
_CG.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
_CG.CGEventSetFlags.restype = None
_CG.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
_CG.CGEventPost.restype = None
_CG.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
_CG.CGPreflightPostEventAccess.restype = ctypes.c_bool
_CG.CGPreflightPostEventAccess.argtypes = []
_CG.CGRequestPostEventAccess.restype = ctypes.c_bool
_CG.CGRequestPostEventAccess.argtypes = []

_CF = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
_CF.CFRelease.restype = None
_CF.CFRelease.argtypes = [ctypes.c_void_p]

# ORCHESTRATOR

def switch_to_desktop_workflow(desktop: int) -> float:
    _require_post_event_access()
    target_space = _space_id_for_desktop(desktop)
    _post_desktop_hotkey(desktop)
    return _wait_until_active(target_space)

# FUNCTIONS

class SpaceSwitchError(Exception):
    pass

def _require_post_event_access() -> None:
    if _CG.CGPreflightPostEventAccess():
        return
    _CG.CGRequestPostEventAccess()
    raise SpaceSwitchError('postevent_not_granted')

def _space_id_for_desktop(desktop: int) -> int:
    space_map = _build_space_map(_CG.CGSMainConnectionID())
    matches = [sid for sid, (_display, number) in space_map.items() if number == desktop]
    if len(matches) != 1:
        raise SpaceSwitchError(f'desktop_{desktop}_space_matches={len(matches)}')
    return matches[0]

def _post_key(keycode: int, down: bool) -> None:
    event = _CG.CGEventCreateKeyboardEvent(None, keycode, down)
    _CG.CGEventSetFlags(event, _FLAG_CONTROL)
    _CG.CGEventPost(_TAP_SESSION, event)
    _CF.CFRelease(event)

def _post_desktop_hotkey(desktop: int) -> None:
    keycode = _DESKTOP_KEYCODES[desktop]
    _post_key(keycode, True)
    _post_key(keycode, False)

def active_space_id() -> int:
    return int(_CG.CGSGetActiveSpace(_CG.CGSMainConnectionID()))

def active_desktop_number():
    space_map = _build_space_map(_CG.CGSMainConnectionID())
    info = space_map.get(active_space_id())
    return info[1] if info else None

def _wait_until_active(target_space: int) -> float:
    t0 = time.monotonic()
    while time.monotonic() - t0 < _SWITCH_TIMEOUT:
        if active_space_id() == target_space:
            return (time.monotonic() - t0) * 1000
        time.sleep(_POLL_INTERVAL)
    raise SpaceSwitchError(f'switch_timeout_{_SWITCH_TIMEOUT:.0f}s')
