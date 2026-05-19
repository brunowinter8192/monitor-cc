# INFRASTRUCTURE
import ctypes
import os
import sys
import threading
import time
from itertools import groupby

# Project root on path so 'src.menubar.discover' resolves when run from any CWD
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import objc
import rumps
from AppKit import (
    NSAttributedString, NSColor, NSFont,
    NSFontAttributeName, NSForegroundColorAttributeName,
    NSPanel, NSStatusWindowLevel, NSTextView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSMakeRect, NSObject, NSRunLoop

# From discover.py: Live session discovery
from src.menubar.discover import list_alive_sessions
# From bg_timer.py: Background sleep-timer scanning
from src.menubar.bg_timer import _scan_bg_sleep_timers

ICON_NORMAL    = '◉'
ICON_BLINK     = '●'
BLINK_DURATION = 0.2
POLL_INTERVAL  = 1.5
_NAME_WIDTH    = 22
_MENLO         = lambda: NSFont.fontWithName_size_('Menlo', 13.0)

_BADGE_WORKING = '[*]'
_BADGE_IDLE    = '[ ]'
_NO_BG         = '   '

PANEL_WIDTH  = 360
PANEL_HEIGHT = 440
PANEL_GAP    = 4   # pts below the status bar


# ORCHESTRATOR

# Entry point: suppress Dock icon, create probe app, start run loop
def run() -> None:
    os.environ.setdefault('LSUIElement', '1')
    app = NSPanelProbeApp()
    app.run()


# FUNCTIONS

# NSObject target for NSStatusBarButton action and Cmd+L performClick_
class _PanelController(NSObject):
    def initWithApp_(self, app):
        self = objc.super(_PanelController, self).init()
        if self is None:
            return None
        self._app = app
        return self

    def togglePanel_(self, sender):
        app = self._app
        if app._panel_open:
            app._panel.orderOut_(None)
            app._panel_open = False
        else:
            _reposition_panel(app._panel, app._nsapp.nsstatusitem)
            app._panel.orderFrontRegardless()
            app._panel_open = True


# NSPanel probe app — polls CC sessions every 1.5s, panel toggles via Cmd+L / bar click
class NSPanelProbeApp(rumps.App):
    def __init__(self):
        super().__init__(ICON_NORMAL, quit_button='Quit', menu=[])
        self._panel_open: bool = False
        self._initialized: bool = False
        self._last_statuses: dict = {}
        self._panel, self._panel_tv = _make_nspanel()   # NSPanel + its NSTextView
        self._panel_controller = _PanelController.alloc().initWithApp_(self)
        _register_hotkey(self)

    @rumps.timer(POLL_INTERVAL)
    def _tick(self, _sender):
        # Lazy-init: null NSMenu, wire button target/action to _PanelController
        if not self._initialized:
            try:
                self._nsapp.nsstatusitem.setMenu_(None)
                btn = self._nsapp.nsstatusitem.button()
                btn.setTarget_(self._panel_controller)
                btn.setAction_(b'togglePanel:')
                self._initialized = True
            except AttributeError:
                return   # _nsapp not ready yet; retry next tick

        try:
            sessions = list_alive_sessions()
        except Exception:
            sessions = []

        changed = _statuses_changed(sessions, self._last_statuses)
        self._last_statuses = {s.name: s.status for s in sessions}
        if changed:
            _blink(self)

        _update_panel_text(self._panel_tv, sessions)


# True if any session's status differs from last snapshot
def _statuses_changed(sessions, last: dict) -> bool:
    current = {s.name: s.status for s in sessions}
    return current != last


# Flash icon to ICON_BLINK for BLINK_DURATION seconds, then restore
def _blink(app: NSPanelProbeApp) -> None:
    app.title = ICON_BLINK
    threading.Timer(BLINK_DURATION, _restore_icon, args=[app]).start()


# Restore normal icon after blink
def _restore_icon(app: NSPanelProbeApp) -> None:
    app.title = ICON_NORMAL


# Badge for sessions with active background tasks
def _format_bg_badge(remaining) -> str:
    if remaining is None:
        return '[B]'
    mins, secs = divmod(remaining, 60)
    return f'[B {mins}:{secs:02d}]'


# Section header line: ─── ProjectName ──────────
def _make_header(project_name: str) -> str:
    fill = '─' * max(2, 30 - len(project_name))
    return f'─── {project_name} {fill}'


# Build NSPanel (nonactivatingPanel, statusBar level) + NSTextView; return (panel, tv)
def _make_nspanel():
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT),
        NSWindowStyleMaskNonactivatingPanel,  # 128 — no focus steal, no auto-dismiss
        2,     # NSBackingStoreBuffered
        True,
    )
    panel.setLevel_(NSStatusWindowLevel)   # 25 — flush under menu bar
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces |   # 1
        NSWindowCollectionBehaviorIgnoresCycle         # 64
    )
    panel.setHasShadow_(True)
    panel.setOpaque_(False)

    inset = 8
    tv_rect = NSMakeRect(inset, inset, PANEL_WIDTH - 2 * inset, PANEL_HEIGHT - 2 * inset)
    tv = NSTextView.alloc().initWithFrame_(tv_rect)
    tv.setEditable_(False)
    tv.setSelectable_(False)
    tv.setRichText_(True)
    tv.setBackgroundColor_(NSColor.windowBackgroundColor())
    tv.setDrawsBackground_(True)

    panel.contentView().addSubview_(tv)
    return panel, tv   # NSPanel is an ObjC object; store textview ref on Python app instance


# Position panel flush under the status bar button
def _reposition_panel(panel: NSPanel, nsstatusitem) -> None:
    btn_win = nsstatusitem.button().window()
    sr = btn_win.frame()   # button's window frame is already in screen coordinates
    pw, ph = PANEL_WIDTH, PANEL_HEIGHT
    px = sr.origin.x + sr.size.width / 2.0 - pw / 2.0
    py = sr.origin.y - ph - PANEL_GAP
    panel.setFrame_display_(NSMakeRect(px, py, pw, ph), False)


# Rebuild NSTextView attributed string from current session list (full replace, no flicker)
def _update_panel_text(tv: NSTextView, sessions) -> None:
    min_remaining = _scan_bg_sleep_timers()
    sorted_sessions = sorted(sessions, key=lambda s: (s.project_name, s.is_worker, s.name))

    lines = []
    for project_name, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
        lines.append(_make_header(project_name))
        for s in group_iter:
            dot   = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
            badge = _format_bg_badge(min_remaining) if s.has_bg else _NO_BG
            prefix = '●' if not s.is_worker else ' '
            lines.append(f'{prefix} {s.name.ljust(_NAME_WIDTH)} {dot} {badge}')

    text = '\n'.join(lines) if lines else 'No active sessions'

    attrs = {NSFontAttributeName: _MENLO()}
    astr = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
    tv.textStorage().setAttributedString_(astr)


# Register Cmd+L as global hotkey via Carbon — identical to production _register_hotkey
def _register_hotkey(app: 'NSPanelProbeApp') -> None:
    OSStatus = ctypes.c_int32

    class EventHotKeyID(ctypes.Structure):
        _fields_ = [('signature', ctypes.c_uint32), ('id', ctypes.c_uint32)]

    class EventTypeSpec(ctypes.Structure):
        _fields_ = [('eventClass', ctypes.c_uint32), ('eventKind', ctypes.c_uint32)]

    EventHandlerProcPtr = ctypes.CFUNCTYPE(
        OSStatus, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

    def _on_hotkey(handler_ref, event, user_data):
        try:
            # With setMenu_(None), performClick_ fires the button's action → togglePanel_
            app._nsapp.nsstatusitem.button().performClick_(None)
        except Exception:
            pass
        return 0

    cb = EventHandlerProcPtr(_on_hotkey)
    carbon = ctypes.CDLL('/System/Library/Frameworks/Carbon.framework/Carbon')

    carbon.GetApplicationEventTarget.restype  = ctypes.c_void_p
    carbon.GetApplicationEventTarget.argtypes = []
    target = carbon.GetApplicationEventTarget()

    spec = EventTypeSpec(0x6B657962, 6)
    handler_ref = ctypes.c_void_p()
    carbon.InstallEventHandler.restype  = OSStatus
    carbon.InstallEventHandler.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(EventTypeSpec), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    carbon.InstallEventHandler(
        target, cb, 1, ctypes.byref(spec), None, ctypes.byref(handler_ref))

    hk_ref = ctypes.c_void_p()
    carbon.RegisterEventHotKey.restype  = OSStatus
    carbon.RegisterEventHotKey.argtypes = [
        ctypes.c_uint32, ctypes.c_uint32, EventHotKeyID,
        ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    carbon.RegisterEventHotKey(
        37, 0x0100,
        EventHotKeyID(0x4D424152, 1),
        target, 0, ctypes.byref(hk_ref))

    app._hotkey_cb  = cb
    app._hotkey_ref = hk_ref


if __name__ == '__main__':
    run()
