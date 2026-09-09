# src/menubar/model_controller.py concern split — menubar milestone A (2026-09)

## Task

`model_controller.py` was 454 LOC (over the 400 ceiling), `ModelController` carried 18
`self.<attr>` (threshold: 10), and the file mixed 2 constant clusters (`_DEFAULT_*`, `_APPLY_*`)
in one file (threshold: 2+ clusters/file triggers a split). First of a menubar refactor series
(milestone A), mirroring the concern-split pattern already applied to `src/proxy/`, `src/panes/`,
`src/gpu_pane/`, `src/news_pane/` earlier in this same worker session.

## Investigation before implementing

Read `model_controller.py`, `app.py`, `panel.py`, `paths.py`, `src/menubar/DOCS.md`,
`setup_py2app.py`, and both `dev/model_selector/` scripts in full. AST-confirmed the 18-attribute
count and that no function in the file exceeded 43 LOC (so no per-function 50-LOC violation, only
the file-LOC and attribute-count and constant-cluster thresholds applied).

**`setup_py2app.py` check (explicitly required by the brief):** `'packages': ['src.menubar',
'rumps']` force-includes the whole `src.menubar` subpackage wholesale — no individual module names
listed anywhere in `OPTIONS`. New sibling modules under `src/menubar/` are automatically bundled;
confirmed no edit needed.

**Grep-confirmed the exact importer set** before touching anything: `panel_lifecycle.py` (`from
.model_controller import _reposition_models_panel`), `app.py` (`from .model_controller import
ModelController`), and the two `dev/model_selector/` scripts. Grepped the 7 button-ref attribute
names and the 6 `_pending_*` field names across `src/` and `dev/` — zero external references to
any of them, confirming they were free to restructure into collaborator objects without any
re-pointing burden on the attribute-rename side.

## The re-export-shim tension, resolved by re-pointing a test instead

`dev/model_selector/verify_model_cycle_and_io.py` accesses 13 names via `mc = importlib.import_module
('src.menubar.model_controller')`: `_MODEL_CHOICES`, `_next_model`, `_EFFORT_CHOICES`,
`_next_effort`, `_MAXTOK_CHOICES`, `_next_max_tokens`, `_write_model_selection`,
`_load_model_selection`, `_DEFAULT_MAIN`, `_DEFAULT_WORKER`, `_dumps_proxy_rules`,
`_write_proxy_rules_model_params`, `_DEFAULT_THINKING`. Under the planned split, EVERY one of
these becomes a `model_selection.py` symbol that `model_controller.py` itself no longer calls
directly (all cycling/load/write logic moves into a `_PendingSelection` collaborator living in
`model_selection.py`). Re-importing all 13 into `model_controller.py` purely so this test kept
resolving them via `mc.X` would have been a textbook re-export shim — explicitly disallowed.
**Resolution:** re-pointed the test's own loader (`_load_model_controller()` →
`_load_model_selection_module()`, module target `model_controller` → `model_selection`) and
renamed the loaded-module variable `mc`→`ms` throughout (43 occurrences, done via a single
word-boundary-safe regex substitution, then hand-fixed the loader function itself and its
docstring). This is exactly the same resolution class as the panes-split milestone's
`build_cache_turns`/`cache_turns.py` re-point and the gpu-pane-split milestone's `p8`
`inspect.getsource` re-point — when a test's only reason to reach a symbol through the OLD module
is compatibility, the correct fix is re-pointing the test, not re-exporting the symbol.
`verify_three_tab_ring.py` needed no changes — it only touches `ModelController`, `_models_panel`,
`_models_open`, none of which moved.

## Class-attribute split: which collaborator got which concern, and why

The brief's own finding named two class-split concerns: "the pending selection (a plain state
object: load-from-disk, cycle, write)" and "the row-button set (UI refs + title refresh)". Both
ended up living in DIFFERENT modules, for a reason not obvious from the finding's own wording:

- `_PendingSelection` (6 attrs) went into `model_selection.py` (the persistence module) rather
  than staying in `model_controller.py`, because it is genuinely pure — none of its methods touch
  AppKit, they only call the persistence module's own load/cycle/write functions. Since
  `model_selection.py`'s own constraint is "must not import AppKit," and `_PendingSelection`
  satisfies that trivially, keeping it there keeps ALL model-selection state+logic together in one
  AppKit-free module, and leaves `model_controller.py` as pure orchestration.
- `_ModelRowButtons` (7 attrs, the 7 NSButton refs) stayed in `model_controller.py` rather than
  moving to `model_panel_ui.py` (the NSPanel-construction module), because it holds RUNTIME state
  recreated every `rebuild()` call (not one-time construction like the panel/button FACTORY
  functions in `model_panel_ui.py`), and its `refresh_titles` method needs `NSAttributedString`/
  `NSColor` — AppKit calls that belong with the controller's own rebuild/refresh lifecycle, not
  with one-time factories.

This split point — "does this collaborator's own behavior need AppKit" and "is it one-time
construction or per-rebuild runtime state" — is the generalizable lesson for future menubar-split
milestones (B, C, ...): the module-level 3-way split (persistence / UI-construction / controller)
doesn't map 1:1 onto the class-level 2-way attribute split; each class-split collaborator lands in
whichever module matches ITS OWN AppKit-dependency and construction-vs-runtime-state shape, not
automatically the module named after its "concern label" in the milestone brief.

## Byte-identity harness build notes

`dev/menubar/model_controller_byte_identity.py` (new `dev/menubar/` area, mirroring
`dev/panes/`/`dev/gpu_pane/` from earlier milestones) has two independent hash sections. The
persistence section needed no monkeypatching at all — every load/write function already accepts a
`path=` override, so redirecting to temp copies was a plain argument, not a patch. The UI section
deliberately excludes `handle_apply` (the only handler that writes to the REAL
`MODEL_SELECTION_FILE`/`PROXY_RULES_FILE`, with no override mechanism in that code path) — `open()`
and the 6 `handle_cycle_*` calls are read-only with respect to those files, so the harness never
writes outside its own tempdir. Both hash sections ran successfully against real AppKit view
creation in this environment — the "if AppKit refuses headless view creation" fallback specified
in the brief was built but never exercised.

One accepted, documented determinism caveat: the UI section's `open()` call reads the REAL
`~/.claude/shared-rules/{model_selection,proxy_rules}.json` (no override exists for that specific
production code path) — the before/after hash comparison is only reliable if those files don't
change between the two runs. Not an issue in this session (single worker, no concurrent live
menubar Apply clicks), but worth knowing for anyone re-running this harness later.

## Verification

`model_controller.py`: 454 → 242 LOC, `ModelController` 18 → 7 attrs. `model_selection.py`: new,
194 LOC, 1 constant cluster (`_DEFAULT_*`), no AppKit import (verified by grep — zero `AppKit`/
`Foundation` references). `model_panel_ui.py`: new, 86 LOC, 1 constant cluster (`_APPLY_*`). No
function in any of the 3 files reached 30 LOC after the split (AST-confirmed), let alone 50.
`PERSISTENCE_HASH`/`UI_HASH` both identical before and after. All 4 required probes passed
unchanged; tracked report files under `dev/model_selector/md/` restored via `git checkout` after
each local run, before every commit.
