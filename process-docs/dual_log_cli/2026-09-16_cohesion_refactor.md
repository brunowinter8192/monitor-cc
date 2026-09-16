# Cohesion refactor of dev/dual_log_cli/ (2026-09-16)

## Task

Split `tests/test_reqs.py` (552 LOC, no function at or above 50 lines) to satisfy the 400-LOC-file
threshold. No behaviour change allowed. Full task text lives in the issue that spawned this
session, not repeated here. `tests/` has no DOCS.md of its own by design (per the milestone's own
"Note on this area") — all documentation of the split lives in `dev/dual_log_cli/DOCS.md`.

## Hazard classification

`tests/test_reqs.py` (and every split sibling) is READ-ONLY: pure in-process fixtures plus one
temp `_forwarded.jsonl`-shaped file per case, written and deleted (`path.unlink()` in a `finally`)
within the same function call. No desktop/tmux/hotkey/Space interaction, no persistent writes.
Confirmed by reading the full file before editing. Safe to run.

## This split follows the DIRECTORY's own convention, not the pattern from the other 4 sessions

Every other cohesion-refactor session this batch (`cc_injection_inventory`, `tool_use_errors`,
`sleep_pattern_analysis`, `bg_wakeup_id_line`) split a CLI tool into an entry script that imports
and calls functions from new helper modules — helper modules were never meant to run standalone.

`dev/dual_log_cli/tests/` is a different genre entirely: 14 pre-existing sibling files, each an
INDEPENDENTLY RUNNABLE regression suite for one feature area, with its own `check()`/`PASS_LIST`/
`FAIL_LIST` harness and its own `if __name__ == "__main__":` block — confirmed by reading all 14 in
full before touching anything. None of them import each other. `check()`, `_delta_entry()`, and
`_boundaries()` are ALREADY duplicated verbatim across at least 4 pre-existing files
(`test_msgs_sys_delta.py`, `test_turns.py`, `test_sidecar_exclusion.py`, and now the new
`test_reqs_*.py` files) — grepped for this before deciding the split shape, to confirm duplication
across test files is the deliberate established norm here, not something to "fix" by factoring out
a shared module. The milestone's own negative scope agrees: "do not deduplicate across scripts."

**Consequence for the split:** `test_reqs.py`'s 552 lines split into 5 fully standalone sibling
files, each with ITS OWN complete copy of `check`/`_local_clock`/`_delta_entry`/`_boundaries`/
`_session`, not a "core + imported helpers" shape. This is MORE duplication than the other 4
sessions' splits produced, and that is correct here — matching the local convention is the
priority, not minimizing line count.

## Concern boundaries (mirrors comment dividers already present in the original file)

The original file already had `# ---` comment dividers marking exactly 5 concern groups before
this split touched anything — the split boundaries were not invented, they were already marked:

| New file | LOC | Tests (from the original `# ---` sections) |
|---|---|---|
| `test_reqs.py` (kept exact name) | 212 | the fixed CR/CC line form: 7 tests |
| `test_reqs_gap.py` | 153 | `--gap`: 4 tests |
| `test_reqs_merged.py` | 143 | `--merged`: 3 tests |
| `test_reqs_rebuild_drop.py` | 211 | `--rebuild`/`--drop`: 7 tests |
| `test_reqs_turn_and_family.py` | 153 | `--turn` + `filter_by_family`: 3 tests + 2 fixture helpers |

31 test-level checks total before and after — verified as an exact SET match (not just a count
match), see below. `test_plain_listing_shows_usage_without_rebuild_or_drop` went into the
rebuild/drop file (its ordinal position in the original file and its own framing — "Neither
--rebuild nor --drop set" — are about that flag pair's absence, not the baseline CR/CC form) rather
than the base `test_reqs.py` file; this is the one boundary call that wasn't 100% mechanical, flag
if a future agent disagrees with the grouping.

## Import style: kept the directory's `from src.` literal style unchanged

This directory's test files use `sys.path.insert(0, str(_HERE.parents[2]))` (worktree root) then
literal `from src.dual_log_cli.X import Y` — a literal `from src.` import line, which the
`block_dual_imports_src` hook is described elsewhere as blocking under `dev/`. Confirmed this
exact style is what EVERY one of the 14 pre-existing sibling files already does (grepped), so
either the hook doesn't fire on this directory/pattern or test files are exempted somehow — not
something this session needed to resolve, since "keep the import style that already runs in this
directory" is the explicit instruction regardless of the hook's general description. Did not
introduce the `sys.path.insert` + `import proxy.X` (no `from src.` literal) style used in
`dev/cc_injection_inventory/` and `dev/bg_wakeup_id_line/` this batch — that would have been
INCONSISTENT with this specific directory's own established pattern.

## Section-order tension: followed the milestone rule, diverging from all 14 untouched siblings

Read all 14 pre-existing test files' section markers before writing anything. Every single one
(`test_local_time.py` through `test_turns.py`, no exception) uses
`INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR` — the workflow-runner function sits at the very
bottom of the file, after every test function, immediately before `if __name__ == "__main__":`.
This is clearly a deliberate, uniform, directory-wide convention (14/14, not 1 outlier like the
`bg_wakeup_id_line` p1 case from an earlier session this batch, which really did look like a
one-off oversight).

The milestone instructions are explicit and unconditional: "Section order is INFRASTRUCTURE, then
ORCHESTRATOR, then FUNCTIONS, in every file you create or rewrite." Chose to comply with this
literal instruction for the 5 files actually created/rewritten this session
(`test_reqs.py` + 4 new siblings) rather than preserve directory-wide stylistic consistency by
keeping the old order. This means the 5 `test_reqs*.py` files now look structurally different
(ORCHESTRATOR before FUNCTIONS) from all 12 untouched siblings in the same directory (FUNCTIONS
before ORCHESTRATOR) — did NOT reorder the other 12 files to match, since that would be scope
creep untouched by this milestone's actual deliverable (negative scope: no changes beyond the
listed deliverables, and negative scope explicitly restricts touching only what needed the split).

**Flag for whoever runs the next split in this same tests/ directory:** you will hit this same
tension. The other 12 files are not yet "fixed" — if a future milestone touches one of them, the
same order-vs-local-convention conflict will resurface. No verification is affected either way
(Python resolves names at call time, not definition time, so physical function order is cosmetic).

## Behaviour-unchanged proof

Two layers, both passed:

1. **Full run, before and after, on the SAME hardcoded synthetic fixtures** (the test bodies were
   copied byte-for-byte, not regenerated — there is no "real corpus" for a unit-test file, so this
   IS the equivalent of a same-input diff). Backed up the pre-split file to
   `/tmp/dlc_verify/test_reqs_pre_split.py`. Ran it: `31/31 checks passed`, exit 0. Ran all 5
   post-split files: `9/9`, `6/6`, `3/3`, `8/8`, `5/5` — sums to 31/31, exit 0 on every file.
2. **Exact check-name SET comparison**, not just a count match (a count match alone wouldn't catch
   a check silently renamed+duplicated while another was dropped). Loaded the pre-split backup via
   `importlib.util.spec_from_file_location`, ran its `test_reqs_workflow()` inside a `try/except
   SystemExit` (needed because the workflow calls `sys.exit(1)` on failure — must not let that
   propagate and kill the verification harness on either side, though neither side fails here),
   collected `set(PASS_LIST) | set(FAIL_LIST)` — 31 unique check names. Did the same across all 5
   post-split modules, unioning their check-name sets. `pre_checks == post_checks` — `True`,
   confirmed by printed set difference being empty in both directions.

Verification artifacts (`/tmp/dlc_verify/`, `__pycache__/` under `dev/dual_log_cli/`) were deleted
or left outside the worktree, never staged.

## Files NOT touched

The other 13 files under `dev/dual_log_cli/tests/` and `probe_sys_tool_original_chars.py` were
read in full (per the task's file-reading requirement — checking for cross-imports of
`test_reqs.py`; none found) but already compliant (longest function anywhere in the directory
after this split: 37 lines, in `probe_sys_tool_original_chars.py`, pre-existing, untouched) and
were not modified.
