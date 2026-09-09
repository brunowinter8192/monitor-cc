# dev/menubar/

## Role

Byte-identity regression harnesses for `src/menubar/` module splits. Add a script here when a
`src/menubar/` refactor (module split, class-attribute split, helper extraction) needs a
before/after correctness proof that isn't already covered by `dev/model_selector/`,
`dev/menubar_per_project/`, or `dev/monitor_lifecycle/`'s own behavior probes.

## Modules

### model_controller_byte_identity.py (198 LOC, new 2026-09, menubar milestone A)

**Purpose:** Byte-identity harness for the menubar milestone A concern split
(`model_controller.py` → `model_controller.py` + `model_selection.py` + `model_panel_ui.py`). Two
independent checks, hashed separately (`PERSISTENCE_HASH`, `UI_HASH`):
(1) **Persistence** — `MODEL_SELECTION_FILE`/`PROXY_RULES_FILE` redirected to temp copies via each
persistence function's own `path=` parameter (no monkeypatching needed — every function already
accepts a path override); the rules file is seeded from a copy of the real
`~/.claude/shared-rules/proxy_rules.json` when present, else a synthetic minimal fixture; runs
load → a fixed cycle sequence (4× model, 3× effort, 3× max_tokens, for both main and worker) →
write; hashes both written files' raw bytes.
(2) **UI** — instantiates `ModelController` with a minimal fake app (`_panel_width`,
`_panel_min_height`, `_auto_focus`, `_panel_controller` — a plain `NSObject` subclass instance),
calls `open()` then each `handle_cycle_*` once (6 calls — NOT `handle_apply`, which would write the
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
