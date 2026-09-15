# INFRASTRUCTURE
import ctypes
import subprocess
from pathlib import Path
from typing import List

from probe04_bridge import _FT_0vv, _FT_vv, _FT_vvvu64, _IMP, _OBJ, _make_uint_array, _sel

# FUNCTIONS

# SLSBridgedMoveWindowsToManagedSpaceOperation — DockDoor / yabai technique.
# Class hierarchy on 26.5: SLSBridgedMoveWindowsToManagedSpaceOperation
#   → SLSAsynchronousBridgedWindowManagementOperation (defines performWithWMBridgeDelegate)
# performWithWMBridgeDelegate returns void — success verified externally via on-screen list.
def _bridged_move(wids: List[int], target_space_id: int) -> None:
    cls = _OBJ.objc_getClass(b"SLSBridgedMoveWindowsToManagedSpaceOperation")
    if not cls:
        raise RuntimeError("SLSBridgedMoveWindowsToManagedSpaceOperation not found — requires macOS 26")
    allocated = ctypes.cast(_IMP, _FT_vv)(cls, _sel("alloc"))
    if not allocated:
        raise RuntimeError("alloc returned nil")
    ns_array  = _make_uint_array(wids)
    operation = ctypes.cast(_IMP, _FT_vvvu64)(
        allocated, _sel("initWithWindows:spaceID:"),
        ns_array, ctypes.c_uint64(target_space_id),
    )
    if not operation:
        raise RuntimeError("initWithWindows:spaceID: returned nil")
    ctypes.cast(_IMP, _FT_0vv)(operation, _sel("performWithWMBridgeDelegate"))

def _take_screenshot(path: Path) -> None:
    subprocess.run(["screencapture", "-x", str(path)], check=True, timeout=5)
