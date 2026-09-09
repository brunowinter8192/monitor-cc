# dev/menubar/

## Role

Byte-identity regression harnesses for `src/menubar/` module splits. Add a script here when a
`src/menubar/` refactor (module split, class-attribute split, helper extraction) needs a
before/after correctness proof that isn't already covered by `dev/model_selector/`,
`dev/menubar_per_project/`, or `dev/monitor_lifecycle/`'s own behavior probes.

## Modules

### model_controller_byte_identity.py (196 LOC, new 2026-09, menubar milestone A; fake-app `.settings` re-point 2026-09 menubar milestone B)

**Purpose:** Byte-identity harness for the menubar milestone A concern split
(`model_controller.py` → `model_controller.py` + `model_selection.py` + `model_panel_ui.py`). Two
independent checks, hashed separately (`PERSISTENCE_HASH`, `UI_HASH`):
(1) **Persistence** — `MODEL_SELECTION_FILE`/`PROXY_RULES_FILE` redirected to temp copies via each
persistence function's own `path=` parameter (no monkeypatching needed — every function already
accepts a path override); the rules file is seeded from a copy of the real
`~/.claude/shared-rules/proxy_rules.json` when present, else a synthetic minimal fixture; runs
load → a fixed cycle sequence (4× model, 3× effort, 3× max_tokens, for both main and worker) →
write; hashes both written files' raw bytes.
(2) **UI** — instantiates `ModelController` with a minimal fake app (`.settings` — a
`SimpleNamespace` with `panel_width`/`panel_min_height`/`auto_focus`, re-pointed 2026-09 menubar
milestone B to match `ModelController`'s own `app.settings.*` reads; `_panel_controller` — a plain
`NSObject` subclass instance), calls `open()` then each `handle_cycle_*` once (6 calls — NOT `handle_apply`, which would write the
REAL shared-rules files; `open()`/`handle_cycle_*` are read-only w.r.t. those files), dumping every
arranged subview's class/frame/`title()`/`attributedTitle().string()`/`tag()`/`action()` after each
step; hashes the dump. Falls back to an import + `open()` smoke check if headless AppKit view
creation fails (not observed in this environment — both checks ran against real AppKit objects
successfully).
**Reads:** `~/.claude/shared-rules/proxy_rules.json` (real file, read-only, only to seed the
persistence check's temp copy — never touches `MODEL_SELECTION_FILE` or writes to the real
`PROXY_RULES_FILE`).
**Writes:** Nothing outside its own tempdir (cleaned up on exit) — stdout only (`PERSISTENCE_HASH:
<hex>`, `UI_HASH: <hex>` lines).
**Run:** `./venv/bin/python dev/menubar/model_controller_byte_identity.py`
**Calls out:** `src.menubar.model_controller` (`ModelController`), `src.menubar.model_selection`
(persistence functions) — both imported via dedicated functions (`_import_model_controller`,
`_import_model_selection`), not a module-level `from src.` line, per `block_dev_imports_src`; the
persistence-function import target was updated from `model_controller` to `model_selection` in the
same commit as the split, matching every other symbol re-point this milestone.

**Determinism note:** the UI check's `open()` reads the REAL `MODEL_SELECTION_FILE`/
`PROXY_RULES_FILE` (no override mechanism exists for that specific code path in production) — the
before/after hash comparison is only reliable if those files don't change between the two runs
(i.e. nobody clicks Apply on a live running menubar app in between). No writes ever happen in the
UI check itself.

Status: `PERSISTENCE_HASH: 650d5b77aafc3c718a08a033b5a56530336a9308552eb842499d5c12d3bc8b06`,
`UI_HASH: 52efdd84205e590eedd0663ee8b21d2bb0db8cd386e48907d865071832e1f2d7` — both identical before
and after the split.

---

### panel_manager_byte_identity.py (211 LOC, new 2026-09, menubar milestone B)

**Purpose:** Byte-identity harness for the menubar milestone B `PanelManager` class-attribute
split (`_panel`/`_panel_sv`/`_panel_quit_btn`/`_toggle_btn`/`_panel_kill_btn` → `_widgets`, a
`_PanelWidgets`; the 6 per-rebuild lookup maps → `_lookups`, a `_PanelLookups`) plus the
`_rebuild_inner` helper extraction. Constructs `PanelManager` with a minimal fake app (`.settings`
— a `SimpleNamespace` with `panel_width`/`panel_min_height`/`auto_focus` — and `._panel_controller`,
a plain `NSObject` subclass instance), calls `rebuild(sessions, bg_by_project)` with a synthetic
5-session/3-project list (`alpha`: two mains sharing `desktop_no=2` → conflict `[!2]` rendering;
`beta`: one main (`desktop_no=1`) + one worker; `gamma`: one main with `desktop_no=None` and a bg
timer in `bg_by_project`), walks every arranged subview of the stack — drilling into the one
`NSGridView` among them for every row/cell's class/title/tag/action/color/height — plus every
`_lookups` map, hashes. Then calls `update_inplace` with one session's status flipped and extends
the hash. Falls back to an import + `rebuild()` smoke check if headless AppKit `NSGridView`
introspection fails (not observed in this environment — ran against real AppKit objects
successfully both before and after the split).
**Reads:** nothing external — synthetic session/bg-timer data is constructed inline.
**Writes:** nothing — stdout only (`HASH: <hex>` or `HASH: SKIPPED (...)` + `SMOKE: ...`).
**Run:** `./venv/bin/python dev/menubar/panel_manager_byte_identity.py`
**Calls out:** `src.menubar.panel_manager` (`PanelManager`), `src.menubar.discover` (`SessionInfo`)
— both imported via dedicated functions (`_import_panel_manager`, `_import_discover`), not a
module-level `from src.` line, per `block_dev_imports_src`.

**Determinism note:** this harness's own accessor code targets `PanelManager`'s CURRENT internal
attribute layout — it was updated in the same commit as the split (pre-split baseline hash
`0efc9d390506a6e17c5b33958074e44d6ae5831ddd898ae82c9bd8b008876d42`, re-confirmed identical against
the post-split `_widgets`/`_lookups` layout), mirroring
`dev/menubar/model_controller_byte_identity.py`'s own import-target update pattern from milestone
A. A future `PanelManager` change must re-verify this hash still matches, updating the accessor
code first if the internal attribute names move again.

---

### discover_byte_identity.py (177 LOC, new 2026-09, menubar milestone C)

**Purpose:** Byte-identity harness for `src/menubar/discover.py:_process_project_dir` (86-LOC
function extraction into `_worker_session_info`/`_main_session_info`/`_hook_freshness`).
Monkeypatches every I/O boundary the function touches (`_newest_jsonl`, `_has_active_bg`,
`_read_hook_state`, `_cwd_from_jsonl`, `_worker_tmux_session`, `_tmux_session_exists`,
`_tmux_window_activity`, `_proc_cwd_for_encoded_dir`, `_proxy_log_newest_mtime`) directly on the
live module object — `discover.py`'s own functions resolve these as module globals at call time,
so reassigning the attribute redirects every internal caller, no `Path.stat` patching needed
(the fake jsonl object supplies its own `.stat()`). Drives 4 scenarios through the real,
unmocked `_process_project_dir`/`_classify_encoded_dir`/`_decode_dir_name` logic and hashes the
resulting `SessionInfo` tuples: `worker_fresh_working_stale_activity` (crash-safety demote
working→idle via stale tmux window activity), `worker_no_worktree_old_mtime` (alive guard fails,
returns `None`), `main_fresh_hook` (status taken directly from a fresh hook), `main_idle_proxy_override`
(JSONL says idle, a newer proxy-log mtime within `THINKING_OVERRIDE_MAX_SECS` overrides to
working). Each scenario's fakes are installed, the call made, then restored, so scenarios don't
leak into each other.
**Reads:** nothing external — all fixtures are constructed inline.
**Writes:** nothing — stdout only (`HASH: <hex>`).
**Run:** `./venv/bin/python dev/menubar/discover_byte_identity.py`
**Calls out:** `src.menubar.discover` (`_process_project_dir`, `SessionInfo`) — imported via a
dedicated function (`_import_discover`), not a module-level `from src.` line, per
`block_dev_imports_src`.

**Determinism note:** the same top-level entry point (`_process_project_dir`) is called
regardless of how its internals are decomposed, so this harness needs no accessor-code update
across the milestone C split — unlike `panel_manager_byte_identity.py`'s `_widgets`/`_lookups`
rename. Baseline hash (pre-split) and post-split hash both matched:
`0395eddc436c042aea4b5fa2ca313f207248dc6efc70679e15520ecf6c636a37`.

`detect_main_desktop_numbers` (`desktop_detection.py`) and `_refresh_ghostty_tty_to_id`
(`ghostty.py`) have no equivalent harness — both call CGS/AppleScript/tty I/O with no clean
monkeypatch seam comparable to `discover.py`'s plain-function boundaries (CGS is `ctypes` CDLL
calls, not overridable Python names in the same way); import smoke (`IMPORT_OK` in the behavior
proof) plus `discover.py:list_alive_sessions`'s existing caller check (both functions are called
from there on every discovery cycle) were used instead, per this milestone's own scope.
