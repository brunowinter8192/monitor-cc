# INFRASTRUCTURE
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
# From hotkey_controller.py: HotkeyController + Carbon Cmd+L / Cmd+K registration
from .hotkey_controller import HotkeyController, register_cmd_l, register_cmd_k
# From menubar_log.py: unified log sink for all menubar diagnostic categories
from .menubar_log import log_menubar
# From panel.py: NSPanel positioning, UI constants
from .panel import (ICON_NORMAL, ICON_BLINK, ICON_BASELINE_OFFSET,
                    PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT,
                    _MENLO)
# From panel_manager.py: PanelManager — main-session panel lifecycle controller
from .panel_manager import PanelManager
# From queue_controller.py: QueueController — per-concern queue panel controller
from .queue_controller import QueueController
# From rag_controller.py: RagController — per-concern RAG panel controller
from .rag_controller import RagController
# From system.py: Ghostty terminal focus
from .system import _focus_session
# From sessions_controller.py: session snapshot cache
from .sessions_controller import SessionsController
# From app_settings.py: Settings load/save
from .app_settings import _load_settings, _save_settings
# From panel_lifecycle.py: Panel open/close/background/cycle
from .panel_lifecycle import (_open_main_panel, _close_main_panel,
                               _open_rag_panel, _close_rag_panel,
                               _open_queue_panel, _close_queue_panel,
                               _deferred_close_open, _background_panel)

BLINK_DURATION = 0.2   # seconds
POLL_INTERVAL  = 1.5   # seconds

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
            elif app.rag._rag_open:
                app.rag._rag_panel.orderFrontRegardless()
            elif app.queue._queue_open:
                app.queue._queue_panel.orderFrontRegardless()
            app._panel_backgrounded = False
            return
        # Cmd+L closes whichever panel is open; if none → open main
        if app.rag._rag_open:
            _close_rag_panel(app)
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

    def focusSession_(self, sender):
        cwd = self._app.panel._cwd_map.get(sender.tag())
        if cwd:
            _focus_session(cwd)

    def toggleAutoJump_(self, sender):
        app = self._app
        app._auto_focus = not app._auto_focus
        _save_settings(app._auto_focus, app._panel_width, app._panel_min_height)
        state = 'ON' if app._auto_focus else 'OFF'
        app.panel._toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'[Sessions] \u00b7 RAG \u00b7 Queue     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))
        app.rag._rag_toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'Sessions \u00b7 [RAG] \u00b7 Queue     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))
        app.queue._queue_toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'Sessions \u00b7 RAG \u00b7 [Queue]     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))

    def killApp_(self, sender):
        # Detached bootout fires after our process exits, unloading the plist so KeepAlive does NOT respawn.
        # Plist reload happens at next login (RunAtLoad) or via manual `launchctl bootstrap`.
        uid = os.getuid()
        label = 'com.brunowinter.monitor-cc-menubar'
        cmd = f'sleep 0.5 && launchctl bootout gui/{uid}/{label}'
        subprocess.Popen(['sh', '-c', cmd], start_new_session=True)
        rumps.quit_application()

    def restartApp_(self, sender):
        uid = os.getuid()
        label = 'com.brunowinter.monitor-cc-menubar'
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
            # Dev/venv mode: write plist pointing to Bash launcher, pure launchctl cycle
            from .setup_menubar import write_plist
            write_plist()
            dest = str(Path.home() / 'Library' / 'LaunchAgents' / f'{label}.plist')
            cmd = (
                f'sleep 0.5 && launchctl bootout gui/{uid}/{label} 2>/dev/null ; '
                f'launchctl bootstrap gui/{uid} "{dest}"'
            )
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
        if app.rag._rag_open:
            app.rag.rebuild()
        elif app.panel._panel_open:
            sessions = list_alive_sessions()
            cwd_to_project = {s.cwd: s.project_name for s in sessions if not s.is_worker and s.cwd}
            bg_by_project = _scan_bg_sleep_timers(cwd_to_project)
            app.panel.rebuild(sessions, bg_by_project)
            app.hotkey.reregister_digits(app.panel._desktop_to_cwd)
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
        self.hotkey = HotkeyController(self)
        self._panel_backgrounded: bool = False   # True while active panel is orderBack_'d behind other windows
        self.queue = QueueController(self)         # queue panel controller; owns all _queue_* state
        self.rag   = RagController(self)           # RAG status panel controller; owns all _rag_* state
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
                self.panel._panel.setDelegate_(self._panel_controller)
                self.queue._queue_panel.setDelegate_(self._panel_controller)
                self.queue._queue_toggle_btn.setTarget_(self._panel_controller)
                self.queue._queue_toggle_btn.setAction_(b'toggleAutoJump:')
                self.rag._rag_panel.setDelegate_(self._panel_controller)
                self.rag._rag_toggle_btn.setTarget_(self._panel_controller)
                self.rag._rag_toggle_btn.setAction_(b'toggleAutoJump:')
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
        self.queue.tick(sessions)
        self.rag.tick(sessions)
        if self.panel._panel_open:
            session_names = {s.name for s in sessions}
            new_abort_projs = {p for p in bg_by_project if p != 'unknown'}
            abort_flap = new_abort_projs != set(self.panel._abort_btns_by_project)
            set_change = session_names != set(self.panel._displayed_items)
            if abort_flap or set_change:
                reasons = '+'.join(r for r, v in [('abort-flap', abort_flap), ('session-set-change', set_change)] if v)
                _tick_log(True, sessions, self.panel._displayed_items, reasons)
                self.panel.rebuild(sessions, bg_by_project)
                self.hotkey.reregister_digits(self.panel._desktop_to_cwd)
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
