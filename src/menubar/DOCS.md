# src/menubar/

## Role

Standalone macOS status-bar (menubar) application that shows all currently-running Claude Code sessions on this Mac with their working/idle status and background-task badge. Independent of the tmux TUI — launched via `workflow.py --mode menubar` or launchd. macOS only (rumps/AppKit).

## Public Interface

`from src.menubar import run` — `run()` is the sole entry point. Called by `workflow.py --mode menubar`.

## Flow

1. `run()` (system.py) → sets `LSUIElement=1` env → acquires singleton lock → instantiates `CCMenuBarApp` → `app.run()` starts AppKit runloop.
2. `CCMenuBarApp._tick()` (app.py) fires every 1.5s → `list_alive_sessions()` → `_scan_bg_sleep_timers(cwd_to_project)` → `focus.tick()` (auto-focus debounce + auto-abort check) → if panel closed: blink on status change; `panel.rebuild()` only on session-set change; if panel open: on None↔Some transition or session-set change call `panel.rebuild()` (adds/removes abort button, grows panel), otherwise `panel.update_inplace()` (updates NSButton attributed titles only, no resize).
3. `list_alive_sessions()` (discover.py) → refreshes CC-process cache (proc_cache.py) → refreshes Ghostty TTY-to-UUID mapping (ghostty.py) → scans `~/.claude/projects/*/` → determines working/idle status per session type → checks `/tmp/claude-<uid>/` for in-progress tasks (proc_cache.py).
4. Click on a main session → `_focus_session(cwd)` (system.py) → looks up Ghostty terminal UUID (ghostty.py) → `focus terminal id "<UUID>"` (Path A) or cwd-match fallback (Path B). Same path triggered by Cmd+1..9 when panel is open (see hotkey_controller.py + app.py lifecycle).

## Modules

### panel.py (369 LOC)

**Purpose:** NSPanel construction, NSView/NSTextField/NSButton subclasses for cursor tracking, all UI factory helpers, and pure computation helpers. Render functions (`rebuild`, `update_inplace`, `_resize_panel`) and re-entry guard moved to `panel_manager.py` (Step 4/6). Footer has two buttons: Kill (left) + Restart (right). Main session rows show the real macOS Mission Control desktop number as slot prefix `[N]` (`_GRID_COL0_W=40`), driven by `SessionInfo.desktop_no`; a conflict (2+ mains on the same desktop) shows `[!N]` in red; detection-failed mains (`desktop_no=None`) show no prefix. Workers carry no prefix. `_project_desktop_no(sessions, project_name)` returns `min(desktop_no)` across a project's mains (None if all-None) — used by `panel_manager.py` for the desktop-ordered sort key. Per-project abort buttons (Option B) embedded inline in separator rows — `_make_separator_view` returns `(NSView, Optional[NSButton])`. Defines `_KeyablePanel(NSPanel)` — overrides `canBecomeKeyWindow` to return True so all three panels can receive keyboard events despite `NSWindowStyleMaskNonactivatingPanel`; imported by `bead_controller.py` and `queue_controller.py`. Also overrides `performKeyEquivalent_` to route Cmd+{V,C,X,A,Z} and Shift+Cmd+Z to the first responder. Pure UI concern — no rumps, no ctypes, no subprocess, no direct `app` instance access.
**Reads:** function parameters only (sessions, bg_by_project, panel_width passed from callers). No direct `app` instance state accessed.
**Writes:** NSPanel frame (via `_reposition_panel`); creates NSView/NSButton/NSTextField UI objects returned to callers.
**Key signatures:** `_make_nspanel()`, `_reposition_panel(panel, nsstatusitem)`, `_compute_required_height(sorted_sessions)`, `_make_separator_view(project_name, panel_width, proj_min_remaining)`.
**Called by:** `panel_lifecycle.py` (`_reposition_panel` in `_open_main_panel`); `panel_manager.py` (imports constants + all factory helpers); `queue_controller.py` (imports constants + helpers).
**Calls out:** `AppKit`, `Foundation`, `itertools`; `.menubar_log` (`log_menubar`).

---

### panel_manager.py (192 LOC)

**Purpose:** Per-concern controller for main-session panel (Step 4/6 of CCMenuBarApp composition refactor). `PanelManager(app)` owns 8 migrating attrs (`_panel_open`, `_initialized`, `_displayed_items`, `_cwd_map`, `_desktop_to_cwd`, `_abort_btns_by_project`, `_abort_project_for_tag`, `_rebuild_in_progress`) plus NSPanel and stack-view refs from `_make_nspanel()` (`_panel`, `_panel_sv`, `_panel_quit_btn`, `_toggle_btn`, `_panel_kill_btn`). Exposes `rebuild(sessions, bg_by_project=None)` (re-entry guarded full panel rebuild, adapted from `panel.py:_rebuild_panel_inner`), `update_inplace(sessions, bg_by_project)` (in-place dot+badge update, adapted from `panel.py:_update_panel_inplace`), `_resize_panel(new_h)` (adapted from `panel.py:_resize_panel`). Settings `_auto_focus`, `_panel_width`, `_panel_min_height` remain on `app` (cross-controller shared preferences; moving to PanelManager would create bead/queue→panel coupling with no benefit).
**Reads:** `self.app._panel_width`, `self.app._panel_min_height`, `self.app._auto_focus`, `self.app._panel_controller`; `sessions` and `bg_by_project` from callers.
**Writes:** `self._displayed_items`, `self._cwd_map`, `self._desktop_to_cwd`, `self._abort_btns_by_project`, `self._abort_project_for_tag` (reset each rebuild); `self._panel` frame (via `_resize_panel`). Sessions sorted by `(_project_desktop_no or +inf, project_name, is_worker, name)` — desktop-ordered, detection-failed projects last. Conflict set (`Counter` over `desktop_no`, count>1) drives `[!N]` red rendering. `_desktop_to_cwd` maps real desktop number → cwd for conflict-free mains only (Cmd+N focuses the session on Mission Control desktop N); conflicted desktops are excluded so the hotkey stays unambiguous. `_cwd_map` maps tag → cwd for click routing.
**Key signatures:** `PanelManager.__init__(app)`, `rebuild(sessions, bg_by_project=None)`, `update_inplace(sessions, bg_by_project)`, `_resize_panel(new_h)`.
**Called by:** `app.py:CCMenuBarApp.__init__` (construction); `app.py:CCMenuBarApp._tick` (`panel.rebuild`, `panel.update_inplace`, `panel._panel_open`, `panel._initialized`, `panel._desktop_to_cwd`); `app.py:_open_main_panel` (`panel.rebuild`, `panel._panel.*`, `panel._panel_open`, `panel._desktop_to_cwd`); `app.py:_close_main_panel` (`panel._panel.*`, `panel._panel_open`); `app.py:_PanelController.focusSession_` (`panel._cwd_map`); `app.py:_PanelController.abortBgTimer_` (`panel._abort_project_for_tag`); `app.py:_PanelController.windowDidEndLiveResize_` (`panel.rebuild`, `panel._panel_open`, `panel._desktop_to_cwd`); `app.py:_background_panel`, `app.py:_deferred_close_open` (`panel._panel`).
**Calls out:** `AppKit`, `Foundation`, `itertools.groupby`; `.panel` (constants + factories).

---

### queue_controller.py (269 LOC)

**Purpose:** Per-concern controller for the queue panel (Step 3/6 of CCMenuBarApp composition refactor). `QueueController(app)` owns all queue state (`_queue_open`, `_queue_panel`, `_queue_sv`, `_queue_toggle_btn`, `_queue_displayed_names`, `_queue_data`, `_pending_queue_tags`, `_pending_queue_views`, `_queue_add_tags`, `_queue_remove_tags`, `_queue_toggle_tags`, `_rebuild_in_progress`) and exposes `tick(sessions)` (load + conditional rebuild), `open(sessions)` (explicit pre-load + unconditional rebuild for panel-open), `rebuild(sessions)` + `_rebuild_inner(sessions)` (re-entry guarded full panel rebuild), `compute_height(sessions)`, `_resize_panel(new_h)`, and action handlers `handle_add_row`, `handle_toggle_entry`, `handle_remove_entry`, `handle_commit_field`, `handle_text_end_editing`, `handle_try_deliver`. Uses `_QueuePanel(_KeyablePanel)` subclass: plain `q` with no modifiers mid-text jumps cursor to end; `q` at end/empty inserts normally (`sendEvent_` heuristic). ONE NSGridView (1-col): every row is a full-width container `NSView` (`wantsLayer=True`). Three-state rows: **draft** (editable NSTextField, `↑` toggle, `×` delete), **queued** (red bg tint `α0.18`, read-only label, `↓` toggle, `×` delete), **sent** (green bg tint, read-only label, no toggle, `×` delete). Column layout (frame-based): `[0..col0_w) text | [col0_w..+22pt) toggle | [+22pt..pw) ×`. Module-level pure helpers (`_make_queue_nspanel`, `_reposition_queue_panel`, `_make_queue_add_btn`) stay module-level; `_reposition_queue_panel` imported by `app.py:_open_queue_panel`. `handle_try_deliver` absorbed from `app.py:_try_deliver_now` — reads `HOOKS_FILE`, delivers via `queue.deliver_message`, marks entry sent. Render functions (`_rebuild_inner`, `compute_height`, `_resize_panel`) and all render-concern helpers moved verbatim to `queue_panel_render.py` (see below).
**Reads:** `self._queue_data`, `self._pending_queue_tags`, `self._pending_queue_views`, `self._queue_add_tags`, `self._queue_remove_tags`, `self._queue_toggle_tags`; `self.app._panel_width`, `self.app._panel_min_height`, `self.app._auto_focus`, `self.app._panel_controller`; `HOOKS_FILE` (`handle_try_deliver`); `sessions` list from caller.
**Writes:** `self._queue_data`, `self._queue_displayed_names`, `self._queue_add_tags`, `self._queue_remove_tags`, `self._pending_queue_tags`, `self._pending_queue_views`, `self._queue_toggle_tags` (reset each rebuild); `self._queue_panel` frame (via `_resize_panel`); `QUEUE_FILE` (via `save_queue`).
**Key signatures:** `QueueController.__init__(app)`, `tick(sessions)`, `open(sessions)`, `rebuild(sessions)`, `handle_add_row(tag)`, `handle_toggle_entry(tag)`, `handle_remove_entry(tag)`, `handle_commit_field(tag, text)`, `handle_text_end_editing(tag, text)`, `handle_try_deliver(session_id, text, idx)`; module-level: `_make_queue_nspanel()`, `_reposition_queue_panel(panel, nsstatusitem)`.
**Called by:** `app.py:CCMenuBarApp.__init__` (construction); `app.py:CCMenuBarApp._tick` (`queue.tick`); `panel_lifecycle.py:_open_queue_panel` (`queue.open`); `app.py:_PanelController.addQueueRow_` → `handle_add_row`; `app.py:_PanelController.toggleQueueEntry_` → `handle_toggle_entry`; `app.py:_PanelController.removeQueueEntry_` → `handle_remove_entry`; `app.py:_PanelController.commitQueueField_` → `handle_commit_field`; `app.py:_PanelController.controlTextDidEndEditing_` → `handle_text_end_editing`; `app.py:_PanelController.windowDidEndLiveResize_` (`queue.rebuild`).
**Calls out:** `AppKit`, `Foundation`, `objc`, `json`, `datetime`; `.panel` (constants + helpers); `.queue` (`load_queue`, `save_queue`, `deliver_message`); `.paths` (`HOOKS_FILE`).

---

### queue_panel_render.py (207 LOC)

**Purpose:** Render-concern module for the queue panel, extracted from `queue_controller.py`. Contains `_rebuild_inner(controller, sessions)` — full NSGridView rebuild dispatched via `_qpr_rebuild_inner` alias; `_compute_height(controller, sessions)` — required-height calculation; `_resize_panel(controller, new_h)` — NSPanel resize anchored at top edge; `_build_session_grid(controller, main_sessions, ...)` — per-session row construction helper; `_build_entry_row_view(controller, s, i, entry, ...)` — per-entry container NSView with three-state rendering (draft/queued/sent); `_make_queue_add_btn(grid_w)` — + button factory. Takes `controller` (a `QueueController` instance) as first argument; mutates controller state dicts (`_pending_queue_tags`, `_pending_queue_views`, `_queue_add_tags`, `_queue_remove_tags`, `_queue_toggle_tags`, `_queue_displayed_names`) as part of rebuild.
**Reads:** `controller._queue_data`, `controller.app._panel_width`, `controller.app._panel_min_height`, `controller.app._auto_focus`, `controller.app._panel_controller`.
**Writes:** controller state dicts (reset + repopulated each rebuild); `controller._queue_panel` frame (via `_resize_panel`); creates AppKit NSView/NSTextField/NSButton UI objects.
**Key signatures:** `_rebuild_inner(controller, sessions)`, `_compute_height(controller, sessions) -> int`, `_resize_panel(controller, new_h)`.
**Called by:** `queue_controller.py:QueueController._rebuild_inner` (alias `_qpr_rebuild_inner`), `QueueController.compute_height`, `QueueController._resize_panel` — thin delegations only.
**Calls out:** `AppKit` (NSGridView, NSView, NSTextField, NSColor, NSAttributedString, NSFont, NSMakeRect), `Foundation`; `.panel` (constants + helpers).

---

### rag_controller.py (181 LOC)

**Purpose:** Per-concern controller for the RAG status panel. `RagController(app)` owns all RAG state (`_rag_open`, `_rag_panel`, `_rag_sv`, `_rag_toggle_btn`, `_rag_status_label`) and exposes `tick(sessions)` (in-place label update each 1.5s tick) and `rebuild()` (full panel rebuild on open/resize). Module-level: `_make_rag_nspanel()` (NSPanel factory), `_reposition_rag_panel(panel, nsstatusitem)`, `_read_rag_status(lock_path)` (reads `~/.rag-locks/rag.lock`; absent/unreadable/dead-pid/non-index-command → `'no indexing currently running'`; live → three-branch format based on lock `progress` dict: (1) `chunks_done`+`chunks_total` present → `'{collection} · {done+1}/{total} docs · {chunks_done}/{chunks_total} chunks · {elapsed}'`; (2) `total > 0`, no chunk fields → `'{collection} · {done}/{total} docs · {elapsed}'`; (3) empty/no progress → `'{collection} · {elapsed}'`; backward-compat with old-format locks lacking chunk fields), `_pid_alive(pid)` (os.kill(pid,0) with ESRCH→False, EPERM→True), `_format_elapsed(started_at)` (ISO-8601 string → `'{M}m{SS}s'` or `'{S}s'`). Panel content: single NSTextField status label; no grid, no interactive rows. Follows the Queue-controller ownership pattern — all panel refs on controller, not on app.
**Reads:** `~/.rag-locks/rag.lock` (via `_read_rag_status`); `self.app._panel_width`, `self.app._panel_min_height`, `self.app._auto_focus`, `self.app._panel_controller`.
**Writes:** `self._rag_status_label` (in-place text update each tick); `self._rag_panel` frame (via `_resize_rag_panel`).
**Key signatures:** `RagController.__init__(app)`, `tick(sessions)`, `rebuild()`; module-level: `_make_rag_nspanel()`, `_reposition_rag_panel(panel, nsstatusitem)`, `_read_rag_status(lock_path=_RAG_LOCK)`.
**Called by:** `app.py:CCMenuBarApp.__init__` (construction); `app.py:CCMenuBarApp._tick` (`rag.tick`); `app.py:_open_rag_panel` (`rag.rebuild`, `_reposition_rag_panel`); `app.py:_PanelController.windowDidEndLiveResize_` (`rag.rebuild`); `app.py:_deferred_close_open`, `app.py:_background_panel`, `app.py:_close_rag_panel` (`rag._rag_panel`, `rag._rag_open`).
**Calls out:** `AppKit`, `Foundation`; `.panel` (constants + helpers); `json`, `os`, `errno`, `datetime`, `pathlib`.

---

### paths.py (55 LOC)

**Purpose:** Single source of truth for 8 APP_SUPPORT file paths under `~/Library/Application Support/com.brunowinter.monitor-cc-menubar/`: `SETTINGS_FILE`, `HOOKS_FILE`, `HOOKS_LOCK`, `PID_FILE`, `QUEUE_FILE` (`msg_queue.json`), `QUEUE_LOCK` (`queue.lock`), `GHOSTTY_CWD_UUID_FILE` (`ghostty_cwd_uuid.json`), `ORCHESTRATOR_SIGNALS_FILE` (`orchestrator_signals.json` — written by worker-cli send, read by menubar for auto-abort grace). Runs `_migrate_from_dotfiles()` and `_migrate_from_old_bundle_id()` at import.
**Reads:** old dotfile paths under `~` on first import (`_migrate_from_dotfiles`); old bundle-id dir `~/Library/Application Support/com.brunowinter.monitor_cc_menubar/` on first import (`_migrate_from_old_bundle_id`).
**Writes:** creates `_APP_SUPPORT` dir; moves old dotfiles + old-bundle-id runtime files to new paths on first import. Idempotent: new wins (no clobber).
**Called by:** `app.py` (`SETTINGS_FILE`); `proc_cache.py` (`HOOKS_FILE`); `queue_controller.py` (`HOOKS_FILE`); `system.py` (`PID_FILE`); `queue.py` (`QUEUE_FILE`, `QUEUE_LOCK`, `GHOSTTY_CWD_UUID_FILE`); `ghostty.py` (`_APP_SUPPORT`). `hook_writer.py` defines `_APP_SUPPORT` inline (standalone script — relative import not usable).
**Calls out:** `pathlib` only.

---

### queue.py (102 LOC)

**Purpose:** Message queue storage + Ghostty delivery for the menubar app side. `load_queue()` / `save_queue(q)` — atomic read/write of `APP_SUPPORT/msg_queue.json` (schema: `{session_id: [{text: str, state: "draft"|"queued"|"sent", sent_at: str|null}]}`). `load_queue` normalizes all legacy formats via `_normalize_entry` on read — migration is transparent on next save. Migration rules: bare string → `{state:"queued"}`; dict missing `state`: `sent_at` non-null → `state:"sent"`, else → `state:"queued"`. Drafts are only created via the + button, never from migration. `deliver_message(cwd, message)` — reads `ghostty_cwd_uuid.json` for terminal UUID, then `focus terminal id UUID` + System Events `keystroke + Return`; falls back to cwd-based focus. Hook delivery uses inline equivalents in `hook_writer.py` (standalone, can't import from package).
**Reads:** `QUEUE_FILE` (`msg_queue.json`); `GHOSTTY_CWD_UUID_FILE` (`ghostty_cwd_uuid.json`).
**Writes:** `QUEUE_FILE` (atomic via temp + `os.replace()`); osascript delivery to Ghostty.
**Called by:** `queue_controller.py:QueueController` (`load_queue`, `save_queue`, `deliver_message`).
**Calls out:** `json`, `os`, `subprocess`; `.paths` (`QUEUE_FILE`, `QUEUE_LOCK`, `GHOSTTY_CWD_UUID_FILE`).

---

### app.py (309 LOC)

**Purpose:** `CCMenuBarApp` (rumps.App subclass) + `_PanelController` (NSObject target for all button actions + NSTextField delegate) + `_tick` timer + blink + bar-icon + settings load/save. Three-panel lifecycle and cycling moved to `panel_lifecycle.py`. Settings load/save moved to `app_settings.py`. Queue action handlers (`addQueueRow_`, `toggleQueueEntry_`, `removeQueueEntry_`, `commitQueueField_`, `controlTextDidEndEditing_`) are 1-line delegates to `self._app.queue.handle_*` methods. `_tick` delegates session snapshot to `self.sessions.refresh()`, focus+abort logic to `self.focus.tick(sessions, bg_by_project, now)`, queue refresh + conditional rebuild to `self.queue.tick(sessions)`, panel rebuild/update to `self.panel.rebuild()` / `self.panel.update_inplace()`, and digit-hotkey re-registration to `self.hotkey.reregister_digits(self.panel._desktop_to_cwd)`; status snapshot updated via `self.focus.update_statuses(sessions)` at tick-end.
**Reads:** `self.sessions.refresh()` (via `SessionsController`) + `_scan_bg_sleep_timers()` on every tick and on panel open; `SETTINGS_FILE` on launch.
**Writes:** bar icon; `SETTINGS_FILE` on toggle/resize; `src/logs/menubar.log` ([abort] category via `_abort_log_write`; [tick] category when `MENUBAR_DIAGNOSTICS=1`).
**Called by:** `system.py:run()` (lazy import).
**Calls out:** `rumps`, `AppKit`, `Foundation`, `objc`, `subprocess`, `threading`; `.sessions_controller`, `.focus_controller`, `.queue_controller`, `.rag_controller`, `.panel_manager`, `.panel`, `.hotkey_controller`, `.system`, `.discover`, `.bg_timer`; `.app_settings` (`_load_settings`, `_save_settings`); `.panel_lifecycle` (8 lifecycle functions); `.menubar_log` (`log_menubar`, lazy `cleanup_old_lines`); `.setup_menubar` (lazy).

---

### app_settings.py (37 LOC)

**Purpose:** Settings load/save extracted from `app.py`. `_load_settings()` reads `SETTINGS_FILE` JSON → `(auto_focus, panel_width, panel_min_height)` with backwards-compat fallback to legacy `panel_max_height` key and clamping to `PANEL_MIN_*` floors. `_save_settings(auto_focus, panel_width, panel_min_height)` writes atomically via tempfile + `os.replace`. Both functions were verbatim-moved from `app.py` (AST-identical).
**Reads:** `SETTINGS_FILE` (`APP_SUPPORT/settings.json`).
**Writes:** `SETTINGS_FILE` (atomic, tempfile swap).
**Called by:** `app.py:CCMenuBarApp.__init__` (`_load_settings`); `app.py:_PanelController.toggleAutoJump_`, `windowDidResize_` (`_save_settings`).
**Calls out:** `json`, `os`; `.paths` (`SETTINGS_FILE`); `.panel` (constants for defaults/clamping).

---

### panel_lifecycle.py (145 LOC)

**Purpose:** Three-panel open/close/background/cycle lifecycle extracted from `app.py`. Contains 8 functions verbatim-moved from `app.py`: `_open_main_panel`, `_close_main_panel`, `_open_rag_panel`, `_close_rag_panel`, `_open_queue_panel`, `_close_queue_panel` (each: rebuild → reposition → show → register hotkeys, or hide → unregister), `_deferred_close_open(app, from_panel, to_panel)` (generic Cmd+→/← cycling; captures outgoing frame, closes from-panel, opens to-panel, restores frame), `_background_panel(app)` (Cmd+K toggle: orderBack_/orderFrontRegardless without closing). No circular import: none of these import `app.py`.
**Reads:** `app.panel.*`, `app.rag.*`, `app.queue.*`, `app.hotkey.*`, `app.sessions`, `app._nsapp.nsstatusitem`; `_scan_bg_sleep_timers`.
**Writes:** NSPanel frame/order via each controller's panel ref; hotkey registration/unregistration via `app.hotkey`.
**Key signatures:** `_open_main_panel(app)`, `_close_main_panel(app)`, `_open_rag_panel(app)`, `_close_rag_panel(app)`, `_open_queue_panel(app)`, `_close_queue_panel(app)`, `_deferred_close_open(app, from_panel, to_panel)`, `_background_panel(app)`.
**Called by:** `app.py:_PanelController.togglePanel_` (`_close_rag_panel`, `_close_queue_panel`, `_close_main_panel`, `_open_main_panel`); `app.py:CCMenuBarApp.__init__` (`_background_panel` lambda via `register_cmd_k`); `app.py` hotkey lambdas for Cmd+→/← cycling.
**Calls out:** `sys`, `Foundation.NSOperationQueue`; `.discover` (`list_alive_sessions`); `.bg_timer` (`_scan_bg_sleep_timers`); `.panel` (`_reposition_panel`); `.rag_controller` (`_reposition_rag_panel`); `.queue_controller` (`_reposition_queue_panel`).

---

### sessions_controller.py (22 LOC)

**Purpose:** Session snapshot cache. `SessionsController` wraps `list_alive_sessions()` with a one-value cache (`_last_sessions`) so all consumers within a tick read the same snapshot without re-calling discovery. First controller in the Step 1/6 CCMenuBarApp composition refactor.
**Reads:** nothing directly; delegates to `discover.py:list_alive_sessions()`.
**Writes:** `self._last_sessions` on each `refresh()` call.
**Called by:** `app.py:CCMenuBarApp.__init__` (construction); `app.py:CCMenuBarApp._tick`, `app.py:_open_main_panel`, `app.py:_open_queue_panel` (`refresh()`); `queue_controller.py:QueueController.handle_add_row/handle_toggle_entry/handle_remove_entry/handle_commit_field` (`self.app.sessions.refresh()`).
**Calls out:** `.discover` (`list_alive_sessions`).

---

### focus_controller.py (110 LOC)

**Purpose:** Per-concern controller for auto-focus debounce and auto-abort idle-workers logic (Step 5/6 of CCMenuBarApp composition refactor). `FocusController(app)` owns `_idle_since_ts` (working→idle debounce per main session), `_all_workers_idle_since_ts` (per-project idle timestamp for auto-abort), `_last_statuses` (status snapshot for blink-on-change and auto-focus transition detection). `tick(sessions, bg_by_project, now)` absorbs both the inline auto-focus block and `_auto_abort_check` from `app.py`: auto-focus fires `_focus_session(cwd)` after 3s debounce (gated on `app._auto_focus`; detects working→idle via `self._last_statuses`); auto-abort fires `_abort_bg_sleep_timers` when all workers of a project are idle for ≥5s while a bg timer is running (orchestrator-signal grace window via `ORCHESTRATOR_SIGNAL_BUFFER_SECS`). `statuses_changed(sessions)` replaces `_statuses_changed(sessions, last)` from `app.py`; `update_statuses(sessions)` replaces the two tick-end `_last_statuses = {name: status}` assignments. Module-level helpers `_abort_log_write` and `_has_recent_send_signal` moved verbatim from `app.py`. Settings `_auto_focus` remains on `app` (read by bead/queue/panel controllers); FocusController reads `self.app._auto_focus`.
**Reads:** `self._idle_since_ts`, `self._all_workers_idle_since_ts`, `self._last_statuses`; `self.app._auto_focus`; `sessions` and `bg_by_project` from callers.
**Writes:** `self._idle_since_ts` (per-main debounce timestamps); `self._all_workers_idle_since_ts` (per-project idle timestamps); `self._last_statuses` (via `update_statuses`); `src/logs/menubar.log` ([abort] category via `_abort_log_write`).
**Key signatures:** `FocusController.__init__(app)`, `tick(sessions, bg_by_project, now)`, `statuses_changed(sessions) -> bool`, `update_statuses(sessions) -> None`; module-level: `_abort_log_write(line)`, `_has_recent_send_signal(worker, signals, now)`.
**Called by:** `app.py:CCMenuBarApp.__init__` (construction); `app.py:CCMenuBarApp._tick` (`focus.tick`, `focus.statuses_changed`, `focus.update_statuses`).
**Calls out:** `.bg_timer` (`_abort_bg_sleep_timers`); `.menubar_log` (`log_menubar`); `.proc_cache` (`_read_orchestrator_signals`, `ORCHESTRATOR_SIGNAL_BUFFER_SECS`); `.system` (`_focus_session`); `sys`, `datetime`.

---

### hotkey_controller.py (320 LOC)

**Purpose:** Carbon global hotkey registration + `HotkeyController` per-concern controller (Step 6/6 of CCMenuBarApp composition refactor). Module-level: `register_cmd_l(callback)` / `register_cmd_k(callback)` — install Cmd+L and Cmd+K hotkeys at app start; caller (`app._hotkey_cb/_ref`, `app._hotkey_k_cb/_ref`) keeps both alive as GC anchors (CFUNCTYPE GC while registered → SIGSEGV). `register_cmd_digits(callback_map)` / `unregister_hotkeys(refs)` — Cmd+1..9 registration lifecycle; `register_cmd_arrow_right/left(callback)` / `unregister_cmd_arrow_right/left(hk_ref)` — Cmd+→/← lifecycle. Module-level state: `_DIGIT_HANDLER_CB/REF`, `_ARROW_HANDLER_CB/REF` persist InstallEventHandler across cycles; `_DIGIT_CALLBACKS` / `_ARROW_CALLBACKS` are mutable dispatch tables. All handlers filter via `GetEventParameter(typeEventHotKeyID)` and return `eventNotHandledErr (-9874)` for unknown IDs. Every dispatch calls `log_menubar('hotkey', ...)`. `HotkeyController(app)` owns the 4 migrating GC refs (`_hotkey_digits_cb/_refs`, `_hotkey_arr_right/left_ref`) and wraps lifecycle calls into `reregister_digits(desktop_to_cwd)`, `register_arrow_right/left(callback)`, `unregister_arrow_right/left()`, `unregister_digits()`.
**Reads:** nothing.
**Writes:** Carbon event handlers + hotkey registrations via CDLL; mutates module-level `_DIGIT_CALLBACKS` / `_ARROW_CALLBACKS` dicts; appends to `src/logs/menubar.log` on each hotkey press.
**Called by:** `app.py:CCMenuBarApp.__init__` (`register_cmd_l`, `register_cmd_k`, `HotkeyController` construction); `app.py:CCMenuBarApp._tick` + `app.py:_open_main_panel` + `app.py:_PanelController.windowDidEndLiveResize_` (`app.hotkey.reregister_digits`); `app.py:_open/close_main/rag/queue_panel` (`app.hotkey.register/unregister_arrow_*`, `app.hotkey.unregister_digits`).
**Calls out:** `ctypes` (Carbon framework CDLL); `.menubar_log` (`log_menubar`); `.system` (`_focus_session`).

---

### menubar_log.py (39 LOC)

**Purpose:** Unified log sink for all menubar diagnostic categories. All output goes to `~/Library/Application Support/com.brunowinter.monitor-cc-menubar/menubar.log` (ISO-second timestamp + `[category]` prefix per line). `log_menubar(category, message)` appends one line. `cleanup_old_lines()` drops lines older than 7 days and rewrites the file. Both functions are fully exception-safe (Carbon/AppKit callbacks must never raise). Categories in use: `hotkey` (every press), `abort` (auto-abort decisions + actions), `detection` (desktop-number transition + failures), `tick` (diagnostic, gated on `MENUBAR_DIAGNOSTICS=1`), `cursor` (gated on `MENUBAR_CURSOR_DEBUG`).
**Reads:** `_APP_SUPPORT/menubar.log` (`cleanup_old_lines` only).
**Writes:** `_APP_SUPPORT/menubar.log` (append on each `log_menubar` call).
**Called by:** `hotkey_controller.py` (`log_menubar`); `app.py` (`log_menubar`, lazy `cleanup_old_lines` via import inside `_tick`); `focus_controller.py` (`log_menubar` via `_abort_log_write`); `bg_timer.py` (`log_menubar`); `panel.py` (`log_menubar`); `desktop_detection.py` (`log_menubar`).
**Calls out:** `datetime` (stdlib); `.paths` (`_APP_SUPPORT`).

---

### system.py (81 LOC)

**Purpose:** `run()` entry point + singleton lock (`_acquire_singleton_lock`) + Ghostty click-to-focus (`_focus_session`). Owns the process-lifecycle concerns; no AppKit dependency.
**Reads:** `PID_FILE` (`APP_SUPPORT/menubar.pid`, lock file); `get_ghostty_terminal_id(cwd)` from `ghostty.py` on click.
**Writes:** `PID_FILE` (`APP_SUPPORT/menubar.pid`); `/tmp/monitor-cc-menubar_focus.log` (focus results via osascript).
**Called by:** `workflow.py` (via `from src.menubar import run` → `__init__.py` → `system.run`); `app.py:_PanelController.focusSession_` (`_focus_session`); `hotkey_controller.py:HotkeyController.reregister_digits` (`_focus_session`); `focus_controller.py:FocusController.tick` (`_focus_session`).
**Calls out:** `fcntl`, `os`, `subprocess` (osascript), `sys`; `.ghostty` (`get_ghostty_terminal_id`); lazy `.app` (`CCMenuBarApp`) inside `run()` only.

---

### discover.py (224 LOC)

**Purpose:** Session discovery entry point. `SessionInfo` includes `session_id: str` (JSONL stem = CC session identifier; key for `msg_queue.json` queue) and `tmux_session_name: str` (worker-`basename(project_path)`-`worker_name` for workers, `''` for mains; used by `app.py:_has_recent_send_signal` for orchestrator-signal lookup — DO NOT reconstruct from `project_name`; `project_name` is now the live-cwd basename, not a decoded encoded-dir component). `list_alive_sessions` calls `_write_cwd_uuid_map()` after each tick so `APP_SUPPORT/ghostty_cwd_uuid.json` stays current for hook delivery. `SessionInfo.name` (display) and `project_name` (group header) BOTH derive from live cwd — NOT from `_classify_encoded_dir` / `_decode_dir_name`. Mains: `project_name = basename(proc_cwd)`; workers: `project_name = basename(project_path_from_cwd)` when cwd readable; fallback (worker cwd unavailable): `_decode_dir_name` result. Worker display name: `worktree_rest.split('/')[0]` where `worktree_rest` is the right side of partitioning cwd on `/.claude/worktrees/` — yields the worktree leaf name regardless of subdir depth. NOT `os.path.basename(cwd)` (drifts to subdir name when worker cd's deeper) and NOT from encoded-dir (`encode_project_path` maps `_`→`-`, lossy). After the per-project loop, `list_alive_sessions` runs one batch desktop-number detection for all mains: builds `{cwd: tty}` and `{cwd: uuid}` maps from `_cc_proc_cache` + `_ghostty_tty_to_id`, calls `detect_main_desktop_numbers(...)`, and `_replace`s each main's `desktop_no` field. Workers always get `desktop_no=None`.
**Reads:** `~/.claude/projects/*/` JSONL mtimes + last lines; delegates to `proc_cache.py`; Ghostty mapping via `ghostty.py`; desktop numbers via `desktop_detection.py`.
**Writes:** delegates `ghostty_cwd_uuid.json` write to `ghostty.py:_write_cwd_uuid_map`.
**Called by:** `app.py:CCMenuBarApp._tick`, `app.py:_open_main_panel`, `app.py:_PanelController.*Queue*` methods.
**Calls out:** `session_finder.get_project_directories`, `session_finder.encode_project_path`; `.proc_cache`; `.ghostty` (`_refresh_ghostty_tty_to_id`, `_write_cwd_uuid_map`, `_ghostty_tty_to_id`); `.desktop_detection` (`detect_main_desktop_numbers`).

---

### desktop_detection.py (350 LOC)

**Purpose:** Batch detection of macOS Mission Control desktop numbers for all Main sessions via private CoreGraphics Services (CGS) APIs + one AppleScript round-trip. Ported from `dev/desktop_detection/01_probe.py`. Three-strategy per-window resolver: name-unique → space-elimination → OSC-2 injection. `detect_main_desktop_numbers(cwd_uuid_map, cwd_tty_map, now) -> {cwd: Optional[int]}`. Results cached `_DET_CACHE_TTL=10s`, force-invalidated when the cwd set changes (session add/remove). All errors (Ghostty down, AppleScript failure, CGS error) are caught, logged once as `[detection] all_failed n_mains=N reason=...` (only when ALL mains fail, not partial), and return all-None — so a detection failure degrades to an empty `[N]` slot, never a crash. Transition logging (`_last_result` module state) logs `[detection] transition <project> <old>-><new> win=<name> n_cand=<N>` on desktop-number change per cwd (transition-gated, no per-cycle spam; `n_cand=0` = CGWindowList title mismatch — typically a worker-spawn/send momentarily blanks titles). Module-level CFUNCTYPE refs (`_FT_vv`, `_FT_vvv`, …) MUST stay module-level — GC'ing them corrupts the IMP pointer table → SIGSEGV. **TCC note:** `kCGWindowName` (window title, needed for matching) is only visible to a process holding Screen Recording permission; the py2app native bundle preserves the bundle identity at API-call time so the grant is effective (the prior Bash-launcher→`exec`→Python chain lost the identity — see `process-docs/desktop_allocation/B1_tcc_responsibility_chain.md`). **Out of scope (NOT wired):** the `_cwd_desktop_lkg` last-known-good state still exists internally but the cross-repo sidecar writer (`_write_cwd_desktop_sidecar` / `CWD_DESKTOP_FILE`) is NOT restored — it served the abandoned window-move feature.
**Reads:** CGS APIs (`CGSCopyManagedDisplaySpaces`, `CGSCopySpacesForWindows`, `CGWindowListCopyWindowInfo`) via ctypes; `osascript` (Ghostty window name/list); `cwd_uuid_map` + `cwd_tty_map` from caller.
**Writes:** module-level caches (`_det_cache`, `_det_cache_ts`, `_det_cache_cwds`, `_last_result`, `_cwd_desktop_lkg`); `[detection]` lines to `menubar.log`.
**Called by:** `discover.py:list_alive_sessions` (`detect_main_desktop_numbers`).
**Calls out:** `ctypes` (CoreGraphics + libobjc), `subprocess` (osascript); `.menubar_log` (`log_menubar`).

---

### proc_cache.py (177 LOC)

**Purpose:** Process and state caches — CC process pid→(tty,cwd) mapping, tmux session state, proxy log mtime lookup, hook state reader, orchestrator-signal reader. Two TTL classes: `_PROC_REFRESH_INTERVAL` = 10s for the expensive `ps -A` / `lsof` caches; `_HOOK_REFRESH_INTERVAL` = 1s for the cheap hooks.json + orchestrator_signals.json reads (must be < POLL_INTERVAL=1.5s so each menubar tick gets a fresh snapshot while intra-tick consumers still see consistency). `_TMUX_REFRESH_INTERVAL` = 3s for `tmux list-sessions`. Exports `ORCHESTRATOR_SIGNAL_BUFFER_SECS = 60s` consumed by `focus_controller.py:FocusController.tick`. Owns `_TASKS_BASE` and `_has_active_bg()`. `_tmux_window_activity(session)` returns unix timestamp of last pane byte-write via `tmux display-message #{window_activity}`; used by `discover.py` for worker stale-demote (replaces JSONL mtime check).
**Reads:** `ps -A` + `lsof -d cwd` (CC process cache); `tmux list-sessions` (tmux state); `tmux display-message #{window_activity}` (per-session, on-demand); `_PROXY_LOG_DIR/api_requests_*.jsonl` mtimes; `HOOKS_FILE` (`APP_SUPPORT/hooks.json`); `ORCHESTRATOR_SIGNALS_FILE` (`APP_SUPPORT/orchestrator_signals.json`, written by worker-cli).
**Writes:** module-level caches (`_cc_proc_cache`, `_tmux_state_cache`, `_proxy_log_mtime_cache`, `_hook_state_cache`, `_orchestrator_signal_cache`).
**Called by:** `discover.py:list_alive_sessions` (refresh calls); `discover.py:_process_project_dir` (query calls + `_tmux_window_activity`); `ghostty.py:_tty_for_cwd` (`_cc_proc_cache` import); `bg_timer.py:_scan_bg_sleep_timers` (`_cc_proc_cache` import); `bg_timer.py:_abort_bg_sleep_timers` (`_TASKS_BASE` import); `focus_controller.py:FocusController.tick` (`_read_orchestrator_signals`, `ORCHESTRATOR_SIGNAL_BUFFER_SECS`).
**Calls out:** `subprocess` (ps, lsof, tmux).

---

### ghostty.py (155 LOC)

**Purpose:** Ghostty terminal UUID mapping via OSC 2 title-marker probe. Maintains `_ghostty_tty_to_id` (tty → UUID) populated incrementally. Exposes `get_ghostty_terminal_id(cwd)` for click-to-focus routing in `system.py`. Also writes `APP_SUPPORT/ghostty_cwd_uuid.json` = `{cwd: uuid}` via `_write_cwd_uuid_map()` (called from `discover.py:list_alive_sessions` after each tick); used by `hook_writer.py` for queue delivery. `_APP_SUPPORT` imported from `paths.py`.
**Reads:** `ps -A` (Ghostty PID + child TTYs); `/dev/ttys<NNN>` (OSC 2 marker writes); `osascript` (terminal id|||name pairs); `_cc_proc_cache`.
**Writes:** `/dev/ttys<NNN>` (probe + cleanup); `_ghostty_tty_to_id`, `_ghostty_tty_last_refresh`, `_ghostty_cwd_uuid_last` (module state); `APP_SUPPORT/ghostty_cwd_uuid.json` (atomic, change-detected).
**Called by:** `discover.py:list_alive_sessions` (`_refresh_ghostty_tty_to_id`, `_write_cwd_uuid_map`); `system.py:_focus_session` (`get_ghostty_terminal_id`).
**Calls out:** `json`, `subprocess`, `time`; `.paths` (`_APP_SUPPORT`); `.proc_cache` (`_cc_proc_cache`).

---

### bg_timer.py (138 LOC)

**Purpose:** Background sleep-timer scanning, per-project attribution, and abort. Detects Opus `sleep N && echo done` background timers via `ps`; attributes each to a project via ancestry-chain walk → `_cc_proc_cache → cwd → cwd_to_project` lookup (walks up to 5 levels from the zsh parent to handle intermediate shell layers between CC and zsh). Returns `Dict[str, BgSleepInfo]` keyed by project_name ('unknown' bucket for unattributed timers). `_abort_bg_sleep_timers` kills PIDs via SIGTERM, writes `aborted\n` to in-progress task files, and appends one line to `/tmp/menubar-abort.log` (killed count, error count, last_err if any).
**Reads:** `ps -A -o pid=,ppid=,etime=,args=` (timer detection); `_cc_proc_cache` (ancestry→cwd attribution); `_TASKS_BASE` task dirs (for abort file writes).
**Writes:** `signal.SIGTERM` to sleep PIDs; `'aborted\n'` to 0-byte `*.output` task files under `_TASKS_BASE`; `src/logs/menubar.log` ([abort] category via `log_menubar`).
**Called by:** `app.py:CCMenuBarApp._tick` (`_scan_bg_sleep_timers`); `app.py:_PanelController.abortBgTimer_` (`_scan_bg_sleep_timers`, `_abort_bg_sleep_timers`); `app.py:_PanelController.windowDidEndLiveResize_` (`_scan_bg_sleep_timers`); `app.py:_auto_abort_check` (`_abort_bg_sleep_timers`).
**Calls out:** `subprocess` (ps); `datetime`; `.proc_cache` (`_TASKS_BASE`, `_cc_proc_cache`); `.menubar_log` (`log_menubar`).

---

### hook_writer.py (198 LOC)

**Purpose:** CC hook handler — reads JSON payload on stdin; updates `hooks.json`; on Stop/StopFailure additionally delivers the first `state="queued"` entry from `msg_queue.json` for the session. Skips `state="draft"` and `state="sent"` entries. Delivery path: `_queue_get_first_unsent` (flock `queue.lock` → find first entry where `state=="queued"`) → `_deliver_message` (UUID focus + System Events keystroke; cwd fallback) → on success: `_queue_mark_sent` (flock → set `state="sent"` + `sent_at=utc-iso` in-place). On delivery failure: entry left unchanged, next Stop retries. Messages are never removed by the hook — only the panel's `×` button removes entries. `_normalize_entry` handles all legacy formats inline (mirrors `queue.py`). Standalone script; defines all 3 APP_SUPPORT paths inline.
**Reads:** stdin (CC hook JSON); `APP_SUPPORT/hooks.json` (inside flock); `APP_SUPPORT/msg_queue.json` (inside flock); `APP_SUPPORT/ghostty_cwd_uuid.json` (UUID lookup).
**Writes:** `APP_SUPPORT/hooks.json` (atomic); `APP_SUPPORT/msg_queue.json` (atomic, inside flock — mark `sent_at` in-place, never removes entries); `APP_SUPPORT/queue.lock`; osascript delivery to Ghostty terminal.
**Called by:** CC hook system (`async: true`). Never imported.
**Calls out:** stdlib (`datetime`, `fcntl`, `json`, `os`, `subprocess`, `time`).

**Usage:** `python3 src/menubar/hook_writer.py` (stdin = CC hook JSON). Install via `hook_setup.py`.

---

### hook_setup.py (115 LOC)

**Purpose:** Idempotent installer for the activity-monitor hooks (UserPromptSubmit/Stop/StopFailure) with two defense layers. **Layer 1 — Worktree Guard:** `_guard_not_worktree()` checks `Path(__file__).resolve().parts` for consecutive `.claude`/`worktrees` components; exits 2 with a clear error message if the script is running from a worktree path — preventing dead-path registration. **Layer 2 — Stale-hook Sweep:** `_sweep_stale_hooks()` iterates ALL event keys in `settings["hooks"]`, checks every `python3 <path>` entry, and removes any whose script path fails `os.path.exists()`; drops now-empty groups, saves atomically, then runs the normal add-loop. Re-running heals stale entries from any source.
**Reads:** `~/.claude/settings.json`.
**Writes:** `~/.claude/settings.json` (atomic via temp + `os.replace()`; up to two saves per run — one after sweep if stale entries found, one after add-loop if new entries installed).
**Called by:** User manually (`python3 src/menubar/hook_setup.py` from Monitor_CC root). Never imported.
**Calls out:** stdlib only (`json`, `os`, `pathlib`, `sys`).

**Usage:** `python3 src/menubar/hook_setup.py` — run once after clone or when hooks need reinstalling. Re-run any time to heal stale hook entries. Restart CC to activate.

---

### setup_menubar.py (30 LOC)

**Purpose:** Plist-writer utility for `app.py:restartApp_`. Exports `write_plist()` (dev/venv mode: substitutes `_BUNDLE_LAUNCHER` = `Contents/MacOS/menubar`) and `write_plist_py2app()` (py2app mode: substitutes `_BUNDLE_EXE` = `Contents/MacOS/monitor-cc-menubar`) — each writes the correct binary name for its mode into `~/Library/LaunchAgents/com.brunowinter.monitor-cc-menubar.plist`. No `__main__` guard; not standalone-runnable. Legacy build pipeline (`setup_menubar_workflow`, `_build_app_bundle`, etc.) removed — production install is now `setup_py2app.py py2app`.
**Reads:** `src/menubar/com.brunowinter.monitor-cc-menubar.plist` (template with `<BUNDLE_LAUNCHER>` token).
**Writes:** `~/Library/LaunchAgents/com.brunowinter.monitor-cc-menubar.plist`.
**Called by:** `app.py:restartApp_` (lazy import of `write_plist` in dev mode; `write_plist_py2app` in py2app mode).
**Calls out:** `pathlib` only.

---

### setup_py2app.py (157 LOC) — at project root, NOT in src/menubar/

**Purpose:** py2app build + install + bootstrap script. Produces `dist/monitor-cc-menubar.app/` (native Mach-O, embedded Python framework), then post-`setup()` runs `_prune_bundle_bloat()` + `_install_bundle`. `_prune_bundle_bloat()` whitelist-prunes the bundle's `src/` to `{menubar, session_finder.py, constants.py, __init__.py, __pycache__}` — prevents `copy_package_data()` from sweeping `src/logs/` (runtime proxy logs, no `__init__.py`, ≥15 GB in main repo). `_install_bundle` copies to `~/Applications/`, ad-hoc codesigns, writes the LaunchAgent plist (inline template substitution — avoids `src.menubar` import chain triggering AppKit in build context), then launchctl bootout + bootstrap (with 1s retry on rc≠0). Placed at project root (not `src/menubar/`) to avoid stdlib `queue` shadowing by `src/menubar/queue.py` when setuptools is loaded.
**Reads:** `src/menubar/menubar_main.py` (entry point); `src/menubar/com.brunowinter.monitor-cc-menubar.plist` (bundled as data file + read by `_install_bundle` for plist substitution).
**Writes:** `dist/monitor-cc-menubar.app/`; `~/Applications/monitor-cc-menubar.app/`; `~/Library/LaunchAgents/com.brunowinter.monitor-cc-menubar.plist`.
**Called by:** User manually (one-time build + after Python upgrade).
**Calls out:** `py2app`, `setuptools`, `shutil`, `pathlib`, `os`, `subprocess`, `time`.

**Usage:** `./venv/bin/pip install py2app && ./venv/bin/python setup_py2app.py py2app` from project root. One command: build + install + bootstrap.

**Post-install TCC step:** Screen Recording permission is no longer required (desktop detection removed). No TCC grant needed for current menubar features.

**Gotcha — copy_package_data sweeps src/logs/:** `src/__init__.py` makes `src` a Package node in py2app's modulegraph. `copy_package_data(src)` then copies every subdirectory of `src/` that has NO `__init__.py` wholesale into the bundle — including `src/logs/` (runtime proxy logs, gitignored). In the main repo this grows to 15 GB+. `_prune_bundle_bloat()` runs post-`setup()` and removes everything from the bundle's `src/` not in `_BUNDLE_SRC_KEEP`. Whitelist must be updated if new cross-package `src.X` imports are added to `src/menubar/`.

---

### menubar_main.py (7 LOC)

**Purpose:** py2app entry wrapper. `from src.menubar import run; run()`. Avoids argparse dispatch in `workflow.py` and prevents heavy non-menubar modules (`src.core`, `src.proxy`, etc.) from entering modulegraph's import trace. No logic beyond the delegation.
**Reads:** nothing.
**Writes:** nothing (delegates entirely to `system.py:run()`).
**Called by:** py2app native launcher at bundle start (via `Contents/MacOS/monitor-cc-menubar`).
**Calls out:** `.system` (via `src.menubar.__init__` which re-exports `run`).

---

## Module Import Graph

```
stdlib only
    ↓
paths.py        (pathlib only — leaf node; triggers migrations at import)
    ↓
proc_cache.py   (json, os, subprocess, time, pathlib, typing; .paths)
    ↓    ↘          ↓
ghostty.py  paths   bg_timer.py
(_cc_proc_cache,    (_TASKS_BASE; .menubar_log log_menubar)
 _APP_SUPPORT)
    ↓
discover.py  ← ghostty.py (_refresh_ghostty_tty_to_id, _ghostty_tty_to_id)
             ← proc_cache.py (_refresh_cc_proc_cache, _refresh_tmux_state,
                               _tmux_session_exists, _read_hook_state,
                               _proxy_log_newest_mtime, _has_active_bg)
             ← desktop_detection.py (detect_main_desktop_numbers)

desktop_detection.py → ctypes (CoreGraphics + libobjc), subprocess; .menubar_log (log_menubar)

menubar_log.py    → datetime, pathlib only (leaf node)
focus_controller.py → sys, datetime; .bg_timer (_abort_bg_sleep_timers); .menubar_log (log_menubar);
                      .proc_cache (_read_orchestrator_signals, ORCHESTRATOR_SIGNAL_BUFFER_SECS);
                      .system (_focus_session)
hotkey_controller.py → ctypes; .menubar_log (log_menubar); .system (_focus_session)
panel.py          → AppKit, Foundation, itertools; .menubar_log (log_menubar)
panel_manager.py  → AppKit, Foundation, itertools.groupby; .panel (constants + factories)
queue_controller.py → AppKit, Foundation, objc, json, datetime; .panel (constants + helpers);
                      .queue (load_queue, save_queue, deliver_message); .paths (HOOKS_FILE)
rag_controller.py → AppKit, Foundation, json, os, errno, datetime, pathlib; .panel (constants + helpers)
system.py         → fcntl, os, subprocess, sys; .ghostty, .paths (PID_FILE)
                    lazy(.app) inside run() only
queue.py          → json, os, subprocess; .paths (QUEUE_FILE, QUEUE_LOCK, GHOSTTY_CWD_UUID_FILE)
app_settings.py   → json, os; .paths (SETTINGS_FILE); .panel (constants)
panel_lifecycle.py → sys, Foundation; .discover, .bg_timer; .panel (_reposition_panel);
                    .rag_controller (_reposition_rag_panel); .queue_controller (_reposition_queue_panel)
app.py            → rumps, objc, AppKit, Foundation, time, threading, os, sys
                    .sessions_controller, .focus_controller, .queue_controller,
                    .rag_controller, .panel_manager, .panel, .hotkey_controller, .system, .discover,
                    .bg_timer, .app_settings, .panel_lifecycle, .menubar_log (log_menubar)
```

No cycles. `system.py` has no module-level import of `app.py`; the lazy import inside `run()` prevents the `app→system→app` circular dependency. `proc_cache.py` has no internal project imports (leaf node). `setup_menubar.py` is a plist-writer utility (not standalone-runnable; no `__main__`); `write_plist()` or `write_plist_py2app()` are lazy-imported in `app.py:restartApp_` (branch-specific, never both). `hook_setup.py` and `hook_writer.py` are standalone scripts (stdlib + subprocess only), not imported by any module. `menubar_main.py` is the py2app entry point — only imported by the native launcher, not by any module in the package.

---

## State

| Variable | Module | Type | Owner | Description |
|---|---|---|---|---|
| `CCMenuBarApp._panel_controller` | app.py | `_PanelController` | app.py | Single PyObjC NSObject as ObjC target for all button actions. Held to prevent ARC GC. |
| `CCMenuBarApp._auto_focus` | app.py | `bool` | app.py | Whether auto-focus is enabled. Loaded from settings; toggled by `toggleAutoJump_`. |
| `CCMenuBarApp._panel_width` | app.py | `int` | app.py owns, panel.py uses | Current panel width in pts. Loaded from settings (fallback: `PANEL_WIDTH=380`). Reset to `PANEL_WIDTH` on user-initiated fresh open via `togglePanel_` (runtime only, no save). Updated by `windowDidResize_` on user drag. Cycling (`_deferred_close_open`) preserves current value. |
| `CCMenuBarApp._panel_min_height` | app.py | `int` | app.py owns, panel.py uses | Height floor for panel. Reset to `PANEL_HEIGHT` on user-initiated fresh open via `togglePanel_` (runtime only, no save). `_rebuild_panel` sizes to `max(_panel_min_height, required_h)`. Updated by `windowDidResize_` on user drag. Cycling preserves current value. |
| `CCMenuBarApp._hotkey_cb` | app.py | `ctypes CFUNCTYPE` | app.py | GC anchor for CFUNCTYPE returned by `register_cmd_l`. MUST stay on app — GC corrupts IMP pointer table → SIGSEGV. |
| `CCMenuBarApp._hotkey_ref` | app.py | `ctypes.c_void_p` | app.py | GC anchor for Carbon hotkey handle returned by `register_cmd_l`. MUST stay on app. |
| `CCMenuBarApp.hotkey` | app.py | `HotkeyController` | hotkey_controller.py | Digit + arrow hotkey lifecycle controller (Step 6/6). Owns `_hotkey_digits_cb/_refs`, `_hotkey_arr_right/left_ref`. Exposes `reregister_digits(desktop_to_cwd)`, `register/unregister_arrow_right/left()`, `unregister_digits()`. |
| `_cc_proc_cache` | proc_cache.py | `Dict[pid, (tty, cwd)]` | module | CC processes. Incremental: `ps -A` every 10s drops gone PIDs; `lsof -d cwd` only for newly seen PIDs. |
| `_cc_proc_last_refresh` | proc_cache.py | `float` | module | Timestamp of last CC cache pass. |
| `_tmux_state_cache` | proc_cache.py | `set` | module | session_name set (alive check only). One `tmux list-sessions` call per 3s. |
| `_tmux_state_last_refresh` | proc_cache.py | `float` | module | Timestamp of last tmux state refresh. |
| `_proxy_log_mtime_cache` | proc_cache.py | `Dict[str, Tuple[float, Optional[float]]]` | module | `opus_<project_key>→(checked_at, newest_mtime)`. TTL=10s. |
| `_hook_state_cache` | proc_cache.py | `Dict[str, dict]` | module | `session_id→{status, cwd, updated_ts}`. Read from `APP_SUPPORT/hooks.json` (`HOOKS_FILE`). TTL=10s. |
| `_hook_state_last_read` | proc_cache.py | `float` | module | Timestamp of last hook state file read. |
| `_ghostty_tty_to_id` | ghostty.py | `Dict[str, str]` | module | tty → Ghostty terminal UUID. Populated incrementally by OSC 2 probe. |
| `_ghostty_tty_last_refresh` | ghostty.py | `float` | module | Timestamp of last probe cycle (updated only when a probe actually ran). |
| `_ghostty_cwd_uuid_last` | ghostty.py | `dict` | module | Previous write state for `ghostty_cwd_uuid.json` change-detection (skip write if unchanged). |
| `CCMenuBarApp.sessions` | app.py | `SessionsController` | sessions_controller.py | Session snapshot cache. `sessions.refresh()` calls `list_alive_sessions()` and caches result; `sessions.data` returns cached snapshot. Replaces bare `_last_sessions` attr. |
| `CCMenuBarApp.queue` | app.py | `QueueController` | queue_controller.py | Queue panel controller. Owns all 11 `_queue_*` attrs (incl. `_queue_open`, `_queue_panel`, `_queue_sv`, `_queue_toggle_btn`, `_queue_data`, `_pending_queue_tags`, `_pending_queue_views`, `_queue_add_tags`, `_queue_remove_tags`, `_queue_toggle_tags`, `_queue_displayed_names`). `queue.tick(sessions)` drives data reload + conditional rebuild; `queue.open(sessions)` used on panel-open (forced rebuild). Action handlers: `handle_add_row`, `handle_toggle_entry`, `handle_remove_entry`, `handle_commit_field`, `handle_text_end_editing`, `handle_try_deliver`. |
| `CCMenuBarApp.rag` | app.py | `RagController` | rag_controller.py | RAG status panel controller. Owns `_rag_open`, `_rag_panel`, `_rag_sv`, `_rag_toggle_btn`, `_rag_status_label`. `rag.tick(sessions)` reads `~/.rag-locks/rag.lock` and updates the status label in-place every tick. `rag.rebuild()` does full panel rebuild (called on open + live-resize). |
| `CCMenuBarApp.panel` | app.py | `PanelManager` | panel_manager.py | Main-session panel controller (Step 4/6). Owns `_panel_open`, `_initialized`, `_displayed_items`, `_cwd_map`, `_desktop_to_cwd`, `_abort_btns_by_project`, `_abort_project_for_tag`, `_rebuild_in_progress`, and NSPanel refs `_panel`, `_panel_sv`, `_panel_quit_btn`, `_toggle_btn`, `_panel_kill_btn`. `panel.rebuild(sessions, bg_by_project)` drives full panel rebuild; `panel.update_inplace(sessions, bg_by_project)` drives in-place dot+badge update. Settings `_auto_focus`, `_panel_width`, `_panel_min_height` remain on `app` (cross-controller shared preferences). |
| `CCMenuBarApp.focus` | app.py | `FocusController` | focus_controller.py | Auto-focus + auto-abort controller (Step 5/6). Owns `_idle_since_ts` (per-main working→idle debounce timestamps), `_all_workers_idle_since_ts` (per-project idle-since timestamps for auto-abort), `_last_statuses` ({name: status} snapshot for blink-on-change and focus-transition detection). `focus.tick(sessions, bg_by_project, now)` drives both auto-focus and auto-abort per tick. `focus.statuses_changed(sessions)` / `focus.update_statuses(sessions)` replace the two `_last_statuses` update sites in `_tick`. Settings `_auto_focus` remains on `app` (read by all four panel controllers). |

## Title-Marker Mapping (tty → Ghostty terminal UUID)

**Problem:** Ghostty's AppleScript `working directory` property reflects the PTY's initial cwd, not the shell's current cwd. `focus (first terminal whose working directory is "...")` fails for sessions where the shell ran `cd X && python3 workflow.py --project Y`. Ghostty does NOT expose `tty` or `pid` via AppleScript.

**Solution:** OSC 2 title-marker bootstrap. Each Ghostty tab has a direct child process (login shell) with a known TTY device (`/dev/ttys<NNN>`). Writing `\033]2;<marker>\007` to that device sets the Ghostty tab's `name` property. An AppleScript query immediately after returns `id|||name` pairs → marker appears in `name` → we learn the UUID for that TTY.

**Probe flow** (`_refresh_ghostty_tty_to_id` in `ghostty.py`):

1. `ps -A -o pid=,command=` parsed for `Ghostty.app/Contents/MacOS` → Ghostty PID.
2. `ps -A -o pid=,ppid=,tty=` filtered by ppid = Ghostty PID → all current TTYs (`all_ttys`).
3. **Stale cleanup**: remove `_ghostty_tty_to_id` entries whose TTY is no longer in `all_ttys` (closed tabs).
4. **Incremental filter**: `new_ttys = [t for t in all_ttys if t not in _ghostty_tty_to_id]`. If empty → return immediately, **no title flash, no sleep**.
5. Write `\033]2;__GHT_<8-hex-random>\007` to each `/dev/<new_tty>`.
6. `time.sleep(0.12)` — 120ms for Ghostty to process the OSC 2 sequence.
7. `osascript` → all terminals `id|||name` pairs (newline-separated).
8. **Cleanup**: write `\033]2;\007` (empty string) to each probed TTY → shell restores its default title.
9. Match markers to IDs → merge into `_ghostty_tty_to_id`.
10. Update `_ghostty_tty_last_refresh = now` **only if probe ran** (step 4 found new TTYs).

## Gotchas

- **Session status detection** (Workers + Mains): Priority-1/2/3 fallback chain with threshold values — see `process-docs/menubar_session_status/menubar_session_status.md` for the full current-state chain.
- **Singleton enforcement via fcntl lock** (`system.py`): `run()` calls `_acquire_singleton_lock()` before constructing `CCMenuBarApp`. Lock file: `PID_FILE` = `APP_SUPPORT/menubar.pid`. On success: sets `FD_CLOEXEC` on the fd (required for clean `os.execv` restart), writes PID, returns open file handle (held on `run()`'s stack frame for the process lifetime). On failure: prints to stderr and calls `sys.exit(0)`. **Exit code 0 is mandatory**: launchd `KeepAlive=true` respawns on non-zero exit only.
- **APP_SUPPORT migration** (`paths.py`): on first import, two migrations run. `_migrate_from_dotfiles()` moves `~/.monitor_cc_menubar_{settings,hooks}.json`, `~/.monitor_cc_menubar_hooks.lock`, and `~/.monitor_cc_menubar.pid` to `~/Library/Application Support/com.brunowinter.monitor-cc-menubar/`. `_migrate_from_old_bundle_id()` moves runtime files from the old bundle-id dir `~/Library/Application Support/com.brunowinter.monitor_cc_menubar/` to the new `com.brunowinter.monitor-cc-menubar/`. `os.rename()` is atomic on APFS/HFS+ (same volume). Both migrations: NEW wins — if new file already exists, old is left in place (no clobber). `hook_writer.py` defines `_APP_SUPPORT` inline (standalone script; relative import not usable).
- **Restart — two-branch flow gated on `sys.frozen`** (`app.py:_PanelController.restartApp_`): py2app sets `sys.frozen = 'macosx_app'` in `__boot__.py`. **py2app branch**: `write_plist_py2app()` (from `setup_menubar.py`) writes the LaunchAgent plist with `ProgramArguments = [.../monitor-cc-menubar]`; detached helper runs `launchctl bootout gui/<uid>/... 2>/dev/null ; launchctl bootstrap gui/<uid> <dest>` — bundle untouched, TCC identity preserved. **Dev/venv branch** (`sys.frozen` absent): `write_plist()` writes `Contents/MacOS/menubar` into the plist; same pure launchctl bootout+bootstrap cycle — no Python subprocess, no bundle rebuild. Both branches end with `rumps.quit_application()`. All imports are inside the branch body (not module-level) to avoid import-order sensitivity.
- **Restart ≠ code update — frozen bundle needs REBUILD** (the trap): the production menubar is a FROZEN py2app bundle (`~/Applications/monitor-cc-menubar.app`, `semi_standalone=False` — Python source COPIED into the bundle at build time, not aliased). The `restartApp_` / launchctl bootout+bootstrap cycle re-launches the SAME bundle (the restart gotcha above explicitly does "no bundle rebuild") — it does NOT pick up edited `src/menubar/*.py`. To deploy a menubar code change you MUST rebuild: `./venv/bin/python setup_py2app.py py2app` (rebuild + reinstall to `~/Applications/` + relaunch launchd). Incident 2026-06-24: the two-level-progress reader (merged Jun 24) stayed invisible because the running bundle was built Jun 13; even a fresh restart re-loaded the stale bundle. Always `setup_py2app.py py2app` after editing menubar code.
- **Kill unloads the plist (`launchctl bootout`)**: `killApp_` (`app.py:_PanelController`) fires `launchctl bootout gui/<uid>/com.brunowinter.monitor-cc-menubar` via a detached `sh -c 'sleep 0.5 && ...'` subprocess (survives parent exit), then calls `rumps.quit_application()`. `bootout` removes the plist from the launchd domain so `KeepAlive=true` no longer respawns the process. Next reload requires login (`RunAtLoad=true`) or manual `launchctl bootstrap gui/<uid> ~/Library/LaunchAgents/com.brunowinter.monitor-cc-menubar.plist`.
- **Lazy import in system.run()**: `from .app import CCMenuBarApp` is inside `run()` to break the `app→system→app` circular import. `app.py` imports `_focus_session` from `system.py` at module level; `system.py` has no module-level import of `app.py`. No circular dependency at module init time.
- **bg_result always passed explicitly to `_rebuild_panel`**: the `_rebuild_panel` fallback scan was removed from panel.py (to keep panel.py free of discover/bg_timer dependency). `app.py:_tick` computes `bg_result = _aggregate_bg(_scan_bg_sleep_timers(cwd_to_project))` once per tick and passes it explicitly to all panel calls.
- **Global hotkey Cmd+L** (`hotkey_controller.py`): `register_cmd_l(callback)` wraps the callback in a ctypes `CFUNCTYPE` and registers via Carbon `RegisterEventHotKey`. Returns `(cb_handle, hk_handle)` — caller (`CCMenuBarApp.__init__`) stores both on `self._hotkey_cb` / `self._hotkey_ref` to prevent GC of the C callback. Same pattern for `register_cmd_k` → `self._hotkey_k_cb` / `self._hotkey_k_ref`.
- `quit_button=None` passed to `rumps.App.__init__` — default rumps quit button is menu-attached and would be orphaned after `setMenu_(None)`. Restart is a footer NSButton wired to `_PanelController.restartApp_`.
- **Lazy-init timing** (`app.py`): `rumps.App._nsapp` is only populated after `app.run()` starts the AppKit runloop. `setMenu_(None)` + button wiring happens in the first `_tick` call (guarded by `if not self._initialized`).
- **Diagnostics gating** (`app.py:_tick_log`): tick logging is gated on `MENUBAR_DIAGNOSTICS=1` env var — default OFF. Without the var, `_tick_log` returns immediately (no file I/O). Enable by launching via `dev/menubar_debug.py` (sets the var automatically) or `launchctl setenv MENUBAR_DIAGNOSTICS 1` for the running launchd service. Log path: `_TICK_LOG = '/tmp/menubar-tick.log'`.
- Background task detection: `/tmp/claude-<uid>/` uses the numeric Unix UID (`os.getuid()`). `*.output` files with `st_size == 0` = in-progress; `done\n` (5 bytes) = completed.
- **Abort leaves task file at 0 bytes:** when the sleep child is killed via SIGTERM, the zsh parent exits via `&&` short-circuit (no `echo done` stdout), so CC writes nothing to the task file — it stays 0 bytes indefinitely. `_abort_bg_sleep_timers` (bg_timer.py) explicitly writes `aborted\n` to all 0-byte task files after kill so `_has_active_bg` returns False and the `[B]` badge disappears.
- **CC uses `zsh -c`, not `bash -c`:** background bash commands are actually `zsh -c "source ... && eval 'cmd' ..."`. `_scan_bg_sleep_timers` correctly matches these because `echo done` appears in the zsh parent's args; the sleep child args are always exactly `sleep N`.
- `LSUIElement=1` must be set before `app.run()` to suppress the Dock icon. Set in `run()` via `os.environ.setdefault`.
- Launched via launchd: `KeepAlive=true` auto-restarts on crash. Logs → `/tmp/monitor-cc-menubar.{log,err}`.
- **launchd PATH inheritance**: `EnvironmentVariables/PATH` in the plist must prepend `/opt/homebrew/bin` — launchd's default PATH lacks Homebrew, making `tmux` unavailable for proc_cache.py worker-alive checks.
- **launchd ASCII locale — all `text=True` subprocess calls need `encoding='utf-8', errors='replace'`**: launchd sets no locale → `locale.getpreferredencoding()` = `'ascii'` → any `subprocess.run(..., text=True)` without explicit encoding crashes on non-ASCII bytes. Confirmed: `ps -A -o command=` and `osascript` output containing CC worker spawn-prompts (emoji, umlauts) caused `UnicodeDecodeError`. All `text=True` calls in the package carry `encoding='utf-8', errors='replace'`. LaunchAgent plist template also sets `PYTHONUTF8=1` as belt-and-suspenders. Any NEW `subprocess.run(..., text=True)` added to this package MUST include `encoding='utf-8', errors='replace'`.
- **Ghostty PID lookup** (`ghostty.py:_ghostty_pid`): `pgrep` is unreliable on macOS for full-path binary names. Use `ps -A -o pid=,command=` parsed directly: `'Ghostty.app/Contents/MacOS' in line` finds the process robustly.
- **Ghostty AppleScript**: Ghostty.sdef exposes `id` (UUID, stable), `name` (current title), `working directory` per `terminal`. `focus` command takes a specifier: `focus terminal id "<UUID>"`. Does NOT expose `tty` or `pid`.
- **OSC 2 cleanup**: After the probe, `\033]2;\007` (empty-string OSC 2) written to the probed TTYs restores the shell's default title. Without cleanup, idle shells show `__GHT_XXXXXXXX` until next prompt display.
- **TTY ownership**: Ghostty children run as `/usr/bin/login` (root) but the `/dev/ttys<NNN>` device files are owned by the logged-in user → write access OK.
- **Dynamic panel height (grow-only)** (`panel.py`): `_rebuild_panel` calls `_compute_required_height` → `_resize_panel(app, max(app._panel_min_height, required_h))`. Panel never shrinks below user-set floor. `NSBoxSeparator` containers require explicit `heightAnchor().constraintEqualToConstant_(18.0)` — plain `NSView` has no `intrinsicContentSize`. NSGridView additionally turns off TAMIC on ALL content views (via `addRowWithViews_`), so any `NSView` placed in a grid cell MUST carry a `heightAnchor` AND `widthAnchor` constraint; without height: `height=0`, `yPlacement=top` pins origin to row top, subviews bleed up; without width: AutoLayout assigns `w=0`, merged-cell content is invisible. `_make_separator_view` (panel.py) sets only `heightAnchor`.
- **Cursor handling on panel edges** (`panel.py`): `_PanelContentView(NSView)` uses NSTrackingArea + `mouseMoved_` for edge detection; `_set_hovered_edge` calls `invalidateCursorRectsForView_` on state change; `resetCursorRects` installs a single full-bounds rect for the current edge state (state-driven, winit pattern). `_CursorlessLabel(NSTextField)` and `_CursorlessButton(NSButton)` suppress child-view `resetCursorRects` to prevent override of edge cursors. Note: `LSUIElement=1` accessory-app context blocks cursor-rect dispatch in practice (cursor change not visible to user); implementation is mechanically correct but AppKit dispatch is suppressed — see `process-docs/menubar_build/menubar_overhaul_2026-05-19.md` Iteration 9.
- **Status-change is panel-no-op**: working↔idle transitions NEVER trigger `_rebuild_panel` or `_resize_panel`. Open panel: status changes go through `_update_panel_inplace`. Closed panel: only trigger `_blink`. Only two events trigger `_rebuild_panel`: (1) session-set change; (2) abort-button None↔Some transition (panel open only). Queue panel has no in-place update path — any change triggers full `_rebuild_queue_panel`.
- **Three-panel cycling** (`app.py`): Sessions → RAG → Queue → Sessions (Cmd+→); reverse (Cmd+←). Each `_open_*_panel` registers BOTH Cmd+→ and Cmd+←; each `_close_*_panel` unregisters both. Generic `_deferred_close_open(app, from, to)` handles all 6 transition combinations dispatched via `NSOperationQueue.mainQueue()`. `unregister_cmd_arrow_*(None)` is a no-op — safe when opposite direction was not registered.
- **NSTextField in nonactivating panel** (`queue_panel.py`, `panel.py`): `NSWindowStyleMaskNonactivatingPanel` prevents the *app* from activating (Ghostty stays frontmost). However the default NSPanel implementation also returns `canBecomeKeyWindow=False` for this mask — this silently prevents `makeFirstResponder_` from routing keyboard events to NSTextField. Fix: `_KeyablePanel(NSPanel)` in `panel.py` overrides `canBecomeKeyWindow` to return True; all three panels use `_KeyablePanel.alloc()`. `makeKeyAndOrderFront_(None)` + `makeFirstResponder_(tf)` in `_rebuild_queue_panel` then correctly grants keyboard focus to the input field without stealing app activation.
- **NSPanel ObjC attribute constraint**: NSPanel (and all PyObjC-bridged ObjC objects) reject arbitrary Python attribute assignment — `panel.my_attr = x` raises `AttributeError`. `_make_nspanel()` returns `(panel, stack, quit_btn)` as a Python tuple.
- **NSStackView gravity**: requires BOTH `addView_inGravity_(view, 1)` AND `setDistribution_(-1)` (`NSStackViewDistributionGravityAreas`). `setDistribution_(0)` ignores gravity entirely. Enum values: `GravityTop=1`, `GravityCenter=2`, `GravityBottom=3`; `DistGravityAreas=-1`, `DistFill=0`.
- **Badge column alignment**: main-session rows only — `[*]`/`[ ]` fixed 3 chars; `[B M:SS]` variable 3–9 chars but nothing follows it, so no misalignment. Worker rows carry no badge column.
- **Settings backwards-compat** (`app.py:_load_settings`): reads `panel_min_height` first, falls back to legacy `panel_max_height`, then `PANEL_HEIGHT=460`. Old files migrate transparently.
- **Auto-abort task-file write is global** (`bg_timer.py:_abort_bg_sleep_timers`): after killing sleep PIDs, writes `aborted\n` to ALL 0-byte `*.output` task files under `_TASKS_BASE`, not just those belonging to the aborted project. Pre-existing behavior shared with manual abort. If project B has live 0-byte task files when project A is auto-aborted, B's `[B]` badge may transiently disappear. In practice rare (requires simultaneous multi-project bg tasks).
- **Per-project abort button (Option B):** abort button is embedded inline in the project's separator row via `_make_separator_view(project_name, pw, proj_min_remaining)`. Returns `(NSView, Optional[NSButton])`. Zero height cost — no extra `_ROW_H` row. Button styled in `systemRedColor` Menlo font, static label `abort`. Target/action wired in `_rebuild_panel`; label is static so no per-tick update. Tag range: 1000+ (above session row tags starting at 1).
- **Ancestry-chain walk** (`bg_timer.py:_scan_bg_sleep_timers`): attribution now walks up to 5 levels from the zsh's parent to find a CC process in `_cc_proc_cache`, instead of a single `gppid = parent[0]` lookup. Handles intermediate shell layers between CC and the zsh (e.g., `CC → sh → zsh → sleep`). Does NOT fix PID-recycling cross-project attribution (narrow timing window; deferred).
- **`_aggregate_bg` removed from `app.py` import:** `_tick` now passes `bg_by_project` directly to panel functions. Session row badge countdown (`min_remaining`) is computed inside panel functions from `bg_by_project.values()`. Manual `abortBgTimer_` uses `_scan_bg_sleep_timers` directly scoped to the clicked project.
- **Hook state as primary signal** (`proc_cache.py:_hook_state_cache`): `session_id` in hook payload == JSONL filename stem. Direct lookup, no encoding/decoding. Hook state stale guard uses `ALIVE_WINDOW_SECS=3600s`. Workers fire hooks too; their entries ARE consulted by the worker status branch. Crash-safety override: if hook says `'working'` but JSONL mtime exceeds `WORKING_THRESHOLD_SECS=10s`, status is demoted to `'idle'` (CC crashed before Stop-hook fired — JSONL writes stop at crash time). Parallel to the main-branch pattern but inverted: main uses JSONL-mtime to lift idle→working; worker branch uses it to demote stale working→idle.
- **Proxy-log thinking signal** (`proc_cache.py:_proxy_log_newest_mtime`): override condition: `proxy_mtime > jsonl_mtime AND (now - proxy_mtime) ≤ THINKING_OVERRIDE_MAX_SECS=300s` → status `working`. The `proxy_mtime > jsonl_mtime` check: proxy writes at the START of the reasoning phase, staying ahead for the full thinking duration. After response completion the proxy latency entry lands ~0.1s BEFORE CC writes JSONL, so `proxy_mtime` drops just below `jsonl_mtime` — no false positive.
- **_PROXY_LOG_DIR placement**: lives in `proc_cache.py` (not `discover.py`) to avoid an import cycle — `_proxy_log_newest_mtime` is its sole consumer and lives in proc_cache.py.
- **Main aliveness = proc-check only** (`discover.py:_process_project_dir`): `_proc_cwd_for_encoded_dir` returning non-None is the sole aliveness gate. The prior `if now - mtime > ALIVE_WINDOW_SECS: return None` JSONL-age drop was removed — it predates the proc-check and incorrectly evicted idle-but-alive sessions with JSONL older than 1h. `ALIVE_WINDOW_SECS` is still used for hook staleness and worker cwd-fallback.
- **Worker name from first worktree path component, not `basename(cwd)` or encoded dir** (`discover.py:_process_project_dir`): `encode_project_path` (`session_finder.py:70`) replaces `_` with `-` — lossily. The `worker_name` from `_classify_encoded_dir` (encoded-dir derived) has underscores replaced with hyphens → wrong tmux name → worker dropped. `os.path.basename(cwd)` was the prior fix: correct when cwd = worktree root, but WRONG when worker cd's into a subdirectory (yields the innermost subdir name, not the worktree name). Current fix: partition cwd on `/.claude/worktrees/`, take `worktree_rest.split('/')[0]` — first component is always the worktree leaf name regardless of subdir depth. Affects both `_worker_tmux_session` call and `SessionInfo.name`. Fallback (cwd unavailable or no `/.claude/worktrees/` in cwd): lossy name from encoded dir — acceptable since no tmux check occurs in that branch.

## Dev Tools

### dev/menubar_debug.py

Foreground debug runner — boots out the launchd service, starts the menubar app directly via venv Python with `MENUBAR_DIAGNOSTICS=1`, and optionally re-registers launchd on exit.

**Usage:**
```bash
# From project root:
python3 dev/menubar_debug.py               # foreground run; Ctrl-C to stop
python3 dev/menubar_debug.py --rebootstrap # same + re-registers launchd service on exit
```

**What it does:**
1. `launchctl bootout` (ignore failure — service may not be loaded)
2. Launches `venv/bin/python3 workflow.py --mode menubar` with `MENUBAR_DIAGNOSTICS=1` in env
3. On Ctrl-C: prints "Stopped"; if `--rebootstrap`: runs `launchctl bootstrap` from the installed plist

Tick log written to `/tmp/menubar-tick.log` while running (gated on `MENUBAR_DIAGNOSTICS=1`). stdout/stderr land in terminal directly. Requires `~/Library/LaunchAgents/com.brunowinter.monitor-cc-menubar.plist` to exist for `--rebootstrap` — run `./venv/bin/python setup_py2app.py py2app` first if missing.
