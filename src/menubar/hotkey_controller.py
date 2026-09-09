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

_CMD_L_ID            = 1
_CMD_K_ID            = 30

# FUNCTIONS

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
        except Exception:
            pass
        return 0

    cb = _EventHandlerProcPtr(_handler)
    handler_ref = ctypes.c_void_p()
    carbon.InstallEventHandler(
        target, cb, 1, ctypes.byref(_HOTKEY_EVENT_SPEC), None, ctypes.byref(handler_ref))
    hk_ref = ctypes.c_void_p()
    carbon.RegisterEventHotKey(
        37, 0x0100,
        _EventHotKeyID(_MBAR_SIG, _CMD_L_ID),
        target, 0, ctypes.byref(hk_ref))
    return cb, hk_ref

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
        except Exception:
            pass
        return 0

    cb = _EventHandlerProcPtr(_handler)
    handler_ref = ctypes.c_void_p()
    carbon.InstallEventHandler(
        target, cb, 1, ctypes.byref(_HOTKEY_EVENT_SPEC), None, ctypes.byref(handler_ref))
    hk_ref = ctypes.c_void_p()
    carbon.RegisterEventHotKey(
        0x28, 0x0100,
        _EventHotKeyID(_MBAR_SIG, _CMD_K_ID),
        target, 0, ctypes.byref(hk_ref))
    return cb, hk_ref


# ORCHESTRATOR

class HotkeyController:
    def __init__(self, app) -> None:
        self.app = app
        self._hotkey_digits_cb   = None
        self._hotkey_digits_refs = []
        self._hotkey_arr_right_ref = None
        self._hotkey_arr_left_ref  = None
        self.global_handles = None

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

    def register_arrow_right(self, callback) -> None:
        _, self._hotkey_arr_right_ref = register_cmd_arrow_right(callback)

    def register_arrow_left(self, callback) -> None:
        _, self._hotkey_arr_left_ref = register_cmd_arrow_left(callback)

    def unregister_arrow_right(self) -> None:
        unregister_cmd_arrow_right(self._hotkey_arr_right_ref)
        self._hotkey_arr_right_ref = None

    def unregister_arrow_left(self) -> None:
        unregister_cmd_arrow_left(self._hotkey_arr_left_ref)
        self._hotkey_arr_left_ref = None

    def unregister_digits(self) -> None:
        if self._hotkey_digits_refs:
            unregister_hotkeys(self._hotkey_digits_refs)
            self._hotkey_digits_refs = []
            self._hotkey_digits_cb   = None
