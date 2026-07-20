# B1 — Step 2 BeadController: Migration Log (2026-05-28)

## What we did

Implemented the pre-approved B1 Phase A plan as a pure-refactor step:

1. **Created `src/menubar/bead_controller.py` (350 LOC):**
   - Module-level pure helpers moved verbatim from `bead_panel.py`: `_make_bead_nspanel`, `_reposition_bead_panel`, `_bead_row_height`, `_make_bead_expand_btn`, `_make_bead_status_btn`, `_make_bead_x_btn`, `_make_expand_view`, `_resize_tracker_panel`.
   - `BeadController(app)` class wraps the 5 migrating functions as methods: `tick`, `_do_refresh`, `compute_height`, `rebuild`, `_rebuild_inner`, `handle_expand`, `handle_untrack`.
   - `project_db_map` + `load_tracked_beads` imports moved from `app.py` → `bead_controller.py` INFRASTRUCTURE.
   - Module-level `_rebuild_bead_in_progress` became `self._rebuild_in_progress` on `BeadController`.

2. **Deleted `src/menubar/bead_panel.py`** via `git rm`.

3. **Updated `src/menubar/app.py` (773→752 LOC):**
   - Import block: 2 old imports (`bead_data`, `bead_panel`) → 1 new import (`bead_controller`).
   - `__init__`: 8 `self._bead_*` attr inits replaced by `self.bead = BeadController(self)`.
   - `_tick`: 3-line counter+condition+refresh block → `self.bead.tick(sessions)`.
   - `expandBead_`: `_handle_expand_bead(self._app, tag)` → `self._app.bead.handle_expand(tag)`.
   - `untrackBead_`: `_handle_untrack_bead(self._app, tag)` → `self._app.bead.handle_untrack(tag)`.
   - `queryBeadStatus_`: `app._bead_query_tags.get(tag)` → `app.bead._bead_query_tags.get(tag)`.
   - `windowDidEndLiveResize_`: `_rebuild_bead_panel(app)` → `app.bead.rebuild()`.
   - `_open_tracker_panel`: `_rebuild_bead_panel(app)` → `app.bead.rebuild()`.
   - `_refresh_bead_data` function body removed (absorbed into `BeadController.tick` + `_do_refresh`).

4. **Updated `src/menubar/DOCS.md`:** `bead_panel.py` entry replaced, State table updated, Import Graph updated, 3 stale `bead_panel.py` cross-references corrected.

## What we found

No surprises. B1 plan matched the current code exactly — all 8 attrs, `_refresh_bead_data` location, tick counter logic, function disposition, and all call sites. The refactor was mechanical.

One minor discrepancy caught during recap: the B1 plan smoke test said "1 line" for `grep -n "_bead_" src/menubar/app.py`. The actual output shows 4 lines — but 3 of them are import name and function-call references (`_make_bead_nspanel`, `_reposition_bead_panel`), not stale `self._bead_*` attrs. Zero stale attrs remain on `CCMenuBarApp`. The check passed in substance.

Three stale `bead_panel.py` cross-references in DOCS.md were caught during recap (panel.py Purpose, queue_panel.py Purpose, Gotchas section) and corrected.

## dev/ scripts used

None — pure refactor, no probes needed.

## Decision / next

Step 2 committed: `5b93a39`. Branch `menubar-refactor-step2`, ready to merge.

Step 3: `QueueController` — `queue_panel.py` → `queue_controller.py`, 11 attrs pre-mapped in Step 1 Phase A session log. Same pattern: file-move, class-wrap, attrs off `CCMenuBarApp`, `self.queue.tick(sessions)` delegate in `_tick`.
