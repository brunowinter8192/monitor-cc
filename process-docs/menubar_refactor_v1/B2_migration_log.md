# B2 — Step 3 QueueController: Migration Log (2026-05-29)

## What we did

Implemented the pre-approved B2 Phase A plan as a pure-refactor step:

1. **Created `src/menubar/queue_controller.py` (448 LOC):**
   - Module-level ObjC class `_QueuePanel(_KeyablePanel)` and constants moved verbatim from `queue_panel.py`.
   - Module-level pure helpers moved verbatim: `_make_queue_nspanel`, `_reposition_queue_panel`, `_make_queue_add_btn`.
   - `load_queue`, `save_queue`, `deliver_message` imports moved from `app.py` → `queue_controller.py` INFRASTRUCTURE.
   - `from .paths import HOOKS_FILE as _HOOKS_FILE` added (needed by `handle_try_deliver`).
   - `QueueController(app)` class wraps all 11 migrating attrs + re-entry guard `_rebuild_in_progress`.
   - `_make_queue_nspanel()` call moved inside `QueueController.__init__` (result stored on `self._queue_panel/sv/toggle_btn`).
   - `_compute_queue_height` → `compute_height(sessions)` method.
   - `_resize_queue_panel` → `_resize_panel(new_h)` method (uses `self._queue_panel`, `self.app._panel_width`).
   - `_rebuild_queue_panel` (re-entry guard) → `rebuild(sessions)` method.
   - `_rebuild_queue_panel_inner` → `_rebuild_inner(sessions)` method.
   - `open(sessions)` method added: explicit `load_queue()` + `rebuild(sessions)` for panel-open path.
   - Five `_PanelController` action-handler bodies moved as methods: `handle_add_row`, `handle_toggle_entry`, `handle_remove_entry`, `handle_commit_field`, `handle_text_end_editing`.
   - `app.py:_try_deliver_now` absorbed as `handle_try_deliver(session_id, text, idx)` — reads `HOOKS_FILE`, calls `deliver_message`, marks entry sent.

2. **Deleted `src/menubar/queue_panel.py`** via `git rm`.

3. **Updated `src/menubar/app.py` (752 → 621 LOC):**
   - Import block: `from .queue_panel import (_make_queue_nspanel, _rebuild_queue_panel, _reposition_queue_panel, _resize_queue_panel)` → `from .queue_controller import QueueController, _reposition_queue_panel`; `from .queue import load_queue, save_queue, deliver_message` → `from .queue import deliver_message`; `HOOKS_FILE` removed from `.paths` import.
   - `__init__`: 11 `self._queue_*` attr inits + `_make_queue_nspanel()` call (lines 341-349) → `self.queue = QueueController(self)` (1 line).
   - `_tick` queue section (7 lines: `load_queue` + change-detect + conditional rebuild) → `self.queue.tick(sessions)` (1 line).
   - `_tick` lazy-init: `self._queue_panel.*` → `self.queue._queue_panel.*`; `self._queue_toggle_btn.*` → `self.queue._queue_toggle_btn.*`.
   - `_PanelController.togglePanel_`: `app._queue_open` → `app.queue._queue_open`; `app._queue_panel` → `app.queue._queue_panel`.
   - `_PanelController.toggleAutoJump_`: `app._queue_toggle_btn` → `app.queue._queue_toggle_btn`.
   - 5 queue action handlers (`addQueueRow_` / `toggleQueueEntry_` / `removeQueueEntry_` / `commitQueueField_` / `controlTextDidEndEditing_`): full bodies → 1-line delegates (`self._app.queue.handle_*(…)`).
   - `_PanelController.windowDidEndLiveResize_`: `app._queue_open` → `app.queue._queue_open`; `_rebuild_queue_panel(app, sessions)` → `app.queue.rebuild(sessions)`.
   - `_deferred_close_open`: `app._queue_panel` → `app.queue._queue_panel` (from_obj + to_obj else branches).
   - `_background_panel`: `app._queue_open` → `app.queue._queue_open` (2 checks); `app._queue_panel.*` → `app.queue._queue_panel.*`.
   - `_open_queue_panel`: `app._queue_data = load_queue()` + `_rebuild_queue_panel(app, sessions)` → `app.queue.open(sessions)`; remaining refs updated to `app.queue._queue_*`.
   - `_close_queue_panel`: `app._queue_panel.orderOut_` → `app.queue._queue_panel.orderOut_`; `app._queue_open = False` → `app.queue._queue_open = False`.
   - `_try_deliver_now` function removed entirely (absorbed into `QueueController.handle_try_deliver`).

4. **Updated `src/menubar/DOCS.md`:**
   - `queue_panel.py` entry replaced with `queue_controller.py (448 LOC)` entry.
   - `app.py` entry updated: 752→621 LOC, description, reads/writes, calls-out, step counter Step 2→3.
   - `queue.py` Called-by updated → `queue_controller.py`.
   - `paths.py` Called-by: added `queue_controller.py` (`HOOKS_FILE`).
   - `sessions_controller.py` Called-by: queue action handler refs updated → `queue_controller.py:QueueController.handle_*`.
   - State table: 11 `CCMenuBarApp._queue_*` rows removed, replaced with single `CCMenuBarApp.queue` row.
   - Module Import Graph: `queue_panel.py` line replaced with `queue_controller.py` line.

## What we found

No surprises in the attr/call-site mapping — all 11 attrs and every call site matched the Phase A plan exactly.

**One deviation from the B1 pattern:** `_queue_panel`, `_queue_sv`, `_queue_toggle_btn` MOVE to `QueueController` (unlike `_tracker_panel`, `_tracker_sv`, `_tracker_toggle_btn` which stayed on app in Step 2). This is correct per the A1 architecture table. The consequence: `_make_queue_nspanel()` call moves inside `QueueController.__init__` rather than staying in `CCMenuBarApp.__init__` + being imported by `app.py`. Only `_reposition_queue_panel` is imported by `app.py` (needed in `_open_queue_panel`).

**`_try_deliver_now` moved:** This function was in `app.py`, not `queue_panel.py`, but it exclusively accessed queue state (`_queue_data`) and used `load_queue`/`save_queue`/`deliver_message`. Moving it to `QueueController.handle_try_deliver` removed all `load_queue`/`save_queue` imports from `app.py` (only `deliver_message` stays for `queryBeadStatus_`). Analogous to how `_refresh_bead_data` was absorbed into `BeadController.tick + _do_refresh` in B1.

**LOC ceiling violation:** `queue_controller.py` is 448 LOC — 48 over the 400-line hard ceiling. This is inherent from the mechanical extraction: `queue_panel.py` (290 LOC) + action handler bodies absorbed from `app.py` (~80 LOC) + `_try_deliver_now` (~30 LOC) + class wrapper overhead (~50 LOC). The natural concern split would separate panel-render (`_rebuild_inner`, `compute_height`, `_resize_panel`) from action-dispatch (`handle_*` methods), but this requires a new architectural decision and is deferred post-Step-6 as a separate task.

**`open(sessions)` method added (not in original B1 pattern):** `_open_queue_panel` needed an explicit `load_queue()` call before rebuild (unlike the bead panel which doesn't pre-fetch). A thin `QueueController.open(sessions)` method (`self._queue_data = load_queue(); self.rebuild(sessions)`) keeps `load_queue` out of `app.py` while preserving the pre-load semantics.

## dev/ scripts used

None — pure refactor, no probes needed.

## Decision / next

Step 3 committed: `8d43950`. Branch `menubar-refactor-step3`, ready to merge.

Step 4: `PanelManager` — new file, 8 attrs migrate from `CCMenuBarApp` (`_panel_open`, `_panel_sv`, `_displayed_items`, `_cwd_map`, `_desktop_to_cwd`, `_abort_btns_by_project`, `_abort_project_for_tag`, `_initialized`). Highest LOC impact on `app.py` since `_rebuild_panel` touches these attrs directly.

Pending: post-refactor split of `queue_controller.py` into render + dispatch concern files (to resolve the 400-LOC ceiling violation) — separate architectural decision required.
