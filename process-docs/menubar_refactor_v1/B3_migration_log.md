# B3 — Step 4 PanelManager: Migration Log (2026-05-29)

## Recovery Note

The Step-4 worker completed the full implementation + smoke tests ("All clean") but died at context-limit ("Prompt is too long") mid-DOCS-update and before writing this recap log. Opus reviewed the worktree diff (imports ok, smoke: `from src.menubar.app import CCMenuBarApp` + singleton-launch exit 0), committed the verified work as `d43be7f`, and merged it. Task A of this session (Step-5 worker) completed the missing recap artifacts.

---

## What we did

1. **Created `src/menubar/panel_manager.py` (192 LOC):**
   - New `PanelManager(app)` class wraps 8 migrating attrs + NSPanel refs: `_panel_open`, `_initialized`, `_displayed_items`, `_cwd_map`, `_desktop_to_cwd`, `_abort_btns_by_project`, `_abort_project_for_tag`, `_rebuild_in_progress`, plus `_panel`, `_panel_sv`, `_panel_quit_btn`, `_toggle_btn`, `_panel_kill_btn` from `_make_nspanel()`.
   - `rebuild(sessions, bg_by_project=None)` — re-entry guarded full panel rebuild (logic adapted from `panel.py:_rebuild_panel` and `_rebuild_panel_inner`).
   - `update_inplace(sessions, bg_by_project)` — in-place dot+badge update (adapted from `panel.py:_update_panel_inplace`).
   - `_resize_panel(new_h)` — NSPanel frame resize (adapted from `panel.py:_resize_panel`).

2. **Reduced `src/menubar/panel.py` 532 → 369 LOC:**
   - Render functions `_rebuild_panel`, `_rebuild_panel_inner`, `_update_panel_inplace`, `_resize_panel` removed from `panel.py` (moved to `PanelManager`).
   - `panel.py` now owns only: NSPanel construction + NSView/NSTextField/NSButton subclasses + UI factory helpers + pure computation helpers. Pure UI concern — no direct `app` instance access.
   - `⚠ over 400 LOC ceiling` flag resolved (was at 532 LOC).

3. **Updated `src/menubar/app.py` (621 → 615 LOC):**
   - Import block: added `from .panel_manager import PanelManager`.
   - `__init__`: 8 `self._panel_*` / `self._displayed_*` / `self._cwd_map` / `self._desktop_to_cwd` / `self._abort_*` / `self._initialized` attr inits replaced by `self.panel = PanelManager(self)`.
   - `_tick`: panel rebuild/update path updated to `self.panel.rebuild(...)` / `self.panel.update_inplace(...)` / `self.panel._panel_open` / `self.panel._displayed_items` / `self.panel._abort_btns_by_project`.
   - `_PanelController` action handlers + lazy-init: updated from bare `app._panel_*` refs to `app.panel._panel_*`.
   - `_reregister_digit_hotkeys`: `app._desktop_to_cwd` → `app.panel._desktop_to_cwd`.
   - `_open_main_panel`, `_close_main_panel`, `_background_panel`, `_deferred_close_open`: `app._panel_*` → `app.panel._panel_*`.

4. **Updated `src/menubar/DOCS.md` (dead worker partial — completed in recap):**
   - `panel.py` entry: 532→369 LOC, ceiling flag resolved, purpose updated to reflect render functions moved.
   - `panel_manager.py (192 LOC)` entry: added (new module).
   - `app.py` entry: 621→615 LOC, step counter Step 3→4, description updated, `.panel_manager` added to Calls-out.
   - State table: 12 old `CCMenuBarApp._panel_*` / `_displayed_*` / `_cwd_map` / `_desktop_to_cwd` / `_abort_*` / `_toggle_btn` / `_initialized` rows removed; replaced with single `CCMenuBarApp.panel` row.
   - Module Import Graph: `panel_manager.py` node added; `app.py` line updated with `.panel_manager`.

## What we found

**Cross-controller decision: `_panel_width`, `_panel_min_height`, `_auto_focus` stay on `app`.**

A1's original note listed `_auto_focus`, `_panel_width`, `_panel_min_height` as "migrate as part of PanelManager step". These were intentionally NOT moved. All three are read by `bead_controller.py` (via `self.app._panel_width`, `self.app._panel_min_height`, `self.app._auto_focus`) and `queue_controller.py` (same refs). Moving them to `PanelManager` would require bead and queue to access `app.panel._auto_focus` etc. — creating a direct bead/queue→panel coupling with no benefit since app already bridges them. They remain on `app` as cross-controller shared preferences.

**panel.py LOC baseline clarification:**
`panel.py` was 532 LOC before Step 4 (inclusive of render functions). After extraction to `panel_manager.py`, actual is 369 (not 373 as estimated). Difference: 4 lines absorbed into `panel_manager.py` overhead vs estimated.

**Stale refs found during recap (post-merge, not fixed by Step-4 worker):**
Two refs in `app.py` reference bare `app._panel_open` / `app._toggle_btn` instead of `app.panel._panel_open` / `app.panel._toggle_btn`:
- Line 95: `toggleBeadTracker_` — `if app._panel_open:` → should be `app.panel._panel_open`
- Line 130: `toggleAutoJump_` — `app._toggle_btn.setAttributedTitle_` → should be `app.panel._toggle_btn.setAttributedTitle_`

These do NOT surface in the smoke tests (import + singleton-launch) but would raise `AttributeError` at runtime when either `toggleBeadTracker_` is triggered while main panel is open, or when `toggleAutoJump_` is triggered. Flagged for Opus; not fixed in this recap (scope is docs-only).

## dev/ scripts used

None — pure refactor, no probes needed.

## Decision / next

Step 4 committed: `d43be7f`. Branch `menubar-refactor-step4`, merged.

Step 5: `FocusController` — new file, 3 attrs (`_idle_since_ts`, `_all_workers_idle_since_ts`, `_last_statuses`) migrate from `CCMenuBarApp`. Encapsulates auto-focus / idle-tracking logic from `_tick`. Lower LOC impact than Step 4; `_auto_focus` stays on `app` (bead/queue read it directly).
