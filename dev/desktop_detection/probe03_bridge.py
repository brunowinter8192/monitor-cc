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
_IMP     = ctypes.cast(_OBJ.objc_msgSend, ctypes.c_void_p).value

_CG.CGSMainConnectionID.argtypes         = []
_CG.CGSMainConnectionID.restype          = ctypes.c_int32
_CG.CGSCopySpacesForWindows.argtypes     = [ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p]
_CG.CGSCopySpacesForWindows.restype      = ctypes.c_void_p
_CG.CGWindowListCopyWindowInfo.argtypes  = [ctypes.c_uint32, ctypes.c_uint32]
_CG.CGWindowListCopyWindowInfo.restype   = ctypes.c_void_p

_LIBPROC               = ctypes.CDLL('/usr/lib/libproc.dylib')
_LIBPROC.proc_pidinfo.restype  = ctypes.c_int
_LIBPROC.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                   ctypes.c_void_p, ctypes.c_int]

# FUNCTIONS

def _sel(s):           return _OBJ.sel_registerName(s.encode())
def _msg1v(o, s, a):   return ctypes.cast(_IMP, _FT_vvv)(o, _sel(s), a)
def _msg1cp(o, s, a):  return ctypes.cast(_IMP, _FT_vvcp)(o, _sel(s), a)
def _msg1l(o, s, a):   return ctypes.cast(_IMP, _FT_vvl)(o, _sel(s), ctypes.c_long(a))
def _msgl(o, s):       return ctypes.cast(_IMP, _FT_lvv)(o, _sel(s))
def _msgp(o, s):       return ctypes.cast(_IMP, _FT_pvv)(o, _sel(s))

def _nsstr(s: str):
    return _msg1cp(_OBJ.objc_getClass(b"NSString"), "stringWithUTF8String:", s.encode())

def _cf_count(a) -> int:   return _msgl(a, "count")
def _cf_at(a, i: int):     return _msg1l(a, "objectAtIndex:", i)
def _dict_val(d, k: str):  return _msg1v(d, "objectForKey:", _nsstr(k))

def _dict_str(d, k: str) -> Optional[str]:
    v = _dict_val(d, k)
    r = _msgp(v, "UTF8String") if v else None
    return r.decode() if r else None

def _dict_long(d, k: str) -> Optional[int]:
    v = _dict_val(d, k)
    return _msgl(v, "intValue") if v else None

def _make_uint_array(vals: List[int]):
    NSA = _OBJ.objc_getClass(b"NSMutableArray")
    NSN = _OBJ.objc_getClass(b"NSNumber")
    arr = ctypes.cast(_IMP, _FT_vv)(NSA, _sel("array"))
    for v in vals:
        n = ctypes.cast(_IMP, _FT_vvl)(NSN, _sel("numberWithUnsignedInt:"), ctypes.c_long(v))
        ctypes.cast(_IMP, _FT_nvv)(arr, _sel("addObject:"), n)
    return arr

# Return human-readable string description of any NSObject via [obj description] → UTF8String
def _cf_describe(v) -> Optional[str]:
    if not v:
        return None
    ns = ctypes.cast(_IMP, _FT_vv)(v, _sel("description"))
    if not ns:
        return None
    r = _msgp(ns, "UTF8String")
    return r.decode('utf-8', errors='replace') if r else None

# Return all string keys from a CF/NS dictionary via [d allKeys]
def _dict_all_keys(d) -> List[str]:
    arr = ctypes.cast(_IMP, _FT_vv)(d, _sel("allKeys"))
    if not arr:
        return []
    result = []
    for i in range(_cf_count(arr)):
        k = _cf_at(arr, i)
        r = _msgp(k, "UTF8String")
        if r:
            result.append(r.decode('utf-8', errors='replace'))
    return result
