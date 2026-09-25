# INFRASTRUCTURE
import ctypes
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_CF = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
_CG = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
_AS = ctypes.CDLL('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')

_UTF8 = 0x08000100
_SINT32 = 3
_SINT64 = 4
_SPACE_MASK = 7
_LIST_ALL = 0
_LIST_ONSCREEN = 1
_TAP_HID = 0
_TAP_SESSION = 1
_FLAG_CONTROL = 1 << 18
_FLAG_FN = 1 << 23
_KEYCODE_CTRL = 59
_KEYCODE_RIGHT = 124
_KEYCODE_LEFT = 123
_DESKTOP_KEYCODES = {1: 18, 2: 19, 3: 20, 4: 21, 5: 23, 6: 22, 7: 26, 8: 28, 9: 25}
_FLT_TRUE_MIN = 1.401298464324817e-45
_FLT_TRUE_MIN_BITS = 1
_PHASES = (1, 2, 4)
_POLL_INTERVAL = 0.02
_SWITCH_TIMEOUT = 3.0
REPORT_DIR = Path(__file__).resolve().parent / 'md'

_CF.CFStringCreateWithCString.restype = ctypes.c_void_p
_CF.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
_CF.CFStringGetCString.restype = ctypes.c_bool
_CF.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
_CF.CFDictionaryGetValue.restype = ctypes.c_void_p
_CF.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_CF.CFArrayGetCount.restype = ctypes.c_long
_CF.CFArrayGetCount.argtypes = [ctypes.c_void_p]
_CF.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
_CF.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
_CF.CFNumberGetValue.restype = ctypes.c_bool
_CF.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
_CF.CFNumberCreate.restype = ctypes.c_void_p
_CF.CFNumberCreate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
_CF.CFArrayCreate.restype = ctypes.c_void_p
_CF.CFArrayCreate.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_long, ctypes.c_void_p]
_CF.CFRelease.restype = None
_CF.CFRelease.argtypes = [ctypes.c_void_p]

_CG.CGSMainConnectionID.restype = ctypes.c_int32
_CG.CGSMainConnectionID.argtypes = []
_CG.CGSGetActiveSpace.restype = ctypes.c_uint64
_CG.CGSGetActiveSpace.argtypes = [ctypes.c_int32]
_CG.CGSCopyManagedDisplaySpaces.restype = ctypes.c_void_p
_CG.CGSCopyManagedDisplaySpaces.argtypes = [ctypes.c_int32]
_CG.CGSCopySpacesForWindows.restype = ctypes.c_void_p
_CG.CGSCopySpacesForWindows.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p]
_CG.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
_CG.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
_CG.CGEventCreate.restype = ctypes.c_void_p
_CG.CGEventCreate.argtypes = [ctypes.c_void_p]
_CG.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
_CG.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
_CG.CGEventSetFlags.restype = None
_CG.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
_CG.CGEventPost.restype = None
_CG.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
_CG.CGEventSetIntegerValueField.restype = None
_CG.CGEventSetIntegerValueField.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int64]
_CG.CGEventSetDoubleValueField.restype = None
_CG.CGEventSetDoubleValueField.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_double]
_CG.CGPreflightPostEventAccess.restype = ctypes.c_bool
_CG.CGPreflightListenEventAccess.restype = ctypes.c_bool
_CG.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
_AS.AXIsProcessTrusted.restype = ctypes.c_bool

_CB_ARRAY = ctypes.addressof(ctypes.c_char.in_dll(_CF, 'kCFTypeArrayCallBacks'))
_CID = _CG.CGSMainConnectionID()

# FUNCTIONS

def cf_str(s: str):
    return _CF.CFStringCreateWithCString(None, s.encode(), _UTF8)

def cf_to_str(ref) -> Optional[str]:
    if not ref:
        return None
    buf = ctypes.create_string_buffer(1024)
    if not _CF.CFStringGetCString(ref, buf, 1024, _UTF8):
        return None
    return buf.value.decode()

def cf_to_int(ref) -> Optional[int]:
    if not ref:
        return None
    out = ctypes.c_int64(0)
    if not _CF.CFNumberGetValue(ref, _SINT64, ctypes.byref(out)):
        return None
    return out.value

def dict_get(d, key: str):
    return _CF.CFDictionaryGetValue(d, cf_str(key))

def array_items(arr) -> list:
    if not arr:
        return []
    return [_CF.CFArrayGetValueAtIndex(arr, i) for i in range(_CF.CFArrayGetCount(arr))]

def active_space() -> int:
    return int(_CG.CGSGetActiveSpace(_CID))

def _space_id_of(space_dict) -> Optional[int]:
    sid = cf_to_int(dict_get(space_dict, 'ManagedSpaceID'))
    if sid is None:
        sid = cf_to_int(dict_get(space_dict, 'id64'))
    return sid

def spaces_with_types() -> List[Tuple[int, Optional[int]]]:
    active = active_space()
    displays = array_items(_CG.CGSCopyManagedDisplaySpaces(_CID))
    for display in displays:
        spaces = [(_space_id_of(s), cf_to_int(dict_get(s, 'type'))) for s in array_items(dict_get(display, 'Spaces'))]
        if any(sid == active for sid, _ in spaces):
            return spaces
    return []

def space_ids() -> List[int]:
    return [sid for sid, _ in spaces_with_types()]

def display_count() -> int:
    return len(array_items(_CG.CGSCopyManagedDisplaySpaces(_CID)))

def active_desktop() -> int:
    ids = space_ids()
    return ids.index(active_space()) + 1

def wait_active(target_space: int, timeout: float = _SWITCH_TIMEOUT) -> Optional[float]:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if active_space() == target_space:
            return (time.monotonic() - t0) * 1000
        time.sleep(_POLL_INTERVAL)
    return None

def wait_active_change(origin_space: int, timeout: float = _SWITCH_TIMEOUT) -> Optional[Tuple[int, float]]:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        now = active_space()
        if now != origin_space:
            return now, (time.monotonic() - t0) * 1000
        time.sleep(_POLL_INTERVAL)
    return None

def permission_state() -> Dict[str, bool]:
    return {
        'Accessibility': bool(_AS.AXIsProcessTrusted()),
        'PostEvent': bool(_CG.CGPreflightPostEventAccess()),
        'ListenEvent': bool(_CG.CGPreflightListenEventAccess()),
        'ScreenCapture': bool(_CG.CGPreflightScreenCaptureAccess()),
    }

def process_ancestry(pid: int) -> List[str]:
    chain = []
    while pid > 1 and len(chain) < 30:
        r = subprocess.run(['ps', '-o', 'ppid=,comm=', '-p', str(pid)], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=5)
        line = r.stdout.strip()
        if not line:
            break
        ppid, _, comm = line.partition(' ')
        chain.append(f'{pid} {comm.strip()}')
        pid = int(ppid)
    return chain

def window_list(option: int) -> List[Tuple[int, str, int]]:
    out = []
    for d in array_items(_CG.CGWindowListCopyWindowInfo(option, 0)):
        wid = cf_to_int(dict_get(d, 'kCGWindowNumber'))
        owner = cf_to_str(dict_get(d, 'kCGWindowOwnerName'))
        layer = cf_to_int(dict_get(d, 'kCGWindowLayer'))
        if wid is not None and owner is not None and layer is not None:
            out.append((wid, owner, layer))
    return out

def ghostty_window_ids(onscreen_only: bool = False) -> List[int]:
    option = _LIST_ONSCREEN if onscreen_only else _LIST_ALL
    return [wid for wid, owner, layer in window_list(option) if owner == 'Ghostty' and layer == 0]

def spaces_for_window(wid: int) -> List[int]:
    num = ctypes.c_int32(wid)
    ref = _CF.CFNumberCreate(None, _SINT32, ctypes.byref(num))
    vals = (ctypes.c_void_p * 1)(ref)
    arr = _CF.CFArrayCreate(None, vals, 1, _CB_ARRAY)
    res = _CG.CGSCopySpacesForWindows(_CID, _SPACE_MASK, arr)
    ids = [cf_to_int(x) for x in array_items(res)]
    _CF.CFRelease(arr)
    _CF.CFRelease(ref)
    return [i for i in ids if i is not None]

def _post_key(keycode: int, down: bool, flags: int, tap: int) -> None:
    ev = _CG.CGEventCreateKeyboardEvent(None, keycode, down)
    _CG.CGEventSetFlags(ev, flags)
    _CG.CGEventPost(tap, ev)
    _CF.CFRelease(ev)

def key_combo(keycode: int, flags: int, tap: int, explicit_modifier: bool) -> None:
    if explicit_modifier:
        _post_key(_KEYCODE_CTRL, True, _FLAG_CONTROL, tap)
    _post_key(keycode, True, flags, tap)
    _post_key(keycode, False, flags, tap)
    if explicit_modifier:
        _post_key(_KEYCODE_CTRL, False, 0, tap)

def cg_desktop_hotkey(desktop: int, tap: int, explicit_modifier: bool) -> None:
    key_combo(_DESKTOP_KEYCODES[desktop], _FLAG_CONTROL, tap, explicit_modifier)

def cg_arrow_hotkey(right: bool, tap: int) -> None:
    key_combo(_KEYCODE_RIGHT if right else _KEYCODE_LEFT, _FLAG_CONTROL | _FLAG_FN, tap, False)

def sysevents_key(keycode: int) -> subprocess.CompletedProcess:
    script = f'tell application "System Events" to key code {keycode} using control down'
    return subprocess.run(['osascript', '-e', script], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=10)

def sysevents_desktop_hotkey(desktop: int) -> subprocess.CompletedProcess:
    return sysevents_key(_DESKTOP_KEYCODES[desktop])

def sysevents_arrow_hotkey(right: bool) -> subprocess.CompletedProcess:
    return sysevents_key(_KEYCODE_RIGHT if right else _KEYCODE_LEFT)

def _flt_min_as_int32(right: bool) -> int:
    return _FLT_TRUE_MIN_BITS if right else -2147483647

def _dock_event(phase: int, right: bool, flavor: str, velocity: float):
    ev = _CG.CGEventCreate(None)
    sign = 1.0 if right else -1.0
    _CG.CGEventSetIntegerValueField(ev, 55, 30)
    _CG.CGEventSetIntegerValueField(ev, 110, 23)
    _CG.CGEventSetIntegerValueField(ev, 132, phase)
    _CG.CGEventSetIntegerValueField(ev, 123, 1)
    if flavor == 'joshuarli':
        _CG.CGEventSetIntegerValueField(ev, 135, _flt_min_as_int32(right))
        _CG.CGEventSetDoubleValueField(ev, 119, 0.0)
        _CG.CGEventSetDoubleValueField(ev, 139, _FLT_TRUE_MIN)
        if phase == 4:
            _CG.CGEventSetDoubleValueField(ev, 129, sign * velocity)
            _CG.CGEventSetDoubleValueField(ev, 130, 0.0)
    else:
        _CG.CGEventSetDoubleValueField(ev, 124, sign * _FLT_TRUE_MIN)
        _CG.CGEventSetDoubleValueField(ev, 129, sign * velocity)
        _CG.CGEventSetDoubleValueField(ev, 130, sign * velocity)
    return ev

def swipe_once(right: bool, flavor: str, velocity: float) -> None:
    for phase in _PHASES:
        dock = _dock_event(phase, right, flavor, velocity)
        companion = _CG.CGEventCreate(None)
        _CG.CGEventSetIntegerValueField(companion, 55, 29)
        _CG.CGEventPost(_TAP_SESSION, dock)
        _CG.CGEventPost(_TAP_SESSION, companion)
        _CF.CFRelease(dock)
        _CF.CFRelease(companion)

def swipe_flavor_defaults(flavor: str) -> float:
    return 400.0 if flavor == 'joshuarli' else 2000.0

def method_a1(desktop: int) -> None:
    cg_desktop_hotkey(desktop, _TAP_SESSION, False)

def method_a2(desktop: int) -> None:
    cg_desktop_hotkey(desktop, _TAP_HID, False)

def method_a3(desktop: int) -> None:
    cg_desktop_hotkey(desktop, _TAP_SESSION, True)

def method_b(desktop: int) -> None:
    sysevents_desktop_hotkey(desktop)

def desktop_methods():
    return {'a1': method_a1, 'a2': method_a2, 'a3': method_a3, 'b': method_b}

def return_home(home_space: int, preferred: List[str]) -> bool:
    if active_space() == home_space:
        return True
    home_desktop = space_ids().index(home_space) + 1
    order = preferred + [m for m in desktop_methods() if m not in preferred]
    for name in order:
        desktop_methods()[name](home_desktop)
        if wait_active(home_space, 2.0) is not None:
            return True
    for flavor in ('joshuarli', 'jurplel'):
        for _ in range(6):
            ids = space_ids()
            cur = ids.index(active_space())
            home = ids.index(home_space)
            if cur == home:
                return True
            swipe_once(home > cur, flavor, swipe_flavor_defaults(flavor))
            time.sleep(1.0)
        if active_space() == home_space:
            return True
    return False

def write_report(script_file: str, text: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f'{Path(script_file).stem}.md'
    path.write_text(text, encoding='utf-8')
    return path
