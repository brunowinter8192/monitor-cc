# INFRASTRUCTURE
import ctypes

# Digit keycodes: kVK_ANSI_1..9 — NOT sequential; order confirmed from IOKit/hid/IOLLEvent.h
_DIGIT_KEYCODES = {1: 18, 2: 19, 3: 20, 4: 21, 5: 23, 6: 22, 7: 26, 8: 28, 9: 25}

_OSStatus = ctypes.c_int32

class _EventHotKeyID(ctypes.Structure):
    _fields_ = [('signature', ctypes.c_uint32), ('id', ctypes.c_uint32)]

class _EventTypeSpec(ctypes.Structure):
    _fields_ = [('eventClass', ctypes.c_uint32), ('eventKind', ctypes.c_uint32)]

# Configure Carbon CDLL with all argtypes needed by both hotkey functions
def _load_carbon():
    carbon = ctypes.CDLL('/System/Library/Frameworks/Carbon.framework/Carbon')
    carbon.GetApplicationEventTarget.restype  = ctypes.c_void_p
    carbon.GetApplicationEventTarget.argtypes = []
    carbon.GetEventParameter.restype  = _OSStatus
    carbon.GetEventParameter.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    carbon.InstallEventHandler.restype  = _OSStatus
    carbon.InstallEventHandler.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(_EventTypeSpec), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    carbon.RegisterEventHotKey.restype  = _OSStatus
    carbon.RegisterEventHotKey.argtypes = [
        ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID,
        ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    carbon.UnregisterEventHotKey.restype  = _OSStatus
    carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
    return carbon

_EventHandlerProcPtr = ctypes.CFUNCTYPE(
    _OSStatus, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

_MBAR_SIG            = 0x4D424152   # OSType 'MBAR'
_CMD_L_ID            = 1            # EventHotKeyID.id for Cmd+L
_HOTKEY_EVENT_SPEC   = _EventTypeSpec(0x6B657962, 6)   # kEventClassKeyboard, kEventHotKeyPressed
_kEventParamDirect   = 0x2D2D2D2D   # kEventParamDirectObject ('----')
_typeEventHotKeyID   = 0x686B6964   # typeEventHotKeyID ('hkid')
_eventNotHandledErr  = -9874

# FUNCTIONS

# Extract EventHotKeyID from a Carbon hotkey event
def _get_hkid(carbon, event) -> _EventHotKeyID:
    hkid = _EventHotKeyID()
    carbon.GetEventParameter(
        event, _kEventParamDirect, _typeEventHotKeyID, None, 8, None,
        ctypes.byref(hkid))
    return hkid

# Register Cmd+L (keycode 37, modifier 0x0100) as global hotkey via Carbon
# Filters via EventHotKeyID (id=1) — returns eventNotHandledErr for all other hotkey events
# so digit handlers (or any other handler) receive their own events unimpeded.
# callback: zero-arg callable invoked on each Cmd+L press
# Returns (cb_handle, hk_handle) — caller MUST keep both alive; GC invalidates the C callback
def register_cmd_l(callback) -> tuple:
    carbon = _load_carbon()
    target = carbon.GetApplicationEventTarget()

    def _handler(handler_ref, event, user_data):
        try:
            hkid = _get_hkid(carbon, event)
            if hkid.id != _CMD_L_ID:
                return _eventNotHandledErr
            callback()
        except Exception:
            pass
        return 0

    cb = _EventHandlerProcPtr(_handler)
    handler_ref = ctypes.c_void_p()
    carbon.InstallEventHandler(
        target, cb, 1, ctypes.byref(_HOTKEY_EVENT_SPEC), None, ctypes.byref(handler_ref))
    hk_ref = ctypes.c_void_p()
    carbon.RegisterEventHotKey(
        37, 0x0100,                              # kVK_ANSI_L, cmdKey
        _EventHotKeyID(_MBAR_SIG, _CMD_L_ID),   # signature 'MBAR', id 1
        target, 0, ctypes.byref(hk_ref))
    return cb, hk_ref

# Register Cmd+1..9 hotkeys (panel-open only); one InstallEventHandler dispatches all via GetEventParameter
# Filters via EventHotKeyID: returns eventNotHandledErr for events with unknown ids (e.g. Cmd+L id=1)
# so the Cmd+L handler receives its own event unimpeded.
# callback_map: {slot_1..9: zero-arg callable}; slots > 9 are ignored
# Returns (cb_handle, [hk_ref_1, ..., hk_ref_N]) — caller MUST keep both alive
def register_cmd_digits(callback_map: dict) -> tuple:
    carbon = _load_carbon()
    target = carbon.GetApplicationEventTarget()

    def _handler(handler_ref, event, user_data):
        try:
            hkid = _get_hkid(carbon, event)
            slot = hkid.id - 1   # ids 2..10 → slots 1..9
            fn = callback_map.get(slot)
            if fn is None:
                return _eventNotHandledErr
            fn()
        except Exception:
            pass
        return 0

    cb = _EventHandlerProcPtr(_handler)
    handler_ref = ctypes.c_void_p()
    carbon.InstallEventHandler(
        target, cb, 1, ctypes.byref(_HOTKEY_EVENT_SPEC), None, ctypes.byref(handler_ref))
    hk_refs = []
    for slot, keycode in _DIGIT_KEYCODES.items():
        if slot not in callback_map:
            continue
        hk_ref = ctypes.c_void_p()
        carbon.RegisterEventHotKey(
            keycode, 0x0100,                                    # digit keycode, cmdKey
            _EventHotKeyID(_MBAR_SIG, slot + 1),               # signature 'MBAR', ids 2..10
            target, 0, ctypes.byref(hk_ref))
        hk_refs.append(hk_ref)
    return cb, hk_refs

# Unregister a list of hotkey refs previously returned by register_cmd_digits
def unregister_hotkeys(refs: list) -> None:
    carbon = _load_carbon()
    for ref in refs:
        carbon.UnregisterEventHotKey(ref)
