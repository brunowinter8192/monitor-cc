# INFRASTRUCTURE
import ctypes
import json
import os
import subprocess
import threading
import time
from itertools import groupby

import rumps
from AppKit import (NSAttributedString, NSFont, NSColor,
                    NSFontAttributeName, NSForegroundColorAttributeName)
from Foundation import NSObject

# From discover.py: Live session discovery + status
from .discover import list_alive_sessions, get_ghostty_terminal_id, _scan_bg_sleep_timers

ICON_NORMAL    = '◉'
ICON_BLINK     = '●'
BLINK_DURATION = 0.2   # seconds
POLL_INTERVAL  = 1.5   # seconds
_NAME_WIDTH    = 22     # chars for left-justified name column
_MENLO         = lambda: NSFont.fontWithName_size_('Menlo', 13.0)
_SETTINGS_PATH = os.path.expanduser('~/.monitor_cc_menubar_settings.json')

_BADGE_WORKING = '[*]'   # green — ASCII fixed-width, no emoji drift
_BADGE_IDLE    = '[ ]'   # red
_NO_BG         = '   '   # 3-char spacer when no background task

# ORCHESTRATOR

# Entry point: set LSUIElement env (no Dock icon), create app, start run loop
def run() -> None:
    os.environ.setdefault('LSUIElement', '1')
    app = CCMenuBarApp()
    app.run()

# FUNCTIONS

# NSMenuDelegate: sets _menu_open flag to switch _tick between full rebuild and in-place update
class _MenuDelegate(NSObject):
    def initWithApp_(self, app):
        self = super().init()
        if self is None:
            return None
        self._app = app
        return self

    def menuWillOpen_(self, menu):
        self._app._menu_open = True

    def menuDidClose_(self, menu):
        self._app._menu_open = False

# macOS menubar app — polls CC sessions every 1.5s, blinks icon on status change
class CCMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__(ICON_NORMAL, quit_button='Quit', menu=['Loading…'])
        self._last_statuses: dict = {}
        self._idle_since_ts: dict = {}
        self._menu_open: bool = False
        self._displayed_items: dict = {}
        self._toggle_item = None
        self._auto_focus: bool = _load_settings()
        _register_hotkey(self)
        delegate = _MenuDelegate.alloc().initWithApp_(self)
        self._menu_delegate = delegate   # hold ref — ARC would collect otherwise
        self._nsapp.nsstatusitem.menu().setDelegate_(delegate)

    @rumps.timer(POLL_INTERVAL)
    def _tick(self, _sender):
        now = time.time()
        try:
            sessions = list_alive_sessions()
        except Exception:
            sessions = []
        # Auto-focus: debounced working→idle trigger for main sessions
        if self._auto_focus:
            for s in sessions:
                if s.is_worker or not s.cwd:
                    self._idle_since_ts.pop(s.name, None)
                    continue
                if s.status == 'idle' and not s.has_bg:
                    if s.name not in self._idle_since_ts:
                        if self._last_statuses.get(s.name) == 'working':
                            self._idle_since_ts[s.name] = now
                    elif now - self._idle_since_ts[s.name] >= 3.0:
                        _focus_session(s.cwd)
                        del self._idle_since_ts[s.name]
                else:
                    self._idle_since_ts.pop(s.name, None)
        # Branch on menu visibility: in-place update keeps NSMenu stable while open
        if self._menu_open:
            _update_menu_inplace(self, sessions)
            self._last_statuses = {s.name: s.status for s in sessions}
        else:
            changed = _statuses_changed(sessions, self._last_statuses)
            self._last_statuses = {s.name: s.status for s in sessions}
            if changed:
                _blink(self)
            _rebuild_menu(self, sessions)


# True if any session's status differs from last tick's snapshot
def _statuses_changed(sessions, last: dict) -> bool:
    current = {s.name: s.status for s in sessions}
    return current != last

# Flash icon to ICON_BLINK for BLINK_DURATION seconds, then restore
def _blink(app: CCMenuBarApp) -> None:
    app.title = ICON_BLINK
    threading.Timer(BLINK_DURATION, _restore_icon, args=[app]).start()

# Restore normal icon title after blink
def _restore_icon(app: CCMenuBarApp) -> None:
    app.title = ICON_NORMAL

# Badge for sessions with active background tasks: [B M:SS] if timer running, [B] otherwise
def _format_bg_badge(remaining) -> str:
    if remaining is None:
        return '[B]'
    mins, secs = divmod(remaining, 60)
    return f'[B {mins}:{secs:02d}]'

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

# Focus Ghostty terminal for cwd; prefers UUID-based focus, falls back to cwd-match
def _focus_session(cwd: str) -> None:
    import datetime
    term_id = get_ghostty_terminal_id(cwd)
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if term_id:
        safe_id = term_id.replace('"', '\\"')
        script = (
            'tell application "Ghostty"\n'
            '  activate\n'
            f'  focus terminal id "{safe_id}"\n'
            'end tell'
        )
        label = f'id={term_id}'
    else:
        safe_cwd = cwd.replace('"', '\\"')
        script = (
            'tell application "Ghostty"\n'
            '  activate\n'
            '  try\n'
            f'    focus (first terminal whose working directory is "{safe_cwd}")\n'
            '  on error\n'
            '  end try\n'
            'end tell'
        )
        label = f'cwd={cwd}'
    try:
        r = subprocess.run(['osascript', '-e', script], capture_output=True, timeout=3)
        msg = (f'{ts} OK {label}\n' if r.returncode == 0 else
               f'{ts} ERR rc={r.returncode} {label} stderr={r.stderr.decode(errors="replace").strip()}\n')
    except subprocess.TimeoutExpired:
        msg = f'{ts} TIMEOUT {label}\n'
    with open('/tmp/monitor_cc_menubar_focus.log', 'a') as fh:
        fh.write(msg)

# Return a click callback that focuses the Ghostty terminal for cwd
def _make_focus_cb(cwd: str):
    def _cb(_sender):
        _focus_session(cwd)
    return _cb

# Register Cmd+L (keycode 37, modifier 0x0100) as global hotkey via Carbon
def _register_hotkey(app: 'CCMenuBarApp') -> None:
    OSStatus = ctypes.c_int32

    class EventHotKeyID(ctypes.Structure):
        _fields_ = [('signature', ctypes.c_uint32), ('id', ctypes.c_uint32)]

    class EventTypeSpec(ctypes.Structure):
        _fields_ = [('eventClass', ctypes.c_uint32), ('eventKind', ctypes.c_uint32)]

    EventHandlerProcPtr = ctypes.CFUNCTYPE(
        OSStatus, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

    def _on_hotkey(handler_ref, event, user_data):
        try:
            app._nsapp.nsstatusitem.button().performClick_(None)
        except Exception:
            pass
        return 0

    cb = EventHandlerProcPtr(_on_hotkey)

    carbon = ctypes.CDLL('/System/Library/Frameworks/Carbon.framework/Carbon')

    carbon.GetApplicationEventTarget.restype  = ctypes.c_void_p
    carbon.GetApplicationEventTarget.argtypes = []
    target = carbon.GetApplicationEventTarget()

    spec = EventTypeSpec(0x6B657962, 6)   # kEventClassKeyboard, kEventHotKeyPressed
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
        37, 0x0100,                          # kVK_ANSI_L, cmdKey
        EventHotKeyID(0x4D424152, 1),        # signature 'MBAR', id 1
        target, 0, ctypes.byref(hk_ref))

    # Keep ctypes objects alive for process lifetime (GC would invalidate callback)
    app._hotkey_cb  = cb
    app._hotkey_ref = hk_ref

# Full menu rebuild (only while menu closed); populates _displayed_items for in-place updates
def _rebuild_menu(app: CCMenuBarApp, sessions) -> None:
    app._displayed_items = {}
    app.menu.clear()
    # Auto-Jump toggle always at top
    label = f'Auto-Jump: {"ON" if app._auto_focus else "OFF"}'
    toggle = rumps.MenuItem(label, callback=_make_toggle_cb(app))
    _set_mono(toggle, label)
    app.menu.add(toggle)
    app._toggle_item = toggle
    app.menu.add(None)
    min_remaining = _scan_bg_sleep_timers()
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
                badge    = _format_bg_badge(min_remaining) if s.has_bg else _NO_BG
                name_col = s.name.ljust(_NAME_WIDTH)
                if not s.is_worker:
                    line = f'● {name_col} {dot} {badge}'
                    cb   = _make_focus_cb(s.cwd) if s.cwd else None
                    item = rumps.MenuItem(line, callback=cb)
                    _set_mono(item, line, NSColor.systemOrangeColor())
                else:
                    line = f'  {name_col} {dot} {badge}'
                    item = rumps.MenuItem(line)
                    _set_mono(item, line)
                app.menu.add(item)
                app._displayed_items[s.name] = item
    if app._quit_button is not None:
        app.menu.add(None)
        app.menu.add(app._quit_button)

# In-place title update while NSMenu is open; setAttributedTitle_ live-rerenders without flicker
def _update_menu_inplace(app: CCMenuBarApp, sessions) -> None:
    min_remaining = _scan_bg_sleep_timers()
    session_map = {s.name: s for s in sessions}
    for name, item in app._displayed_items.items():
        s = session_map.get(name)
        if s is None:
            continue
        dot = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
        badge = _format_bg_badge(min_remaining) if s.has_bg else _NO_BG
        name_col = name.ljust(_NAME_WIDTH)
        if not s.is_worker:
            _set_mono(item, f'● {name_col} {dot} {badge}', NSColor.systemOrangeColor())
        else:
            _set_mono(item, f'  {name_col} {dot} {badge}')

# Load auto_focus bool from settings JSON; returns False (default OFF) on any error
def _load_settings() -> bool:
    try:
        return bool(json.loads(open(_SETTINGS_PATH).read()).get('auto_focus', False))
    except Exception:
        return False

# Atomic settings write: tempfile + os.replace to prevent partial-write corruption
def _save_settings(auto_focus: bool) -> None:
    try:
        tmp = _SETTINGS_PATH + '.tmp'
        open(tmp, 'w').write(json.dumps({'auto_focus': auto_focus}))
        os.replace(tmp, _SETTINGS_PATH)
    except Exception:
        pass

# Callback for Auto-Jump toggle: flips _auto_focus, persists; menu redraws on next closed-tick
def _make_toggle_cb(app: CCMenuBarApp):
    def _cb(_sender):
        app._auto_focus = not app._auto_focus
        _save_settings(app._auto_focus)
    return _cb
