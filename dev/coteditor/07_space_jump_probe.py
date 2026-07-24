# INFRASTRUCTURE
import ctypes
import signal
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Tuple

from AppKit import NSEvent, NSScreen, NSWorkspace

_REPORTS_DIR = Path(__file__).parent / "07_reports"

_CG = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
_CG.CGSMainConnectionID.argtypes = []
_CG.CGSMainConnectionID.restype  = ctypes.c_int32
_CG.CGSGetActiveSpace.argtypes   = [ctypes.c_int32]
_CG.CGSGetActiveSpace.restype    = ctypes.c_uint64

_EDGE_PX        = 3
_POLL_HZ        = 10
_POLL_INTERVAL  = 1.0 / _POLL_HZ
_BUFFER_SECONDS = 10
_BUFFER_LEN     = _POLL_HZ * _BUFFER_SECONDS


# FUNCTIONS

# True when bit 0 (left button) of NSEvent.pressedMouseButtons() is set
def _left_button_down() -> bool:
    return bool(NSEvent.pressedMouseButtons() & 0x1)

# Global mouse position, bottom-left origin (NSEvent.mouseLocation semantics)
def _mouse_position() -> Tuple[float, float]:
    loc = NSEvent.mouseLocation()
    return loc.x, loc.y

# True when (x, y) is within _EDGE_PX of any edge of its containing NSScreen;
# also True when no screen contains the point (cursor pushed past all bounds)
def _at_edge(x: float, y: float) -> bool:
    for screen in NSScreen.screens():
        f = screen.frame()
        x0, y0 = f.origin.x, f.origin.y
        x1, y1 = x0 + f.size.width, y0 + f.size.height
        if x0 <= x <= x1 and y0 <= y <= y1:
            return (x - x0 <= _EDGE_PX or x1 - x <= _EDGE_PX or
                    y - y0 <= _EDGE_PX or y1 - y <= _EDGE_PX)
    return True

# Frontmost application's localized name, "" if unavailable
def _frontmost_app() -> str:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.localizedName() if app else ""

# Active Space ID via CGS bridge (connection ID + active space, no full space map needed)
def _active_space(cid: int) -> int:
    return _CG.CGSGetActiveSpace(cid)

# Wall-clock timestamp, millisecond precision
def _timestamp() -> str:
    t = time.time()
    ms = int((t - int(t)) * 1000)
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(t)) + f'.{ms:03d}'

# One poll: all required fields for a single sample
def _take_sample(cid: int) -> Dict:
    x, y = _mouse_position()
    return {
        'ts':         _timestamp(),
        'x':          x,
        'y':          y,
        'at_edge':    _at_edge(x, y),
        'left_down':  _left_button_down(),
        'space_id':   _active_space(cid),
        'app':        _frontmost_app(),
    }

# Dense one-line rendering of a sample
def _format_sample(s: Dict) -> str:
    return (f"{s['ts']}  x={s['x']:.0f} y={s['y']:.0f} at_edge={s['at_edge']}"
            f" left_down={s['left_down']} space={s['space_id']} app={s['app']}")

# Write JUMP header + full rolling buffer to the log, flush immediately
def _dump_jump(logf, buffer: Deque[Dict], old_space: int, new_space: int) -> None:
    logf.write(f"\n### JUMP {_timestamp()}  space {old_space} -> {new_space}"
               f"  (buffer: {len(buffer)} samples)\n")
    for s in buffer:
        logf.write(_format_sample(s) + '\n')
    logf.flush()


# ORCHESTRATOR

def probe_workflow() -> None:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    run_ts = time.strftime('%Y%m%d_%H%M%S')
    log_path = _REPORTS_DIR / f'space_jump_{run_ts}.log'
    logf = open(log_path, 'a', encoding='utf-8')
    print(f'Log: {log_path}')
    logf.write(f'=== Space-Jump Probe started {_timestamp()} '
               f'(poll={_POLL_HZ}Hz buffer={_BUFFER_SECONDS}s edge_px={_EDGE_PX}) ===\n')
    logf.flush()

    cid = _CG.CGSMainConnectionID()
    buffer: Deque[Dict] = deque(maxlen=_BUFFER_LEN)
    state = {'running': True}

    def _shutdown(signum, frame):
        state['running'] = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    prev_space = _active_space(cid)
    try:
        while state['running']:
            loop_start = time.monotonic()
            sample = _take_sample(cid)
            buffer.append(sample)
            if sample['space_id'] != prev_space:
                _dump_jump(logf, buffer, prev_space, sample['space_id'])
                print(f"JUMP: space {prev_space} -> {sample['space_id']} at {sample['ts']}")
                prev_space = sample['space_id']
            elapsed = time.monotonic() - loop_start
            time.sleep(max(0.0, _POLL_INTERVAL - elapsed))
    finally:
        logf.write(f'=== Space-Jump Probe stopped {_timestamp()} ===\n')
        logf.flush()
        logf.close()


if __name__ == '__main__':
    probe_workflow()
