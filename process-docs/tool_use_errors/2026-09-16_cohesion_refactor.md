# Cohesion refactor of dev/tool_use_errors/ (2026-09-16)

## Task

Split `A_error_cluster_audit.py` (365 LOC, `format_report` 184 LOC, `run_cross_check` 51 LOC) to
satisfy the 400-LOC-file / 50-LOC-function thresholds. No behaviour change allowed. Full task
text lives in the issue that spawned this session, not repeated here.

## Hazard classification (done before running anything)

`A_error_cluster_audit.py` is READ-ONLY: it opens `src/logs/tool_errors.jsonl` and
`src/logs/api_requests_*.jsonl` for reading and writes one markdown report under
`dev/tool_use_errors/reports/`. Confirmed by reading the full file before editing — no
`osascript`, no `tmux`, no window/pane/hotkey/Space APIs, no monitor restart. Safe to run.

## DOCS.md output-path drift (pre-existing, fixed this session)

The pre-existing `DOCS.md` claimed the report is written to `md/<date>_error_cluster_audit.md`.
It isn't — the code writes to `REPORTS_DIR = SCRIPT_DIR/"reports"`. Confirmed empirically: ran
the untouched pre-split script, it wrote
`dev/tool_use_errors/reports/2026-09-16_error_cluster_audit.md`. The `md/` directory in this
folder holds unrelated older manual reports (`2026-05-22_opus.md`,
`2026-05-30_error_cluster_audit.md`) that predate whatever renamed the output dir. Per explicit
user instruction this session, the DOCS.md text was corrected to say `reports/` — the CODE path
was left untouched (negative scope: "do not change output paths"). If a future session finds the
`reports/` dir itself doesn't exist yet in a fresh checkout: it's created on demand by
`write_report`'s `os.makedirs(..., exist_ok=True)`, this is not a bug.

## Module split (final)

| File | LOC | Concern |
|---|---|---|
| `A_error_cluster_audit.py` | 50 | entry: path resolution (worktree-aware `.git` traversal), orchestrator |
| `error_cluster_extraction.py` | 41 | load `tool_errors.jsonl`, cluster entries by error-shape regex |
| `error_cluster_crosscheck.py` | 73 | scan proxy logs for the `stripped_hook_error_prefix` modification, compare timestamps against the hook-prefixed bucket |
| `error_cluster_report.py` | 245 | classify bucket verdicts, build the markdown report section by section, write it |

Dependency direction: `A_error_cluster_audit -> {error_cluster_extraction, error_cluster_crosscheck,
error_cluster_report}` (fan-out from the orchestrator), and `error_cluster_report ->
error_cluster_extraction` (imports `_EXIT_CODE_RE` for the exit-code distribution table — the
same regex used to bucket in the first place, reused for the corresponding report subsection).
No cycles.

## Two extraction functions needed a signature change to avoid a cycle

`run_cross_check` and `write_report` were already fully parameterized in the original
monolith (`logs_dir`, `reports_dir`, `date` passed as arguments, not read from module globals) —
this made the split trivial for those two: no path-recomputation duplication needed in the new
modules at all.

`format_report` was the one exception: it read `REPORT_DATE` as a **module-level global** from
the entry script instead of taking it as a parameter. Since the entry script imports
`format_report` FROM the new report module, importing `REPORT_DATE` the other way round
(report module importing back from the entry script) would be circular. Fixed by adding
`report_date` as an explicit 4th parameter: `format_report(entries, buckets, cc, report_date)`.
This is an internal function signature change, not a CLI/output-path change, so it's within
scope — the two are easy to conflate, worth being explicit about the distinction in the recap.

**Lesson for next split job in a similar file:** before splitting, check whether every function
you're about to move reads a global from the file it's leaving. A function that takes everything
via parameters splits for free; one that reads a global needs either the global promoted to a
parameter (preferred, done here) or the constant duplicated into the new module (only viable if
the constant is cheap to recompute independently, e.g. path resolution in the
`cc_injection_inventory` split from the previous session — see that area's process-docs).

## Behaviour-unchanged proof

Two layers, both passed:

1. **Full-script run + diff on real input.** Backed up the pre-split file to
   `/tmp/tue_verify/A_error_cluster_audit_pre_split.py` before any edit. Ran the untouched script
   for real against the actual `src/logs/tool_errors.jsonl` (274 entries) — the default
   `src/logs/api_requests_*.jsonl` glob matched zero files in this environment (all proxy logs
   in this repo live under `src/logs/dual_log/`, not directly under `src/logs/`), so the
   cross-check path deterministically takes its "inconclusive" branch either way; this doesn't
   weaken the proof since both pre- and post-split runs hit the exact same zero-file case.
   Captured output to `/tmp/tue_verify/pre_report.md` (md5 `3121118c47901380a2943dca0e659d3c`,
   138 lines), deleted the generated `dev/tool_use_errors/reports/` dir from the worktree. Ran
   the fully-split script with no argument changes — byte-identical report (`diff` exit 0, same
   md5), identical stdout (the printed report path).
2. **Synthetic per-function check for the largest split** (`format_report`, 184 -> 7 functions,
   plus the added `report_date` parameter). Loaded the pre-split backup via
   `importlib.util.spec_from_file_location` — this REQUIRES the backup file to physically sit
   inside the worktree's `dev/tool_use_errors/` directory during the check, not in `/tmp/`: the
   original module runs `_resolve_main_project()` at IMPORT TIME (module-level code, not inside
   a function), which walks up from the file's own directory looking for a `.git` — pointed at
   `/tmp/`, this raises `RuntimeError: Cannot find main project root` before you even get to call
   anything. Copied the backup to `dev/tool_use_errors/_pre_split_backup.py` (untracked, deleted
   before commit), then it imports cleanly. Built a synthetic `buckets`/`entries`/`cc` covering
   all 7 bucket kinds, called `pre.format_report(entries, buckets, cc)` (3-arg, old signature)
   vs. `error_cluster_report.format_report(entries, buckets, cc, report_date)` (4-arg, new
   signature), compared with the pre-split output's own `REPORT_DATE` substituted for the
   synthetic `report_date` string (the only intentional difference given the signature change) —
   exact string match (`len=5516`).

**Reusable gotcha for this codebase's split pattern in general:** if a target script resolves
`MAIN_PROJECT`/`git`-relative paths at import time (module-level, not inside a function — check
for this BEFORE writing the synthetic check), `spec_from_file_location` backups must be staged
inside the real worktree tree, not `/tmp/`, or the import itself throws before your test code
ever runs.

Verification artifacts (`dev/tool_use_errors/reports/`, `_pre_split_backup.py`, `__pycache__/`,
everything under `/tmp/tue_verify/`) were all deleted or left outside the worktree before commit
— none are staged.

## Files NOT touched

`dev/tool_use_errors/md/*.md` (the two older, unrelated manual reports) were left untouched.
