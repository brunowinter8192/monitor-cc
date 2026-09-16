# INFRASTRUCTURE
import sys
import time

from AppKit import NSEvent, NSEventMaskMouseMoved, NSTrackingArea

from cursor_edges_constants import _TA_OPTS

# FUNCTIONS

def _log(msg: str) -> None:
    t = time.strftime('%H:%M:%S')
    print(f'[{t}] {msg}', file=sys.stderr, flush=True)


def _dump_hierarchy(view, indent: int = 0) -> None:
    cls = type(view).__name__
    f   = view.frame()
    _log(
        f'{"  " * indent}{cls}  '
        f'frame=({f.origin.x:.0f},{f.origin.y:.0f} '
        f'{f.size.width:.0f}×{f.size.height:.0f})'
    )
    for sv in view.subviews():
        _dump_hierarchy(sv, indent + 1)


def _install_tracking_area(view) -> None:
    for ta in list(view.trackingAreas()):
        view.removeTrackingArea_(ta)
    ta = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
        view.bounds(), _TA_OPTS, view, None)
    view.addTrackingArea_(ta)


def _install_global_mouse_monitor() -> None:
    def _handler(event):
        pt = event.locationInWindow()
        win = event.window()
        win_cls = type(win).__name__ if win else 'None'
        _log(
            f'NSEventMonitor  mouseMoved  loc=({pt.x:.1f},{pt.y:.1f})'
            f'  window={win_cls}'
        )
        return event
    NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
        NSEventMaskMouseMoved, _handler)
