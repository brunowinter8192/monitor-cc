# INFRASTRUCTURE
import ctypes
import json
import objc
import os
import subprocess
import threading
import time
from itertools import groupby

import rumps
from AppKit import (NSAttributedString, NSButton, NSColor, NSFont,
                    NSFontAttributeName, NSForegroundColorAttributeName,
                    NSLayoutAttributeLeading, NSPanel, NSScrollView,
                    NSStackView, NSTextField, NSView,
                    NSStatusWindowLevel,
                    NSUserInterfaceLayoutOrientationVertical,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindowStyleMaskNonactivatingPanel)
from Foundation import NSMakeRect, NSObject

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

PANEL_WIDTH  = 380   # pts
PANEL_HEIGHT = 460   # pts
PANEL_GAP    = 4     # pts below the status bar button
_FOOTER_H    = 30    # pts — fixed footer height for Quit button

# ORCHESTRATOR

# Entry point: set LSUIElement env (no Dock icon), create app, start run loop
def run() -> None:
    os.environ.setdefault('LSUIElement', '1')
    app = CCMenuBarApp()
    app.run()

# FUNCTIONS

# ObjC target for bar-button toggle, session-row click, Auto-Jump toggle, Quit
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

    def focusSession_(self, sender):
        cwd = self._app._cwd_map.get(sender.tag())
        if cwd:
            _focus_session(cwd)

    def toggleAutoJump_(self, sender):
        app = self._app
        app._auto_focus = not app._auto_focus
        _save_settings(app._auto_focus)
        label = f'Auto-Jump: {"ON" if app._auto_focus else "OFF"}'
        astr = NSAttributedString.alloc().initWithString_attributes_(
            label, {NSFontAttributeName: _MENLO()})
        sender.setAttributedTitle_(astr)

    def quitApp_(self, sender):
        rumps.quit_application()


# macOS menubar app — polls CC sessions every 1.5s, NSPanel sticky-toggle via Cmd+L / bar click
class CCMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__(ICON_NORMAL, quit_button=None, menu=[])
        self._last_statuses: dict = {}
        self._idle_since_ts: dict = {}
        self._panel_open: bool = False
        self._initialized: bool = False
        self._displayed_items: dict = {}
        self._cwd_map: dict = {}
        self._auto_focus: bool = _load_settings()
        self._panel, self._panel_sv, self._panel_quit_btn = _make_nspanel()
        self._panel_controller = _PanelController.alloc().initWithApp_(self)
        _register_hotkey(self)

    @rumps.timer(POLL_INTERVAL)
    def _tick(self, _sender):
        if not self._initialized:
            try:
                self._nsapp.nsstatusitem.setMenu_(None)   # detach NSMenu; performClick_ → action
                btn = self._nsapp.nsstatusitem.button()
                btn.setTarget_(self._panel_controller)
                btn.setAction_(b'togglePanel:')
                self._panel_quit_btn.setTarget_(self._panel_controller)
                self._panel_quit_btn.setAction_(b'quitApp:')
                self._initialized = True
            except AttributeError:
                return   # _nsapp not ready yet; retry next tick
        now = time.time()
        try:
            sessions = list_alive_sessions()
        except Exception:
            sessions = []
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
        if self._panel_open:
            _update_panel_inplace(self, sessions)
            self._last_statuses = {s.name: s.status for s in sessions}
        else:
            changed = _statuses_changed(sessions, self._last_statuses)
            self._last_statuses = {s.name: s.status for s in sessions}
            if changed:
                _blink(self)
            _rebuild_panel(self, sessions)


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
            app._nsapp.nsstatusitem.button().performClick_(None)   # → togglePanel_
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
    app._hotkey_cb  = cb   # keep ctypes objects alive; GC would invalidate callback
    app._hotkey_ref = hk_ref

# Build NSPanel (nonactivatingPanel) + NSScrollView+NSStackView (sessions) + footer Quit button
# Returns (panel, stack_view, quit_btn) — stored on app instance; ObjC objects reject Python attrs
def _make_nspanel():
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT),
        NSWindowStyleMaskNonactivatingPanel, 2, True)
    panel.setLevel_(NSStatusWindowLevel)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces |
        NSWindowCollectionBehaviorIgnoresCycle)
    panel.setHasShadow_(True)
    panel.setOpaque_(False)
    footer = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH, _FOOTER_H))
    quit_btn = NSButton.alloc().initWithFrame_(NSMakeRect(PANEL_WIDTH - 70, 4, 62, 22))
    quit_btn.setTitle_('Quit')
    quit_btn.setBezelStyle_(1)   # NSBezelStyleRounded
    footer.addSubview_(quit_btn)
    panel.contentView().addSubview_(footer)
    scroll_h = PANEL_HEIGHT - _FOOTER_H
    scroll = NSScrollView.alloc().initWithFrame_(
        NSMakeRect(0, _FOOTER_H, PANEL_WIDTH, scroll_h))
    scroll.setHasVerticalScroller_(True)
    scroll.setHasHorizontalScroller_(False)
    scroll.setAutohidesScrollers_(True)
    scroll.setDrawsBackground_(False)
    stack = NSStackView.alloc().initWithFrame_(
        NSMakeRect(0, 0, PANEL_WIDTH - 16, scroll_h))
    stack.setOrientation_(NSUserInterfaceLayoutOrientationVertical)
    stack.setAlignment_(NSLayoutAttributeLeading)
    stack.setSpacing_(1.0)
    stack.setDistribution_(0)   # NSStackViewDistributionFill
    scroll.setDocumentView_(stack)
    panel.contentView().addSubview_(scroll)
    return panel, stack, quit_btn

# Position panel flush below the NSStatusItem button
def _reposition_panel(panel, nsstatusitem) -> None:
    sr = nsstatusitem.button().window().frame()   # button window is already in screen coords
    px = sr.origin.x + sr.size.width / 2.0 - PANEL_WIDTH / 2.0
    py = sr.origin.y - PANEL_HEIGHT - PANEL_GAP
    panel.setFrame_display_(NSMakeRect(px, py, PANEL_WIDTH, PANEL_HEIGHT), False)

# Borderless Menlo-font NSButton row for session / toggle entries
def _make_row_button(text: str, color=None) -> NSButton:
    attrs = {NSFontAttributeName: _MENLO()}
    if color is not None:
        attrs[NSForegroundColorAttributeName] = color
    btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH - 22, 20))
    btn.setBordered_(False)
    btn.setButtonType_(7)   # NSButtonTypeMomentaryPushIn
    btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(text, attrs))
    return btn

# Non-interactive Menlo-font NSTextField for project-header lines
def _make_header_label(text: str) -> NSTextField:
    tf = NSTextField.labelWithString_('')
    tf.setFrame_(NSMakeRect(0, 0, PANEL_WIDTH - 22, 18))
    tf.setAttributedStringValue_(
        NSAttributedString.alloc().initWithString_attributes_(
            text, {NSFontAttributeName: _MENLO()}))
    return tf

# Full panel rebuild (only while panel is closed); populates _displayed_items + _cwd_map
def _rebuild_panel(app: CCMenuBarApp, sessions) -> None:
    for sv in list(app._panel_sv.arrangedSubviews()):
        app._panel_sv.removeArrangedSubview_(sv)
        sv.removeFromSuperview()
    app._displayed_items = {}
    app._cwd_map = {}
    next_tag = [1]
    label = f'Auto-Jump: {"ON" if app._auto_focus else "OFF"}'
    toggle_btn = _make_row_button(label)
    toggle_btn.setTarget_(app._panel_controller)
    toggle_btn.setAction_(b'toggleAutoJump:')
    app._panel_sv.addArrangedSubview_(toggle_btn)
    app._panel_sv.addArrangedSubview_(_make_header_label('─' * 44))
    min_remaining = _scan_bg_sleep_timers()
    if not sessions:
        app._panel_sv.addArrangedSubview_(_make_header_label('No active sessions'))
        return
    sorted_sessions = sorted(sessions, key=lambda s: (s.project_name, s.is_worker, s.name))
    for project_name, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
        app._panel_sv.addArrangedSubview_(_make_header_label(_make_header(project_name)))
        for s in group_iter:
            dot      = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
            badge    = _format_bg_badge(min_remaining) if s.has_bg else _NO_BG
            name_col = s.name.ljust(_NAME_WIDTH)
            if not s.is_worker:
                line = f'● {name_col} {dot} {badge}'
                btn  = _make_row_button(line, NSColor.systemOrangeColor())
                tag  = next_tag[0]; next_tag[0] += 1
                btn.setTag_(tag)
                btn.setTarget_(app._panel_controller)
                btn.setAction_(b'focusSession:')
                app._cwd_map[tag] = s.cwd or ''
            else:
                line = f'  {name_col} {dot} {badge}'
                btn  = _make_row_button(line)
            app._panel_sv.addArrangedSubview_(btn)
            app._displayed_items[s.name] = btn

# In-place title update while NSPanel is open; preserves widget positions + scroll state
def _update_panel_inplace(app: CCMenuBarApp, sessions) -> None:
    min_remaining = _scan_bg_sleep_timers()
    session_map = {s.name: s for s in sessions}
    for name, btn in app._displayed_items.items():
        s = session_map.get(name)
        if s is None:
            continue
        dot      = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
        badge    = _format_bg_badge(min_remaining) if s.has_bg else _NO_BG
        name_col = name.ljust(_NAME_WIDTH)
        if not s.is_worker:
            line, color = f'● {name_col} {dot} {badge}', NSColor.systemOrangeColor()
        else:
            line, color = f'  {name_col} {dot} {badge}', None
        attrs = {NSFontAttributeName: _MENLO()}
        if color is not None:
            attrs[NSForegroundColorAttributeName] = color
        btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(line, attrs))

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
