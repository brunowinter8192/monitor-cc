# INFRASTRUCTURE
import threading
import rumps

# From discover.py: Live session discovery + status
from .discover import list_alive_sessions

ICON_NORMAL    = '◉'
ICON_BLINK     = '●'
BLINK_DURATION = 0.2   # seconds
POLL_INTERVAL  = 1.5   # seconds

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

# Rebuild dropdown menu; re-appends quit button so it survives menu.clear()
def _rebuild_menu(app: CCMenuBarApp, sessions) -> None:
    items = []
    for s in sessions:
        dot = '🟢' if s.status == 'working' else '🔴'
        badge = ' [B]' if s.has_bg else ''
        items.append(f'{s.name}  {dot}{badge}')
    if not items:
        items = ['No active sessions']
    if app._quit_button is not None:
        items.append(None)
        items.append(app._quit_button)
    app.menu = items
