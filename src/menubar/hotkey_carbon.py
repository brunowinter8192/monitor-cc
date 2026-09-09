# INFRASTRUCTURE
import ctypes

from .menubar_log import log_menubar

_OSStatus = ctypes.c_int32

class _EventHotKeyID(ctypes.Structure):
    _fields_ = [('signature', ctypes.c_uint32), ('id', ctypes.c_uint32)]

class _EventTypeSpec(ctypes.Structure):
    _fields_ = [('eventClass', ctypes.c_uint32), ('eventKind', ctypes.c_uint32)]

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
    carbon.GetEventTime.restype  = ctypes.c_double
    carbon.GetEventTime.argtypes = [ctypes.c_void_p]
    carbon.GetCurrentEventTime.restype  = ctypes.c_double
    carbon.GetCurrentEventTime.argtypes = []
    return carbon

_EventHandlerProcPtr = ctypes.CFUNCTYPE(
    _OSStatus, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

_MBAR_SIG            = 0x4D424152
_HOTKEY_EVENT_SPEC   = _EventTypeSpec(0x6B657962, 6)
_kEventParamDirect   = 0x2D2D2D2D
_typeEventHotKeyID   = 0x686B6964
_eventNotHandledErr  = -9874

# FUNCTIONS

def _log_queue_delay(carbon, event, handler_entry_t: float, hotkey_name: str) -> None:
    event_t = carbon.GetEventTime(event)
    queue_delay_ms = (handler_entry_t - event_t) * 1000
    log_menubar('latency', f'hotkey={hotkey_name} queue_delay_ms={queue_delay_ms:.1f}')

def _get_hkid(carbon, event) -> _EventHotKeyID:
    hkid = _EventHotKeyID()
    carbon.GetEventParameter(
        event, _kEventParamDirect, _typeEventHotKeyID, None, 8, None,
        ctypes.byref(hkid))
    return hkid
