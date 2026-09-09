# INFRASTRUCTURE
import sys

from Foundation import NSOperationQueue

# From panel.py: NSPanel repositioning
from .panel import _reposition_panel
# From rag_controller.py: RAG panel repositioning
from .rag_controller import _reposition_rag_panel
# From model_panel_ui.py: Models panel repositioning
from .model_panel_ui import _reposition_models_panel

# FUNCTIONS

# Generic deferred panel switch for Cmd+→/← cycling.
# Safety-net: exceptions must not propagate to ObjC (NSBlockOperation has no Python bridge → SIGABRT).
# Cycling order: Sessions → RAG → Models → Sessions (Cmd+→); reverse for Cmd+←.
# Captures outgoing panel frame before close; restores position+size to incoming panel after open,
# so user-dragged position and width are preserved across cycles (the _open_* _reposition_* calls
# would otherwise re-center the panel under the status bar icon on every cycle).
def _deferred_close_open(app: 'CCMenuBarApp', from_panel: str, to_panel: str) -> None:
    try:
        if from_panel == 'main':  from_obj = app.panel._widgets.panel
        elif from_panel == 'rag': from_obj = app.rag._rag_panel
        else:                     from_obj = app.models._models_panel
        from_frame = from_obj.frame()   # capture before close
        if from_panel == 'main':  _close_main_panel(app)
        elif from_panel == 'rag': _close_rag_panel(app)
        else:                     _close_models_panel(app)
        if to_panel == 'main':    _open_main_panel(app)
        elif to_panel == 'rag':   _open_rag_panel(app)
        else:                     _open_models_panel(app)
        if to_panel == 'main':    to_obj = app.panel._widgets.panel
        elif to_panel == 'rag':   to_obj = app.rag._rag_panel
        else:                     to_obj = app.models._models_panel
        to_obj.setFrame_display_(from_frame, True)   # restore position; display:True flushes immediately
    except Exception as e:
        print(f'[menubar] cycling {from_panel}→{to_panel} error: {e}', file=sys.stderr)

# Cmd+K handler: toggle active panel between foreground and background (orderBack_/orderFrontRegardless).
# Does NOT close the panel — _panel_open / _rag_open / _models_open stay True.
# Cycling (Cmd+→/←) resets _panel_backgrounded via _close_main/rag/models_panel before opening the other.
def _background_panel(app: 'CCMenuBarApp') -> None:
    try:
        if app.panel._panel_backgrounded:
            if app.panel._panel_open:
                app.panel._widgets.panel.setLevel_(25)   # NSStatusWindowLevel — restore before foregrounding
                app.panel._widgets.panel.orderFrontRegardless()
            elif app.rag._rag_open:
                app.rag._rag_panel.setLevel_(25)   # NSStatusWindowLevel
                app.rag._rag_panel.orderFrontRegardless()
            elif app.models._models_open:
                app.models._models_panel.setLevel_(25)   # NSStatusWindowLevel
                app.models._models_panel.orderFrontRegardless()
            app.panel._panel_backgrounded = False
        elif app.panel._panel_open:
            app.panel._widgets.panel.setLevel_(0)   # NSNormalWindowLevel — allows orderBack_ to work
            app.panel._widgets.panel.orderBack_(None)
            app.panel._panel_backgrounded = True
        elif app.rag._rag_open:
            app.rag._rag_panel.setLevel_(0)   # NSNormalWindowLevel
            app.rag._rag_panel.orderBack_(None)
            app.panel._panel_backgrounded = True
        elif app.models._models_open:
            app.models._models_panel.setLevel_(0)   # NSNormalWindowLevel
            app.models._models_panel.orderBack_(None)
            app.panel._panel_backgrounded = True
    except Exception as e:
        print(f'[menubar] Cmd+K deferred-block error: {e}', file=sys.stderr)

# Open main panel: rebuild → reposition → show → register Cmd+→ (→RAG) + Cmd+← (→Models wrap) + Cmd+1..9
def _open_main_panel(app: 'CCMenuBarApp') -> None:
    # 2026-08 (hotkey_latency M3): consumes the background discovery snapshot (app.sessions) —
    # no direct list_alive_sessions()/_scan_bg_sleep_timers() calls on the main thread anymore.
    sessions = app.sessions.refresh()
    bg_by_project = app.sessions.bg_by_project
    app.panel.rebuild(sessions, bg_by_project)
    _reposition_panel(app.panel._widgets.panel, app._nsapp.nsstatusitem)
    app.panel._widgets.panel.orderFrontRegardless()
    app.panel._widgets.panel.enableCursorRects()
    app.panel._panel_open = True
    app.hotkey.reregister_digits(app.panel._lookups.desktop_to_cwd)
    app.hotkey.register_arrow_right(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'main', 'rag')))
    app.hotkey.register_arrow_left(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'main', 'models')))

# Close main panel: hide + unregister Cmd+→ + Cmd+← + Cmd+1..9
def _close_main_panel(app: 'CCMenuBarApp') -> None:
    app.panel._widgets.panel.orderOut_(None)
    app.panel._panel_open = False
    app.panel._panel_backgrounded = False
    app.hotkey.unregister_digits()
    app.hotkey.unregister_arrow_right()
    app.hotkey.unregister_arrow_left()

# Open RAG panel: rebuild → reposition → show + register Cmd+→ (→Models) + Cmd+← (→Sessions)
def _open_rag_panel(app: 'CCMenuBarApp') -> None:
    app.rag.rebuild()
    _reposition_rag_panel(app.rag._rag_panel, app._nsapp.nsstatusitem)
    app.rag._rag_panel.orderFrontRegardless()
    app.rag._rag_panel.enableCursorRects()
    app.rag._rag_open = True
    app.hotkey.register_arrow_right(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'rag', 'models')))
    app.hotkey.register_arrow_left(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'rag', 'main')))

# Close RAG panel: hide + unregister Cmd+→ + Cmd+←
def _close_rag_panel(app: 'CCMenuBarApp') -> None:
    app.rag._rag_panel.orderOut_(None)
    app.rag._rag_open = False
    app.panel._panel_backgrounded = False
    app.hotkey.unregister_arrow_right()
    app.hotkey.unregister_arrow_left()

# Open Models panel: reload from disk + rebuild → reposition → show + register Cmd+→ (→Sessions wrap) + Cmd+← (→RAG)
def _open_models_panel(app: 'CCMenuBarApp') -> None:
    app.models.open()
    _reposition_models_panel(app.models._models_panel, app._nsapp.nsstatusitem)
    app.models._models_panel.orderFrontRegardless()
    app.models._models_panel.enableCursorRects()
    app.models._models_open = True
    app.hotkey.register_arrow_right(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'models', 'main')))
    app.hotkey.register_arrow_left(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'models', 'rag')))

# Close Models panel: hide + unregister Cmd+→ + Cmd+←
def _close_models_panel(app: 'CCMenuBarApp') -> None:
    app.models._models_panel.orderOut_(None)
    app.models._models_open = False
    app.panel._panel_backgrounded = False
    app.hotkey.unregister_arrow_right()
    app.hotkey.unregister_arrow_left()
