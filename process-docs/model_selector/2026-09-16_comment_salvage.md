# process-docs/model_selector/2026-09-16_comment_salvage.md

Session: dev/model_selector/ module-standards conformance (comment/docstring removal + DOCS.md rewrite).
Date: 2026-09-16.

## Purpose of this file

Every comment and docstring deleted from `dev/model_selector/*.py` during this milestone, copied
verbatim before deletion, plus the full pre-rewrite content of `dev/model_selector/DOCS.md`.
Nothing judged and dropped — see the milestone rules in the calling agent's prompt (module-standards
conformance: relocate then delete, decide nothing).

File count (4) and comment/docstring totals (75 comments, 0 docstrings) matched the prompt's
stated measured state exactly — no discrepancy this session.

Grep for `__doc__`/`argparse`/`description=`/`epilog=`/`.help(` across `dev/model_selector/*.py`
before deletion: zero matches, and 0 docstrings existed to begin with.

## Execution-safety note for this session

`verify_three_tab_ring.py` constructs real `PanelManager`/`RagController`/`ModelController`
instances backed by real NSPanel objects (its own comment says so outright: "real NSPanel objects
underneath") — main's explicit classification, confirmed by reading the file. It was never
executed. Behavior-preservation was proven instead by mechanically stripping comments/docstrings
from a copy of the pre-edit source and diffing that stripped copy byte-for-byte against the
actual post-edit file.

`verify_hook_writer_split.py`, `verify_hook17_removal.py`, and `verify_model_cycle_and_io.py` each
write to a FIXED-name tracked report (`md/verify_hook_writer_split.md`,
`md/verify_hook17_removal.md`, `md/verify_model_cycle_and_io.md` — no timestamp in the filename,
unlike every other dev/ area touched so far this cycle). Each was snapshotted before any run,
executed before and after the edit for comparison, then the tracked report was restored from the
snapshot before commit regardless of content match, so no tracked artifact carries this session's
run-to-run noise (e.g. wall-clock timestamps embedded in the report body).

Comment/docstring counts confirmed via AST + tokenize before deletion: 75 comments, 0 docstrings,
matching the task's stated measured state exactly.

## Salvage from dev/model_selector/DOCS.md

Full content of dev/model_selector/DOCS.md as it stood before this rewrite (104 lines),
preserved verbatim since the whole file is being replaced with the mandated leaner format
(Role capped at 50 words, Purpose capped at 25 words per module, no Gotchas section in the
new format, Public Interface / Flow / State sections added).

```markdown
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

### verify_model_cycle_and_io.py (317 LOC)

**Purpose:** Regression guard for `src/menubar/model_selection.py`'s pure cycle logic
(`_next_model`/`_next_effort`/`_next_max_tokens`, each stepping and wrapping through their known
value sets, and confirming an unrecognized current value starts the cycle at the first choice; plus
`_next_thinking`/`_thinking_is_enabled`, toggling exactly between the on `{"type": "adaptive",
"display": "summarized"}` and off `{"type": "disabled"}` states), `model_selection.json` I/O
(atomic write, exact 2-key schema, an unrecognized-but-valid on-disk value preserved verbatim
rather than replaced), and `proxy_rules.json` read-modify-write (the custom serializer's
indent-2-except-`model_params` format fidelity, `_write_proxy_rules_model_params` against an
existing target model with its thinking state flipped off, a missing target model created with
thinking left on, and graceful degradation on a malformed file).
**Reads:** nothing persistent — every case uses a tempdir path or an in-memory fixture string,
never the real `~/.claude/shared-rules/model_selection.json` or `proxy_rules.json`.
**Writes:** `md/verify_model_cycle_and_io.md`.
**Called by:** none — run manually; re-run after any `model_selection.py` I/O change.
**Calls out:** `src/menubar/model_selection.py`, loaded via
`importlib.import_module('src.menubar.model_selection')` (package-relative imports require real
package context).

---

### verify_three_tab_ring.py (149 LOC)

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

### verify_hook17_removal.py (91 LOC)

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
```

## Salvage from dev/proxy/verify_hook_writer_split.py

COMMENT L17:
```
# Feed synthetic UserPromptSubmit + Stop payloads through hook_writer_workflow against a
```

COMMENT L18:
```
# tempdir-isolated _APP_SUPPORT; assert hooks.json state transitions and absence of any
```

COMMENT L19:
```
# queue-file side effect (msg_queue.json / queue.lock never created).
```

COMMENT L53:
```
# Import hook_writer.py fresh with _APP_SUPPORT + derived file paths redirected to tmp_dir
```

COMMENT L65:
```
# Run one payload through hook_writer_workflow with stdin swapped for the JSON payload
```

## Salvage from dev/proxy/verify_hook17_removal.py

COMMENT L15:
```
# Verify Hook 17 (block_worker_spawn_opus.py) retirement: the file is gone, hook_setup.py no
```

COMMENT L16:
```
# longer lists it, and the real _sweep_stale_hooks() pure function removes a dead-path entry —
```

COMMENT L17:
```
# the actual mechanism that heals ~/.claude/settings.json, exercised here on a synthetic
```

COMMENT L18:
```
# in-memory dict, never the real file (hook_setup.py refuses to even run from a worktree —
```

COMMENT L19:
```
# _guard_not_worktree() — so it can't be invoked directly from here anyway).
```

COMMENT L55:
```
# deliberately does not exist
```

COMMENT L56:
```
# a real, existing file
```

## Salvage from dev/proxy/verify_model_cycle_and_io.py

COMMENT L14:
```
# A minimal fixture mirroring proxy_rules.json's real on-disk convention, confirmed by a manual
```

COMMENT L15:
```
# byte-diff against the live file at implementation time: every section is byte-identical to
```

COMMENT L16:
```
# plain json.dumps(indent=2), EXCEPT model_params, whose per-model entries render as one compact
```

COMMENT L17:
```
# single-line JSON object each. Used both to pin that convention as a regression check and as the
```

COMMENT L18:
```
# base fixture for the read-modify-write tests below.
```

COMMENT L46:
```
# Verify cycle-order correctness for all 3 cycle kinds (model/effort/max_tokens), atomic-write +
```

COMMENT L47:
```
# read-back/fallback correctness for model_selection.json, and the proxy_rules.json read-modify-
```

COMMENT L48:
```
# write (format fidelity, foreign-content preservation, missing-entry creation, malformed-file
```

COMMENT L49:
```
# fallback) — all against temp paths, never the real ~/.claude/shared-rules/.
```

COMMENT L83:
```
# Load the real src.menubar.model_selection module via importlib (dev/ probes must not
```

COMMENT L84:
```
# write a literal 'from src.' / 'import src.' statement; a dynamic import_module call is not
```

COMMENT L85:
```
# that statement and is needed here anyway — model_selection.py has a package-relative import
```

COMMENT L86:
```
# that only resolves when loaded as part of the src.menubar package). (2026-09, menubar
```

COMMENT L87:
```
# milestone A: every symbol this script touches — the cycle constants/functions and the
```

COMMENT L88:
```
# model_selection.json/proxy_rules.json load/write functions — moved out of model_controller.py
```

COMMENT L89:
```
# into this pure persistence module; re-pointed here rather than re-exported from
```

COMMENT L90:
```
# model_controller.py, which no longer calls any of them directly.)
```

COMMENT L95:
```
# Section 1: the 4-value model cycle (all 4 values step correctly, wraps, unrecognized -> first)
```

COMMENT L112:
```
# Section 2: the effort cycle (low -> medium -> high -> wraps; 'max' deliberately absent)
```

COMMENT L131:
```
# Section 3: the max_tokens cycle (32000 -> 64000 -> 128000 -> wraps)
```

COMMENT L149:
```
# Section 4: the thinking toggle — exactly 2 states (on: adaptive/summarized, off: disabled),
```

COMMENT L150:
```
# added so the Models pane can turn thinking off entirely, separately for Main and Worker.
```

COMMENT L167:
```
# Section 5: model_selection.json atomic write — unchanged behavior for existing callers
```

COMMENT L181:
```
# Section 6: model_selection.json read-back + fallback — unchanged behavior for existing callers
```

COMMENT L201:
```
# Correction from review (milestone 2): an unrecognized-but-valid on-disk value must be
```

COMMENT L202:
```
# preserved verbatim on display, NOT silently replaced by the default.
```

COMMENT L216:
```
# Section 7: the custom proxy_rules.json serializer reproduces the real file's own convention
```

COMMENT L217:
```
# byte-for-byte on an unmodified round-trip — the mechanism the read-modify-write below relies on.
```

COMMENT L227:
```
# Section 8: Apply's read-modify-write — foreign sections/keys/models byte-preserved, missing
```

COMMENT L228:
```
# per-model entry created with the established thinking-block shape, touched entries updated
```

COMMENT L229:
```
# (including the thinking toggle: main is switched off, worker's fresh entry stays on).
```

COMMENT L245:
```
# main = claude-opus-5 (existing entry, gets new effort/max_tokens, thinking switched off)
```

COMMENT L246:
```
# worker = claude-sonnet-5 (NOT in the fixture — must be created, thinking stays on)
```

COMMENT L269:
```
# Foreign top-level section untouched
```

COMMENT L273:
```
# Untouched model entry (claude-fable-5) and its thinking block untouched
```

COMMENT L278:
```
# Third, also-untouched model entry, proving the preservation isn't just "the other of two"
```

COMMENT L284:
```
# Touched entry (main): effort/max_tokens updated AND thinking switched to disabled
```

COMMENT L289:
```
# Missing entry (worker) created with the established thinking-block shape, thinking on
```

COMMENT L295:
```
# Section 9: a malformed proxy_rules.json degrades to a fresh minimal file, never raises
```

COMMENT L307:
```
# must parse — no raise from the write
```

## Salvage from dev/proxy/verify_three_tab_ring.py

COMMENT L18:
```
# Drive the REAL panel_lifecycle.py ring functions (_open_*_panel/_close_*_panel/
```

COMMENT L19:
```
# _deferred_close_open) against a lightweight FakeApp — no mocking of ring logic itself, only
```

COMMENT L20:
```
# of the NSOperationQueue async-dispatch wrapper (so the captured hotkey callbacks can be
```

COMMENT L21:
```
# executed synchronously without a real AppKit run loop) and of app.hotkey/app.sessions (which
```

COMMENT L22:
```
# have no bearing on ring correctness). Verifies both cycle directions land correctly.
```

COMMENT L33:
```
# NSOperationQueue.mainQueue() normally schedules async on the real run loop, which never
```

COMMENT L34:
```
# spins in this headless probe. Patch only the dispatch wrapper to run synchronously —
```

COMMENT L35:
```
# everything downstream of it (the ring logic itself) is the real, unmocked code.
```

COMMENT L56:
```
# main -> rag
```

COMMENT L60:
```
# rag -> models
```

COMMENT L64:
```
# models -> main
```

COMMENT L72:
```
# main -> models
```

COMMENT L76:
```
# models -> rag
```

COMMENT L80:
```
# rag -> main
```

COMMENT L84:
```
# Dynamic import_module call (not a literal 'from src.'/'import src.' statement) — needed
```

COMMENT L85:
```
# because these modules have package-relative imports that only resolve inside src.menubar.
```

COMMENT L89:
```
# Records the two most-recently-registered arrow callbacks; .right()/.left() invoke them,
```

COMMENT L90:
```
# exercising the real registered closure (including its NSOperationQueue dispatch, patched
```

COMMENT L91:
```
# synchronous for this test) rather than calling _deferred_close_open directly.
```

COMMENT L124:
```
# Synchronous stand-in for Foundation.NSOperationQueue — mainQueue().addOperationWithBlock_
```

COMMENT L125:
```
# just calls the block immediately instead of scheduling on the (nonexistent, in this probe) run loop.
```

COMMENT L134:
```
# Real PanelManager/RagController/ModelController instances (real NSPanel objects underneath)
```

COMMENT L135:
```
# driven by a minimal attribute-only app double — no rumps.App/run-loop needed for ring logic.
```

