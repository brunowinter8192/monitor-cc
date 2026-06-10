# INFRASTRUCTURE
import sys

from Foundation import NSOperationQueue

# From discover.py: Live session discovery
from .discover import list_alive_sessions
# From bg_timer.py: Background sleep-timer scanning
from .bg_timer import _scan_bg_sleep_timers
# From panel.py: NSPanel repositioning
from .panel import _reposition_panel
# From rag_controller.py: RAG panel repositioning
from .rag_controller import _reposition_rag_panel
# From queue_controller.py: queue panel repositioning
from .queue_controller import _reposition_queue_panel

# FUNCTIONS

# Generic deferred panel switch for Cmd+→/← cycling.
# Safety-net: exceptions must not propagate to ObjC (NSBlockOperation has no Python bridge → SIGABRT).
# Cycling order: Sessions → RAG → Queue → Sessions (Cmd+→); reverse for Cmd+←.
# Captures outgoing panel frame before close; restores position+size to incoming panel after open,
# so user-dragged position and width are preserved across cycles (the _open_* _reposition_* calls
# would otherwise re-center the panel under the status bar icon on every cycle).
def _deferred_close_open(app: 'CCMenuBarApp', from_panel: str, to_panel: str) -> None:
    try:
        if from_panel == 'main':  from_obj = app.panel._panel
        elif from_panel == 'rag': from_obj = app.rag._rag_panel
        else:                     from_obj = app.queue._queue_panel
        from_frame = from_obj.frame()   # capture before close
        if from_panel == 'main':  _close_main_panel(app)
        elif from_panel == 'rag': _close_rag_panel(app)
        elif from_panel == 'queue': _close_queue_panel(app)
        if to_panel == 'main':    _open_main_panel(app)
        elif to_panel == 'rag':   _open_rag_panel(app)
        elif to_panel == 'queue': _open_queue_panel(app)
        if to_panel == 'main':    to_obj = app.panel._panel
        elif to_panel == 'rag':   to_obj = app.rag._rag_panel
        else:                     to_obj = app.queue._queue_panel
        to_obj.setFrame_display_(from_frame, True)   # restore position; display:True flushes immediately
    except Exception as e:
        print(f'[menubar] cycling {from_panel}→{to_panel} error: {e}', file=sys.stderr)

# Cmd+K handler: toggle active panel between foreground and background (orderBack_/orderFrontRegardless).
# Does NOT close the panel — _panel_open / _rag_open / _queue_open stay True.
# Cycling (Cmd+→/←) resets _panel_backgrounded via _close_main/rag/queue_panel before opening the other.
def _background_panel(app: 'CCMenuBarApp') -> None:
    try:
        if app._panel_backgrounded:
            if app.panel._panel_open:
                app.panel._panel.setLevel_(25)   # NSStatusWindowLevel — restore before foregrounding
                app.panel._panel.orderFrontRegardless()
            elif app.rag._rag_open:
                app.rag._rag_panel.setLevel_(25)   # NSStatusWindowLevel
                app.rag._rag_panel.orderFrontRegardless()
            elif app.queue._queue_open:
                app.queue._queue_panel.setLevel_(25)   # NSStatusWindowLevel
                app.queue._queue_panel.orderFrontRegardless()
            app._panel_backgrounded = False
        elif app.panel._panel_open:
            app.panel._panel.setLevel_(0)   # NSNormalWindowLevel — allows orderBack_ to work
            app.panel._panel.orderBack_(None)
            app._panel_backgrounded = True
        elif app.rag._rag_open:
            app.rag._rag_panel.setLevel_(0)   # NSNormalWindowLevel
            app.rag._rag_panel.orderBack_(None)
            app._panel_backgrounded = True
        elif app.queue._queue_open:
            app.queue._queue_panel.setLevel_(0)   # NSNormalWindowLevel
            app.queue._queue_panel.orderBack_(None)
            app._panel_backgrounded = True
    except Exception as e:
        print(f'[menubar] Cmd+K deferred-block error: {e}', file=sys.stderr)

# Open main panel: rebuild → reposition → show → register Cmd+→ (→RAG) + Cmd+← (→Queue wrap) + Cmd+1..9
def _open_main_panel(app: 'CCMenuBarApp') -> None:
    sessions = app.sessions.refresh()
    cwd_to_project = {s.cwd: s.project_name for s in sessions if not s.is_worker and s.cwd}
    bg_by_project = _scan_bg_sleep_timers(cwd_to_project)
    app.panel.rebuild(sessions, bg_by_project)
    _reposition_panel(app.panel._panel, app._nsapp.nsstatusitem)
    app.panel._panel.orderFrontRegardless()
    app.panel._panel.enableCursorRects()
    app.panel._panel_open = True
    app.hotkey.reregister_digits(app.panel._desktop_to_cwd)
    app.hotkey.register_arrow_right(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'main', 'rag')))
    app.hotkey.register_arrow_left(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'main', 'queue')))

# Close main panel: hide + unregister Cmd+→ + Cmd+← + Cmd+1..9
def _close_main_panel(app: 'CCMenuBarApp') -> None:
    app.panel._panel.orderOut_(None)
    app.panel._panel_open = False
    app._panel_backgrounded = False
    app.hotkey.unregister_digits()
    app.hotkey.unregister_arrow_right()
    app.hotkey.unregister_arrow_left()

# Open RAG panel: rebuild → reposition → show + register Cmd+→ (→Queue) + Cmd+← (→Sessions)
def _open_rag_panel(app: 'CCMenuBarApp') -> None:
    app.rag.rebuild()
    _reposition_rag_panel(app.rag._rag_panel, app._nsapp.nsstatusitem)
    app.rag._rag_panel.orderFrontRegardless()
    app.rag._rag_panel.enableCursorRects()
    app.rag._rag_open = True
    app.hotkey.register_arrow_right(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'rag', 'queue')))
    app.hotkey.register_arrow_left(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'rag', 'main')))

# Close RAG panel: hide + unregister Cmd+→ + Cmd+←
def _close_rag_panel(app: 'CCMenuBarApp') -> None:
    app.rag._rag_panel.orderOut_(None)
    app.rag._rag_open = False
    app._panel_backgrounded = False
    app.hotkey.unregister_arrow_right()
    app.hotkey.unregister_arrow_left()

# Open queue panel: load data + rebuild → reposition → show + register Cmd+→ (→Sessions wrap) + Cmd+← (→RAG)
def _open_queue_panel(app: 'CCMenuBarApp') -> None:
    sessions = app.sessions.refresh()
    app.queue.open(sessions)
    _reposition_queue_panel(app.queue._queue_panel, app._nsapp.nsstatusitem)
    app.queue._queue_panel.orderFrontRegardless()
    app.queue._queue_panel.enableCursorRects()
    app.queue._queue_open = True
    app.hotkey.register_arrow_right(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'queue', 'main')))
    app.hotkey.register_arrow_left(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'queue', 'rag')))

# Close queue panel: hide + unregister Cmd+→ + Cmd+←
def _close_queue_panel(app: 'CCMenuBarApp') -> None:
    app.queue._queue_panel.orderOut_(None)
    app.queue._queue_open = False
    app._panel_backgrounded = False
    app.hotkey.unregister_arrow_right()
    app.hotkey.unregister_arrow_left()
