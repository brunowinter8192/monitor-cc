# menubar_refactor_v1 — Phase A Architecture Decision

## Context

`src/menubar/app.py` carries 767 LOC, 35 instance attrs on `CCMenuBarApp`, 25 imports, and three conceptually separate concerns (session discovery, bead tracking, queue UI, panel lifecycle, hotkey wiring) all inlined into one class. The `⚠ over 400 LOC ceiling` flag in DOCS.md was deferred pending this refactor.

**Goal:** Composition-with-per-Concern-Controllers. Six controllers each own a subset of state and behavior. `CCMenuBarApp` becomes a slim Coordinator: holds the 6 controller refs, the `@rumps.App` binding (cannot move), and `_tick` as delegating orchestrator.

**Constraint:** Pure refactor. Zero functional change. `decisions/menubar_desktop_allocation.md` and `decisions/menubar_session_status.md` ISTs are NOT touched.

---

## Criteria (Opus-approved priority order)

1. **Extensibility** — adding controller 7 or swapping an impl must not require touching CCMenuBarApp
2. **Maintainability** — each concern's state, lifecycle, and behavior readable in isolation
3. **Effort** — subordinate; pattern must be achievable in incremental steps without breaking the menubar between steps

---

## Paths Considered

### Path A — Strict Split (independent modules, no class hierarchy)

Each concern becomes a standalone module (`sessions.py`, `focus.py`, …) with module-level state (à la `proc_cache.py` pattern). `CCMenuBarApp._tick` calls module-level functions, passing `app` as a parameter.

**Pro:**
- Zero object overhead; matches existing pattern in `proc_cache.py`, `ghostty.py`
- No `self.app` circular reference concern

**Con:**
- Module-level mutable state is harder to mock and test
- Coordinating 6 modules of mutable state across a timer callback produces implicit coupling (shared implicit namespace)
- `_tick` can't be refactored into "delegate to each controller" — it remains a monolith calling 6 sets of module functions
- Adding a 7th concern means adding another module import to app.py; no clear "the controller knows about itself" boundary

### Path B — Composition with per-Concern Controller Classes ← **CHOSEN**

Each concern is a class: `SessionsController`, `FocusController`, `BeadController`, `QueueController`, `HotkeyController`, `PanelManager`. Instance stored on `CCMenuBarApp`: `self.sessions`, `self.focus`, etc. Each controller takes `app` in `__init__` for back-references where needed.

**Pro:**
- `CCMenuBarApp._tick` delegates: `self.sessions.refresh()`, `self.focus.tick(sessions, now)`, etc. Coordination point is explicit and readable
- State encapsulated within the controller instance; no module-level mutable global surface
- Incremental migration: each controller added one at a time; app works at each step
- Matches the existing `_PanelController` (NSObject) pattern already in `app.py` — adding Python-level controllers is a natural extension, not a foreign concept
- Adding controller 7 = add file, add `self.new = NewController(self)`, add one delegate call in `_tick`

**Con:**
- `self.app` back-reference from each controller → circular reference at Python level (not ObjC level). Benign in CPython (ref-counted, GC'd), but worth documenting
- Slightly more boilerplate than module functions

### Path C — Module-Functions with Per-Module State (hybrid)

Existing modules (`bead_panel.py`, `queue_panel.py`, `hotkey.py`) absorb their own state as module-level globals. `CCMenuBarApp` stops holding those attrs; modules expose `init(app)` / `tick(app)` / `get_data()`.

**Pro:**
- Smallest file changes — existing module files stay nearly intact
- No new class concept

**Con:**
- Module-level state is shared process-wide → impossible to have two concurrent instances (menubar runs as singleton, but the constraint is invisible)
- Mixed pattern: some concerns are class instances, some are module globals — inconsistent
- `CCMenuBarApp.__init__` still must call each module's `init(app)` function; no structural improvement over Path B but loses encapsulation benefit
- Existing `_PanelController` precedent argues for class-based approach

---

## Chosen Path: B (Composition with per-Concern Controllers)

**Reasoning:**

1. The existing `_PanelController(NSObject)` ObjC-bridge class already demonstrates the pattern: a class that holds `self._app` ref and contains a cohesive set of action-handler methods. The 6 pure-Python controllers follow the same structural idiom without the ObjC overhead.
2. `core/monitor.py` uses module-level state, but it is a single-concern module (polling loop state) with no sub-concerns and no per-tick delegation. The menubar has 6+ distinct concerns — class-per-concern is justified.
3. Incremental migration (one controller per worker dispatch) requires that the menubar keeps running after each step. Path B allows this cleanly: each step adds one controller and removes N attrs from CCMenuBarApp; other controllers don't exist yet and their attrs remain on app.
4. `_tick` as a pure delegator is the desired end-state: `sessions = self.sessions.refresh()` / `self.focus.tick(sessions, now)` / `self.bead.tick(sessions)` / etc. This end-state is only achievable cleanly with controller instances.

---

## Controller Table (final architecture)

| Controller | File | Owns attrs (current CCMenuBarApp attrs) |
|---|---|---|
| `SessionsController` | NEW `src/menubar/sessions_controller.py` | `_last_sessions` |
| `FocusController` | NEW `src/menubar/focus_controller.py` | `_idle_since_ts`, `_all_workers_idle_since_ts`, `_last_statuses` |
| `BeadController` | `bead_panel.py` → renamed `bead_controller.py` | `_bead_data`, `_bead_db_paths`, `_bead_displayed`, `_bead_expand_tags`, `_bead_expanded`, `_bead_query_tags`, `_bead_tick_counter`, `_bead_untrack_tags` |
| `QueueController` | `queue_panel.py` → renamed `queue_controller.py` | `_queue_open`, `_queue_panel`, `_queue_sv`, `_queue_toggle_btn`, `_queue_displayed_names`, `_queue_data`, `_pending_queue_tags`, `_pending_queue_views`, `_queue_add_tags`, `_queue_remove_tags`, `_queue_toggle_tags` |
| `HotkeyController` | `hotkey.py` → renamed `hotkey_controller.py` | `_hotkey_arr_left_ref`, Cmd+1-9 mapping (`_hotkey_digits_cb`, `_hotkey_digits_refs`) |
| `PanelManager` | NEW `src/menubar/panel_manager.py` | `_panel_open`, `_panel_sv`, `_displayed_items`, `_cwd_map`, `_desktop_to_cwd`, `_abort_btns_by_project`, `_abort_project_for_tag`, `_initialized` |

**`_PanelController` rename:** Not renamed in this refactor. The `_PanelController` NSObject is the ObjC-bridge action-target class; renaming it would require ObjC selector table regeneration (the class name is part of PyObjC's dynamic class registration). If future clarity demands it, rename → `_PanelButtonTarget` in a separate step. Not part of Steps 1-6.

**CCMenuBarApp retains permanently:**
- `@rumps.App` subclass binding (cannot move — rumps hooks into the class at metaclass level)
- Refs to 6 controllers (`self.sessions`, `self.focus`, `self.bead`, `self.queue`, `self.hotkey`, `self.panel`)
- `_tick` as orchestrator (delegates; cannot move — `@rumps.timer` decorator is bound to the class)
- `_panel_controller` (the `_PanelController` NSObject instance — must stay alive on app for ARC/GC pinning)
- AppKit/NSStatusBar/NSPanel direct refs: `_panel`, `_panel_sv`, `_panel_quit_btn`, `_toggle_btn`, `_panel_kill_btn`, `_tracker_panel`, `_tracker_sv`, `_tracker_toggle_btn` (these transfer to controllers in later steps)
- `_hotkey_cb`, `_hotkey_ref`, `_hotkey_k_cb`, `_hotkey_k_ref` (Cmd+L / Cmd+K global hotkeys — pinned for GC safety)
- `_auto_focus`, `_panel_width`, `_panel_min_height` (settings — touch multiple controllers; stay on app for now, migrate as part of PanelManager step)
- `_last_log_cleanup_ts`, `_panel_backgrounded`, `_tracker_open` (minor cross-cutting; stay on app for now)

---

## Migration Sequence Rationale

Steps ordered smallest-risk first to validate the composition pattern before touching high-LOC, high-entanglement concerns.

| Step | Controller | Risk | Rationale |
|---|---|---|---|
| 1 | `SessionsController` | LOW | 1 attr (`_last_sessions`), 8 call sites, no UI, no ObjC. Validates pattern end-to-end. |
| 2 | `BeadController` | MEDIUM-LOW | 8 attrs, cleanest concern boundary (bead-tab only), `bead_panel.py` already exists as a near-complete file-move candidate |
| 3 | `QueueController` | MEDIUM | 11 attrs, queue_panel.py exists, ObjC action-handlers stay in `_PanelController` (they just call `self._app.queue.method()`) |
| 4 | `PanelManager` | MEDIUM-HIGH | 8 attrs but touches `_rebuild_panel` deeply; `panel.py` reads most of these attrs directly |
| 5 | `FocusController` | MEDIUM | 3 attrs, isolated to auto-focus / auto-abort path; lower LOC impact |
| 6 | `HotkeyController` | LOW-MEDIUM | 3 attrs, `hotkey.py` almost self-contained already; done last because Cmd+arrows are tied to panel lifecycle |

---

## Step 1 Scope: SessionsController

### Attr Migration

| Attr | Current location | Move to |
|---|---|---|
| `_last_sessions: list = []` | `CCMenuBarApp.__init__` (line 351) | `SessionsController._last_sessions` |

No other attr migrates in Step 1.

### Call-Site Analysis (all `_last_sessions` refs in `app.py`)

| Line | Context | Migration |
|---|---|---|
| 113 | `queryBeadStatus_`: reads `app._last_sessions` to find cwd by project_name | → `app.sessions.data` |
| 187 | `addQueueRow_`: `sessions = list_alive_sessions(); app._last_sessions = sessions` | → `sessions = self._app.sessions.refresh()` |
| 215 | `toggleQueueEntry_`: same pattern | → `sessions = self._app.sessions.refresh()` |
| 235 | `removeQueueEntry_`: same pattern | → `sessions = self._app.sessions.refresh()` |
| 255 | `commitQueueField_`: same pattern | → `sessions = self._app.sessions.refresh()` |
| 294 | `windowDidEndLiveResize_` (queue branch): same pattern | → `sessions = self._app.sessions.refresh()` |
| 351 | `CCMenuBarApp.__init__`: `self._last_sessions: list = []` | → `self.sessions = SessionsController(self)` |
| 389 | `_tick`: `sessions = list_alive_sessions()` (try/except at 386-388) + `self._last_sessions = sessions` | → `try: sessions = self.sessions.refresh(); except: sessions = []` |
| 634 | `_open_main_panel`: `sessions = list_alive_sessions(); app._last_sessions = sessions` | → `sessions = app.sessions.refresh()` |
| 691 | `_open_queue_panel`: same pattern | → `sessions = app.sessions.refresh()` |

**NOT migrated** (call `list_alive_sessions()` locally without updating `_last_sessions`):
- Line 166-167 (`abortBgTimer_`): local-use-only fresh fetch for bg-abort logic — NOT a cache update; stays as `sessions = list_alive_sessions()`
- Line 287-288 (`windowDidEndLiveResize_` panel-open branch): local-use-only — stays as `sessions = list_alive_sessions()`

`from .discover import list_alive_sessions` import stays in `app.py` for these two remaining direct call sites.

### `SessionsController` Public API

```python
class SessionsController:
    def __init__(self, app: 'CCMenuBarApp') -> None:
        self.app = app
        self._last_sessions: list = []

    def refresh(self) -> list:
        """Call list_alive_sessions(), update cache, return new snapshot. Does NOT swallow exceptions."""
        sessions = list_alive_sessions()
        self._last_sessions = sessions
        return sessions

    @property
    def data(self) -> list:
        """Return cached session snapshot from last refresh()."""
        return self._last_sessions
```

- Type annotation uses `list` (not `List[SessionInfo]`) to avoid importing `SessionInfo` into the controller; callers already have the concrete type from their existing imports.
- `refresh()` does NOT swallow exceptions — the `_tick` call site wraps in try/except, and the `_PanelController` methods do not (matching current behavior at each site).
- `self.app` held for potential future use (e.g., if a controller needs to poke another controller). Not used in Step 1.

### LOC Estimate

`sessions_controller.py`: ~25 LOC (infrastructure + class + 3 methods with comments).  
`app.py` net reduction: −10 lines (1 attr init removed, 8 assignments replaced, import cleanup minimal).

---

## What This Refactor Explicitly Does NOT Change

- Session discovery logic (`discover.py`, `proc_cache.py`) — untouched
- Status detection thresholds — untouched (`decisions/menubar_session_status.md` IST unchanged)
- Desktop allocation / py2app bundle — untouched (`decisions/menubar_desktop_allocation.md` IST unchanged)
- `_PanelController` ObjC selectors and action-handler logic — untouched
- All panel rendering (panel.py, bead_panel.py, queue_panel.py) — untouched in Step 1
- Auto-abort logic, auto-focus logic — untouched in Step 1
- Hotkey registration — untouched in Step 1
- Menubar visual behavior — zero change

---

## Verification Plan for Step 1

**Check 1 — Import smoke test:**
```bash
cd <worktree>
./venv/bin/python -c "from src.menubar.sessions_controller import SessionsController; print(SessionsController)"
```
Expected: `<class 'src.menubar.sessions_controller.SessionsController'>`

**Check 2 — CCMenuBarApp import (catches missed `_last_sessions` refs):**
```bash
./venv/bin/python -c "from src.menubar.app import CCMenuBarApp; print(CCMenuBarApp)"
```
Expected: `<class 'src.menubar.app.CCMenuBarApp'>` with no AttributeError or ImportError.

**Check 3 — Singleton-lock launch:**
```bash
./venv/bin/python workflow.py --mode menubar
```
Expected exit code 0 (singleton lock blocks second instance — proves full init path ran, SessionsController was instantiated, no AttributeError on `self.sessions.data` read).

**Check 4 — No bare `_last_sessions` on CCMenuBarApp:**
```bash
grep -n "_last_sessions" src/menubar/app.py
```
Expected: zero lines (or only internal controller refs like `self.sessions._last_sessions` which would be in sessions_controller.py, not app.py).

**Check 5 — LOC reduction:**
```bash
wc -l src/menubar/app.py
```
Expected: < 767 (migrations removed lines).

**Check 6 — docs-drift-check:**
```bash
docs-drift-check
```
Expected: 0 new findings (DOCS.md updated with new module entry and updated State table).

---

## OldThemes Continuation

Subsequent worker dispatches append to this folder:
- `B1_migration_log.md` — BeadController (Step 2)
- `B2_migration_log.md` — QueueController (Step 3)
- etc.

Final summary doc (after all 6 steps): `README.md` in this folder — lists all dev probes run (none for this pure-refactor sequence), final controller inventory, and any architectural learnings.
