# INFRASTRUCTURE
from Foundation import NSOperationQueue

from src.menubar.menubar_log import log_menubar
from src.menubar.panel import _reposition_panel, _reposition_tab_panel
from src.menubar.panel_tabs import TAB_KEYS

_RING = TAB_KEYS

# FUNCTIONS

def _panel_of(app: 'CCMenuBarApp', name: str):
    if name == 'main':   return app.panel._widgets.panel
    if name == 'rag':    return app.rag._rag_panel
    if name == 'models': return app.models._models_panel
    return app.launch._launch_panel

def _open_tab_name(app: 'CCMenuBarApp'):
    if app.panel._panel_open:      return 'main'
    if app.rag._rag_open:          return 'rag'
    if app.models._models_open:    return 'models'
    if app.launch._launch_open:    return 'launch'
    return None

def _close_panel(app: 'CCMenuBarApp', name: str) -> None:
    if name == 'main':     _close_main_panel(app)
    elif name == 'rag':    _close_rag_panel(app)
    elif name == 'models': _close_models_panel(app)
    else:                  _close_launch_panel(app)

def _open_panel(app: 'CCMenuBarApp', name: str) -> None:
    if name == 'main':     _open_main_panel(app)
    elif name == 'rag':    _open_rag_panel(app)
    elif name == 'models': _open_models_panel(app)
    else:                  _open_launch_panel(app)

def _neighbor(name: str, step: int) -> str:
    return _RING[(_RING.index(name) + step) % len(_RING)]

def _register_ring_arrows(app: 'CCMenuBarApp', name: str) -> None:
    app.hotkey.register_arrow_right(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, name, _neighbor(name, 1))))
    app.hotkey.register_arrow_left(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, name, _neighbor(name, -1))))

def _deferred_close_open(app: 'CCMenuBarApp', from_panel: str, to_panel: str) -> None:
    try:
        from_frame = _panel_of(app, from_panel).frame()
        _close_panel(app, from_panel)
        _open_panel(app, to_panel)
        _panel_of(app, to_panel).setFrame_display_(from_frame, True)
    except Exception as e:
        log_menubar('panel', f'cycling {from_panel}->{to_panel} error: {e!r}')

def _background_panel(app: 'CCMenuBarApp') -> None:
    try:
        open_tab = _open_tab_name(app)
        if app.panel._panel_backgrounded:
            if open_tab is not None:
                panel = _panel_of(app, open_tab)
                panel.setLevel_(25)
                panel.orderFrontRegardless()
            app.panel._panel_backgrounded = False
        elif open_tab is not None:
            panel = _panel_of(app, open_tab)
            panel.setLevel_(0)
            panel.orderBack_(None)
            app.panel._panel_backgrounded = True
    except Exception as e:
        log_menubar('panel', f'Cmd+K deferred-block error: {e!r}')

def _open_main_panel(app: 'CCMenuBarApp') -> None:
    sessions = app.sessions.refresh()
    bg_by_project = app.sessions.bg_by_project
    app.panel.rebuild(sessions, bg_by_project)
    _reposition_panel(app.panel._widgets.panel, app._nsapp.nsstatusitem)
    app.panel._widgets.panel.orderFrontRegardless()
    app.panel._widgets.panel.enableCursorRects()
    app.panel._panel_open = True
    app.hotkey.reregister_digits(app.panel._lookups.desktop_to_cwd)
    _register_ring_arrows(app, 'main')

def _close_main_panel(app: 'CCMenuBarApp') -> None:
    app.panel._widgets.panel.orderOut_(None)
    app.panel._panel_open = False
    app.panel._panel_backgrounded = False
    app.hotkey.unregister_digits()
    app.hotkey.unregister_arrow_right()
    app.hotkey.unregister_arrow_left()

def _open_rag_panel(app: 'CCMenuBarApp') -> None:
    app.rag.rebuild()
    _reposition_tab_panel(app.rag._rag_panel, app._nsapp.nsstatusitem)
    app.rag._rag_panel.orderFrontRegardless()
    app.rag._rag_panel.enableCursorRects()
    app.rag._rag_open = True
    _register_ring_arrows(app, 'rag')

def _close_rag_panel(app: 'CCMenuBarApp') -> None:
    app.rag._rag_panel.orderOut_(None)
    app.rag._rag_open = False
    app.panel._panel_backgrounded = False
    app.hotkey.unregister_arrow_right()
    app.hotkey.unregister_arrow_left()

def _open_models_panel(app: 'CCMenuBarApp') -> None:
    app.models.open()
    _reposition_tab_panel(app.models._models_panel, app._nsapp.nsstatusitem)
    app.models._models_panel.orderFrontRegardless()
    app.models._models_panel.enableCursorRects()
    app.models._models_open = True
    _register_ring_arrows(app, 'models')

def _close_models_panel(app: 'CCMenuBarApp') -> None:
    app.models._models_panel.orderOut_(None)
    app.models._models_open = False
    app.panel._panel_backgrounded = False
    app.hotkey.unregister_arrow_right()
    app.hotkey.unregister_arrow_left()

def _open_launch_panel(app: 'CCMenuBarApp') -> None:
    app.launch.open()
    _reposition_tab_panel(app.launch._launch_panel, app._nsapp.nsstatusitem)
    app.launch._launch_panel.orderFrontRegardless()
    app.launch._launch_panel.enableCursorRects()
    app.launch._launch_open = True
    _register_ring_arrows(app, 'launch')

def _close_launch_panel(app: 'CCMenuBarApp') -> None:
    app.launch._launch_panel.orderOut_(None)
    app.launch._launch_open = False
    app.panel._panel_backgrounded = False
    app.hotkey.unregister_arrow_right()
    app.hotkey.unregister_arrow_left()
