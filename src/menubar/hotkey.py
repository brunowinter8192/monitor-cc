# INFRASTRUCTURE
import ctypes

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
