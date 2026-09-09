# INFRASTRUCTURE
import ctypes

from .menubar_log import log_menubar
from .hotkey_carbon import (
    _EventHotKeyID, _EventHandlerProcPtr, _MBAR_SIG, _HOTKEY_EVENT_SPEC, _get_hkid,
    _load_carbon, _log_queue_delay, _eventNotHandledErr,
)

_DIGIT_KEYCODES = {1: 18, 2: 19, 3: 20, 4: 21, 5: 23, 6: 22, 7: 26, 8: 28, 9: 25}

_DIGIT_CALLBACKS    = {}
_DIGIT_HANDLER_CB   = None
_DIGIT_HANDLER_REF  = None

# FUNCTIONS

def _ensure_digit_handler():
    global _DIGIT_HANDLER_CB, _DIGIT_HANDLER_REF
    if _DIGIT_HANDLER_CB is not None:
        return
    carbon = _load_carbon()
    target = carbon.GetApplicationEventTarget()

    def _handler(handler_ref, event, user_data):
        _entry_t = carbon.GetCurrentEventTime()
        try:
            hkid = _get_hkid(carbon, event)
            slot = hkid.id - 1
            fn = _DIGIT_CALLBACKS.get(slot)
            if fn is None:
                return _eventNotHandledErr
            log_menubar('hotkey', f'cmd+{slot}')
            _log_queue_delay(carbon, event, _entry_t, f'cmd+{slot}')
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
            keycode, 0x0100,
            _EventHotKeyID(_MBAR_SIG, slot + 1),
            target, 0, ctypes.byref(hk_ref))
        hk_refs.append(hk_ref)
    return None, hk_refs

def unregister_hotkeys(refs: list) -> None:
    carbon = _load_carbon()
    for ref in refs:
        carbon.UnregisterEventHotKey(ref)
    _DIGIT_CALLBACKS.clear()
