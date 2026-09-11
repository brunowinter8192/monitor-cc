# dev/menubar/

## Role

Byte-identity regression harnesses for `src/menubar/` module splits. Add a script here when a
`src/menubar/` refactor (module split, class-attribute split, helper extraction) needs a
before/after correctness proof that isn't already covered by `dev/model_selector/`,
`dev/menubar_per_project/`, or `dev/monitor_lifecycle/`'s own behavior probes.

## Modules

### model_controller_byte_identity.py (196 LOC)

**Purpose:** Byte-identity harness for `ModelController` — two independent hashed checks:
persistence (redirects `MODEL_SELECTION_FILE`/`PROXY_RULES_FILE` to temp copies via each
function's own `path=` parameter, runs a fixed cycle sequence for main and worker, hashes both
written files' raw bytes) and UI (instantiates `ModelController` with a minimal fake app, calls
`open()` then each `handle_cycle_*`, hashing every arranged subview's class/frame/title/tag/
action).
**Reads:** `~/.claude/shared-rules/proxy_rules.json` (read-only, to seed the persistence check's
temp copy).
**Writes:** nothing outside its own tempdir — stdout only (`PERSISTENCE_HASH: <hex>`, `UI_HASH:
<hex>`).
**Called by:** none — run manually; re-run after any `model_controller.py`/`model_selection.py`
change.
**Calls out:** `src.menubar.model_controller` (`ModelController`), `src.menubar.model_selection`
(persistence functions) — both imported via dedicated functions, not a module-level `from src.`
line, per `block_dev_imports_src`.

**Determinism note:** the UI check's `open()` reads the REAL `MODEL_SELECTION_FILE`/
`PROXY_RULES_FILE` (no override seam for that code path in production) — the before/after
comparison only holds if those files don't change between the two runs (nobody clicks Apply on a
live menubar in between). The UI check itself never writes.

---

### panel_manager_byte_identity.py (211 LOC)

**Purpose:** Byte-identity harness for `PanelManager` — constructs it with a minimal fake app,
calls `rebuild(sessions, bg_by_project)` with a synthetic multi-project/multi-session list
(including a desktop-number conflict case), walks every arranged subview (drilling into the one
`NSGridView` for every row/cell's class/title/tag/action/color/height) plus every internal lookup
map, hashes; then calls `update_inplace` with one session's status flipped and extends the hash.
**Reads:** nothing external — synthetic session/bg-timer data built inline.
**Writes:** nothing — stdout only (`HASH: <hex>` or `HASH: SKIPPED (...)` + `SMOKE: ...`).
**Called by:** none — run manually; re-run after any `PanelManager` internal-attribute change.
**Calls out:** `src.menubar.panel_manager` (`PanelManager`), `src.menubar.discover`
(`SessionInfo`) — both imported via dedicated functions, not a module-level `from src.` line, per
`block_dev_imports_src`.

**Gotcha:** this harness's accessor code targets `PanelManager`'s CURRENT internal attribute
layout (`_widgets`/`_lookups`) — a future attribute rename requires updating the accessor code
here first, or the hash comparison silently breaks instead of catching a real regression.

---

### discover_byte_identity.py (177 LOC)

**Purpose:** Byte-identity harness for `_process_project_dir` in `src/menubar/discover.py` —
monkeypatches every I/O boundary the function touches directly on the live module object
(`_newest_jsonl`, `_has_active_bg`, `_read_hook_state`, `_cwd_from_jsonl`, `_worker_tmux_session`,
`_tmux_session_exists`, `_tmux_window_activity`, `_proc_cwd_for_encoded_dir`,
`_proxy_log_newest_mtime`), drives 4 scenarios through the real, unmocked
`_process_project_dir`/`_classify_encoded_dir`/`_decode_dir_name` logic, and hashes the resulting
`SessionInfo` tuples.
**Reads:** nothing external — all fixtures constructed inline.
**Writes:** nothing — stdout only (`HASH: <hex>`).
**Called by:** none — run manually; re-run after any `_process_project_dir` change.
**Calls out:** `src.menubar.discover` (`_process_project_dir`, `SessionInfo`) — imported via a
dedicated function, not a module-level `from src.` line, per `block_dev_imports_src`.

---

## Gotchas

**`detect_main_desktop_numbers` (`desktop_detection.py`) and `_refresh_ghostty_tty_to_id`
(`ghostty.py`) have no byte-identity harness in this directory.** Both call CGS/AppleScript/tty
I/O with no clean monkeypatch seam comparable to `discover.py`'s plain-function boundaries (CGS is
`ctypes` CDLL calls, not overridable Python names) — only import-smoke coverage plus
`discover.py:list_alive_sessions`'s own caller check exist for these two functions.
