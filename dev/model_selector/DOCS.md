# dev/model_selector/

## Role
Verification scripts for the menubar's Models tab (`src/menubar/`) and the launcher/worker-spawn/
hook changes that make its config file actually take effect at proxy startup. Touch when changing
`model_selection.py`, `panel_lifecycle.py`'s ring, or the launcher's precedence chain.

## Public Interface
No `__init__.py` in this directory. Each script is its own entry point, run directly, e.g.
`python3 dev/model_selector/verify_hook_writer_split.py` or `bash verify_launcher_model_precedence.sh`.

## Flow
Synthetic payloads, tempdir paths, or in-memory fixtures go in. Each script drives real
production code (`hook_writer.py`, `model_selection.py`, `panel_lifecycle.py`'s ring, or the
launcher's parse loop mirrored in bash) and asserts specific invariants. Output is stdout plus a
report under `md/`.

## Modules

### verify_hook_writer_split.py (71 LOC)

**Purpose:** Regression guard for `hook_writer.py`'s hook-state half — feeds synthetic
`UserPromptSubmit`/`Stop` payloads through the real workflow, asserting status transitions and
no queue-file side effect.
**Reads:** nothing persistent — builds its own tempdir.
**Writes:** `md/verify_hook_writer_split.md`.
**Called by:** none — run manually; re-run after any `hook_writer.py` change.
**Calls out:** `src/menubar/hook_writer.py`, loaded via `importlib.util.spec_from_file_location`.

---

### verify_model_cycle_and_io.py (278 LOC)

**Purpose:** Regression guard for `model_selection.py`'s cycle logic (model/effort/max_tokens/
thinking) and its `model_selection.json`/`proxy_rules.json` read-modify-write I/O.
**Reads:** nothing persistent — every case uses a tempdir path or an in-memory fixture string.
**Writes:** `md/verify_model_cycle_and_io.md`.
**Called by:** none — run manually; re-run after any `model_selection.py` I/O change.
**Calls out:** `src.menubar.model_selection`, loaded via `importlib.import_module`.

---

### verify_four_tab_ring.py (128 LOC)

**Purpose:** Regression guard for the four-tab Cmd+→/← ring (Sessions/RAG/Models/Launch) — drives the
real, unmocked ring functions against a `_FakeApp` wrapping real panel controllers.
**Reads:** nothing persistent (HOME is redirected to a temp dir via `dev/session_launcher/test_env.py`).
**Writes:** `md/verify_four_tab_ring.md`.
**Called by:** none — run manually; MUTATES the desktop (real NSPanel objects underneath); do
not run. Re-run after any ring-wiring change in `panel_lifecycle.py`.
**Calls out:** `src/menubar/panel_manager.py`, `rag_controller.py`, `model_controller.py`,
`launch_controller.py`, `panel_lifecycle.py`, `Foundation`, `dev/session_launcher/test_env.py`.

---

### verify_launcher_model_precedence.sh (186 LOC)

**Purpose:** Full precedence-chain dry run for the launcher's model selection — explicit
`--model` > config-file `main` key > nothing injected (no CLI shortcuts since 2026-09-23).
**Reads:** nothing persistent outside its own tempdir.
**Writes:** `md/verify_launcher_model_precedence_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to the launcher's precedence logic.
**Calls out:** `jq`, `src/claude_proxy_start.sh`'s parse loop (mirrored, not sourced).

---

### verify_hook17_removal.py (86 LOC)

**Purpose:** Confirms a retired hook's removal — the file is gone, no longer registered, and
`_sweep_stale_hooks()` removes a dead-path entry while leaving a live one untouched.
**Reads:** nothing persistent — synthetic dict built in-process.
**Writes:** `md/verify_hook17_removal.md`.
**Called by:** none — run manually; re-run if `_sweep_stale_hooks()` itself changes.
**Calls out:** `src/hooks/hook_setup.py`.

---

## State
No persistent state lives in this directory. Every script builds its own tempdir/in-memory
fixture and discards it at exit; none touch the real `~/.claude/shared-rules/model_selection.json`
or `~/.claude/settings.json` — the real regeneration mechanism for the latter is
`.githooks/post-merge`, not a script here.
