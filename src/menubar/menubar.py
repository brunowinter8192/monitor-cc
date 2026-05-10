# INFRASTRUCTURE
import subprocess
import threading
from itertools import groupby

import rumps
from AppKit import (NSAttributedString, NSFont, NSColor,
                    NSFontAttributeName, NSForegroundColorAttributeName)

# From discover.py: Live session discovery + status
from .discover import list_alive_sessions

ICON_NORMAL    = '◉'
ICON_BLINK     = '●'
BLINK_DURATION = 0.2   # seconds
POLL_INTERVAL  = 1.5   # seconds
_NAME_WIDTH    = 22     # chars for left-justified name column
_MENLO         = lambda: NSFont.fontWithName_size_('Menlo', 13.0)

_BADGE_WORKING = '[*]'   # green — ASCII fixed-width, no emoji drift
_BADGE_IDLE    = '[ ]'   # red
_BADGE_BG      = '[B]'   # orange badge suffix for background tasks
_NO_BG         = '   '   # 3-char spacer when no background task

# ORCHESTRATOR

# Entry point: set LSUIElement env (no Dock icon), create app, start run loop
def run() -> None:
    import os
    os.environ.setdefault('LSUIElement', '1')
    app = CCMenuBarApp()
    app.run()

# FUNCTIONS

# macOS menubar app — polls CC sessions every 1.5s, blinks icon on status change
class CCMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__(ICON_NORMAL, quit_button='Quit', menu=['Loading…'])
        self._last_statuses: dict = {}

    @rumps.timer(POLL_INTERVAL)
    def _tick(self, _sender):
        try:
            sessions = list_alive_sessions()
        except Exception:
            sessions = []
        if _statuses_changed(sessions, self._last_statuses):
            self._last_statuses = {s.name: s.status for s in sessions}
            _blink(self)
        else:
            self._last_statuses = {s.name: s.status for s in sessions}
        _rebuild_menu(self, sessions)


# True if any session's status differs from last tick's snapshot
def _statuses_changed(sessions, last: dict) -> bool:
    current = {s.name: s.status for s in sessions}
    return current != last

# Flash icon to ICON_BLINK for BLINK_DURATION seconds, then restore
def _blink(app: CCMenuBarApp) -> None:
    app.title = ICON_BLINK
    threading.Timer(BLINK_DURATION, _restore_icon, args=[app]).start()

# Restore normal icon title (called from threading.Timer callback)
def _restore_icon(app: CCMenuBarApp) -> None:
    app.title = ICON_NORMAL

# Apply Menlo monospace font (+ optional color) to a rumps MenuItem via NSAttributedString
def _set_mono(item, text: str, color=None) -> None:
    attrs = {NSFontAttributeName: _MENLO()}
    if color is not None:
        attrs[NSForegroundColorAttributeName] = color
    astr = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
    item._menuitem.setAttributedTitle_(astr)

# Section header line: ─── ProjectName ──────────
def _make_header(project_name: str) -> str:
    fill = '─' * max(2, 30 - len(project_name))
    return f'─── {project_name} {fill}'

# Focus Ghostty terminal whose working directory matches cwd; no-op if not found
def _focus_session(cwd: str) -> None:
    script = (
        'tell application "Ghostty"\n'
        '  activate\n'
        f'  focus (first terminal whose working directory is "{cwd}")\n'
        'end tell'
    )
    subprocess.run(['osascript', '-e', script], capture_output=True, timeout=3)

# Return a click callback that focuses the Ghostty terminal for cwd
def _make_focus_cb(cwd: str):
    def _cb(_sender):
        _focus_session(cwd)
    return _cb

# Rebuild dropdown menu grouped by project; clear first to prevent accumulation
def _rebuild_menu(app: CCMenuBarApp, sessions) -> None:
    app.menu.clear()
    if not sessions:
        app.menu.add('No active sessions')
    else:
        sorted_sessions = sorted(sessions, key=lambda s: (s.project_name, s.is_worker, s.name))
        for project_name, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
            header_text = _make_header(project_name)
            header = rumps.MenuItem(header_text)
            _set_mono(header, header_text)
            app.menu.add(header)
            for s in group_iter:
                dot      = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
                badge    = _BADGE_BG if s.has_bg else _NO_BG
                name_col = s.name.ljust(_NAME_WIDTH)
                if not s.is_worker:
                    # prefix '● ' = 2 chars; badge column at 2+22+1=25
                    line = f'● {name_col} {dot} {badge}'
                    cb   = _make_focus_cb(s.cwd) if s.cwd else None
                    item = rumps.MenuItem(line, callback=cb, key='l' if cb else None)
                    _set_mono(item, line, NSColor.systemOrangeColor())
                else:
                    # prefix '  ' = 2 chars (indent via name padding); same badge column
                    line = f'  {name_col} {dot} {badge}'
                    item = rumps.MenuItem(line)
                    _set_mono(item, line)
                app.menu.add(item)
    if app._quit_button is not None:
        app.menu.add(None)
        app.menu.add(app._quit_button)
