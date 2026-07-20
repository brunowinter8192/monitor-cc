# B1 — Step 2 BeadController: Phase A Plan (2026-05-28)

**Status:** Phase A complete and pre-approved. Phase B (implementation) NOT executed this session — next session resumes from here with direct Go.

Worker `menubar-refactor` produced this plan at 29% context after Phase A.1 (`SessionsController` Step 1/6, commit `0af5843`, merged in `dev`). Worker killed at session-end. Next dispatch can reuse this Phase A verbatim and skip directly to implementation.

## Scope (per A1 Architecture Decision)

- **File move:** `src/menubar/bead_panel.py` → `src/menubar/bead_controller.py`
- **Class wrap:** top-level functions in `bead_panel.py` become methods of `BeadController(app)`
- **8 attrs migrate** from `CCMenuBarApp` → `self.bead.*` in BeadController:
  `_bead_data`, `_bead_db_paths`, `_bead_displayed`, `_bead_expand_tags`, `_bead_expanded`, `_bead_query_tags`, `_bead_tick_counter`, `_bead_untrack_tags`
- **`_refresh_bead_data` function in `app.py`** (NOT in `bead_panel.py`) — absorbed into `BeadController.tick(sessions)`

## Function Disposition

### Stay module-level in `bead_controller.py` (pure helpers, no migrating-attr ownership)

| Function | Reason |
|---|---|
| `_make_bead_nspanel()` | Pure NSPanel factory; returns `_tracker_panel`/`_tracker_sv`/`_tracker_toggle_btn` (stay on app) |
| `_reposition_bead_panel(panel, nsstatusitem)` | Pure geometry, no state |
| `_bead_row_height(row_text, btn_w)` | Pure computation |
| `_make_bead_expand_btn(bead, panel_width, is_expanded)` | Pure factory |
| `_make_bead_status_btn()` | Pure factory |
| `_make_bead_x_btn()` | Pure factory |
| `_make_expand_view(text, panel_width)` | Pure factory |
| `_resize_tracker_panel(app, new_h)` | Accesses only `app._panel_width` + `app._tracker_panel`, both stay on app |

### Module-level state that moves into `BeadController.__init__`

`_rebuild_bead_in_progress = False` → `self._rebuild_in_progress: bool = False`

### Become BeadController methods

| Old function | New method | Signature |
|---|---|---|
| `_compute_bead_height(app)` | `compute_height()` | `(self) -> int` |
| `_rebuild_bead_panel(app)` | `rebuild()` | `(self) -> None` |
| `_rebuild_bead_panel_inner(app)` | `_rebuild_inner()` | `(self) -> None` |
| `_handle_expand_bead(app, tag)` | `handle_expand(tag)` | `(self, tag: int) -> None` |
| `_handle_untrack_bead(app, tag)` | `handle_untrack(tag)` | `(self, tag: int) -> None` |
| `_refresh_bead_data(app, sessions)` (from `app.py`) | `tick(sessions)` + `_do_refresh(sessions)` | `(self, sessions) -> None` each |

## Constructor

```python
class BeadController:
    def __init__(self, app) -> None:
        self.app = app
        self._bead_data: dict         = {}
        self._bead_db_paths: dict     = {}
        self._bead_expanded: dict     = {}
        self._bead_displayed: dict    = {}
        self._bead_expand_tags: dict  = {}
        self._bead_untrack_tags: dict = {}
        self._bead_query_tags: dict   = {}
        self._bead_tick_counter: int  = 4   # starts at 4 -> first tick fires refresh
        self._rebuild_in_progress: bool = False
```

## `_tick` delegate call

Before (3 lines in app.py):

```python
self._bead_tick_counter += 1
if self._bead_tick_counter % 5 == 0 or self._tracker_open:
    _refresh_bead_data(self, sessions)
```

After (1 line):

```python
self.bead.tick(sessions)
```

`BeadController.tick(sessions)` owns the counter + condition + refresh internally.

## app.py Call-Site Changes

| Site | Before | After |
|---|---|---|
| `__init__` (8 attrs) | `self._bead_data = {}` ... x 8 | removed; `self.bead = BeadController(self)` |
| `__init__` (tracker panel) | `self._tracker_panel, self._tracker_sv, self._tracker_toggle_btn = _make_bead_nspanel()` | unchanged (stays on app) |
| `_tick` (3 lines) | counter + condition + `_refresh_bead_data` | `self.bead.tick(sessions)` |
| `expandBead_` | `_handle_expand_bead(self._app, sender.tag())` | `self._app.bead.handle_expand(sender.tag())` |
| `untrackBead_` | `_handle_untrack_bead(self._app, sender.tag())` | `self._app.bead.handle_untrack(sender.tag())` |
| `queryBeadStatus_` | `app._bead_query_tags.get(sender.tag())` | `app.bead._bead_query_tags.get(sender.tag())` |
| `windowDidEndLiveResize_` | `_rebuild_bead_panel(app)` | `app.bead.rebuild()` |
| `_open_tracker_panel` | `_rebuild_bead_panel(app)` | `app.bead.rebuild()` |
| `_refresh_bead_data` function body | exists in app.py | removed (absorbed into `BeadController.tick()` + `_do_refresh()`) |

## Import Block Change in app.py

```python
# Before:
from .bead_panel import (_make_bead_nspanel, _rebuild_bead_panel, _reposition_bead_panel,
                          _handle_expand_bead, _handle_untrack_bead, _resize_tracker_panel)
from .bead_data import project_db_map, load_tracked_beads

# After:
from .bead_controller import BeadController, _make_bead_nspanel, _reposition_bead_panel
```

`project_db_map` + `load_tracked_beads` move into `bead_controller.py`'s INFRASTRUCTURE. The `bead_data` import in `app.py` is removed.

## Attr Translation Inside bead_controller.py

In every method: `app._bead_*` → `self._bead_*`, `app._tracker_*` / `app._panel_*` / `app._auto_focus` / `app._panel_controller` → `self.app._tracker_*` etc.

## Verification (same 4 Smoke-Tests as Step 1)

```bash
./venv/bin/python -c "from src.menubar.bead_controller import BeadController; print(BeadController)"
./venv/bin/python -c "from src.menubar.app import CCMenuBarApp; print(CCMenuBarApp)"
./venv/bin/python workflow.py --mode menubar > /tmp/smoke.txt 2>&1; echo "exit=$?"; cat /tmp/smoke.txt
grep -n "_bead_" src/menubar/app.py   # should show only: self.bead._bead_query_tags (1 line)
```

## Resume Instructions (next session)

1. Spawn fresh worker `menubar-refactor-step2` (or reuse if alive) with project path `/Users/brunowinter2000/Documents/ai/Monitor_CC`
2. Worker prompt: "Read `decisions/OldThemes/menubar_refactor_v1/B1_step2_bead_controller_phase_a.md` and `A1_architecture_decision.md`. Implement Step 2 per the B1 Phase A plan — it is pre-approved by Opus, skip Phase A re-derivation, go directly to implementation. Run the 4 smoke tests. Commit with message `refactor(menubar): introduce BeadController (Step 2/6)`. Output completion checklist + SHA."
3. After commit + merge: continue with Step 3 (QueueController, 11 attrs already pre-mapped in Step 1's Phase A response — see session log)

## Remaining Steps (3 → 6)

| # | Controller | Source module | Attr count | Status |
|---|---|---|---|---|
| 3 | QueueController | `queue_panel.py` → `queue_controller.py` | 11 (pre-mapped) | not started |
| 4 | PanelManager | NEW `panel_manager.py` | ~8 | not started |
| 5 | FocusController | NEW `focus_controller.py` | 3 | not started |
| 6 | HotkeyController | `hotkey.py` → `hotkey_controller.py` | ~4-5 | not started |
