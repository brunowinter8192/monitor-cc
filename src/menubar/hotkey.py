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
_CMD_K_ID            = 30           # EventHotKeyID.id for Cmd+K (30 avoids collision: L=1, digits=2-10, arrows=20-21)
_CMD_RIGHT_ID        = 20           # EventHotKeyID.id for Cmd+→ (kVK_RightArrow = 0x7C)
_CMD_LEFT_ID         = 21           # EventHotKeyID.id for Cmd+← (kVK_LeftArrow = 0x7B)
_HOTKEY_EVENT_SPEC   = _EventTypeSpec(0x6B657962, 6)   # kEventClassKeyboard, kEventHotKeyPressed
_kEventParamDirect   = 0x2D2D2D2D   # kEventParamDirectObject ('----')
_typeEventHotKeyID   = 0x686B6964   # typeEventHotKeyID ('hkid')
_eventNotHandledErr  = -9874

# Persistent module-level state for the digit handler.
# CFUNCTYPE installed ONCE via _ensure_digit_handler(); never dropped → no SEGV from GC.
# register/unregister only manage hotkey registrations + this dict.
_DIGIT_CALLBACKS    = {}     # mutable slot→callable map; mutated by register/unregister
_DIGIT_HANDLER_CB   = None   # persistent CFUNCTYPE — module-anchored, never reassigned to None
_DIGIT_HANDLER_REF  = None   # handler_ref from InstallEventHandler

# Persistent module-level state for the arrow-key handler.
# Same pattern as digits: CFUNCTYPE + handler_ref live at module scope forever.
# Per-call CFUNCTYPE (old pattern) let Carbon hold a dangling pointer after cb=None GC → SIGABRT
# on the next hotkey event. register/unregister only touch hk_ref + this dict.
_ARROW_CALLBACKS    = {}     # {_CMD_RIGHT_ID: callable, _CMD_LEFT_ID: callable}
_ARROW_HANDLER_CB   = None   # persistent CFUNCTYPE — module-anchored
_ARROW_HANDLER_REF  = None   # handler_ref from InstallEventHandler

# FUNCTIONS

# Extract EventHotKeyID from a Carbon hotkey event
def _get_hkid(carbon, event) -> _EventHotKeyID:
    hkid = _EventHotKeyID()
    carbon.GetEventParameter(
        event, _kEventParamDirect, _typeEventHotKeyID, None, 8, None,
        ctypes.byref(hkid))
    return hkid

# Install the digit handler exactly once; subsequent calls are no-ops
def _ensure_digit_handler():
    global _DIGIT_HANDLER_CB, _DIGIT_HANDLER_REF
    if _DIGIT_HANDLER_CB is not None:
        return
    carbon = _load_carbon()
    target = carbon.GetApplicationEventTarget()

    def _handler(handler_ref, event, user_data):
        try:
            hkid = _get_hkid(carbon, event)
            slot = hkid.id - 1   # ids 2..10 → slots 1..9
            fn = _DIGIT_CALLBACKS.get(slot)
            if fn is None:
                return _eventNotHandledErr
            fn()
        except Exception:
            pass
        return 0

    _DIGIT_HANDLER_CB = _EventHandlerProcPtr(_handler)
    handler_ref = ctypes.c_void_p()
    carbon.InstallEventHandler(
        target, _DIGIT_HANDLER_CB, 1, ctypes.byref(_HOTKEY_EVENT_SPEC),
        None, ctypes.byref(handler_ref))
    _DIGIT_HANDLER_REF = handler_ref

# Install the arrow-key handler exactly once; subsequent calls are no-ops
def _ensure_arrow_handler():
    global _ARROW_HANDLER_CB, _ARROW_HANDLER_REF
    if _ARROW_HANDLER_CB is not None:
        return
    carbon = _load_carbon()
    target = carbon.GetApplicationEventTarget()

    def _handler(handler_ref, event, user_data):
        try:
            hkid = _get_hkid(carbon, event)
            fn = _ARROW_CALLBACKS.get(hkid.id)
            if fn is None:
                return _eventNotHandledErr
            fn()
        except Exception:
            pass
        return 0

    _ARROW_HANDLER_CB = _EventHandlerProcPtr(_handler)
    handler_ref = ctypes.c_void_p()
    carbon.InstallEventHandler(
        target, _ARROW_HANDLER_CB, 1, ctypes.byref(_HOTKEY_EVENT_SPEC),
        None, ctypes.byref(handler_ref))
    _ARROW_HANDLER_REF = handler_ref

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

# Register Cmd+1..9 hotkeys (panel-open only).
# Uses the persistent module-level handler (_ensure_digit_handler); only hotkey registrations
# are created/destroyed on each open/close cycle — the CFUNCTYPE is never GC'd.
# callback_map: {slot_1..9: zero-arg callable}
# Returns (None, [hk_ref_list]) — cb-slot is None (module holds the anchor); tuple kept for caller compat
def register_cmd_digits(callback_map: dict) -> tuple:
    _ensure_digit_handler()
    _DIGIT_CALLBACKS.clear()
    _DIGIT_CALLBACKS.update({s: cb for s, cb in callback_map.items() if s in _DIGIT_KEYCODES})
    carbon = _load_carbon()
    target = carbon.GetApplicationEventTarget()
    hk_refs = []
    for slot, keycode in _DIGIT_KEYCODES.items():
        if slot not in _DIGIT_CALLBACKS:
            continue
        hk_ref = ctypes.c_void_p()
        carbon.RegisterEventHotKey(
            keycode, 0x0100,                        # digit keycode, cmdKey
            _EventHotKeyID(_MBAR_SIG, slot + 1),    # signature 'MBAR', ids 2..10
            target, 0, ctypes.byref(hk_ref))
        hk_refs.append(hk_ref)
    return None, hk_refs

# Unregister a list of hotkey refs previously returned by register_cmd_digits; clears dispatch table
def unregister_hotkeys(refs: list) -> None:
    carbon = _load_carbon()
    for ref in refs:
        carbon.UnregisterEventHotKey(ref)
    _DIGIT_CALLBACKS.clear()

# Register Cmd+→ (kVK_RightArrow = 0x7C) via the persistent module-level arrow handler.
# Returns (None, hk_ref) — None because module holds the CFUNCTYPE anchor (no per-call GC risk).
def register_cmd_arrow_right(callback) -> tuple:
    _ensure_arrow_handler()
    _ARROW_CALLBACKS[_CMD_RIGHT_ID] = callback
    carbon = _load_carbon()
    target = carbon.GetApplicationEventTarget()
    hk_ref = ctypes.c_void_p()
    carbon.RegisterEventHotKey(
        0x7C, 0x0100,
        _EventHotKeyID(_MBAR_SIG, _CMD_RIGHT_ID),
        target, 0, ctypes.byref(hk_ref))
    return None, hk_ref

# Register Cmd+← (kVK_LeftArrow = 0x7B) via the persistent module-level arrow handler.
# Returns (None, hk_ref) — None because module holds the CFUNCTYPE anchor (no per-call GC risk).
def register_cmd_arrow_left(callback) -> tuple:
    _ensure_arrow_handler()
    _ARROW_CALLBACKS[_CMD_LEFT_ID] = callback
    carbon = _load_carbon()
    target = carbon.GetApplicationEventTarget()
    hk_ref = ctypes.c_void_p()
    carbon.RegisterEventHotKey(
        0x7B, 0x0100,
        _EventHotKeyID(_MBAR_SIG, _CMD_LEFT_ID),
        target, 0, ctypes.byref(hk_ref))
    return None, hk_ref

# Unregister Cmd+→: clear callback from dispatch table + unregister hotkey registration
def unregister_cmd_arrow_right(hk_ref) -> None:
    _ARROW_CALLBACKS.pop(_CMD_RIGHT_ID, None)
    if hk_ref is not None:
        _load_carbon().UnregisterEventHotKey(hk_ref)

# Unregister Cmd+←: clear callback from dispatch table + unregister hotkey registration
def unregister_cmd_arrow_left(hk_ref) -> None:
    _ARROW_CALLBACKS.pop(_CMD_LEFT_ID, None)
    if hk_ref is not None:
        _load_carbon().UnregisterEventHotKey(hk_ref)

# Register Cmd+K (kVK_ANSI_K = 0x28) as global hotkey via Carbon.
# Always-active (same lifetime as Cmd+L): registered once, never unregistered.
# Returns (cb_handle, hk_handle) — caller MUST keep both alive to prevent GC of C callback.
def register_cmd_k(callback) -> tuple:
    carbon = _load_carbon()
    target = carbon.GetApplicationEventTarget()

    def _handler(handler_ref, event, user_data):
        try:
            hkid = _get_hkid(carbon, event)
            if hkid.id != _CMD_K_ID:
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
        0x28, 0x0100,                              # kVK_ANSI_K, cmdKey
        _EventHotKeyID(_MBAR_SIG, _CMD_K_ID),
        target, 0, ctypes.byref(hk_ref))
    return cb, hk_ref
