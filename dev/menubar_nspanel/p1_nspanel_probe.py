# INFRASTRUCTURE
import os
import sys
import threading
import time
from itertools import groupby

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

from src.menubar.discover import list_alive_sessions
from src.menubar.bg_timer import _scan_bg_sleep_timers

from p1_hotkey import _register_hotkey

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
PANEL_GAP    = 4


# ORCHESTRATOR

def run() -> None:
    os.environ.setdefault('LSUIElement', '1')
    app = NSPanelProbeApp()
    app.run()


# FUNCTIONS

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


class NSPanelProbeApp(rumps.App):
    def __init__(self):
        super().__init__(ICON_NORMAL, quit_button='Quit', menu=[])
        self._panel_open: bool = False
        self._initialized: bool = False
        self._last_statuses: dict = {}
        self._panel, self._panel_tv = _make_nspanel()
        self._panel_controller = _PanelController.alloc().initWithApp_(self)
        _register_hotkey(self)

    @rumps.timer(POLL_INTERVAL)
    def _tick(self, _sender):
        if not self._initialized:
            try:
                self._nsapp.nsstatusitem.setMenu_(None)
                btn = self._nsapp.nsstatusitem.button()
                btn.setTarget_(self._panel_controller)
                btn.setAction_(b'togglePanel:')
                self._initialized = True
            except AttributeError:
                return

        try:
            sessions = list_alive_sessions()
        except Exception:
            sessions = []

        changed = _statuses_changed(sessions, self._last_statuses)
        self._last_statuses = {s.name: s.status for s in sessions}
        if changed:
            _blink(self)

        _update_panel_text(self._panel_tv, sessions)


def _statuses_changed(sessions, last: dict) -> bool:
    current = {s.name: s.status for s in sessions}
    return current != last


def _blink(app: NSPanelProbeApp) -> None:
    app.title = ICON_BLINK
    threading.Timer(BLINK_DURATION, _restore_icon, args=[app]).start()


def _restore_icon(app: NSPanelProbeApp) -> None:
    app.title = ICON_NORMAL


def _format_bg_badge(remaining) -> str:
    if remaining is None:
        return '[B]'
    mins, secs = divmod(remaining, 60)
    return f'[B {mins}:{secs:02d}]'


def _make_header(project_name: str) -> str:
    fill = '─' * max(2, 30 - len(project_name))
    return f'─── {project_name} {fill}'


def _make_nspanel():
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT),
        NSWindowStyleMaskNonactivatingPanel,
        2,
        True,
    )
    panel.setLevel_(NSStatusWindowLevel)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces |
        NSWindowCollectionBehaviorIgnoresCycle
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
    return panel, tv


def _reposition_panel(panel: NSPanel, nsstatusitem) -> None:
    btn_win = nsstatusitem.button().window()
    sr = btn_win.frame()
    pw, ph = PANEL_WIDTH, PANEL_HEIGHT
    px = sr.origin.x + sr.size.width / 2.0 - pw / 2.0
    py = sr.origin.y - ph - PANEL_GAP
    panel.setFrame_display_(NSMakeRect(px, py, pw, ph), False)


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


if __name__ == '__main__':
    run()
