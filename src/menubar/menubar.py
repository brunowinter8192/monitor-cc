# INFRASTRUCTURE
import ctypes
import fcntl
import json
import objc
import os
import subprocess
import sys
import threading
import time
from itertools import groupby

import rumps
from AppKit import (NSAttributedString, NSBaselineOffsetAttributeName,
                    NSBox, NSButton, NSColor, NSCursor, NSFont,
                    NSFontAttributeName, NSForegroundColorAttributeName,
                    NSLayoutAttributeLeading, NSPanel,
                    NSStackView, NSTextField, NSView,
                    NSStatusWindowLevel,
                    NSUserInterfaceLayoutOrientationVertical,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindowStyleMaskNonactivatingPanel,
                    NSWindowStyleMaskResizable)
from Foundation import NSMakeRect, NSMakeSize, NSObject, NSOperationQueue

# From discover.py: Live session discovery + status
from .discover import (list_alive_sessions, get_ghostty_terminal_id,
                       _scan_bg_sleep_timers, _abort_bg_sleep_timers)

ICON_NORMAL          = '◉'
ICON_BLINK           = '●'
ICON_BASELINE_OFFSET = 1.0   # pts — vertical offset applied via NSBaselineOffsetAttributeName; adjust if icon drifts
BLINK_DURATION       = 0.2   # seconds
POLL_INTERVAL  = 1.5   # seconds
_NAME_WIDTH    = 22     # chars for left-justified name column
_MENLO         = lambda: NSFont.fontWithName_size_('Menlo', 13.0)
_SETTINGS_PATH = os.path.expanduser('~/.monitor_cc_menubar_settings.json')

_BADGE_WORKING = '[*]'   # green — ASCII fixed-width, no emoji drift
_BADGE_IDLE    = '[ ]'   # red
_NO_BG         = '   '   # 3-char spacer when no background task
_TICK_LOG      = '/tmp/menubar-tick.log'

PANEL_WIDTH      = 380   # pts
PANEL_HEIGHT     = 460   # pts — initial height; floor for first-run (no settings)
PANEL_MIN_WIDTH  = 250   # pts — minimum width enforced by setContentMinSize_
PANEL_MIN_HEIGHT = 120   # pts — minimum height enforced by setContentMinSize_
PANEL_GAP        = 4     # pts below the status bar button
_FOOTER_H        = 30    # pts — fixed footer height for Restart button
_TOP_BAR_H       = 21    # pts — fixed top-bar height for Auto-Jump button (analog to footer, at top edge)
_ROW_H           = 21    # pts — session NSButton row (20) + 1pt NSStackView spacing
_LABEL_H         = 19    # pts — header/separator NSTextField (18) + 1pt NSStackView spacing
_LAUNCHD_LABEL   = 'com.brunowinter.monitor_cc_menubar'

# ORCHESTRATOR

# Entry point: set LSUIElement env (no Dock icon), acquire singleton lock, create app, start run loop
def run() -> None:
    os.environ.setdefault('LSUIElement', '1')
    _lock_fh = _acquire_singleton_lock()
    if _lock_fh is None:
        print('Another menubar instance is already running, exiting.', file=sys.stderr)
        sys.exit(0)   # exit 0 — launchd KeepAlive only respawns on non-zero exit
    app = CCMenuBarApp()
    app.run()

# FUNCTIONS

# Acquire exclusive fcntl lock on ~/.monitor_cc_menubar.pid; returns open file handle on success, None if locked
# Caller must keep the file handle alive (do not close/GC) — fcntl locks are released when the fd is closed
_LOCK_PATH = os.path.expanduser('~/.monitor_cc_menubar.pid')

def _acquire_singleton_lock():
    fh = open(_LOCK_PATH, 'w')
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    fcntl.fcntl(fh, fcntl.F_SETFD, fcntl.FD_CLOEXEC)   # auto-release on os.execv restart
    fh.write(str(os.getpid()))
    fh.flush()
    return fh

# ObjC target for bar-button toggle, session-row click, Auto-Jump toggle, Restart
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
        _save_settings(app._auto_focus, app._panel_width, app._panel_min_height)
        state = 'ON' if app._auto_focus else 'OFF'
        astr = NSAttributedString.alloc().initWithString_attributes_(
            f'Auto-Jump: {state}', {NSFontAttributeName: _MENLO()})
        sender.setAttributedTitle_(astr)

    def restartApp_(self, sender):
        # os.execv replaces current process in-place: same PID, no race condition, no double bar-icon
        # FD_CLOEXEC on the singleton lock fd ensures it is released before the new process image runs
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def abortBgTimer_(self, sender):
        result = _scan_bg_sleep_timers()
        if result:
            _abort_bg_sleep_timers(result.sleep_pids)

    def windowDidResize_(self, notification):
        frame = notification.object().frame()
        app   = self._app
        app._panel_width      = int(max(frame.size.width,  PANEL_MIN_WIDTH))
        app._panel_min_height = int(max(frame.size.height, PANEL_MIN_HEIGHT))
        _save_settings(app._auto_focus, app._panel_width, app._panel_min_height)

    def windowDidEndLiveResize_(self, notification):
        app = self._app
        if app._panel_open:
            bg_result = _scan_bg_sleep_timers()
            _rebuild_panel(app, list_alive_sessions(), bg_result)


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
        self._abort_btn = None   # NSButton ref; set by _rebuild_panel when timer running
        self._auto_focus, self._panel_width, self._panel_min_height = _load_settings()
        self._panel, self._panel_sv, self._panel_quit_btn, self._toggle_btn = _make_nspanel()
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
                self._panel_quit_btn.setAction_(b'restartApp:')
                self._toggle_btn.setTarget_(self._panel_controller)
                self._toggle_btn.setAction_(b'toggleAutoJump:')
                self._panel.setDelegate_(self._panel_controller)
                _set_bar_icon(self, ICON_NORMAL)   # replace setTitle_ with attributed version
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
            bg_result = _scan_bg_sleep_timers()
            session_names = {s.name for s in sessions}
            abort_flap = (bg_result is not None) != (self._abort_btn is not None)
            set_change = session_names != set(self._displayed_items)
            if abort_flap or set_change:
                reasons = '+'.join(r for r, v in [('abort-flap', abort_flap), ('session-set-change', set_change)] if v)
                _tick_log(True, sessions, self._displayed_items, reasons)
                _rebuild_panel(self, sessions, bg_result)
            else:
                _tick_log(True, sessions, self._displayed_items, 'no-change')
                _update_panel_inplace(self, sessions, bg_result)
            self._last_statuses = {s.name: s.status for s in sessions}
        else:
            session_names = {s.name for s in sessions}
            changed = _statuses_changed(sessions, self._last_statuses)
            self._last_statuses = {s.name: s.status for s in sessions}
            if changed:
                _blink(self)
            if session_names != set(self._displayed_items):
                _tick_log(False, sessions, self._displayed_items, 'session-set-change')
                _rebuild_panel(self, sessions)
            else:
                _tick_log(False, sessions, self._displayed_items, 'no-change')


# True if any session's status differs from last tick's snapshot
def _statuses_changed(sessions, last: dict) -> bool:
    current = {s.name: s.status for s in sessions}
    return current != last

# Append one diagnostic line per tick to _TICK_LOG; action is 'abort-flap', 'session-set-change', 'abort-flap+session-set-change', or 'no-change'
def _tick_log(panel_open: bool, sessions, displayed_items: dict, action: str) -> None:
    try:
        ts = time.strftime('%Y-%m-%dT%H:%M:%S')
        line = (f'{ts} open={panel_open} n={len(sessions)} '
                f'sessions={sorted(s.name for s in sessions)} '
                f'displayed={sorted(displayed_items)} action={action}\n')
        with open(_TICK_LOG, 'a') as fh:
            fh.write(line)
    except Exception:
        pass

# Set bar icon via attributed string with pinned baseline; must be called on main thread
def _set_bar_icon(app: 'CCMenuBarApp', text: str) -> None:
    astr = NSAttributedString.alloc().initWithString_attributes_(
        text, {
            NSFontAttributeName: NSFont.menuBarFontOfSize_(0),
            NSBaselineOffsetAttributeName: ICON_BASELINE_OFFSET,
        })
    app._nsapp.nsstatusitem.button().setAttributedTitle_(astr)

# Flash icon to ICON_BLINK for BLINK_DURATION seconds, then restore on main thread
def _blink(app: CCMenuBarApp) -> None:
    _set_bar_icon(app, ICON_BLINK)
    def _restore():
        NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _set_bar_icon(app, ICON_NORMAL))
    threading.Timer(BLINK_DURATION, _restore).start()

# Badge for sessions with active background tasks: [B M:SS] if timer running, [B] otherwise
def _format_bg_badge(remaining) -> str:
    if remaining is None:
        return '[B]'
    mins, secs = divmod(remaining, 60)
    return f'[B {mins}:{secs:02d}]'

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

# NSView subclass as panel contentView — defines cursor rects for resize edges via resetCursorRects
# Canonical macOS cursor-zone API: AppKit calls resetCursorRects on window activation and after resize,
# merges all views' rects in z-order. Child views (NSTextField, NSButton) install their own rects in
# their resetCursorRects and win over NSCursor.set() calls in mouseMoved_ — that is why the
# mouseMoved_/NSTrackingArea approach failed (I-Beam from NSTextField labels always overrode our set()).
# resetCursorRects on the contentView installs rects at the correct z-order level.
class _PanelContentView(NSView):
    def resetCursorRects(self):
        w    = self.bounds().size.width
        h    = self.bounds().size.height
        EDGE = 8
        self.addCursorRect_cursor_(NSMakeRect(0,        0,    w,            EDGE),      NSCursor.resizeUpDownCursor())
        self.addCursorRect_cursor_(NSMakeRect(0,        0,    EDGE,         h),         NSCursor.resizeLeftRightCursor())
        self.addCursorRect_cursor_(NSMakeRect(w - EDGE, 0,    EDGE,         h),         NSCursor.resizeLeftRightCursor())
        self.addCursorRect_cursor_(NSMakeRect(EDGE,     EDGE, w - 2 * EDGE, h - EDGE),  NSCursor.arrowCursor())

# Build NSPanel + fixed footer (Restart) + fixed top_bar (Auto-Jump) + NSStackView (sessions, middle)
# Returns (panel, stack_view, quit_btn, toggle_btn) — stored on app instance; ObjC objects reject Python attrs
# Layout (y=0 = bottom of contentView):
#   [0, 0,                       pw, _FOOTER_H]   footer   mask=2  — widthSizable, bottom-anchored at y=0
#   [0, _FOOTER_H,               pw, stack_h]     stack    mask=18 — width+height sizable, fills middle
#   [0, PANEL_HEIGHT-_TOP_BAR_H, pw, _TOP_BAR_H]  top_bar  mask=10 — widthSizable|minYMargin, top-anchored
def _make_nspanel():
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT),
        NSWindowStyleMaskNonactivatingPanel | NSWindowStyleMaskResizable, 2, True)
    panel.setLevel_(NSStatusWindowLevel)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces |
        NSWindowCollectionBehaviorIgnoresCycle)
    panel.setHasShadow_(True)
    panel.setOpaque_(False)
    panel.setContentMinSize_(NSMakeSize(PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT))
    cv = _PanelContentView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT))
    panel.setContentView_(cv)
    footer = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH, _FOOTER_H))
    footer.setAutoresizingMask_(2)   # NSViewWidthSizable
    quit_btn = NSButton.alloc().initWithFrame_(NSMakeRect(PANEL_WIDTH - 86, 4, 78, 22))
    quit_btn.setAutoresizingMask_(1)   # NSViewMinXMargin — right-anchored
    quit_btn.setTitle_('Restart')
    quit_btn.setBezelStyle_(1)   # NSBezelStyleRounded
    footer.addSubview_(quit_btn)
    cv.addSubview_(footer)
    top_bar = NSView.alloc().initWithFrame_(NSMakeRect(0, PANEL_HEIGHT - _TOP_BAR_H, PANEL_WIDTH, _TOP_BAR_H))
    top_bar.setAutoresizingMask_(10)   # NSViewWidthSizable(2) | NSViewMinYMargin(8) — bottom margin flexible → stays at top edge on resize
    toggle_btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH - 22, _TOP_BAR_H - 1))
    toggle_btn.setBordered_(False)
    toggle_btn.setButtonType_(7)   # NSButtonTypeMomentaryPushIn
    toggle_btn.setAutoresizingMask_(2)   # NSViewWidthSizable — stretches with top_bar
    top_bar.addSubview_(toggle_btn)
    cv.addSubview_(top_bar)
    stack_h = PANEL_HEIGHT - _FOOTER_H - _TOP_BAR_H
    stack = NSStackView.alloc().initWithFrame_(
        NSMakeRect(0, _FOOTER_H, PANEL_WIDTH, stack_h))
    stack.setAutoresizingMask_(18)   # NSViewWidthSizable|NSViewHeightSizable — auto-fills middle on resize
    stack.setOrientation_(NSUserInterfaceLayoutOrientationVertical)
    stack.setAlignment_(NSLayoutAttributeLeading)
    stack.setSpacing_(1.0)
    stack.setDistribution_(-1)   # NSStackViewDistributionGravityAreas — required for addView_inGravity_ to work
    cv.addSubview_(stack)
    return panel, stack, quit_btn, toggle_btn

# Position panel flush below the NSStatusItem button; reads current panel dimensions (set by _resize_panel)
def _reposition_panel(panel, nsstatusitem) -> None:
    w  = panel.frame().size.width    # dynamic — updated by _resize_panel on each rebuild
    h  = panel.frame().size.height
    sr = nsstatusitem.button().window().frame()   # button window is already in screen coords
    px = sr.origin.x + sr.size.width / 2.0 - w / 2.0
    py = sr.origin.y - h - PANEL_GAP
    panel.setFrame_display_(NSMakeRect(px, py, w, h), False)

# Borderless Menlo-font NSButton row for session / toggle entries
def _make_row_button(text: str, panel_width: int, color=None) -> NSButton:
    attrs = {NSFontAttributeName: _MENLO()}
    if color is not None:
        attrs[NSForegroundColorAttributeName] = color
    btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, panel_width - 22, 20))
    btn.setBordered_(False)
    btn.setButtonType_(7)   # NSButtonTypeMomentaryPushIn
    btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(text, attrs))
    return btn

# NSTextField subclass that suppresses the default I-Beam cursor rect installation
# NSTextField.resetCursorRects installs I-Beam over its full frame; no-op override prevents
# child-view I-Beam from winning over the panel edge cursors defined in _PanelContentView
class _CursorlessLabel(NSTextField):
    def resetCursorRects(self): pass

# Non-interactive Menlo-font NSTextField for plain text labels (e.g. "No active sessions")
def _make_header_label(text: str, panel_width: int) -> NSTextField:
    tf = _CursorlessLabel.labelWithString_('')
    tf.setFrame_(NSMakeRect(0, 0, panel_width - 22, 18))
    tf.setAttributedStringValue_(
        NSAttributedString.alloc().initWithString_attributes_(
            text, {NSFontAttributeName: _MENLO()}))
    return tf

# NSBox (1pt horizontal rule) spanning content width; used as top-level separator between toggle and sessions
# panel_width - 22: 22pt total horizontal margin matches row-button and label frames (consistent inset across all stack items)
def _make_line_separator(panel_width: int) -> NSView:
    w = panel_width - 22
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, 18))
    container.heightAnchor().constraintEqualToConstant_(18.0).setActive_(True)   # explicit height — NSView has no intrinsicContentSize; without this NSStackView collapses it to 0 under Auto Layout
    line = NSBox.alloc().initWithFrame_(NSMakeRect(0, 9, w, 1))
    line.setBoxType_(2)   # NSBoxSeparator — 1pt system-colored horizontal rule
    container.addSubview_(line)
    return container

# NSBox (1pt horizontal rule) with NSTextField label overlay — project name masks the line behind it
# label background = NSColor.windowBackgroundColor() to opaquely cover the NSBox behind the text
def _make_separator_view(project_name: str, panel_width: int) -> NSView:
    w = panel_width - 22
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, 18))
    container.heightAnchor().constraintEqualToConstant_(18.0).setActive_(True)   # explicit height — same reason as _make_line_separator
    line = NSBox.alloc().initWithFrame_(NSMakeRect(0, 9, w, 1))
    line.setBoxType_(2)   # NSBoxSeparator
    container.addSubview_(line)
    label_w = min(len(project_name) * 8 + 6, w - 12)
    tf = _CursorlessLabel.labelWithString_(project_name)
    tf.setFrame_(NSMakeRect(12, 0, label_w, 18))
    tf.setFont_(_MENLO())
    tf.setDrawsBackground_(True)
    tf.setBackgroundColor_(NSColor.windowBackgroundColor())
    container.addSubview_(tf)
    return container

# Compute exact panel height needed to display all sessions; no truncation
def _compute_required_height(sorted_sessions, bg_result) -> int:
    h = _FOOTER_H + _TOP_BAR_H + _LABEL_H   # footer + top-bar (Auto-Jump) + separator-in-stack
    if bg_result is not None:
        h += _ROW_H                           # abort timer button
    if not sorted_sessions:
        return h + _LABEL_H                   # "No active sessions" label
    for _, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
        group_list = list(group_iter)
        h += _LABEL_H + len(group_list) * _ROW_H
    return h

# Resize NSPanel frame to new_h; anchors TOP edge (not bottom-left origin) so panel stays flush below bar icon
# NSStackView auto-resizes via autoresizingMask=18 (NSViewWidthSizable|NSViewHeightSizable)
def _resize_panel(app: CCMenuBarApp, new_h: float) -> None:
    w         = app._panel_width
    frame     = app._panel.frame()
    top_y     = frame.origin.y + frame.size.height   # fix the TOP edge in screen coords
    app._panel.setFrame_display_(
        NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)

# Full panel rebuild; populates _displayed_items + _cwd_map + _abort_btn
def _rebuild_panel(app: CCMenuBarApp, sessions, bg_result=None) -> None:
    for sv in list(app._panel_sv.arrangedSubviews()):
        app._panel_sv.removeView_(sv)
    app._displayed_items = {}
    app._cwd_map = {}
    app._abort_btn = None
    next_tag = [1]
    pw = app._panel_width
    sorted_sessions = sorted(sessions, key=lambda s: (s.project_name, s.is_worker, s.name))
    if bg_result is None:
        bg_result = _scan_bg_sleep_timers()
    min_remaining = bg_result.min_remaining if bg_result else None
    required_h = _compute_required_height(sorted_sessions, bg_result)
    _resize_panel(app, max(app._panel_min_height, required_h))
    state = 'ON' if app._auto_focus else 'OFF'
    app._toggle_btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            f'Auto-Jump: {state}', {NSFontAttributeName: _MENLO()}))
    app._panel_sv.addView_inGravity_(_make_line_separator(pw), 1)
    if bg_result is not None:
        abort_btn = _make_row_button('  ⊗ abort timer', pw)
        abort_btn.setTarget_(app._panel_controller)
        abort_btn.setAction_(b'abortBgTimer:')
        app._panel_sv.addView_inGravity_(abort_btn, 1)
        app._abort_btn = abort_btn
    if not sorted_sessions:
        app._panel_sv.addView_inGravity_(_make_header_label('No active sessions', pw), 1)
        return
    for project_name, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
        app._panel_sv.addView_inGravity_(_make_separator_view(project_name, pw), 1)
        for s in group_iter:
            dot      = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
            badge    = _format_bg_badge(min_remaining) if s.has_bg else _NO_BG
            name_col = s.name.ljust(_NAME_WIDTH)
            if not s.is_worker:
                line = f'● {name_col} {dot} {badge}'
                btn  = _make_row_button(line, pw, NSColor.systemOrangeColor())
                tag  = next_tag[0]; next_tag[0] += 1
                btn.setTag_(tag)
                btn.setTarget_(app._panel_controller)
                btn.setAction_(b'focusSession:')
                app._cwd_map[tag] = s.cwd or ''
            else:
                line = f'  {name_col} {dot} {badge}'
                btn  = _make_row_button(line, pw)
            app._panel_sv.addView_inGravity_(btn, 1)
            app._displayed_items[s.name] = btn

# In-place title update while NSPanel is open; preserves widget positions
def _update_panel_inplace(app: CCMenuBarApp, sessions, bg_result) -> None:
    min_remaining = bg_result.min_remaining if bg_result else None
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

# Load settings; returns (auto_focus, panel_width, panel_min_height); falls back to module defaults on any error
# panel_min_height: reads 'panel_min_height' first, falls back to legacy 'panel_max_height', then PANEL_HEIGHT
# panel_width and panel_min_height clamped to PANEL_MIN_* floors to handle stale/invalid JSON
def _load_settings():
    try:
        d = json.loads(open(_SETTINGS_PATH).read())
        raw_h = d.get('panel_min_height', d.get('panel_max_height', PANEL_HEIGHT))
        return (
            bool(d.get('auto_focus', False)),
            max(int(d.get('panel_width', PANEL_WIDTH)), PANEL_MIN_WIDTH),
            max(int(raw_h),                             PANEL_MIN_HEIGHT),
        )
    except Exception:
        return False, PANEL_WIDTH, PANEL_HEIGHT

# Atomic settings write: tempfile + os.replace to prevent partial-write corruption
def _save_settings(auto_focus: bool, panel_width: int, panel_min_height: int) -> None:
    try:
        tmp = _SETTINGS_PATH + '.tmp'
        open(tmp, 'w').write(json.dumps({
            'auto_focus': auto_focus,
            'panel_width': panel_width,
            'panel_min_height': panel_min_height,
        }))
        os.replace(tmp, _SETTINGS_PATH)
    except Exception:
        pass
