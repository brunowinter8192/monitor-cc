# INFRASTRUCTURE
import ctypes

from .menubar_log import log_menubar
from .system import _focus_session
from .hotkey_carbon import (
    _EventHotKeyID, _EventHandlerProcPtr, _MBAR_SIG, _HOTKEY_EVENT_SPEC, _get_hkid,
    _load_carbon, _log_queue_delay, _eventNotHandledErr,
)
from .hotkey_digits import register_cmd_digits, unregister_hotkeys
from .hotkey_arrows import (
    register_cmd_arrow_right, register_cmd_arrow_left,
    unregister_cmd_arrow_right, unregister_cmd_arrow_left,
)

# Cmd+L/Cmd+K single-shot hotkey registration + HotkeyController per-concern controller
# (Step 6/6 of CCMenuBarApp composition refactor). Digit (Cmd+1..9) and arrow (Cmd+→/←)
# registration split out into hotkey_digits.py/hotkey_arrows.py (menubar milestone C) — see
# those modules for the _DIGIT_*/_ARROW_* constant clusters and their persistent-handler state.
_CMD_L_ID            = 1            # EventHotKeyID.id for Cmd+L
_CMD_K_ID            = 30           # EventHotKeyID.id for Cmd+K (30 avoids collision: L=1, digits=2-10, arrows=20-21)

# FUNCTIONS

# Register Cmd+L (keycode 37, modifier 0x0100) as global hotkey via Carbon
# Filters via EventHotKeyID (id=1) — returns eventNotHandledErr for all other hotkey events
# so digit handlers (or any other handler) receive their own events unimpeded.
# callback: zero-arg callable invoked on each Cmd+L press
# Returns (cb_handle, hk_handle) — caller MUST keep both alive; GC invalidates the C callback
def register_cmd_l(callback) -> tuple:
    carbon = _load_carbon()
    target = carbon.GetApplicationEventTarget()

    def _handler(handler_ref, event, user_data):
        _entry_t = carbon.GetCurrentEventTime()
        try:
            hkid = _get_hkid(carbon, event)
            if hkid.id != _CMD_L_ID:
                return _eventNotHandledErr
            log_menubar('hotkey', 'cmd+l')
            _log_queue_delay(carbon, event, _entry_t, 'cmd+l')
            callback()
        except Exception:  # log-safe: Carbon handler must not raise
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

# Register Cmd+K (kVK_ANSI_K = 0x28) as global hotkey via Carbon.
# Always-active (same lifetime as Cmd+L): registered once, never unregistered.
# Returns (cb_handle, hk_handle) — caller MUST keep both alive to prevent GC of C callback.
def register_cmd_k(callback) -> tuple:
    carbon = _load_carbon()
    target = carbon.GetApplicationEventTarget()

    def _handler(handler_ref, event, user_data):
        _entry_t = carbon.GetCurrentEventTime()
        try:
            hkid = _get_hkid(carbon, event)
            if hkid.id != _CMD_K_ID:
                return _eventNotHandledErr
            log_menubar('hotkey', 'cmd+k')
            _log_queue_delay(carbon, event, _entry_t, 'cmd+k')
            callback()
        except Exception:  # log-safe: Carbon handler must not raise
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


# ORCHESTRATOR

# Per-concern controller for digit (Cmd+1..9) and arrow (Cmd+→/←) hotkey lifecycle (Step 6/6)
class HotkeyController:
    def __init__(self, app) -> None:
        self.app = app
        self._hotkey_digits_cb   = None   # GC anchor for Cmd+1..9 CFUNCTYPE (module holds; kept for compat)
        self._hotkey_digits_refs = []     # hk_refs for active Cmd+1..9 registrations
        self._hotkey_arr_right_ref = None   # hk_ref for active Cmd+→ registration
        self._hotkey_arr_left_ref  = None   # hk_ref for active Cmd+← registration

    # Register (or re-register) Cmd+1..9 hotkeys mapped by desktop slot → cwd
    def reregister_digits(self, desktop_to_cwd: dict) -> None:
        if self._hotkey_digits_refs:
            unregister_hotkeys(self._hotkey_digits_refs)
            self._hotkey_digits_refs = []
            self._hotkey_digits_cb   = None
        slots = {dn: cwd for dn, cwd in desktop_to_cwd.items() if dn <= 9 and cwd}
        if not slots:
            return
        def _make_digit_cb(slot, cwd):
            def _cb():
                log_menubar('hotkey', f'cmd+{slot} → focus {cwd}')
                _focus_session(cwd)
            return _cb
        cb_map = {slot: _make_digit_cb(slot, cwd) for slot, cwd in slots.items()}
        self._hotkey_digits_cb, self._hotkey_digits_refs = register_cmd_digits(cb_map)

    # Register Cmd+→; stores hk_ref for later unregister
    def register_arrow_right(self, callback) -> None:
        _, self._hotkey_arr_right_ref = register_cmd_arrow_right(callback)

    # Register Cmd+←; stores hk_ref for later unregister
    def register_arrow_left(self, callback) -> None:
        _, self._hotkey_arr_left_ref = register_cmd_arrow_left(callback)

    # Unregister Cmd+→ and clear stored ref
    def unregister_arrow_right(self) -> None:
        unregister_cmd_arrow_right(self._hotkey_arr_right_ref)
        self._hotkey_arr_right_ref = None

    # Unregister Cmd+← and clear stored ref
    def unregister_arrow_left(self) -> None:
        unregister_cmd_arrow_left(self._hotkey_arr_left_ref)
        self._hotkey_arr_left_ref = None

    # Unregister all Cmd+1..9 hotkeys and clear state
    def unregister_digits(self) -> None:
        if self._hotkey_digits_refs:
            unregister_hotkeys(self._hotkey_digits_refs)
            self._hotkey_digits_refs = []
            self._hotkey_digits_cb   = None
