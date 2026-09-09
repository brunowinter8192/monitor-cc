# INFRASTRUCTURE
import ctypes

from .menubar_log import log_menubar
from .hotkey_carbon import (
    _EventHotKeyID, _EventHandlerProcPtr, _MBAR_SIG, _HOTKEY_EVENT_SPEC, _get_hkid,
    _load_carbon, _log_queue_delay, _eventNotHandledErr,
)

_CMD_RIGHT_ID        = 20
_CMD_LEFT_ID         = 21

_ARROW_CALLBACKS    = {}
_ARROW_HANDLER_CB   = None
_ARROW_HANDLER_REF  = None

# FUNCTIONS

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
        except Exception:
            pass
        return 0

    _ARROW_HANDLER_CB = _EventHandlerProcPtr(_handler)
    handler_ref = ctypes.c_void_p()
    carbon.InstallEventHandler(
        target, _ARROW_HANDLER_CB, 1, ctypes.byref(_HOTKEY_EVENT_SPEC),
        None, ctypes.byref(handler_ref))
    _ARROW_HANDLER_REF = handler_ref

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

def unregister_cmd_arrow_right(hk_ref) -> None:
    _ARROW_CALLBACKS.pop(_CMD_RIGHT_ID, None)
    if hk_ref is not None:
        _load_carbon().UnregisterEventHotKey(hk_ref)

def unregister_cmd_arrow_left(hk_ref) -> None:
    _ARROW_CALLBACKS.pop(_CMD_LEFT_ID, None)
    if hk_ref is not None:
        _load_carbon().UnregisterEventHotKey(hk_ref)
