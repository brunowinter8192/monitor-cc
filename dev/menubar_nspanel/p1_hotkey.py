# INFRASTRUCTURE
import ctypes
import sys


# FUNCTIONS

def _hotkey_ctypes_defs():
    OSStatus = ctypes.c_int32

    class EventHotKeyID(ctypes.Structure):
        _fields_ = [('signature', ctypes.c_uint32), ('id', ctypes.c_uint32)]

    class EventTypeSpec(ctypes.Structure):
        _fields_ = [('eventClass', ctypes.c_uint32), ('eventKind', ctypes.c_uint32)]

    EventHandlerProcPtr = ctypes.CFUNCTYPE(
        OSStatus, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    return OSStatus, EventHotKeyID, EventTypeSpec, EventHandlerProcPtr


def _register_hotkey(app: 'NSPanelProbeApp') -> None:
    OSStatus, EventHotKeyID, EventTypeSpec, EventHandlerProcPtr = _hotkey_ctypes_defs()

    def _on_hotkey(handler_ref, event, user_data):
        try:
            app._nsapp.nsstatusitem.button().performClick_(None)
        except Exception as exc:
            print(f'hotkey click failed: {exc!r}', file=sys.stderr)
        return 0

    cb = EventHandlerProcPtr(_on_hotkey)
    carbon = ctypes.CDLL('/System/Library/Frameworks/Carbon.framework/Carbon')

    carbon.GetApplicationEventTarget.restype  = ctypes.c_void_p
    carbon.GetApplicationEventTarget.argtypes = []
    target = carbon.GetApplicationEventTarget()

    spec = EventTypeSpec(0x6B657962, 6)
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
        37, 0x0100,
        EventHotKeyID(0x4D424152, 1),
        target, 0, ctypes.byref(hk_ref))

    app._hotkey_cb  = cb
    app._hotkey_ref = hk_ref
