# dev/menubar/

## Role
Byte-identity regression harnesses for `src/menubar/` module splits. Add a script here when a
`src/menubar/` refactor (module split, class-attribute split, helper extraction) needs a
before/after correctness proof that isn't already covered by `dev/model_selector/`,
`dev/menubar_per_project/`, or `dev/monitor_lifecycle/`'s own behavior probes.

## Public Interface
No `__init__.py` in this directory. Entry paths: `./venv/bin/python
dev/menubar/discover_byte_identity.py`, `./venv/bin/python
dev/menubar/model_controller_byte_identity.py`, `./venv/bin/python
dev/menubar/panel_manager_byte_identity.py`.

## Flow
Each script imports its `src/menubar/` target via `importlib` (not a literal `from src.` line),
drives it against synthetic or monkeypatched-I/O fixtures, and hashes the resulting state
(tuples, written file bytes, or AppKit subview dumps) to a single stdout `HASH:` line — no
persistent output files.

## Modules

### discover_byte_identity.py (144 LOC)

**Purpose:** Byte-identity harness for `_process_project_dir` in `src/menubar/discover.py` —
monkeypatches every I/O boundary the function touches and hashes 4 scenarios' results.
**Reads:** nothing external — all fixtures constructed inline.
**Writes:** nothing — stdout only (`HASH: <hex>`).
**Kind:** verification aid, not a test: it prints a hash and asserts nothing, a human compares two runs taken before and after a change. Input is synthetic and built inline, so two runs on the same tree give the same hash.
**Called by:** none — run manually; re-run after any `_process_project_dir` change.
**Calls out:** `src.menubar.discover` (`_process_project_dir`, `SessionInfo`) — imported via a
dedicated function, not a module-level `from src.` line, per `block_dev_imports_src`.

---

### model_controller_byte_identity.py (162 LOC)

**Purpose:** Byte-identity harness for `ModelController` — hashes a sandboxed persistence cycle
(model/effort/max_tokens/thinking) and a headless UI subview dump across `open()`/`handle_cycle_*`.
**Reads:** `~/.claude/shared-rules/proxy_rules.json` (read-only, to seed the persistence check's
temp copy).
**Writes:** nothing outside its own tempdir — stdout only (`PERSISTENCE_HASH: <hex>`, `UI_HASH:
<hex>`).
**Kind:** verification aid, not a test: it prints a hash and asserts nothing, a human compares two runs taken before and after a change. It seeds one check from the real `~/.claude/shared-rules/proxy_rules.json`, with no env seam, so a changed rules file changes the hash.
**Called by:** none — run manually; re-run after any `model_controller.py`/`model_selection.py`
change.
**Calls out:** `src.menubar.model_controller` (`ModelController`), `src.menubar.model_selection`
(persistence functions) — both imported via dedicated functions, not a module-level `from src.`
line, per `block_dev_imports_src`.

---

### panel_manager_byte_identity.py (172 LOC)

**Purpose:** Byte-identity harness for `PanelManager` — hashes a synthetic multi-project
`rebuild()` and a subsequent `update_inplace()`, dumping every `NSGridView` row/cell and lookup map.
**Reads:** nothing external — synthetic session/bg-timer data built inline.
**Writes:** nothing — stdout only (`HASH: <hex>` or `HASH: SKIPPED (...)` + `SMOKE: ...`).
**Kind:** verification aid, not a test: it prints a hash and asserts nothing, a human compares two runs taken before and after a change. Input is synthetic and built inline, so two runs on the same tree give the same hash.
**Called by:** none — run manually; re-run after any `PanelManager` internal-attribute change.
**Calls out:** `src.menubar.panel_manager` (`PanelManager`), `src.menubar.discover`
(`SessionInfo`) — both imported via dedicated functions, not a module-level `from src.` line, per
`block_dev_imports_src`.

---

## State
None of the three modules owns any persistent state — each constructs a fresh throwaway
`ModelController`/`PanelManager`/fake-`discover` scenario inside its own process, hashes the
result, and exits; `model_controller_byte_identity.py`'s persistence check is the only one that
writes files, and only inside a `tempfile.TemporaryDirectory()` it owns and discards on exit.
