# dev/model_selector/

## Role

Verification scripts for the menubar's Models tab (`src/menubar/`) and the launcher/worker-spawn/
hook changes that make its config file actually take effect at proxy startup. `md/` holds every
script's report.

## Modules

### verify_hook_writer_split.py (76 LOC)

**Purpose:** Regression guard for `src/menubar/hook_writer.py`'s hook-state half
(`_write_state`/`_load_state`) — feeds synthetic `UserPromptSubmit`/`Stop` payloads through the
real `hook_writer_workflow()` against a tempdir-isolated `_APP_SUPPORT`, asserting both status
transitions and the absence of any queue-file side effect.
**Reads:** nothing persistent — builds its own tempdir.
**Writes:** `md/verify_hook_writer_split.md`.
**Called by:** none — run manually; re-run after any `hook_writer.py` change.
**Calls out:** `src/menubar/hook_writer.py` (loaded via `importlib.util.spec_from_file_location`
— the module has zero relative imports).

---

### verify_model_cycle_and_io.py (287 LOC)

**Purpose:** Regression guard for `src/menubar/model_selection.py`'s pure cycle logic
(`_next_model`/`_next_effort`/`_next_max_tokens`, each stepping and wrapping through their known
value sets, and confirming an unrecognized current value starts the cycle at the first choice),
`model_selection.json` I/O (atomic write, exact 2-key schema, an unrecognized-but-valid on-disk
value preserved verbatim rather than replaced), and `proxy_rules.json` read-modify-write (the
custom serializer's indent-2-except-`model_params` format fidelity, `_write_proxy_rules_model_params`
against an existing and a missing target model, and graceful degradation on a malformed file).
**Reads:** nothing persistent — every case uses a tempdir path or an in-memory fixture string,
never the real `~/.claude/shared-rules/model_selection.json` or `proxy_rules.json`.
**Writes:** `md/verify_model_cycle_and_io.md`.
**Called by:** none — run manually; re-run after any `model_selection.py` I/O change.
**Calls out:** `src/menubar/model_selection.py`, loaded via
`importlib.import_module('src.menubar.model_selection')` (package-relative imports require real
package context).

---

### verify_three_tab_ring.py (143 LOC)

**Purpose:** Regression guard for the three-tab Cmd+→/← ring (Sessions/RAG/Models) — drives the
real, unmocked `_open_main_panel`/`_open_rag_panel`/`_open_models_panel`/`_close_*_panel`/
`_deferred_close_open` from `panel_lifecycle.py` against a lightweight `_FakeApp` wrapping real
`PanelManager`/`RagController`/`ModelController` instances and real NSPanel objects, verifying
both ring directions (main→rag→models→main and reverse). Only
`Foundation.NSOperationQueue`'s async-dispatch wrapper is patched to run synchronously.
**Reads:** nothing persistent.
**Writes:** `md/verify_three_tab_ring.md`.
**Called by:** none — run manually; re-run after any ring-wiring change in `panel_lifecycle.py`.
**Calls out:** `src/menubar/panel_manager.py`, `rag_controller.py`, `model_controller.py`,
`panel_lifecycle.py`, `Foundation`.

---

### verify_launcher_model_precedence.sh (200 LOC)

**Purpose:** Full precedence-chain dry run for `src/claude_proxy_start.sh`'s model selection —
explicit `--model` > `--fable`/`--opus` shortcut > `main` key from
`~/.claude/shared-rules/model_selection.json` > nothing injected — mirroring the real script's
parse loop (keep in sync when editing either). 12 cases: tier-1/2 sanity, 3 config-tier cases, 4
degradation cases (missing file, malformed JSON, missing key, empty key value), all against a
temp `MODEL_SELECTION_FILE` override. `dev/native-model-start/p1_arg_parse_dry_run.sh` covers
tiers 1-2 only, in isolation, and stays accurate for that narrower scope.
**Reads:** nothing persistent outside its own tempdir.
**Writes:** `md/verify_launcher_model_precedence_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to `claude_proxy_start.sh`'s
precedence logic.
**Calls out:** `jq`, `src/claude_proxy_start.sh`'s parse loop (mirrored, not sourced).

---

### verify_hook17_removal.py (82 LOC)

**Purpose:** Confirms `block_worker_spawn_opus.py`'s retirement — the file is gone,
`hook_setup.py:_HOOK_SCRIPTS` no longer lists it, and `_sweep_stale_hooks()` correctly removes a
dead-path entry from a synthetic in-memory settings dict while leaving a live entry untouched.
Never invokes `hook_setup_workflow()` itself (`_guard_not_worktree()` refuses to run from any
worktree) and never touches the real settings file.
**Reads:** nothing persistent — synthetic dict built in-process.
**Writes:** `md/verify_hook17_removal.md`.
**Called by:** none — run manually; re-run if `_sweep_stale_hooks()` itself changes.
**Calls out:** `src/hooks/hook_setup.py`.

---

## Gotchas

**None of these scripts touch the real `~/.claude/shared-rules/model_selection.json` or
`~/.claude/settings.json`.** Every script needing a config file uses a `tempfile`/`mktemp` path,
and `verify_hook17_removal.py` exercises `_sweep_stale_hooks()` on a synthetic dict instead of the
guarded `hook_setup_workflow()`.

**The real regeneration mechanism for `~/.claude/settings.json` after a `src/hooks/` change is
`.githooks/post-merge`**, not a script in this directory — it greps
`git diff --name-only ORIG_HEAD HEAD` for `^src/hooks/` and re-runs `hook_setup.py` on the next
real merge. See `process-docs/model_selector/` for the full trace.
