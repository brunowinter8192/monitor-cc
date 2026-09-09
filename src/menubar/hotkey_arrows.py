# INFRASTRUCTURE
import ctypes

from .menubar_log import log_menubar
from .hotkey_carbon import (
    _EventHotKeyID, _EventHandlerProcPtr, _MBAR_SIG, _HOTKEY_EVENT_SPEC, _get_hkid,
    _load_carbon, _log_queue_delay, _eventNotHandledErr,
)

# Cmd+→/← arrow-hotkey registration — split out of hotkey_controller.py (menubar milestone C,
# _ARROW_* constant cluster). _CMD_RIGHT_ID/_CMD_LEFT_ID moved here too (peeled off the old
# _CMD_* naming cluster) — they're consumed exclusively by this module's persistent handler
# dispatch and registration, never by Cmd+L/Cmd+K. The `global` rebinds below stay in this
# module because this module owns the persistent handler state they mutate.
_CMD_RIGHT_ID        = 20           # EventHotKeyID.id for Cmd+→ (kVK_RightArrow = 0x7C)
_CMD_LEFT_ID         = 21           # EventHotKeyID.id for Cmd+← (kVK_LeftArrow = 0x7B)

# Persistent module-level state for the arrow-key handler.
# Same pattern as digits: CFUNCTYPE + handler_ref live at module scope forever.
# Per-call CFUNCTYPE (old pattern) let Carbon hold a dangling pointer after cb=None GC → SIGABRT
# on the next hotkey event. register/unregister only touch hk_ref + this dict.
_ARROW_CALLBACKS    = {}     # {_CMD_RIGHT_ID: callable, _CMD_LEFT_ID: callable}
_ARROW_HANDLER_CB   = None   # persistent CFUNCTYPE — module-anchored
_ARROW_HANDLER_REF  = None   # handler_ref from InstallEventHandler

# FUNCTIONS

# Install the arrow-key handler exactly once; subsequent calls are no-ops
def _ensure_arrow_handler():
    global _ARROW_HANDLER_CB, _ARROW_HANDLER_REF
    if _ARROW_HANDLER_CB is not None:
        return
    carbon = _load_carbon()
    target = carbon.GetApplicationEventTarget()

    def _handler(handler_ref, event, user_data):
        _entry_t = carbon.GetCurrentEventTime()
        try:
            hkid = _get_hkid(carbon, event)
            fn = _ARROW_CALLBACKS.get(hkid.id)
            if fn is None:
                return _eventNotHandledErr
            name = 'cmd+right' if hkid.id == _CMD_RIGHT_ID else 'cmd+left'
            log_menubar('hotkey', name)
            _log_queue_delay(carbon, event, _entry_t, name)
            fn()
        except Exception:  # log-safe: Carbon handler must not raise
            pass
        return 0

    _ARROW_HANDLER_CB = _EventHandlerProcPtr(_handler)
    handler_ref = ctypes.c_void_p()
    carbon.InstallEventHandler(
        target, _ARROW_HANDLER_CB, 1, ctypes.byref(_HOTKEY_EVENT_SPEC),
        None, ctypes.byref(handler_ref))
    _ARROW_HANDLER_REF = handler_ref

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
