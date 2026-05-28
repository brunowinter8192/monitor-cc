# INFRASTRUCTURE
import json
import objc
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import rumps
from AppKit import (NSAttributedString, NSBaselineOffsetAttributeName, NSFont,
                    NSFontAttributeName)
from Foundation import NSObject, NSOperationQueue

# From discover.py: Live session discovery
from .discover import list_alive_sessions
# From bg_timer.py: Background sleep-timer scanning and abort
from .bg_timer import _scan_bg_sleep_timers, _abort_bg_sleep_timers
# From focus_controller.py: FocusController — auto-focus debounce + auto-abort idle-workers
from .focus_controller import FocusController
# From hotkey.py: Carbon Cmd+L, Cmd+1..9, Cmd+arrows, Cmd+K registration
from .hotkey import (register_cmd_l, register_cmd_digits, unregister_hotkeys,
                     register_cmd_arrow_right, register_cmd_arrow_left,
                     unregister_cmd_arrow_right, unregister_cmd_arrow_left,
                     register_cmd_k)
# From menubar_log.py: unified log sink for all menubar diagnostic categories
from .menubar_log import log_menubar
# From bead_controller.py: BeadController + NSPanel factory + panel repositioning
from .bead_controller import BeadController, _make_bead_nspanel, _reposition_bead_panel
# From panel.py: NSPanel positioning, UI constants
from .panel import (ICON_NORMAL, ICON_BLINK, ICON_BASELINE_OFFSET,
                    PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT,
                    _MENLO, _reposition_panel)
# From panel_manager.py: PanelManager — main-session panel lifecycle controller
from .panel_manager import PanelManager
# From queue_controller.py: QueueController + queue panel repositioning
from .queue_controller import QueueController, _reposition_queue_panel
# From system.py: Ghostty terminal focus
from .system import _focus_session
# From paths.py: APP_SUPPORT-relative settings path
from .paths import SETTINGS_FILE as _SETTINGS_PATH
# From queue.py: deliver_message used by queryBeadStatus_
from .queue import deliver_message
# From sessions_controller.py: session snapshot cache
from .sessions_controller import SessionsController

BLINK_DURATION = 0.2   # seconds
POLL_INTERVAL  = 1.5   # seconds
_SETUP_PY      = Path(__file__).resolve().parent / 'setup_menubar.py'

# FUNCTIONS

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
        # Panel backgrounded (Cmd+K): Cmd+L / bar-click brings it back to front, does NOT close
        if app._panel_backgrounded:
            if app.panel._panel_open:
                app.panel._panel.orderFrontRegardless()
            elif app._tracker_open:
                app._tracker_panel.orderFrontRegardless()
            elif app.queue._queue_open:
                app.queue._queue_panel.orderFrontRegardless()
            app._panel_backgrounded = False
            return
        # Cmd+L closes whichever panel is open; if none → open main
        if app._tracker_open:
            _close_tracker_panel(app)
            return
        if app.queue._queue_open:
            _close_queue_panel(app)
            return
        if app.panel._panel_open:
            _close_main_panel(app)
        else:
            app._panel_width = PANEL_WIDTH       # reset on user-initiated fresh open; no _save_settings
            app._panel_min_height = PANEL_HEIGHT
            _open_main_panel(app)

    def toggleBeadTracker_(self, sender):
        app = self._app
        if app._tracker_open:
            _close_tracker_panel(app)
        else:
            if app._panel_open:
                _close_main_panel(app)
            _open_tracker_panel(app)

    def expandBead_(self, sender):
        self._app.bead.handle_expand(sender.tag())

    def untrackBead_(self, sender):
        self._app.bead.handle_untrack(sender.tag())

    def queryBeadStatus_(self, sender):
        app  = self._app
        info = app.bead._bead_query_tags.get(sender.tag())
        print(f"queue: queryBeadStatus_ tag={sender.tag()} info={info}", file=sys.stderr)
        if not info:
            return
        bead_id, project_name = info
        cwd = next((s.cwd for s in app.sessions.data
                    if not s.is_worker and s.project_name == project_name), None)
        if not cwd:
            print(f"queue: queryBeadStatus_ no cwd for project={project_name}", file=sys.stderr)
            return
        print(f"queue: queryBeadStatus_ delivering bead_id={bead_id} cwd={cwd}", file=sys.stderr)
        deliver_message(cwd, f'{bead_id} wie lautet der status was wurde getan was ist offen')

    def focusSession_(self, sender):
        cwd = self._app.panel._cwd_map.get(sender.tag())
        if cwd:
            _focus_session(cwd)

    def toggleAutoJump_(self, sender):
        app = self._app
        app._auto_focus = not app._auto_focus
        _save_settings(app._auto_focus, app._panel_width, app._panel_min_height)
        state = 'ON' if app._auto_focus else 'OFF'
        app._toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'[Sessions] \u00b7 Beads \u00b7 Queue     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))
        app._tracker_toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'Sessions \u00b7 [Beads] \u00b7 Queue     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))
        app.queue._queue_toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'Sessions \u00b7 Beads \u00b7 [Queue]     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))

    def killApp_(self, sender):
        # Detached bootout fires after our process exits, unloading the plist so KeepAlive does NOT respawn.
        # Plist reload happens at next login (RunAtLoad) or via manual `launchctl bootstrap`.
        uid = os.getuid()
        label = 'com.brunowinter.monitor_cc_menubar'
        cmd = f'sleep 0.5 && launchctl bootout gui/{uid}/{label}'
        subprocess.Popen(['sh', '-c', cmd], start_new_session=True)
        rumps.quit_application()

    def restartApp_(self, sender):
        uid = os.getuid()
        label = 'com.brunowinter.monitor_cc_menubar'
        if getattr(sys, 'frozen', False):
            # py2app bundle mode: write plist pointing to native binary, pure launchctl cycle
            from .setup_menubar import write_plist_py2app
            write_plist_py2app()
            dest = str(Path.home() / 'Library' / 'LaunchAgents' / f'{label}.plist')
            cmd = (
                f'sleep 0.5 && launchctl bootout gui/{uid}/{label} 2>/dev/null ; '
                f'launchctl bootstrap gui/{uid} "{dest}"'
            )
        else:
            # Dev/venv mode: write plist pointing to Bash launcher, run setup_menubar.py to rebootstrap
            from .setup_menubar import write_plist
            write_plist()
            cmd = f'sleep 0.5 && "{sys.executable}" "{_SETUP_PY}"'
        subprocess.Popen(['sh', '-c', cmd], start_new_session=True)
        rumps.quit_application()   # clean status-bar teardown; launchd starts new instance

    def abortBgTimer_(self, sender):
        # Per-project abort: only kill timers for the project whose button was clicked
        project_name = self._app.panel._abort_project_for_tag.get(sender.tag())
        if project_name is None:
            return
        sessions = list_alive_sessions()
        cwd_to_project = {s.cwd: s.project_name for s in sessions if not s.is_worker and s.cwd}
        proj_bg = _scan_bg_sleep_timers(cwd_to_project).get(project_name)
        if proj_bg:
            _abort_bg_sleep_timers(proj_bg.sleep_pids)

    def addQueueRow_(self, sender):
        self._app.queue.handle_add_row(sender.tag())

    def toggleQueueEntry_(self, sender):
        self._app.queue.handle_toggle_entry(sender.tag())

    def removeQueueEntry_(self, sender):
        self._app.queue.handle_remove_entry(sender.tag())

    def commitQueueField_(self, sender):
        self._app.queue.handle_commit_field(sender.tag(), str(sender.stringValue()))

    def controlTextDidEndEditing_(self, notification):
        tf = notification.object()
        self._app.queue.handle_text_end_editing(tf.tag(), str(tf.stringValue()))

    def windowDidResize_(self, notification):
        frame = notification.object().frame()
        app   = self._app
        app._panel_width      = int(max(frame.size.width,  PANEL_MIN_WIDTH))
        app._panel_min_height = int(max(frame.size.height, PANEL_MIN_HEIGHT))
        _save_settings(app._auto_focus, app._panel_width, app._panel_min_height)

    def windowDidEndLiveResize_(self, notification):
        app = self._app
        if app._tracker_open:
            app.bead.rebuild()
        elif app.panel._panel_open:
            sessions = list_alive_sessions()
            cwd_to_project = {s.cwd: s.project_name for s in sessions if not s.is_worker and s.cwd}
            bg_by_project = _scan_bg_sleep_timers(cwd_to_project)
            app.panel.rebuild(sessions, bg_by_project)
            _reregister_digit_hotkeys(app)
        elif app.queue._queue_open:
            sessions = app.sessions.refresh()
            app.queue.rebuild(sessions)


# macOS menubar app — polls CC sessions every 1.5s, NSPanel sticky-toggle via Cmd+L / bar click
class CCMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__(ICON_NORMAL, quit_button=None, menu=[])
        self._auto_focus, self._panel_width, self._panel_min_height = _load_settings()
        self.focus = FocusController(self)
        self.panel = PanelManager(self)
        self._panel_controller = _PanelController.alloc().initWithApp_(self)

        def _on_hotkey():
            try:
                self._nsapp.nsstatusitem.button().performClick_(None)   # → togglePanel_
            except Exception:
                pass

        self._hotkey_cb, self._hotkey_ref = register_cmd_l(_on_hotkey)
        self._hotkey_k_cb, self._hotkey_k_ref = register_cmd_k(
            lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: _background_panel(self)))
        self._hotkey_digits_cb   = None   # GC anchor for Cmd+1..9 CFUNCTYPE
        self._hotkey_digits_refs = []     # GC anchor for Cmd+1..9 hk_refs
        self._tracker_open: bool     = False
        self.bead = BeadController(self)
        self._tracker_panel, self._tracker_sv, self._tracker_toggle_btn = _make_bead_nspanel()
        self._hotkey_arr_right_ref = None   # hk_ref for Cmd+→ (module holds CFUNCTYPE anchor)
        self._hotkey_arr_left_ref  = None   # hk_ref for Cmd+← (module holds CFUNCTYPE anchor)
        self._panel_backgrounded: bool = False   # True while active panel is orderBack_'d behind other windows
        self.queue = QueueController(self)         # queue panel controller; owns all _queue_* state
        self.sessions = SessionsController(self)   # session snapshot cache; refresh() + .data property
        self._last_log_cleanup_ts: float = 0.0    # monotonic ts of last cleanup_old_lines run (0 → fires on first tick)

    @rumps.timer(POLL_INTERVAL)
    def _tick(self, _sender):
        _t = time.monotonic()
        if _t - self._last_log_cleanup_ts > 86400:    # 24h
            from .menubar_log import cleanup_old_lines
            cleanup_old_lines()
            self._last_log_cleanup_ts = _t
        if not self.panel._initialized:
            try:
                self._nsapp.nsstatusitem.setMenu_(None)   # detach NSMenu; performClick_ → action
                btn = self._nsapp.nsstatusitem.button()
                btn.setTarget_(self._panel_controller)
                btn.setAction_(b'togglePanel:')
                self.panel._panel_quit_btn.setTarget_(self._panel_controller)
                self.panel._panel_quit_btn.setAction_(b'restartApp:')
                self.panel._panel_kill_btn.setTarget_(self._panel_controller)
                self.panel._panel_kill_btn.setAction_(b'killApp:')
                self.panel._toggle_btn.setTarget_(self._panel_controller)
                self.panel._toggle_btn.setAction_(b'toggleAutoJump:')
                self._tracker_toggle_btn.setTarget_(self._panel_controller)
                self._tracker_toggle_btn.setAction_(b'toggleAutoJump:')
                self.panel._panel.setDelegate_(self._panel_controller)
                self._tracker_panel.setDelegate_(self._panel_controller)
                self.queue._queue_panel.setDelegate_(self._panel_controller)
                self.queue._queue_toggle_btn.setTarget_(self._panel_controller)
                self.queue._queue_toggle_btn.setAction_(b'toggleAutoJump:')
                _set_bar_icon(self, ICON_NORMAL)   # replace setTitle_ with attributed version
                self.panel._initialized = True
            except AttributeError:
                return   # _nsapp not ready yet; retry next tick
        now = time.time()
        try:
            sessions = self.sessions.refresh()
        except Exception:
            sessions = []
        cwd_to_project = {s.cwd: s.project_name for s in sessions if not s.is_worker and s.cwd}
        bg_by_project = _scan_bg_sleep_timers(cwd_to_project)
        self.focus.tick(sessions, bg_by_project, now)
        self.bead.tick(sessions)
        self.queue.tick(sessions)
        if self.panel._panel_open:
            session_names = {s.name for s in sessions}
            new_abort_projs = {p for p in bg_by_project if p != 'unknown'}
            abort_flap = new_abort_projs != set(self.panel._abort_btns_by_project)
            set_change = session_names != set(self.panel._displayed_items)
            if abort_flap or set_change:
                reasons = '+'.join(r for r, v in [('abort-flap', abort_flap), ('session-set-change', set_change)] if v)
                _tick_log(True, sessions, self.panel._displayed_items, reasons)
                self.panel.rebuild(sessions, bg_by_project)
                _reregister_digit_hotkeys(self)
            else:
                _tick_log(True, sessions, self.panel._displayed_items, 'no-change')
                self.panel.update_inplace(sessions, bg_by_project)
            self.focus.update_statuses(sessions)
        else:
            session_names = {s.name for s in sessions}
            changed = self.focus.statuses_changed(sessions)
            self.focus.update_statuses(sessions)
            if changed:
                _blink(self)
            if session_names != set(self.panel._displayed_items):
                _tick_log(False, sessions, self.panel._displayed_items, 'session-set-change')
                self.panel.rebuild(sessions, bg_by_project)
            else:
                _tick_log(False, sessions, self.panel._displayed_items, 'no-change')


# Append one diagnostic line per tick to menubar.log; gated on MENUBAR_DIAGNOSTICS=1 env var (default OFF)
def _tick_log(panel_open: bool, sessions, displayed_items: dict, action: str) -> None:
    if os.getenv('MENUBAR_DIAGNOSTICS') != '1':
        return
    line = (f'open={panel_open} n={len(sessions)} '
            f'sessions={sorted(s.name for s in sessions)} '
            f'displayed={sorted(displayed_items)} action={action}')
    log_menubar('tick', line)

# Set bar icon via attributed string with pinned baseline; must be called on main thread
def _set_bar_icon(app: 'CCMenuBarApp', text: str) -> None:
    astr = NSAttributedString.alloc().initWithString_attributes_(
        text, {
            NSFontAttributeName: NSFont.menuBarFontOfSize_(0),
            NSBaselineOffsetAttributeName: ICON_BASELINE_OFFSET,
        })
    app._nsapp.nsstatusitem.button().setAttributedTitle_(astr)

# Flash icon to ICON_BLINK for BLINK_DURATION seconds, then restore on main thread
def _blink(app: 'CCMenuBarApp') -> None:
    _set_bar_icon(app, ICON_BLINK)
    def _restore():
        NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _set_bar_icon(app, ICON_NORMAL))
    threading.Timer(BLINK_DURATION, _restore).start()

# Register (or re-register) Cmd+1..9 hotkeys mapped by desktop_no (conflict-free mains only)
def _reregister_digit_hotkeys(app: 'CCMenuBarApp') -> None:
    if app._hotkey_digits_refs:
        unregister_hotkeys(app._hotkey_digits_refs)
        app._hotkey_digits_refs = []
        app._hotkey_digits_cb   = None
    slots = {dn: cwd for dn, cwd in app.panel._desktop_to_cwd.items() if dn <= 9 and cwd}
    if not slots:
        return
    def _make_digit_cb(slot, cwd):
        def _cb():
            log_menubar('hotkey', f'cmd+{slot} → focus {cwd}')
            _focus_session(cwd)
        return _cb
    cb_map = {slot: _make_digit_cb(slot, cwd) for slot, cwd in slots.items()}
    app._hotkey_digits_cb, app._hotkey_digits_refs = register_cmd_digits(cb_map)

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


# Generic deferred panel switch for Cmd+→/← cycling.
# Safety-net: exceptions must not propagate to ObjC (NSBlockOperation has no Python bridge → SIGABRT).
# Cycling order: Sessions → Beads → Queue → Sessions (Cmd+→); reverse for Cmd+←.
# Captures outgoing panel frame before close; restores position+size to incoming panel after open,
# so user-dragged position and width are preserved across cycles (the _open_* _reposition_* calls
# would otherwise re-center the panel under the status bar icon on every cycle).
def _deferred_close_open(app: 'CCMenuBarApp', from_panel: str, to_panel: str) -> None:
    try:
        if from_panel == 'main':      from_obj = app.panel._panel
        elif from_panel == 'tracker': from_obj = app._tracker_panel
        else:                         from_obj = app.queue._queue_panel
        from_frame = from_obj.frame()   # capture before close
        if from_panel == 'main':      _close_main_panel(app)
        elif from_panel == 'tracker': _close_tracker_panel(app)
        elif from_panel == 'queue':   _close_queue_panel(app)
        if to_panel == 'main':        _open_main_panel(app)
        elif to_panel == 'tracker':   _open_tracker_panel(app)
        elif to_panel == 'queue':     _open_queue_panel(app)
        if to_panel == 'main':        to_obj = app.panel._panel
        elif to_panel == 'tracker':   to_obj = app._tracker_panel
        else:                         to_obj = app.queue._queue_panel
        to_obj.setFrame_display_(from_frame, True)   # restore position; display:True flushes immediately
    except Exception as e:
        print(f'[menubar] cycling {from_panel}→{to_panel} error: {e}', file=sys.stderr)

# Cmd+K handler: toggle active panel between foreground and background (orderBack_/orderFrontRegardless).
# Does NOT close the panel — _panel_open / _tracker_open stay True.
# Cycling (Cmd+→/←) resets _panel_backgrounded via _close_main/tracker_panel before opening the other.
def _background_panel(app: 'CCMenuBarApp') -> None:
    try:
        if app._panel_backgrounded:
            if app.panel._panel_open:
                app.panel._panel.setLevel_(25)   # NSStatusWindowLevel — restore before foregrounding
                app.panel._panel.orderFrontRegardless()
            elif app._tracker_open:
                app._tracker_panel.setLevel_(25)   # NSStatusWindowLevel
                app._tracker_panel.orderFrontRegardless()
            elif app.queue._queue_open:
                app.queue._queue_panel.setLevel_(25)   # NSStatusWindowLevel
                app.queue._queue_panel.orderFrontRegardless()
            app._panel_backgrounded = False
        elif app.panel._panel_open:
            app.panel._panel.setLevel_(0)   # NSNormalWindowLevel — allows orderBack_ to work
            app.panel._panel.orderBack_(None)
            app._panel_backgrounded = True
        elif app._tracker_open:
            app._tracker_panel.setLevel_(0)   # NSNormalWindowLevel
            app._tracker_panel.orderBack_(None)
            app._panel_backgrounded = True
        elif app.queue._queue_open:
            app.queue._queue_panel.setLevel_(0)   # NSNormalWindowLevel
            app.queue._queue_panel.orderBack_(None)
            app._panel_backgrounded = True
    except Exception as e:
        print(f'[menubar] Cmd+K deferred-block error: {e}', file=sys.stderr)

# Open main panel: rebuild → reposition → show → register Cmd+→ (→Beads) + Cmd+← (→Queue wrap) + Cmd+1..9
def _open_main_panel(app: 'CCMenuBarApp') -> None:
    sessions = app.sessions.refresh()
    cwd_to_project = {s.cwd: s.project_name for s in sessions if not s.is_worker and s.cwd}
    bg_by_project = _scan_bg_sleep_timers(cwd_to_project)
    app.panel.rebuild(sessions, bg_by_project)
    _reposition_panel(app.panel._panel, app._nsapp.nsstatusitem)
    app.panel._panel.orderFrontRegardless()
    app.panel._panel.enableCursorRects()
    app.panel._panel_open = True
    _reregister_digit_hotkeys(app)
    _, app._hotkey_arr_right_ref = register_cmd_arrow_right(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'main', 'tracker')))
    _, app._hotkey_arr_left_ref = register_cmd_arrow_left(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'main', 'queue')))

# Close main panel: hide + unregister Cmd+→ + Cmd+← + Cmd+1..9
def _close_main_panel(app: 'CCMenuBarApp') -> None:
    app.panel._panel.orderOut_(None)
    app.panel._panel_open = False
    app._panel_backgrounded = False
    if app._hotkey_digits_refs:
        unregister_hotkeys(app._hotkey_digits_refs)
        app._hotkey_digits_refs = []
        app._hotkey_digits_cb   = None
    unregister_cmd_arrow_right(app._hotkey_arr_right_ref)
    app._hotkey_arr_right_ref = None
    unregister_cmd_arrow_left(app._hotkey_arr_left_ref)
    app._hotkey_arr_left_ref = None

# Open tracker panel: rebuild → reposition → show + register Cmd+→ (→Queue) + Cmd+← (→Sessions)
def _open_tracker_panel(app: 'CCMenuBarApp') -> None:
    app.bead.rebuild()
    _reposition_bead_panel(app._tracker_panel, app._nsapp.nsstatusitem)
    app._tracker_panel.orderFrontRegardless()
    app._tracker_panel.enableCursorRects()
    app._tracker_open = True
    _, app._hotkey_arr_right_ref = register_cmd_arrow_right(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'tracker', 'queue')))
    _, app._hotkey_arr_left_ref = register_cmd_arrow_left(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'tracker', 'main')))

# Close tracker panel: hide + unregister Cmd+→ + Cmd+←
def _close_tracker_panel(app: 'CCMenuBarApp') -> None:
    app._tracker_panel.orderOut_(None)
    app._tracker_open = False
    app._panel_backgrounded = False
    unregister_cmd_arrow_right(app._hotkey_arr_right_ref)
    app._hotkey_arr_right_ref = None
    unregister_cmd_arrow_left(app._hotkey_arr_left_ref)
    app._hotkey_arr_left_ref = None

# Open queue panel: load data + rebuild → reposition → show + register Cmd+→ (→Sessions wrap) + Cmd+← (→Beads)
def _open_queue_panel(app: 'CCMenuBarApp') -> None:
    sessions = app.sessions.refresh()
    app.queue.open(sessions)
    _reposition_queue_panel(app.queue._queue_panel, app._nsapp.nsstatusitem)
    app.queue._queue_panel.orderFrontRegardless()
    app.queue._queue_panel.enableCursorRects()
    app.queue._queue_open = True
    _, app._hotkey_arr_right_ref = register_cmd_arrow_right(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'queue', 'main')))
    _, app._hotkey_arr_left_ref = register_cmd_arrow_left(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'queue', 'tracker')))

# Close queue panel: hide + unregister Cmd+→ + Cmd+←
def _close_queue_panel(app: 'CCMenuBarApp') -> None:
    app.queue._queue_panel.orderOut_(None)
    app.queue._queue_open = False
    app._panel_backgrounded = False
    unregister_cmd_arrow_right(app._hotkey_arr_right_ref)
    app._hotkey_arr_right_ref = None
    unregister_cmd_arrow_left(app._hotkey_arr_left_ref)
    app._hotkey_arr_left_ref = None

# Atomic settings write: tempfile + os.replace to prevent partial-write corruption
def _save_settings(auto_focus: bool, panel_width: int, panel_min_height: int) -> None:
    try:
        tmp = _SETTINGS_PATH.with_name(_SETTINGS_PATH.name + '.tmp')
        open(tmp, 'w').write(json.dumps({
            'auto_focus': auto_focus,
            'panel_width': panel_width,
            'panel_min_height': panel_min_height,
        }))
        os.replace(tmp, _SETTINGS_PATH)
    except Exception:
        pass


