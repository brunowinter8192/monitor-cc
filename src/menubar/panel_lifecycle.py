# INFRASTRUCTURE
import sys

from Foundation import NSOperationQueue

from .panel import _reposition_panel
from .rag_controller import _reposition_rag_panel
from .model_panel_ui import _reposition_models_panel

# FUNCTIONS

def _deferred_close_open(app: 'CCMenuBarApp', from_panel: str, to_panel: str) -> None:
    try:
        if from_panel == 'main':  from_obj = app.panel._widgets.panel
        elif from_panel == 'rag': from_obj = app.rag._rag_panel
        else:                     from_obj = app.models._models_panel
        from_frame = from_obj.frame()
        if from_panel == 'main':  _close_main_panel(app)
        elif from_panel == 'rag': _close_rag_panel(app)
        else:                     _close_models_panel(app)
        if to_panel == 'main':    _open_main_panel(app)
        elif to_panel == 'rag':   _open_rag_panel(app)
        else:                     _open_models_panel(app)
        if to_panel == 'main':    to_obj = app.panel._widgets.panel
        elif to_panel == 'rag':   to_obj = app.rag._rag_panel
        else:                     to_obj = app.models._models_panel
        to_obj.setFrame_display_(from_frame, True)
    except Exception as e:
        print(f'[menubar] cycling {from_panel}→{to_panel} error: {e}', file=sys.stderr)

def _background_panel(app: 'CCMenuBarApp') -> None:
    try:
        if app.panel._panel_backgrounded:
            if app.panel._panel_open:
                app.panel._widgets.panel.setLevel_(25)
                app.panel._widgets.panel.orderFrontRegardless()
            elif app.rag._rag_open:
                app.rag._rag_panel.setLevel_(25)
                app.rag._rag_panel.orderFrontRegardless()
            elif app.models._models_open:
                app.models._models_panel.setLevel_(25)
                app.models._models_panel.orderFrontRegardless()
            app.panel._panel_backgrounded = False
        elif app.panel._panel_open:
            app.panel._widgets.panel.setLevel_(0)
            app.panel._widgets.panel.orderBack_(None)
            app.panel._panel_backgrounded = True
        elif app.rag._rag_open:
            app.rag._rag_panel.setLevel_(0)
            app.rag._rag_panel.orderBack_(None)
            app.panel._panel_backgrounded = True
        elif app.models._models_open:
            app.models._models_panel.setLevel_(0)
            app.models._models_panel.orderBack_(None)
            app.panel._panel_backgrounded = True
    except Exception as e:
        print(f'[menubar] Cmd+K deferred-block error: {e}', file=sys.stderr)

def _open_main_panel(app: 'CCMenuBarApp') -> None:
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

def _close_main_panel(app: 'CCMenuBarApp') -> None:
    app.panel._widgets.panel.orderOut_(None)
    app.panel._panel_open = False
    app.panel._panel_backgrounded = False
    app.hotkey.unregister_digits()
    app.hotkey.unregister_arrow_right()
    app.hotkey.unregister_arrow_left()

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

def _close_rag_panel(app: 'CCMenuBarApp') -> None:
    app.rag._rag_panel.orderOut_(None)
    app.rag._rag_open = False
    app.panel._panel_backgrounded = False
    app.hotkey.unregister_arrow_right()
    app.hotkey.unregister_arrow_left()

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

def _close_models_panel(app: 'CCMenuBarApp') -> None:
    app.models._models_panel.orderOut_(None)
    app.models._models_open = False
    app.panel._panel_backgrounded = False
    app.hotkey.unregister_arrow_right()
    app.hotkey.unregister_arrow_left()
