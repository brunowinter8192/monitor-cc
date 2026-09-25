# INFRASTRUCTURE
import ctypes
import signal
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Tuple

from AppKit import NSEvent, NSScreen, NSWorkspace

_REPORTS_DIR = Path(__file__).parent / "log"

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


# ORCHESTRATOR

def probe_workflow() -> None:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    run_ts = time.strftime('%Y%m%d_%H%M%S')
    log_path = compute_log_path(run_ts)
    logf = open(log_path, 'a', encoding='utf-8')
    print_log(log_path)
    run_write(logf)
    logf.flush()

    cid = _CG.CGSMainConnectionID()
    buffer = assign_values()
    state = compute_state()

    _shutdown = make_shutdown_handler(state)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    prev_space = _active_space(cid)
    guarded_write(state, cid, buffer, prev_space, logf)


# FUNCTIONS

def compute_log_path(run_ts):
    return _REPORTS_DIR / f'space_jump_{run_ts}.log'


def print_log(log_path):
    print(f'Log: {log_path}')


def run_write(logf):
    logf.write(f'=== Space-Jump Probe started {_timestamp()} '
               f'(poll={_POLL_HZ}Hz buffer={_BUFFER_SECONDS}s edge_px={_EDGE_PX}) ===\n')


def _timestamp() -> str:
    t = time.time()
    ms = int((t - int(t)) * 1000)
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(t)) + f'.{ms:03d}'


def assign_values():
    buffer: Deque[Dict] = deque(maxlen=_BUFFER_LEN)
    return buffer


def compute_state():
    return {'running': True}


def make_shutdown_handler(state):
    def _shutdown(signum, frame):
        state['running'] = False
    return _shutdown


def _active_space(cid: int) -> int:
    return _CG.CGSGetActiveSpace(cid)


def guarded_write(state, cid, buffer, prev_space, logf):
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


def _mouse_position() -> Tuple[float, float]:
    loc = NSEvent.mouseLocation()
    return loc.x, loc.y


def _at_edge(x: float, y: float) -> bool:
    for screen in NSScreen.screens():
        f = screen.frame()
        x0, y0 = f.origin.x, f.origin.y
        x1, y1 = x0 + f.size.width, y0 + f.size.height
        if x0 <= x <= x1 and y0 <= y <= y1:
            return (x - x0 <= _EDGE_PX or x1 - x <= _EDGE_PX or
                    y - y0 <= _EDGE_PX or y1 - y <= _EDGE_PX)
    return True


def _left_button_down() -> bool:
    return bool(NSEvent.pressedMouseButtons() & 0x1)


def _frontmost_app() -> str:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.localizedName() if app else ""


def _dump_jump(logf, buffer: Deque[Dict], old_space: int, new_space: int) -> None:
    logf.write(f"\n### JUMP {_timestamp()}  space {old_space} -> {new_space}"
               f"  (buffer: {len(buffer)} samples)\n")
    for s in buffer:
        logf.write(_format_sample(s) + '\n')
    logf.flush()


def _format_sample(s: Dict) -> str:
    return (f"{s['ts']}  x={s['x']:.0f} y={s['y']:.0f} at_edge={s['at_edge']}"
            f" left_down={s['left_down']} space={s['space_id']} app={s['app']}")


if __name__ == '__main__':
    probe_workflow()
