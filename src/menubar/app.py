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

from .bg_timer import _abort_bg_sleep_timers
from .discovery_worker import start_discovery_worker
from .focus_controller import FocusController
from .hotkey_controller import HotkeyController, register_cmd_l, register_cmd_k
from .menubar_log import log_menubar
from .bar_icons import ICON_NORMAL, ICON_BLINK, ICON_BASELINE_OFFSET
from .panel_dims import PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT
from .panel import _MENLO
from .panel_manager import PanelManager
from .rag_controller import RagController
from .model_controller import ModelController
from .monitor_sweep_scheduler import maybe_run_sweep_workflow
from .system import _focus_session, _focus_worker, _open_or_focus_monitor
from .sessions_controller import SessionsController
from .app_settings import _load_settings, _save_settings
from .panel_lifecycle import (_open_main_panel, _close_main_panel,
                               _open_rag_panel, _close_rag_panel,
                               _open_models_panel, _close_models_panel,
                               _deferred_close_open, _background_panel)

BLINK_DURATION = 0.2
POLL_INTERVAL  = 1.5
TICK_LATENCY_THRESHOLD_MS = 200

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
        if app.panel._panel_backgrounded:
            if app.panel._panel_open:
                app.panel._widgets.panel.orderFrontRegardless()
            elif app.rag._rag_open:
                app.rag._rag_panel.orderFrontRegardless()
            elif app.models._models_open:
                app.models._models_panel.orderFrontRegardless()
            app.panel._panel_backgrounded = False
            return
        if app.rag._rag_open:
            _close_rag_panel(app)
            return
        if app.models._models_open:
            _close_models_panel(app)
            return
        if app.panel._panel_open:
            _close_main_panel(app)
        else:
            app.settings.panel_width = PANEL_WIDTH
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
        uid = os.getuid()
        label = 'com.brunowinter.monitor-cc-menubar'
        cmd = f'sleep 0.5 && launchctl bootout gui/{uid}/{label}'
        subprocess.Popen(['sh', '-c', cmd], start_new_session=True)
        rumps.quit_application()

    def restartApp_(self, sender):
        uid = os.getuid()
        label = 'com.brunowinter.monitor-cc-menubar'
        if getattr(sys, 'frozen', False):
            from .setup_menubar import write_plist_py2app
            write_plist_py2app()
            dest = str(Path.home() / 'Library' / 'LaunchAgents' / f'{label}.plist')
            cmd = (
                f'sleep 0.5 && launchctl bootout gui/{uid}/{label} 2>/dev/null ; '
                f'launchctl bootstrap gui/{uid} "{dest}"'
            )
        else:
            from .setup_menubar import write_plist
            write_plist()
            dest = str(Path.home() / 'Library' / 'LaunchAgents' / f'{label}.plist')
            cmd = (
                f'sleep 0.5 && launchctl bootout gui/{uid}/{label} 2>/dev/null ; '
                f'launchctl bootstrap gui/{uid} "{dest}"'
            )
        subprocess.Popen(['sh', '-c', cmd], start_new_session=True)
        rumps.quit_application()

    def abortBgTimer_(self, sender):
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


class PanelSettings:
    def __init__(self, auto_focus: bool, panel_width: int, panel_min_height: int):
        self.auto_focus = auto_focus
        self.panel_width = panel_width
        self.panel_min_height = panel_min_height

_last_log_cleanup_ts: float = 0.0

def _maybe_cleanup_logs(now: float) -> None:
    global _last_log_cleanup_ts
    if now - _last_log_cleanup_ts > 86400:
        from .menubar_log import cleanup_old_lines
        cleanup_old_lines()
        _last_log_cleanup_ts = now

class CCMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__(ICON_NORMAL, quit_button=None, menu=[])
        self.settings = PanelSettings(*_load_settings())
        self.focus = FocusController(self)
        self.panel = PanelManager(self)
        self._panel_controller = _PanelController.alloc().initWithApp_(self)

        def _on_hotkey():
            try:
                self._nsapp.nsstatusitem.button().performClick_(None)
            except Exception:
                pass

        self.hotkey = HotkeyController(self)
        cmd_l_cb, cmd_l_ref = register_cmd_l(_on_hotkey)
        cmd_k_cb, cmd_k_ref = register_cmd_k(
            lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: _background_panel(self)))
        self.hotkey.global_handles = (cmd_l_cb, cmd_l_ref, cmd_k_cb, cmd_k_ref)
        self.rag    = RagController(self)
        self.models = ModelController(self)
        self.sessions = SessionsController(self)
        start_discovery_worker()

    def _ensure_wired(self) -> bool:
        if self.panel._initialized:
            return True
        try:
            self._nsapp.nsstatusitem.setMenu_(None)
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
            _set_bar_icon(self, ICON_NORMAL)
            self.panel._initialized = True
            return True
        except AttributeError:
            return False

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
        maybe_run_sweep_workflow(now)
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


def _tick_log(panel_open: bool, sessions, displayed_items: dict, action: str) -> None:
    if os.getenv('MENUBAR_DIAGNOSTICS') != '1':
        return
    line = (f'open={panel_open} n={len(sessions)} '
            f'sessions={sorted(s.name for s in sessions)} '
            f'displayed={sorted(displayed_items)} action={action}')
    log_menubar('tick', line)

def _set_bar_icon(app: 'CCMenuBarApp', text: str) -> None:
    astr = NSAttributedString.alloc().initWithString_attributes_(
        text, {
            NSFontAttributeName: NSFont.menuBarFontOfSize_(0),
            NSBaselineOffsetAttributeName: ICON_BASELINE_OFFSET,
        })
    app._nsapp.nsstatusitem.button().setAttributedTitle_(astr)

def _blink(app: 'CCMenuBarApp') -> None:
    _set_bar_icon(app, ICON_BLINK)
    def _restore():
        NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _set_bar_icon(app, ICON_NORMAL))
    threading.Timer(BLINK_DURATION, _restore).start()
