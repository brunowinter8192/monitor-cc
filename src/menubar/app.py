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
# From hotkey.py: Carbon Cmd+L, Cmd+1..9, Cmd+arrows, Cmd+K registration
from .hotkey import (register_cmd_l, register_cmd_digits, unregister_hotkeys,
                     register_cmd_arrow_right, register_cmd_arrow_left,
                     unregister_cmd_arrow_right, unregister_cmd_arrow_left,
                     register_cmd_k)
# From bead_data.py: bd subprocess wrappers for tracker panel
from .bead_data import project_db_map, load_tracked_beads
# From bead_panel.py: NSPanel + render for bead tracker
from .bead_panel import (_make_bead_nspanel, _rebuild_bead_panel, _reposition_bead_panel,
                          _handle_expand_bead, _handle_untrack_bead, _resize_tracker_panel)
# From panel.py: NSPanel construction, render, positioning, UI constants
from .panel import (ICON_NORMAL, ICON_BLINK, ICON_BASELINE_OFFSET,
                    PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT,
                    _MENLO, _make_nspanel, _reposition_panel,
                    _rebuild_panel, _update_panel_inplace)
# From queue_panel.py: standalone queue NSPanel + render
from .queue_panel import (_make_queue_nspanel, _rebuild_queue_panel, _reposition_queue_panel,
                           _resize_queue_panel)
# From system.py: Ghostty terminal focus
from .system import _focus_session
# From paths.py: APP_SUPPORT-relative settings path
from .paths import SETTINGS_FILE as _SETTINGS_PATH
# From queue.py: message queue storage
from .queue import load_queue, save_queue

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
        # Panel backgrounded (Cmd+K): Cmd+L / bar-click brings it back to front, does NOT close
        if app._panel_backgrounded:
            if app._panel_open:
                app._panel.orderFrontRegardless()
            elif app._tracker_open:
                app._tracker_panel.orderFrontRegardless()
            elif app._queue_open:
                app._queue_panel.orderFrontRegardless()
            app._panel_backgrounded = False
            return
        # Cmd+L closes whichever panel is open; if none → open main
        if app._tracker_open:
            _close_tracker_panel(app)
            return
        if app._queue_open:
            _close_queue_panel(app)
            return
        if app._panel_open:
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
        _handle_expand_bead(self._app, sender.tag())

    def untrackBead_(self, sender):
        _handle_untrack_bead(self._app, sender.tag())

    def focusSession_(self, sender):
        cwd = self._app._cwd_map.get(sender.tag())
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
        app._queue_toggle_btn.setAttributedTitle_(
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
        from .setup_menubar import write_plist
        write_plist()   # resync ~/Library/LaunchAgents plist synchronously before exit
        # Detached helper: bootout + bootstrap (with retry) after current process exits
        cmd = f'sleep 0.5 && "{sys.executable}" "{_SETUP_PY}"'
        subprocess.Popen(['sh', '-c', cmd], start_new_session=True)
        rumps.quit_application()   # clean status-bar teardown; launchd respawns from fresh plist

    def abortBgTimer_(self, sender):
        # Per-project abort: only kill timers for the project whose button was clicked
        project_name = self._app._abort_project_for_tag.get(sender.tag())
        if project_name is None:
            return
        sessions = list_alive_sessions()
        cwd_to_project = {s.cwd: s.project_name for s in sessions if not s.is_worker and s.cwd}
        proj_bg = _scan_bg_sleep_timers(cwd_to_project).get(project_name)
        if proj_bg:
            _abort_bg_sleep_timers(proj_bg.sleep_pids)

    def addQueueRow_(self, sender):
        app = self._app
        session_id = app._queue_add_tags.get(sender.tag())
        if not session_id:
            return
        app._pending_queue_count[session_id] = app._pending_queue_count.get(session_id, 0) + 1
        sessions = list_alive_sessions()
        app._last_sessions = sessions
        _rebuild_queue_panel(app, sessions)

    def removeQueueMsg_(self, sender):
        app = self._app
        info = app._queue_remove_tags.get(sender.tag())
        if not info:
            return
        session_id, idx = info
        q = load_queue()
        msgs = q.get(session_id, [])
        if 0 <= idx < len(msgs):
            del msgs[idx]
            if msgs:
                q[session_id] = msgs
            else:
                q.pop(session_id, None)
            save_queue(q)
            app._queue_data = q
        sessions = list_alive_sessions()
        app._last_sessions = sessions
        _rebuild_queue_panel(app, sessions)

    def commitQueueField_(self, sender):
        app = self._app
        tag        = sender.tag()
        text       = str(sender.stringValue()).strip()
        session_id = app._pending_queue_tags.get(tag)
        app._committed_queue_tags.add(tag)   # suppress controlTextDidEndEditing_ cancel path
        if text and session_id:
            q = load_queue()
            q.setdefault(session_id, []).append({"text": text, "sent_at": None})
            save_queue(q)
            app._queue_data = q
        if session_id:
            count = app._pending_queue_count.get(session_id, 1) - 1
            if count > 0:
                app._pending_queue_count[session_id] = count
            else:
                app._pending_queue_count.pop(session_id, None)
        sessions = list_alive_sessions()
        app._last_sessions = sessions
        _rebuild_queue_panel(app, sessions)

    def controlTextDidEndEditing_(self, notification):
        app = self._app
        tag = notification.object().tag()
        if tag in app._committed_queue_tags:
            app._committed_queue_tags.discard(tag)
            return   # already committed via Enter — don't cancel
        # Focus lost without Enter → decrement pending count for this row
        session_id = app._pending_queue_tags.get(tag)
        if session_id:
            count = app._pending_queue_count.get(session_id, 1) - 1
            if count > 0:
                app._pending_queue_count[session_id] = count
            else:
                app._pending_queue_count.pop(session_id, None)
        if app._queue_open:
            sessions = list_alive_sessions()
            app._last_sessions = sessions
            _rebuild_queue_panel(app, sessions)

    def windowDidResize_(self, notification):
        frame = notification.object().frame()
        app   = self._app
        app._panel_width      = int(max(frame.size.width,  PANEL_MIN_WIDTH))
        app._panel_min_height = int(max(frame.size.height, PANEL_MIN_HEIGHT))
        _save_settings(app._auto_focus, app._panel_width, app._panel_min_height)

    def windowDidEndLiveResize_(self, notification):
        app = self._app
        if app._tracker_open:
            _rebuild_bead_panel(app)
        elif app._panel_open:
            sessions = list_alive_sessions()
            cwd_to_project = {s.cwd: s.project_name for s in sessions if not s.is_worker and s.cwd}
            bg_by_project = _scan_bg_sleep_timers(cwd_to_project)
            _rebuild_panel(app, sessions, bg_by_project)
            _reregister_digit_hotkeys(app)
        elif app._queue_open:
            sessions = list_alive_sessions()
            app._last_sessions = sessions
            _rebuild_queue_panel(app, sessions)


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
        self._abort_btns_by_project: dict = {}   # {project_name: NSButton}; per-project abort buttons
        self._abort_project_for_tag: dict = {}   # {tag_int: project_name}; for abortBgTimer_ dispatch
        self._auto_focus, self._panel_width, self._panel_min_height = _load_settings()
        self._panel, self._panel_sv, self._panel_quit_btn, self._toggle_btn, self._panel_kill_btn = _make_nspanel()
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
        self._bead_data: dict        = {}   # {project_name: [bead_dict, ...]}
        self._bead_db_paths: dict    = {}   # {project_name: Path}
        self._bead_expanded: dict    = {}   # {bead_id: expand_text_str}
        self._bead_displayed: dict   = {}   # {bead_id: NSButton} expand buttons
        self._bead_expand_tags: dict = {}   # {tag: bead_id}
        self._bead_untrack_tags: dict = {}  # {tag: (bead_id, project_name)}
        self._bead_tick_counter: int = 4    # starts at 4 → first tick fires refresh
        self._tracker_panel, self._tracker_sv, self._tracker_toggle_btn = _make_bead_nspanel()
        self._hotkey_arr_right_ref = None   # hk_ref for Cmd+→ (module holds CFUNCTYPE anchor)
        self._hotkey_arr_left_ref  = None   # hk_ref for Cmd+← (module holds CFUNCTYPE anchor)
        self._panel_backgrounded: bool = False   # True while active panel is orderBack_'d behind other windows
        # Queue panel state
        self._queue_open: bool = False
        self._queue_panel, self._queue_sv, self._queue_toggle_btn = _make_queue_nspanel()
        self._queue_displayed_names: set = set()   # session names currently shown in queue panel
        self._queue_data: dict = {}                # {session_id: [msgs]} — refreshed each tick from msg_queue.json
        self._pending_queue_count: dict = {}       # {session_id: int} — count of active inline NSTextField rows per session
        self._pending_queue_tags: dict = {}        # {NSTextField tag → session_id}; reset on each rebuild
        self._queue_add_tags: dict = {}            # {+ button tag → session_id}; reset on each rebuild
        self._queue_remove_tags: dict = {}         # {− button tag → (session_id, msg_index)}; reset each rebuild
        self._committed_queue_tags: set = set()    # NSTextField tags committed via Enter; prevent cancel in controlTextDidEndEditing_
        self._last_sessions: list = []             # last live sessions snapshot; used by queue panel rebuild

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
                self._tracker_toggle_btn.setTarget_(self._panel_controller)
                self._tracker_toggle_btn.setAction_(b'toggleAutoJump:')
                self._panel.setDelegate_(self._panel_controller)
                self._tracker_panel.setDelegate_(self._panel_controller)
                self._queue_panel.setDelegate_(self._panel_controller)
                self._queue_toggle_btn.setTarget_(self._panel_controller)
                self._queue_toggle_btn.setAction_(b'toggleAutoJump:')
                _set_bar_icon(self, ICON_NORMAL)   # replace setTitle_ with attributed version
                self._initialized = True
            except AttributeError:
                return   # _nsapp not ready yet; retry next tick
        now = time.time()
        try:
            sessions = list_alive_sessions()
        except Exception:
            sessions = []
        self._last_sessions = sessions
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
        self._bead_tick_counter += 1
        if self._bead_tick_counter % 5 == 0 or self._tracker_open:
            _refresh_bead_data(self, sessions)
        # Refresh queue data; detect changes to trigger panel rebuild if open
        new_queue = load_queue()
        queue_changed = new_queue != self._queue_data
        self._queue_data = new_queue
        if self._queue_open:
            q_names = {s.name for s in sessions if not s.is_worker}
            if queue_changed or q_names != self._queue_displayed_names:
                _rebuild_queue_panel(self, sessions)
        if self._panel_open:
            session_names = {s.name for s in sessions}
            new_abort_projs = {p for p in bg_by_project if p != 'unknown'}
            abort_flap = new_abort_projs != set(self._abort_btns_by_project)
            set_change = session_names != set(self._displayed_items)
            if abort_flap or set_change:
                reasons = '+'.join(r for r, v in [('abort-flap', abort_flap), ('session-set-change', set_change)] if v)
                _tick_log(True, sessions, self._displayed_items, reasons)
                _rebuild_panel(self, sessions, bg_by_project)
                _reregister_digit_hotkeys(self)
            else:
                _tick_log(True, sessions, self._displayed_items, 'no-change')
                _update_panel_inplace(self, sessions, bg_by_project)
            self._last_statuses = {s.name: s.status for s in sessions}
        else:
            session_names = {s.name for s in sessions}
            changed = _statuses_changed(sessions, self._last_statuses)
            self._last_statuses = {s.name: s.status for s in sessions}
            if changed:
                _blink(self)
            if session_names != set(self._displayed_items):
                _tick_log(False, sessions, self._displayed_items, 'session-set-change')
                _rebuild_panel(self, sessions, bg_by_project)
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

# Register (or re-register) Cmd+1..9 hotkeys from current _cwd_map (slots 1..9); unregisters previous refs first
def _reregister_digit_hotkeys(app: 'CCMenuBarApp') -> None:
    if app._hotkey_digits_refs:
        unregister_hotkeys(app._hotkey_digits_refs)
        app._hotkey_digits_refs = []
        app._hotkey_digits_cb   = None
    slots = {slot: cwd for slot, cwd in app._cwd_map.items() if slot <= 9 and cwd}
    if not slots:
        return
    cb_map = {slot: (lambda cwd=cwd: _focus_session(cwd)) for slot, cwd in slots.items()}
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
        if from_panel == 'main':      from_obj = app._panel
        elif from_panel == 'tracker': from_obj = app._tracker_panel
        else:                         from_obj = app._queue_panel
        from_frame = from_obj.frame()   # capture before close
        if from_panel == 'main':      _close_main_panel(app)
        elif from_panel == 'tracker': _close_tracker_panel(app)
        elif from_panel == 'queue':   _close_queue_panel(app)
        if to_panel == 'main':        _open_main_panel(app)
        elif to_panel == 'tracker':   _open_tracker_panel(app)
        elif to_panel == 'queue':     _open_queue_panel(app)
        if to_panel == 'main':        to_obj = app._panel
        elif to_panel == 'tracker':   to_obj = app._tracker_panel
        else:                         to_obj = app._queue_panel
        to_obj.setFrame_display_(from_frame, True)   # restore position; display:True flushes immediately
    except Exception as e:
        print(f'[menubar] cycling {from_panel}→{to_panel} error: {e}', file=sys.stderr)

# Cmd+K handler: toggle active panel between foreground and background (orderBack_/orderFrontRegardless).
# Does NOT close the panel — _panel_open / _tracker_open stay True.
# Cycling (Cmd+→/←) resets _panel_backgrounded via _close_main/tracker_panel before opening the other.
def _background_panel(app: 'CCMenuBarApp') -> None:
    try:
        if app._panel_backgrounded:
            if app._panel_open:
                app._panel.setLevel_(25)   # NSStatusWindowLevel — restore before foregrounding
                app._panel.orderFrontRegardless()
            elif app._tracker_open:
                app._tracker_panel.setLevel_(25)   # NSStatusWindowLevel
                app._tracker_panel.orderFrontRegardless()
            elif app._queue_open:
                app._queue_panel.setLevel_(25)   # NSStatusWindowLevel
                app._queue_panel.orderFrontRegardless()
            app._panel_backgrounded = False
        elif app._panel_open:
            app._panel.setLevel_(0)   # NSNormalWindowLevel — allows orderBack_ to work
            app._panel.orderBack_(None)
            app._panel_backgrounded = True
        elif app._tracker_open:
            app._tracker_panel.setLevel_(0)   # NSNormalWindowLevel
            app._tracker_panel.orderBack_(None)
            app._panel_backgrounded = True
        elif app._queue_open:
            app._queue_panel.setLevel_(0)   # NSNormalWindowLevel
            app._queue_panel.orderBack_(None)
            app._panel_backgrounded = True
    except Exception as e:
        print(f'[menubar] Cmd+K deferred-block error: {e}', file=sys.stderr)

# Open main panel: rebuild → reposition → show → register Cmd+→ (→Beads) + Cmd+← (→Queue wrap) + Cmd+1..9
def _open_main_panel(app: 'CCMenuBarApp') -> None:
    sessions = list_alive_sessions()
    app._last_sessions = sessions
    cwd_to_project = {s.cwd: s.project_name for s in sessions if not s.is_worker and s.cwd}
    bg_by_project = _scan_bg_sleep_timers(cwd_to_project)
    _rebuild_panel(app, sessions, bg_by_project)
    _reposition_panel(app._panel, app._nsapp.nsstatusitem)
    app._panel.orderFrontRegardless()
    app._panel.enableCursorRects()
    app._panel_open = True
    _reregister_digit_hotkeys(app)
    _, app._hotkey_arr_right_ref = register_cmd_arrow_right(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'main', 'tracker')))
    _, app._hotkey_arr_left_ref = register_cmd_arrow_left(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'main', 'queue')))

# Close main panel: hide + unregister Cmd+→ + Cmd+← + Cmd+1..9
def _close_main_panel(app: 'CCMenuBarApp') -> None:
    app._panel.orderOut_(None)
    app._panel_open = False
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
    _rebuild_bead_panel(app)
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

# Open queue panel: rebuild → reposition → show + register Cmd+→ (→Sessions wrap) + Cmd+← (→Beads)
def _open_queue_panel(app: 'CCMenuBarApp') -> None:
    sessions = list_alive_sessions()
    app._last_sessions = sessions
    app._queue_data = load_queue()
    _rebuild_queue_panel(app, sessions)
    _reposition_queue_panel(app._queue_panel, app._nsapp.nsstatusitem)
    app._queue_panel.orderFrontRegardless()
    app._queue_panel.enableCursorRects()
    app._queue_open = True
    _, app._hotkey_arr_right_ref = register_cmd_arrow_right(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'queue', 'main')))
    _, app._hotkey_arr_left_ref = register_cmd_arrow_left(
        lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: _deferred_close_open(app, 'queue', 'tracker')))

# Close queue panel: hide + unregister Cmd+→ + Cmd+←
def _close_queue_panel(app: 'CCMenuBarApp') -> None:
    app._queue_panel.orderOut_(None)
    app._queue_open = False
    app._panel_backgrounded = False
    unregister_cmd_arrow_right(app._hotkey_arr_right_ref)
    app._hotkey_arr_right_ref = None
    unregister_cmd_arrow_left(app._hotkey_arr_left_ref)
    app._hotkey_arr_left_ref = None

# Refresh bead data from sessions; rebuild tracker panel if open and bead set changed
def _refresh_bead_data(app: 'CCMenuBarApp', sessions) -> None:
    pdb      = project_db_map(sessions)
    new_data = load_tracked_beads(pdb)
    changed  = new_data != app._bead_data
    app._bead_db_paths, app._bead_data = pdb, new_data
    if changed and app._tracker_open:
        _rebuild_bead_panel(app)

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
