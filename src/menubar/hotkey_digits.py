# INFRASTRUCTURE
import ctypes

from .menubar_log import log_menubar
from .hotkey_carbon import (
    _EventHotKeyID, _EventHandlerProcPtr, _MBAR_SIG, _HOTKEY_EVENT_SPEC, _get_hkid,
    _load_carbon, _log_queue_delay, _eventNotHandledErr,
)

# Cmd+1..9 digit-hotkey registration — split out of hotkey_controller.py (menubar milestone C,
# _DIGIT_* constant cluster). The `global` rebinds below stay in this module because this module
# owns the persistent handler state they mutate.

# Digit keycodes: kVK_ANSI_1..9 — NOT sequential; order confirmed from IOKit/hid/IOLLEvent.h
_DIGIT_KEYCODES = {1: 18, 2: 19, 3: 20, 4: 21, 5: 23, 6: 22, 7: 26, 8: 28, 9: 25}

# Persistent module-level state for the digit handler.
# CFUNCTYPE installed ONCE via _ensure_digit_handler(); never dropped → no SEGV from GC.
# register/unregister only manage hotkey registrations + this dict.
_DIGIT_CALLBACKS    = {}     # mutable slot→callable map; mutated by register/unregister
_DIGIT_HANDLER_CB   = None   # persistent CFUNCTYPE — module-anchored, never reassigned to None
_DIGIT_HANDLER_REF  = None   # handler_ref from InstallEventHandler

# FUNCTIONS

# Install the digit handler exactly once; subsequent calls are no-ops
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
            slot = hkid.id - 1   # ids 2..10 → slots 1..9
            fn = _DIGIT_CALLBACKS.get(slot)
            if fn is None:
                return _eventNotHandledErr
            log_menubar('hotkey', f'cmd+{slot}')
            _log_queue_delay(carbon, event, _entry_t, f'cmd+{slot}')
            fn()
        except Exception:  # log-safe: Carbon handler must not raise
            pass
        return 0

    _DIGIT_HANDLER_CB = _EventHandlerProcPtr(_handler)
    handler_ref = ctypes.c_void_p()
    carbon.InstallEventHandler(
        target, _DIGIT_HANDLER_CB, 1, ctypes.byref(_HOTKEY_EVENT_SPEC),
        None, ctypes.byref(handler_ref))
    _DIGIT_HANDLER_REF = handler_ref

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
