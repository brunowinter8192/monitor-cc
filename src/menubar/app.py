# INFRASTRUCTURE
import objc
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict

import rumps
from AppKit import (NSAttributedString, NSBaselineOffsetAttributeName, NSFont,
                    NSFontAttributeName)
from Foundation import NSObject, NSOperationQueue

# From bg_timer.py: orchestrator wake-up process (worker-cli wait + legacy sleep timer) abort
from .bg_timer import _abort_bg_sleep_timers
# From discovery_worker.py: background-thread session/bg-sleep-timer snapshot producer
from .discovery_worker import start_discovery_worker
# From focus_controller.py: FocusController — auto-focus debounce
from .focus_controller import FocusController
# From hotkey_controller.py: HotkeyController + Carbon Cmd+L / Cmd+K registration
from .hotkey_controller import HotkeyController, register_cmd_l, register_cmd_k
# From menubar_log.py: unified log sink for all menubar diagnostic categories
from .menubar_log import log_menubar
# From bar_icons.py: menubar status-item icon glyphs (ICON_* constant cluster)
from .bar_icons import ICON_NORMAL, ICON_BLINK, ICON_BASELINE_OFFSET
# From panel_dims.py: main-panel outer dimensions (PANEL_* constant cluster)
from .panel_dims import PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT
# From panel.py: NSPanel positioning, UI constants
from .panel import _MENLO
# From panel_manager.py: PanelManager — main-session panel lifecycle controller
from .panel_manager import PanelManager
# From rag_controller.py: RagController — per-concern RAG panel controller
from .rag_controller import RagController
# From model_controller.py: ModelController — per-concern Models panel controller
from .model_controller import ModelController
# From monitor_sweep_scheduler.py: at-most-once-per-24h daily monitor_cc_* tmux sweep, tick-driven
from .monitor_sweep_scheduler import maybe_run_sweep_workflow
# From system.py: Ghostty terminal focus + per-project monitor launch/focus
from .system import _focus_session, _focus_worker, _open_or_focus_monitor
# From sessions_controller.py: session snapshot cache
from .sessions_controller import SessionsController
# From app_settings.py: Settings load/save
from .app_settings import _load_settings, _save_settings
# From panel_lifecycle.py: Panel open/close/background/cycle
from .panel_lifecycle import (_open_main_panel, _close_main_panel,
                               _open_rag_panel, _close_rag_panel,
                               _open_models_panel, _close_models_panel,
                               _deferred_close_open, _background_panel)

BLINK_DURATION = 0.2   # seconds
POLL_INTERVAL  = 1.5   # seconds
TICK_LATENCY_THRESHOLD_MS = 200   # log a [latency] breakdown line only when total _tick duration exceeds this

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
        if app.panel._panel_backgrounded:
            if app.panel._panel_open:
                app.panel._widgets.panel.orderFrontRegardless()
            elif app.rag._rag_open:
                app.rag._rag_panel.orderFrontRegardless()
            elif app.models._models_open:
                app.models._models_panel.orderFrontRegardless()
            app.panel._panel_backgrounded = False
            return
        # Cmd+L closes whichever panel is open; if none → open main
        if app.rag._rag_open:
            _close_rag_panel(app)
            return
        if app.models._models_open:
            _close_models_panel(app)
            return
        if app.panel._panel_open:
            _close_main_panel(app)
        else:
            app.settings.panel_width = PANEL_WIDTH       # reset on user-initiated fresh open; no _save_settings
            app.settings.panel_min_height = PANEL_HEIGHT
            _open_main_panel(app)

    def focusSession_(self, sender):
        cwd = self._app.panel._lookups.cwd_map.get(sender.tag())
        if cwd:
            _focus_session(cwd)

    def focusWorker_(self, sender):
        tmux_session_name = self._app.panel._lookups.worker_tag_map.get(sender.tag())
        if tmux_session_name:
            _focus_worker(tmux_session_name)

    def openMonitor_(self, sender):
        cwd = self._app.panel._lookups.cwd_map.get(sender.tag())
        if cwd:
            _open_or_focus_monitor(cwd)

    def toggleAutoJump_(self, sender):
        app = self._app
        app.settings.auto_focus = not app.settings.auto_focus
        _save_settings(app.settings.auto_focus, app.settings.panel_width, app.settings.panel_min_height)
        state = 'ON' if app.settings.auto_focus else 'OFF'
        app.panel._widgets.toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'[Sessions] \u00b7 RAG \u00b7 Models     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))
        app.rag._rag_toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'Sessions \u00b7 [RAG] \u00b7 Models     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))
        app.models._models_toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'Sessions \u00b7 RAG \u00b7 [Models]     Auto-Jump: {state}',
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
        # Per-project abort: only kill timers for the project whose button was clicked.
        # 2026-08 (hotkey_latency M3): consumes the background discovery snapshot (cheap
        # in-memory read) instead of calling list_alive_sessions()/_scan_bg_sleep_timers()
        # synchronously on the main thread.
        project_name = self._app.panel._lookups.abort_project_for_tag.get(sender.tag())
        if project_name is None:
            return
        self._app.sessions.refresh()
        proj_bg = self._app.sessions.bg_by_project.get(project_name)
        if proj_bg:
            _abort_bg_sleep_timers(proj_bg.sleep_pids)

    def cycleMainModel_(self, sender):
        self._app.models.handle_cycle_main()

    def cycleMainEffort_(self, sender):
        self._app.models.handle_cycle_main_effort()

    def cycleMainMaxTokens_(self, sender):
        self._app.models.handle_cycle_main_max_tokens()

    def cycleWorkerModel_(self, sender):
        self._app.models.handle_cycle_worker()

    def cycleWorkerEffort_(self, sender):
        self._app.models.handle_cycle_worker_effort()

    def cycleWorkerMaxTokens_(self, sender):
        self._app.models.handle_cycle_worker_max_tokens()

    def applyModelSelection_(self, sender):
        self._app.models.handle_apply()

    def windowDidResize_(self, notification):
        frame = notification.object().frame()
        app   = self._app
        app.settings.panel_width      = int(max(frame.size.width,  PANEL_MIN_WIDTH))
        app.settings.panel_min_height = int(max(frame.size.height, PANEL_MIN_HEIGHT))
        _save_settings(app.settings.auto_focus, app.settings.panel_width, app.settings.panel_min_height)

    def windowDidEndLiveResize_(self, notification):
        # 2026-08 (hotkey_latency M3): panel branch now consumes the background discovery
        # snapshot (app.sessions) instead of calling list_alive_sessions()/_scan_bg_sleep_timers()
        # synchronously on the main thread.
        app = self._app
        if app.rag._rag_open:
            app.rag.rebuild()
        elif app.models._models_open:
            app.models.rebuild()
        elif app.panel._panel_open:
            sessions = app.sessions.refresh()
            bg_by_project = app.sessions.bg_by_project
            app.panel.rebuild(sessions, bg_by_project)
            app.hotkey.reregister_digits(app.panel._lookups.desktop_to_cwd)


# Persisted panel preferences (loaded/saved via app_settings.py); auto_focus/panel_width/
# panel_min_height are the exact triple _load_settings()/_save_settings() round-trip.
class PanelSettings:
    def __init__(self, auto_focus: bool, panel_width: int, panel_min_height: int):
        self.auto_focus = auto_focus
        self.panel_width = panel_width
        self.panel_min_height = panel_min_height

# GC anchors for the two always-on Carbon hotkeys (Cmd+L, Cmd+K) — ctypes CFUNCTYPE + hk_ref must
# stay alive for as long as the registration is active, or GC corrupts the IMP pointer table.
class _GlobalHotkeys:
    def __init__(self, cmd_l_cb, cmd_l_ref, cmd_k_cb, cmd_k_ref):
        self.cmd_l_cb = cmd_l_cb
        self.cmd_l_ref = cmd_l_ref
        self.cmd_k_cb = cmd_k_cb
        self.cmd_k_ref = cmd_k_ref

# monotonic ts of last cleanup_old_lines() run (0 → fires on first tick); module-scope since the
# menubar app is a singleton process (same pattern as discovery_worker.py's _snapshot and
# monitor_sweep_scheduler.py's _last_sweep_ts).
_last_log_cleanup_ts: float = 0.0

# Runs cleanup_old_lines() at most once per 24h; called unconditionally at the top of every _tick.
def _maybe_cleanup_logs(now: float) -> None:
    global _last_log_cleanup_ts
    if now - _last_log_cleanup_ts > 86400:    # 24h
        from .menubar_log import cleanup_old_lines
        cleanup_old_lines()
        _last_log_cleanup_ts = now

# macOS menubar app — polls CC sessions every 1.5s, NSPanel sticky-toggle via Cmd+L / bar click
class CCMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__(ICON_NORMAL, quit_button=None, menu=[])
        self.settings = PanelSettings(*_load_settings())
        self.focus = FocusController(self)
        self.panel = PanelManager(self)
        self._panel_controller = _PanelController.alloc().initWithApp_(self)

        def _on_hotkey():
            try:
                self._nsapp.nsstatusitem.button().performClick_(None)   # → togglePanel_
            except Exception:
                pass

        cmd_l_cb, cmd_l_ref = register_cmd_l(_on_hotkey)
        cmd_k_cb, cmd_k_ref = register_cmd_k(
            lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: _background_panel(self)))
        self._global_hotkeys = _GlobalHotkeys(cmd_l_cb, cmd_l_ref, cmd_k_cb, cmd_k_ref)
        self.hotkey = HotkeyController(self)
        self.rag    = RagController(self)           # RAG status panel controller; owns all _rag_* state
        self.models = ModelController(self)          # Models panel controller; owns all _models_* state
        self.sessions = SessionsController(self)   # session snapshot cache; refresh() + .data property
        start_discovery_worker()   # background thread: list_alive_sessions + _scan_bg_sleep_timers, ~1.5s cadence

    # One-time NSStatusItem/target/action wiring — runs once rumps.App.run() has populated
    # self._nsapp; returns False (retry next tick) until that's ready.
    def _ensure_wired(self) -> bool:
        if self.panel._initialized:
            return True
        try:
            self._nsapp.nsstatusitem.setMenu_(None)   # detach NSMenu; performClick_ → action
            btn = self._nsapp.nsstatusitem.button()
            btn.setTarget_(self._panel_controller)
            btn.setAction_(b'togglePanel:')
            self.panel._widgets.quit_btn.setTarget_(self._panel_controller)
            self.panel._widgets.quit_btn.setAction_(b'restartApp:')
            self.panel._widgets.kill_btn.setTarget_(self._panel_controller)
            self.panel._widgets.kill_btn.setAction_(b'killApp:')
            self.panel._widgets.toggle_btn.setTarget_(self._panel_controller)
            self.panel._widgets.toggle_btn.setAction_(b'toggleAutoJump:')
            self.panel._widgets.panel.setDelegate_(self._panel_controller)
            self.rag._rag_panel.setDelegate_(self._panel_controller)
            self.rag._rag_toggle_btn.setTarget_(self._panel_controller)
            self.rag._rag_toggle_btn.setAction_(b'toggleAutoJump:')
            self.models._models_panel.setDelegate_(self._panel_controller)
            self.models._models_toggle_btn.setTarget_(self._panel_controller)
            self.models._models_toggle_btn.setAction_(b'toggleAutoJump:')
            _set_bar_icon(self, ICON_NORMAL)   # replace setTitle_ with attributed version
            self.panel._initialized = True
            return True
        except AttributeError:
            return False   # _nsapp not ready yet; retry next tick

    # Panel-open branch of _tick: rebuild on session-set/abort-flap change, else in-place update.
    def _tick_panel_open(self, sessions, bg_by_project) -> None:
        session_names = {s.name for s in sessions}
        new_abort_projs = {p for p in bg_by_project if p != 'unknown'}
        abort_flap = new_abort_projs != set(self.panel._lookups.abort_btns_by_project)
        set_change = session_names != set(self.panel._lookups.displayed_items)
        if abort_flap or set_change:
            reasons = '+'.join(r for r, v in [('abort-flap', abort_flap), ('session-set-change', set_change)] if v)
            _tick_log(True, sessions, self.panel._lookups.displayed_items, reasons)
            self.panel.rebuild(sessions, bg_by_project)
            self.hotkey.reregister_digits(self.panel._lookups.desktop_to_cwd)
        else:
            _tick_log(True, sessions, self.panel._lookups.displayed_items, 'no-change')
            self.panel.update_inplace(sessions, bg_by_project)
        self.focus.update_statuses(sessions)

    # Panel-closed branch of _tick: blink on status change, rebuild only on session-set change.
    def _tick_panel_closed(self, sessions, bg_by_project) -> None:
        session_names = {s.name for s in sessions}
        changed = self.focus.statuses_changed(sessions)
        self.focus.update_statuses(sessions)
        if changed:
            _blink(self)
        if session_names != set(self.panel._lookups.displayed_items):
            _tick_log(False, sessions, self.panel._lookups.displayed_items, 'session-set-change')
            self.panel.rebuild(sessions, bg_by_project)
        else:
            _tick_log(False, sessions, self.panel._lookups.displayed_items, 'no-change')

    @rumps.timer(POLL_INTERVAL)
    def _tick(self, _sender):
        _t = time.monotonic()
        _maybe_cleanup_logs(_t)
        if not self._ensure_wired():
            return
        _tick_t0 = time.monotonic()
        phases: Dict[str, float] = {}
        now = time.time()
        # 2026-09: daily monitor_cc_* tmux sweep, migrated off its own LaunchAgent (blocked by a
        # TCC Full Disk Access wall under launchd — see process-docs/monitor_lifecycle/) onto this
        # tick, which already runs under launchd WITH the grant. Cheap in-memory gate check every
        # cycle; the real sweep (tmux/subprocess I/O) runs on its own daemon thread at most once
        # per 24h, never inline on the tick.
        maybe_run_sweep_workflow(now)
        # 2026-08 (hotkey_latency M3): consume the background discovery snapshot (cheap in-memory
        # read, no subprocess/AppleScript I/O) instead of running list_alive_sessions() +
        # _scan_bg_sleep_timers() synchronously on the main thread. Their own per-cycle cost is
        # now logged separately by discovery_worker.py as [latency] bg_refresh lines.
        _p0 = time.monotonic()
        try:
            sessions = self.sessions.refresh()
            bg_by_project = self.sessions.bg_by_project
        except Exception:
            sessions = []
            bg_by_project = {}
        phases['snapshot_consume'] = time.monotonic() - _p0
        _p0 = time.monotonic()
        self.focus.tick(sessions, now)
        phases['focus_tick'] = time.monotonic() - _p0
        _p0 = time.monotonic()
        self.rag.tick(sessions)
        phases['rag_tick'] = time.monotonic() - _p0
        _p0 = time.monotonic()
        if self.panel._panel_open:
            self._tick_panel_open(sessions, bg_by_project)
        else:
            self._tick_panel_closed(sessions, bg_by_project)
        phases['panel_rebuild_update'] = time.monotonic() - _p0
        _tick_total_ms = (time.monotonic() - _tick_t0) * 1000
        if _tick_total_ms > TICK_LATENCY_THRESHOLD_MS:
            breakdown = ' '.join(f'{k}={v * 1000:.0f}ms' for k, v in phases.items())
            log_menubar('latency', f'tick total={_tick_total_ms:.0f}ms {breakdown}')


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
