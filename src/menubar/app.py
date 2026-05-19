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
# From bg_timer.py: Background sleep-timer scanning, aggregation, and abort
from .bg_timer import _scan_bg_sleep_timers, _abort_bg_sleep_timers, _aggregate_bg
# From hotkey.py: Carbon Cmd+L registration
from .hotkey import register_cmd_l
# From panel.py: NSPanel construction, render, positioning, UI constants
from .panel import (ICON_NORMAL, ICON_BLINK, ICON_BASELINE_OFFSET,
                    PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT,
                    _MENLO, _make_nspanel, _reposition_panel,
                    _rebuild_panel, _update_panel_inplace)
# From system.py: Ghostty terminal focus
from .system import _focus_session
# From paths.py: APP_SUPPORT-relative settings path
from .paths import SETTINGS_FILE as _SETTINGS_PATH

BLINK_DURATION = 0.2   # seconds
POLL_INTERVAL  = 1.5   # seconds
_TICK_LOG      = '/tmp/menubar-tick.log'
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
        if app._panel_open:
            app._panel.orderOut_(None)
            app._panel_open = False
        else:
            _reposition_panel(app._panel, app._nsapp.nsstatusitem)
            app._panel.orderFrontRegardless()
            # orderFrontRegardless doesn't activate the app → cursor-rect dispatch gets
            # re-disabled on each show; re-enable explicitly (initial call in panel.py
            # _make_nspanel covers first show only; this covers every subsequent open).
            app._panel.enableCursorRects()
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

    def killApp_(self, sender):
        # Detached bootout fires after our process exits, unloading the plist so KeepAlive does NOT respawn.
        # Plist reload happens at next login (RunAtLoad) or via manual `launchctl bootstrap`.
        uid = os.getuid()
        label = 'com.brunowinter.monitor_cc_menubar'
        cmd = f'sleep 0.5 && launchctl bootout gui/{uid}/{label}'
        subprocess.Popen(['sh', '-c', cmd], start_new_session=True)
        rumps.quit_application()

    def restartApp_(self, sender):
        from .setup_menubar import write_plist
        write_plist()   # resync ~/Library/LaunchAgents plist synchronously before exit
        # Detached helper: bootout + bootstrap (with retry) after current process exits
        cmd = f'sleep 0.5 && "{sys.executable}" "{_SETUP_PY}"'
        subprocess.Popen(['sh', '-c', cmd], start_new_session=True)
        rumps.quit_application()   # clean status-bar teardown; launchd respawns from fresh plist

    def abortBgTimer_(self, sender):
        sessions = list_alive_sessions()
        cwd_to_project = {s.cwd: s.project_name for s in sessions if not s.is_worker and s.cwd}
        agg = _aggregate_bg(_scan_bg_sleep_timers(cwd_to_project))
        if agg:
            _abort_bg_sleep_timers(agg.sleep_pids)

    def windowDidResize_(self, notification):
        frame = notification.object().frame()
        app   = self._app
        app._panel_width      = int(max(frame.size.width,  PANEL_MIN_WIDTH))
        app._panel_min_height = int(max(frame.size.height, PANEL_MIN_HEIGHT))
        _save_settings(app._auto_focus, app._panel_width, app._panel_min_height)

    def windowDidEndLiveResize_(self, notification):
        app = self._app
        if app._panel_open:
            sessions = list_alive_sessions()
            cwd_to_project = {s.cwd: s.project_name for s in sessions if not s.is_worker and s.cwd}
            bg_result = _aggregate_bg(_scan_bg_sleep_timers(cwd_to_project))
            _rebuild_panel(app, sessions, bg_result)


# macOS menubar app — polls CC sessions every 1.5s, NSPanel sticky-toggle via Cmd+L / bar click
class CCMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__(ICON_NORMAL, quit_button=None, menu=[])
        self._last_statuses: dict = {}
        self._idle_since_ts: dict = {}
        self._all_workers_idle_since_ts: dict = {}
        self._panel_open: bool = False
        self._initialized: bool = False
        self._displayed_items: dict = {}
        self._cwd_map: dict = {}
        self._abort_btn = None   # NSButton ref; set by _rebuild_panel when timer running
        self._auto_focus, self._panel_width, self._panel_min_height = _load_settings()
        self._panel, self._panel_sv, self._panel_quit_btn, self._toggle_btn, self._panel_kill_btn = _make_nspanel()
        self._panel_controller = _PanelController.alloc().initWithApp_(self)

        def _on_hotkey():
            try:
                self._nsapp.nsstatusitem.button().performClick_(None)   # → togglePanel_
            except Exception:
                pass

        self._hotkey_cb, self._hotkey_ref = register_cmd_l(_on_hotkey)

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
                self._panel_kill_btn.setTarget_(self._panel_controller)
                self._panel_kill_btn.setAction_(b'killApp:')
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
        cwd_to_project = {s.cwd: s.project_name for s in sessions if not s.is_worker and s.cwd}
        bg_by_project = _scan_bg_sleep_timers(cwd_to_project)
        _auto_abort_check(self, sessions, bg_by_project, now)
        bg_result = _aggregate_bg(bg_by_project)
        if self._panel_open:
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
                _rebuild_panel(self, sessions, bg_result)
            else:
                _tick_log(False, sessions, self._displayed_items, 'no-change')


# Per-project auto-abort: if all workers idle for ≥5s and project has a bg timer, abort it
def _auto_abort_check(app: 'CCMenuBarApp', sessions, bg_by_project: dict, now: float) -> None:
    workers_by_project: dict = {}
    for s in sessions:
        if s.is_worker:
            workers_by_project.setdefault(s.project_name, []).append(s)
    for proj, proj_bg in bg_by_project.items():
        if proj == 'unknown':
            continue
        workers = workers_by_project.get(proj, [])
        all_idle = bool(workers) and all(w.status == 'idle' for w in workers)
        if all_idle:
            if proj not in app._all_workers_idle_since_ts:
                app._all_workers_idle_since_ts[proj] = now
            elif now - app._all_workers_idle_since_ts[proj] >= 5.0:
                _abort_bg_sleep_timers(proj_bg.sleep_pids)
                app._all_workers_idle_since_ts.pop(proj, None)
        else:
            app._all_workers_idle_since_ts.pop(proj, None)
    for proj in list(app._all_workers_idle_since_ts):
        if proj not in bg_by_project:
            del app._all_workers_idle_since_ts[proj]

# True if any session's status differs from last tick's snapshot
def _statuses_changed(sessions, last: dict) -> bool:
    current = {s.name: s.status for s in sessions}
    return current != last

# Append one diagnostic line per tick to _TICK_LOG; gated on MENUBAR_DIAGNOSTICS=1 env var (default OFF)
def _tick_log(panel_open: bool, sessions, displayed_items: dict, action: str) -> None:
    if os.getenv('MENUBAR_DIAGNOSTICS') != '1':
        return
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
def _blink(app: 'CCMenuBarApp') -> None:
    _set_bar_icon(app, ICON_BLINK)
    def _restore():
        NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _set_bar_icon(app, ICON_NORMAL))
    threading.Timer(BLINK_DURATION, _restore).start()

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
        tmp = _SETTINGS_PATH.with_name(_SETTINGS_PATH.name + '.tmp')
        open(tmp, 'w').write(json.dumps({
            'auto_focus': auto_focus,
            'panel_width': panel_width,
            'panel_min_height': panel_min_height,
        }))
        os.replace(tmp, _SETTINGS_PATH)
    except Exception:
        pass
