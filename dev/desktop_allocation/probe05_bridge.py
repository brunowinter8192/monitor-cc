# INFRASTRUCTURE
import ctypes
from typing import List, Optional

_CG  = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
_OBJ = ctypes.CDLL('/usr/lib/libobjc.A.dylib')

_OBJ.sel_registerName.restype  = ctypes.c_void_p
_OBJ.sel_registerName.argtypes = [ctypes.c_char_p]
_OBJ.objc_getClass.restype     = ctypes.c_void_p
_OBJ.objc_getClass.argtypes    = [ctypes.c_char_p]

_FT_vv   = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_vvv  = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_vvcp = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)
_FT_vvl  = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)
_FT_lvv  = ctypes.CFUNCTYPE(ctypes.c_long,   ctypes.c_void_p, ctypes.c_void_p)
_FT_pvv  = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p)
_FT_nvv  = ctypes.CFUNCTYPE(None,            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

_IMP = ctypes.cast(_OBJ.objc_msgSend, ctypes.c_void_p).value

_CG.CGSMainConnectionID.argtypes         = []
_CG.CGSMainConnectionID.restype          = ctypes.c_int32
_CG.CGSGetActiveSpace.argtypes           = [ctypes.c_int32]
_CG.CGSGetActiveSpace.restype            = ctypes.c_uint64
_CG.CGSCopyManagedDisplaySpaces.argtypes = [ctypes.c_int32]
_CG.CGSCopyManagedDisplaySpaces.restype  = ctypes.c_void_p
_CG.CGSCopySpacesForWindows.argtypes     = [ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p]
_CG.CGSCopySpacesForWindows.restype      = ctypes.c_void_p
_CG.CGWindowListCopyWindowInfo.argtypes  = [ctypes.c_uint32, ctypes.c_uint32]
_CG.CGWindowListCopyWindowInfo.restype   = ctypes.c_void_p

# FUNCTIONS


def _sel(s: str):
    return _OBJ.sel_registerName(s.encode())

def _msg1v(obj, s: str, a):
    return ctypes.cast(_IMP, _FT_vvv)(obj, _sel(s), a)

def _msg1cp(obj, s: str, a: bytes):
    return ctypes.cast(_IMP, _FT_vvcp)(obj, _sel(s), a)

def _msg1l(obj, s: str, a: int):
    return ctypes.cast(_IMP, _FT_vvl)(obj, _sel(s), ctypes.c_long(a))

def _msgl(obj, s: str) -> int:
    return ctypes.cast(_IMP, _FT_lvv)(obj, _sel(s))

def _msgp(obj, s: str):
    return ctypes.cast(_IMP, _FT_pvv)(obj, _sel(s))

def _nsstr(s: str):
    cls = _OBJ.objc_getClass(b"NSString")
    return _msg1cp(cls, "stringWithUTF8String:", s.encode())

def _cf_count(arr) -> int:
    return _msgl(arr, "count")

def _cf_at(arr, i: int):
    return _msg1l(arr, "objectAtIndex:", i)

def _dict_val(d, key: str):
    return _msg1v(d, "objectForKey:", _nsstr(key))

def _dict_str(d, key: str) -> Optional[str]:
    v = _dict_val(d, key)
    if not v:
        return None
    r = _msgp(v, "UTF8String")
    return r.decode() if r else None

def _dict_long(d, key: str) -> Optional[int]:
    v = _dict_val(d, key)
    return _msgl(v, "intValue") if v else None

def _make_uint_array(values: List[int]):
    NSMutableArray = _OBJ.objc_getClass(b"NSMutableArray")
    NSNumber       = _OBJ.objc_getClass(b"NSNumber")
    arr = ctypes.cast(_IMP, _FT_vv)(NSMutableArray, _sel("array"))
    for v in values:
        n = ctypes.cast(_IMP, _FT_vvl)(NSNumber, _sel("numberWithUnsignedInt:"), ctypes.c_long(v))
        ctypes.cast(_IMP, _FT_nvv)(arr, _sel("addObject:"), n)
    return arr
