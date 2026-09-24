# dev/menubar/

## Role
Byte-identity regression harnesses for `src/menubar/` module splits, plus the `p5_*` parallel strands that prove the phase 5 fallback and tripwire changes (`P5_ROOT` points them at a pristine source tree for before/after comparison). Add a script here when a
`src/menubar/` refactor (module split, class-attribute split, helper extraction) needs a
before/after correctness proof that isn't already covered by `dev/model_selector/`,
`dev/menubar_per_project/`, or `dev/monitor_lifecycle/`'s own behavior probes.

## Public Interface
No `__init__.py` in this directory. Entry paths: `./venv/bin/python
dev/menubar/discover_byte_identity.py`, `./venv/bin/python
dev/menubar/model_controller_byte_identity.py`, `./venv/bin/python
dev/menubar/panel_manager_byte_identity.py`; `./venv/bin/python dev/menubar/p5_run_all.py` runs all phase 5 strands in parallel.

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

### p5_common.py (49 LOC)

**Purpose:** Shared helpers for the phase 5 strands: repo-root switch via `P5_ROOT`, module import through `importlib`, stderr capture, digest and PASS/FAIL check.
**Reads:** env `P5_ROOT` (optional alternate source tree)
**Writes:** nothing.
**Called by:** the `p5_g*` strands.
**Calls out:** `src.menubar.*` via `importlib` (no literal `from src.` line).

---

### p5_g1_log.py (51 LOC)

**Purpose:** Strand for `menubar_log.py`: normal append and retention unchanged, write and cleanup failures reach stderr.
**Reads:** a temp directory it creates.
**Writes:** stdout PASS/FAIL lines.
**Called by:** `p5_run_all.py`.
**Calls out:** `src.menubar.menubar_log`.

---

### p5_g2_state.py (151 LOC)

**Purpose:** Strand for the state and config readers and writers: missing file silent, unreadable file logged, unreadable rules file never overwritten, write order, hook_writer, paths shims gone.
**Reads:** temp directories with synthetic JSON.
**Writes:** stdout PASS/FAIL and `DIFF` digest lines.
**Called by:** `p5_run_all.py`.
**Calls out:** `src.menubar.{app_settings,model_selection,proc_cache,monitor_sweep_scheduler,rag_controller,hook_writer,paths}`.

---

### p5_g3_app.py (137 LOC)

**Purpose:** Strand for app wiring, restart route, panel cycle errors and Carbon hotkey status/handler failures, driven by fake carbon objects and fake app objects.
**Reads:** nothing external.
**Writes:** stdout PASS/FAIL lines.
**Called by:** `p5_run_all.py`.
**Calls out:** `src.menubar.{app,panel_lifecycle,hotkey_controller,hotkey_digits,hotkey_arrows}`.

---

### p5_g4_detection.py (91 LOC)

**Purpose:** Strand for `desktop_detection.py`: CGS key handling, route logging on change, removed last-known-good state; normal results digest-compared.
**Reads:** nothing external (fake CoreGraphics dicts).
**Writes:** stdout PASS/FAIL and `DIFF` digest lines.
**Called by:** `p5_run_all.py`.
**Calls out:** `src.menubar.desktop_detection`.

---

### p5_g5_discover.py (133 LOC)

**Purpose:** Strand for `discover.py`, `discovery_worker.py` and the `panel.py` guard: skipped projects logged once, route lines on change, worker loop error handling, session results digest-compared.
**Reads:** temp jsonl files.
**Writes:** stdout PASS/FAIL and `DIFF` digest lines.
**Called by:** `p5_run_all.py`.
**Calls out:** `src.menubar.{discover,discovery_worker}`; AST read of `panel.py`.

---

### p5_g6_caches.py (287 LOC)

**Purpose:** Strand for `proc_cache.py`, `ghostty.py`, `bg_timer.py`, `bg_task_orphans.py`: subprocess failures logged, unknown tmux activity is None, proxy log dir derived from the project root; normal outputs digest-compared.
**Reads:** temp directories; fake subprocess results.
**Writes:** stdout PASS/FAIL and `DIFF` digest lines.
**Called by:** `p5_run_all.py`.
**Calls out:** `src.menubar.{proc_cache,ghostty,bg_timer,bg_task_orphans,discover}`.

---

### p5_g7_model.py (69 LOC)

**Purpose:** Strand for `ModelController`: every cycle handler dispatches and refreshes as before, failures and the Apply flash defect land in `menubar.log`.
**Reads:** nothing external (fake pending selection and buttons).
**Writes:** stdout PASS/FAIL lines.
**Called by:** `p5_run_all.py`.
**Calls out:** `src.menubar.model_controller`.

---

### p5_g8_system.py (109 LOC)

**Purpose:** Strand for `system.py` and `skill_discovery.py`: singleton lock, python3 resolution raising and logging, viewer tty, skill fallback routes.
**Reads:** temp directories.
**Writes:** stdout PASS/FAIL and `DIFF` digest lines.
**Called by:** `p5_run_all.py`.
**Calls out:** `src.menubar.{system,skill_discovery}`.

---

### p5_run_all.py (37 LOC)

**Purpose:** Runs all `p5_g*` strands in parallel subprocesses; every strand stops at its first failing check, siblings finish, the parent reports which strand aborted.
**Reads:** nothing.
**Writes:** stdout summary line per strand.
**Called by:** none — run manually.
**Calls out:** `subprocess`, `concurrent.futures`.

---

## State
None of the byte-identity modules owns any persistent state — each constructs a fresh throwaway
`ModelController`/`PanelManager`/fake-`discover` scenario inside its own process, hashes the
result, and exits; `model_controller_byte_identity.py`'s persistence check is the only one that
writes files, and only inside a `tempfile.TemporaryDirectory()` it owns and discards on exit.

The `p5_*` strands own no state either: each creates a temp directory, points `menubar_log.MENUBAR_LOG` and the module under test at it, and never touches the real app-support directory.
