# B4 — Step 5 FocusController: Migration Log (2026-05-29)

## What we did

1. **Created `src/menubar/focus_controller.py` (110 LOC):**
   - Module-level pure helpers moved verbatim from `app.py`: `_abort_log_write`, `_has_recent_send_signal`.
   - `FocusController(app)` class wraps all 3 migrating attrs + absorbs 2 functions:
     - `tick(sessions, bg_by_project, now)` absorbs the inline auto-focus block (lines 289–302) AND `_auto_abort_check` module-level function (lines 341–382). Reads `self.app._auto_focus` (stays on app).
     - `statuses_changed(sessions) -> bool` replaces `_statuses_changed(sessions, last)` module-level function.
     - `update_statuses(sessions)` replaces the two `self._last_statuses = {name: status}` assignments at tick-end.

2. **Updated `src/menubar/app.py` (615 → 527 LOC):**
   - Import block: removed `from datetime import datetime, timezone` (only used in `_auto_abort_check`); removed `from .proc_cache import _read_orchestrator_signals, ORCHESTRATOR_SIGNAL_BUFFER_SECS` (all consumers moved); added `from .focus_controller import FocusController`.
   - `__init__`: removed 3 attr inits (`_last_statuses`, `_idle_since_ts`, `_all_workers_idle_since_ts`); added `self.focus = FocusController(self)`.
   - `_tick` (ordering-critical changes, see below):
     - Removed inline auto-focus block (14 lines).
     - Moved `bg_by_project = _scan_bg_sleep_timers(cwd_to_project)` BEFORE focus delegate (was after the inline block).
     - Replaced `_auto_abort_check(self, sessions, bg_by_project, now)` → `self.focus.tick(sessions, bg_by_project, now)`.
     - Panel-open path: `self._last_statuses = ...` → `self.focus.update_statuses(sessions)`.
     - Panel-closed path: `_statuses_changed(sessions, self._last_statuses)` → `self.focus.statuses_changed(sessions)` (BEFORE `update_statuses`); `self._last_statuses = ...` → `self.focus.update_statuses(sessions)`.
   - Removed 4 module-level functions: `_auto_abort_check`, `_has_recent_send_signal`, `_statuses_changed`, `_abort_log_write`.

3. **Updated `src/menubar/DOCS.md`:**
   - `focus_controller.py (110 LOC)` entry added.
   - `app.py` entry: 615→527 LOC, step counter Step 4→5, description updated (removes `_auto_abort_check` mention, adds `focus.tick` delegation), `.focus_controller` added to Calls-out.
   - State table: 3 old `CCMenuBarApp._*_statuses`/`_idle_since_ts`/`_all_workers_idle_since_ts` rows removed; `CCMenuBarApp.focus` row added (after `CCMenuBarApp.panel`).
   - Module Import Graph: `focus_controller.py` node added; `app.py` line updated with `.focus_controller`.
   - `proc_cache.py` Purpose updated: stale `app.py:_auto_abort_check` reference → `focus_controller.py:FocusController.tick`.
   - `proc_cache.py` Called-by: added `focus_controller.py` (`_read_orchestrator_signals`, `ORCHESTRATOR_SIGNAL_BUFFER_SECS`).
   - `system.py` Called-by: added `focus_controller.py:FocusController.tick` (`_focus_session`).
   - `menubar_log.py` Called-by: added `focus_controller.py` (`log_menubar` via `_abort_log_write`).
   - Flow section (line 14): removed stale `_auto_abort_check()` symbol reference.

## What we found

**Ordering guard — `_last_statuses` is read BEFORE it is written (verified):**

The critical constraint is that `_last_statuses` must hold the OLD snapshot when:
1. `FocusController.tick()` reads it (working→idle transition detection for auto-focus)
2. `statuses_changed()` reads it (blink-on-change detection in panel-closed path)

And it is updated ONLY at tick-end via `update_statuses()`. This ordering was preserved exactly:
- `self.focus.tick(...)` reads `self._last_statuses` (old) → fires auto-focus if needed
- Panel-closed: `changed = self.focus.statuses_changed(sessions)` reads old → THEN `self.focus.update_statuses(sessions)` writes new
- Panel-open: `self.focus.update_statuses(sessions)` writes new at tick-end (no change-check needed)

**Ordering change: auto-focus runs AFTER `_scan_bg_sleep_timers` (behavior-neutral):**

Original: auto-focus block ran BEFORE `bg_by_project` was computed. After Step 5: `focus.tick()` is called AFTER `bg_by_project` is computed (so that the single call absorbs both auto-focus + auto-abort). This reordering is functionally neutral: the auto-focus check uses `s.has_bg` from `SessionInfo` (set by `discover.py:list_alive_sessions`), NOT from the freshly-computed `bg_by_project`.

**Cross-controller coupling: `_auto_focus` stays on `app` (confirmed):**

`bead_controller.py:255`, `queue_controller.py:160`, `panel_manager.py:76` all read `app._auto_focus` directly. Moving it to FocusController would require those three controllers to dereference `app.focus._auto_focus` — more indirection with no gain. FocusController reads `self.app._auto_focus` inside `tick()`.

**`_abort_bg_sleep_timers` stays in app.py imports (two call sites):**

`from .bg_timer import _scan_bg_sleep_timers, _abort_bg_sleep_timers` stays in app.py because `_abort_bg_sleep_timers` is called directly from `_PanelController.abortBgTimer_` (line 181 — manual abort button click). FocusController independently imports it for the auto-abort path.

**Pre-existing stale refs in app.py (flagged in B3, not fixed):**
Lines 95 (`toggleBeadTracker_`: `app._panel_open`) and 130 (`toggleAutoJump_`: `app._toggle_btn`) remain unfixed. Out of scope for this step.

## dev/ scripts used

None — pure refactor, no probes needed.

## Decision / next

Step 5 committed: `aca344f`. Branch `menubar-refactor-step5`.

Step 6: `HotkeyController` — `hotkey.py` (265 LOC) stays, 3 attrs migrate (`_hotkey_arr_left_ref`, `_hotkey_digits_cb`, `_hotkey_digits_refs`). `hotkey.py` is already nearly self-contained; Step 6 formalizes the class-wrapper pattern and moves the remaining attrs off `CCMenuBarApp`. After Step 6, `app.py` should drop below 400 LOC ceiling.
