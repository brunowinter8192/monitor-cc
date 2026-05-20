# INFRASTRUCTURE
import ctypes

# Digit keycodes: kVK_ANSI_1..9 — NOT sequential; order confirmed from IOKit/hid/IOLLEvent.h
_DIGIT_KEYCODES = {1: 18, 2: 19, 3: 20, 4: 21, 5: 23, 6: 22, 7: 26, 8: 28, 9: 25}

# FUNCTIONS

# Register Cmd+L (keycode 37, modifier 0x0100) as global hotkey via Carbon
# callback: zero-arg callable invoked on each Cmd+L press
# Returns (cb_handle, hk_handle) — caller MUST keep both alive; GC invalidates the C callback
def register_cmd_l(callback) -> tuple:
    OSStatus = ctypes.c_int32

    class EventHotKeyID(ctypes.Structure):
        _fields_ = [('signature', ctypes.c_uint32), ('id', ctypes.c_uint32)]

    class EventTypeSpec(ctypes.Structure):
        _fields_ = [('eventClass', ctypes.c_uint32), ('eventKind', ctypes.c_uint32)]

    EventHandlerProcPtr = ctypes.CFUNCTYPE(
        OSStatus, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

    def _handler(handler_ref, event, user_data):
        try:
            callback()
        except Exception:
            pass
        return 0

    cb = EventHandlerProcPtr(_handler)
    carbon = ctypes.CDLL('/System/Library/Frameworks/Carbon.framework/Carbon')
    carbon.GetApplicationEventTarget.restype  = ctypes.c_void_p
    carbon.GetApplicationEventTarget.argtypes = []
    target = carbon.GetApplicationEventTarget()
    spec = EventTypeSpec(0x6B657962, 6)   # kEventClassKeyboard, kEventHotKeyPressed
    handler_ref = ctypes.c_void_p()
    carbon.InstallEventHandler.restype  = OSStatus
    carbon.InstallEventHandler.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(EventTypeSpec), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    carbon.InstallEventHandler(
        target, cb, 1, ctypes.byref(spec), None, ctypes.byref(handler_ref))
    hk_ref = ctypes.c_void_p()
    carbon.RegisterEventHotKey.restype  = OSStatus
    carbon.RegisterEventHotKey.argtypes = [
        ctypes.c_uint32, ctypes.c_uint32, EventHotKeyID,
        ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    carbon.RegisterEventHotKey(
        37, 0x0100,                          # kVK_ANSI_L, cmdKey
        EventHotKeyID(0x4D424152, 1),        # signature 'MBAR', id 1
        target, 0, ctypes.byref(hk_ref))
    return cb, hk_ref

# Register Cmd+1..9 hotkeys (panel-open only); one InstallEventHandler dispatches all via GetEventParameter
# callback_map: {slot_1..9: zero-arg callable}; slots > 9 are ignored
# Returns (cb_handle, [hk_ref_1, ..., hk_ref_N]) — caller MUST keep both alive
def register_cmd_digits(callback_map: dict) -> tuple:
    OSStatus = ctypes.c_int32

    class EventHotKeyID(ctypes.Structure):
        _fields_ = [('signature', ctypes.c_uint32), ('id', ctypes.c_uint32)]

    class EventTypeSpec(ctypes.Structure):
        _fields_ = [('eventClass', ctypes.c_uint32), ('eventKind', ctypes.c_uint32)]

    EventHandlerProcPtr = ctypes.CFUNCTYPE(
        OSStatus, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    carbon = ctypes.CDLL('/System/Library/Frameworks/Carbon.framework/Carbon')
    carbon.GetApplicationEventTarget.restype  = ctypes.c_void_p
    carbon.GetApplicationEventTarget.argtypes = []
    carbon.GetEventParameter.restype  = OSStatus
    carbon.GetEventParameter.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    carbon.InstallEventHandler.restype  = OSStatus
    carbon.InstallEventHandler.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(EventTypeSpec), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    carbon.RegisterEventHotKey.restype  = OSStatus
    carbon.RegisterEventHotKey.argtypes = [
        ctypes.c_uint32, ctypes.c_uint32, EventHotKeyID,
        ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    ]

    target = carbon.GetApplicationEventTarget()

    def _handler(handler_ref, event, user_data):
        try:
            hkid = EventHotKeyID()
            carbon.GetEventParameter(
                event,
                0x2D2D2D2D,       # kEventParamDirectObject ('----')
                0x686B6964,       # typeEventHotKeyID ('hkid')
                None, 8, None,
                ctypes.byref(hkid),
            )
            slot = hkid.id - 1   # ids 2..10 → slots 1..9
            fn = callback_map.get(slot)
            if fn is not None:
                fn()
        except Exception:
            pass
        return 0

    cb = EventHandlerProcPtr(_handler)
    spec = EventTypeSpec(0x6B657962, 6)   # kEventClassKeyboard, kEventHotKeyPressed
    handler_ref = ctypes.c_void_p()
    carbon.InstallEventHandler(
        target, cb, 1, ctypes.byref(spec), None, ctypes.byref(handler_ref))
    hk_refs = []
    for slot, keycode in _DIGIT_KEYCODES.items():
        if slot not in callback_map:
            continue
        hk_ref = ctypes.c_void_p()
        carbon.RegisterEventHotKey(
            keycode, 0x0100,                       # digit keycode, cmdKey
            EventHotKeyID(0x4D424152, slot + 1),   # signature 'MBAR', id 2..10
            target, 0, ctypes.byref(hk_ref))
        hk_refs.append(hk_ref)
    return cb, hk_refs

# Unregister a list of hotkey refs previously returned by register_cmd_digits
def unregister_hotkeys(refs: list) -> None:
    carbon = ctypes.CDLL('/System/Library/Frameworks/Carbon.framework/Carbon')
    carbon.UnregisterEventHotKey.restype  = ctypes.c_int32
    carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
    for ref in refs:
        carbon.UnregisterEventHotKey(ref)
