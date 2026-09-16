# Cohesion refactor of dev/cc_injection_inventory/ (2026-09-16)

## Task

Split `cc_injection_inventory.py` (758 LOC, functions `_build_report` 177 LOC, `_process_file`
84 LOC, `_classify_user_segment` 66 LOC) to satisfy the 400-LOC-file / 50-LOC-function thresholds.
No behaviour change allowed. Full task text lives in the issue that spawned this session, not
repeated here.

## Hazard classification (done before running anything)

`cc_injection_inventory.py` is READ-ONLY with respect to the machine: it opens dual-log JSONL
files under `src/logs/dual_log/` for reading and writes a markdown report under
`dev/cc_injection_inventory/md/`. It never touches tmux panes, macOS windows, Spaces, hotkeys, or
the monitor process. Confirmed by reading the full pre-split file before editing anything — no
`osascript`, no `tmux`, no window/pane APIs anywhere in it. Safe to run for verification.

## Module split (final)

| File | LOC | Concern |
|---|---|---|
| `cc_injection_inventory.py` | 117 | entry: CLI args, log-file glob resolution + self-scan exclusion, orchestrator |
| `cc_injection_extraction.py` | 125 | walks one JSONL file's raw entries, extracts segments (system/message/tool_result) |
| `cc_injection_aggregation.py` | 92 | dedup-by-exact-text, registry/pending bookkeeping, two-phase user-text template resolution |
| `cc_injection_classification.py` | 250 | runs the real `src/proxy` strip pipeline against a synthetic message per segment, returns origin labels |
| `cc_injection_report.py` | 271 | builds the markdown report section by section, writes it, prints console summary |

Dependency direction is linear, no cycles: `inventory -> extraction -> aggregation ->
classification`, and `inventory -> report` (report has no dependents inside the split, it's a
pure leaf). This mirrors the natural pipeline order (extract raw segment -> dedup/aggregate ->
classify -> report), so the module boundary equals the pipeline stage boundary.

## Import mechanics — read this before touching this directory again

Two DIFFERENT import styles coexist and neither is wrong, they solve different problems:

1. **Sibling dev-file imports** (`cc_injection_inventory.py` importing `cc_injection_extraction`,
   etc.) use plain `from cc_injection_extraction import _process_file` — NO package prefix, no
   `sys.path` manipulation. This works because Python auto-prepends the executed script's own
   directory to `sys.path[0]`. Precedent: `dev/proxy_dual_log/attribution_coverage.py` +
   `attribution_coverage_{analyse,classify,report}.py` do the exact same thing. Do NOT add
   `sys.path.insert` for these — it's not needed and would be dead code.

2. **`src/proxy.*` imports** (only needed in `cc_injection_classification.py`, since that's the
   only module that calls `rules.apply_modification_rules`) keep the pre-existing style: compute
   `_WORKTREE_ROOT`, `sys.path.insert(0, str(_WORKTREE_ROOT / "src"))`, then
   `import proxy.rules as rules` (package-style, not `importlib.util.spec_from_file_location`).
   This avoids the `block_dev_imports_src` hook, which blocks literal `from src.`/`import src.`
   lines — `import proxy.rules` after inserting `src/` onto the path sidesteps it. Note
   `dev/proxy_dual_log/attribution_coverage.py` uses a THIRD style
   (`importlib.util.spec_from_file_location`) for the same problem — that's a different
   precedent from a different tool, don't mix it in here. Follow whatever style already runs in
   the specific directory you're editing.

Consequence: `cc_injection_classification.py` re-runs its own `_SCRIPT_DIR` /
`_WORKTREE_ROOT` / `sys.path.insert` block rather than importing that setup from the entry
script. This looks like duplication but isn't optional — a module needs to be independently
importable (e.g. for a future test file, or for the `importlib.util.spec_from_file_location`
verification pattern used below) without relying on import order set up by whichever script
happens to run first.

## `_build_methodology_section` — the split that isn't obvious from the hit list

The original hit list only flagged 3 functions (`_build_report` 177, `_process_file` 84,
`_classify_user_segment` 66). Splitting `_build_report` into 6 section-builder functions looked
sufficient on paper, but one of those extracted functions —
`_build_methodology_section` — came out at 80 LOC on its own, because it's one giant static
markdown text block with no internal branching. **A function being pure literal data with zero
logic does not exempt it from the LOC threshold.** Caught this by running an AST-based
longest-function scan (`ast.walk` for `FunctionDef`/`AsyncFunctionDef`, `end_lineno - lineno + 1`)
across every file in the directory AFTER the first pass — do this, don't eyeball line counts.
Fixed by splitting it further into `_build_methodology_dedup_and_scope` (16 lines),
`_build_methodology_origin_rules` (44 lines), `_build_methodology_grouping_and_scan` (16 lines),
concatenated by the parent. Final longest function in the whole directory: 44 LOC.

**Lesson for next split job:** run the AST longest-function scan as your OWN verification step,
don't trust that splitting the functions named in the hit list is sufficient — a split can create
a new violation that wasn't in the original file at all (because the original function was even
longer and hid this sub-block's length).

## Behaviour-unchanged proof

Two layers, both passed:

1. **Full-script diff on real input.** Backed up the pre-split file to
   `/tmp/cc_inj_verify/cc_injection_inventory_pre_split.py` before any edit. Ran the pre-split
   script and the fully-split script with identical args
   (`--logs-glob <main-repo>/src/logs/dual_log/api_requests_worker_52fce57c_wsrefactor_1789506614_original.jsonl
   --max-entries 3000`) against a real, non-growing dual-log file (15MB, not this session's own
   live-growing log). Output reports were byte-identical (`md5` match, `diff` exit 0), console
   summary lines identical. Re-ran this same check again after the follow-up
   `_build_methodology_section` split — still byte-identical.
   - Picked a small STATIC file deliberately: the default glob would also match this session's
     own live-growing worker log (`api_requests_worker_*_alpha_*`), which is excluded by the
     self-scan logic but would make repeat runs non-reproducible if targeted directly. An
     explicit `--logs-glob` bypasses exclusion anyway, so point it at a finished task's file.
2. **Synthetic per-function check for the largest single split** (`_build_report`, 177 -> 6
   functions). Loaded the pre-split backup via
   `importlib.util.spec_from_file_location("cc_pre_split", pre_path)` +
   `module_from_spec` + `spec.loader.exec_module`, built a small synthetic `registry` covering
   all 5 origins (COVERED/UNCLASSIFIED/OURS/KEEP/INJECTED) plus `file_stats`/`counters`/
   `excluded_files`, called `pre._build_report(...)` and the new `cc_injection_report._build_report(...)`
   with the identical args, asserted string equality. Passed (`len=8262`, exact match). This is
   the pattern to reuse for any future split of this directory: real-input diff first (cheap,
   comprehensive), synthetic per-function check second (targeted, catches anything the sampled
   real-input rows didn't happen to exercise).

Verification artifacts (`md/verify_pre.md`, `md/verify_post*.md`, `/tmp/cc_inj_verify/`) were all
deleted or left outside the worktree before commit — none are staged.

## Files NOT touched

`dev/cc_injection_inventory/md/*.md` (existing reports) were left untouched. No other file in
`dev/cc_injection_inventory/` existed before this session besides the one 758-LOC script and
`DOCS.md`.
