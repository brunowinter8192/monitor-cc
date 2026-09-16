# Cohesion refactor of dev/pipeline/ (2026-09-16)

## Task

Split `format_stability/01_unknown_types.py` (198 LOC, `write_report` 64 LOC) to satisfy the
50-LOC-function threshold. No behaviour change allowed. Full task text lives in the issue that
spawned this session, not repeated here. `format_stability/`, `io_profile/`, `memory_profile/`,
and `parsing_profile/` are all subdirectories of `dev/pipeline/` with no `DOCS.md` of their own
(per the milestone's own "Note on this area") — all documentation lives in `dev/pipeline/DOCS.md`.

## Scope: single file, one function, no multi-file split needed

198 LOC is well under the 400-LOC file threshold — same shape as three other sessions this batch
(`bg_wakeup_id_line`, `worker_pane_split`, `thinking`): one file already compliant on size, one
function over the 50-line threshold. Extracted 6 report-section helpers
(`compute_coverage`, `report_header_lines`, `top_level_types_table`, `content_block_types_table`,
`unknown_types_table`, `versions_table`, `summary_lines` — 7 total) from `write_report`, all
inside the same file. Final file: 240 LOC, longest function 47 lines (`scan_all_files`,
pre-existing, already compliant, untouched).

**Note on naming:** the pre-existing helpers in this file (`find_all_jsonl_files`,
`scan_all_files`, `extract_content_block_types`, etc.) have NO leading underscore, unlike the
convention used in most other `dev/` scripts touched this batch. Matched the existing file's own
convention exactly — the new helpers are also un-underscored (`compute_coverage`, not
`_compute_coverage`) for consistency with their neighbors in this specific file.

## Read all 4 scripts in the directory — only one was in scope

Per the task's file-reading requirement, read `io_profile/01_poll_cycle_cost.py` (164 LOC),
`memory_profile/01_cache_growth.py` (114 LOC), and `parsing_profile/01_multipass_cost.py`
(139 LOC) in full, checking for cross-imports with `format_stability/01_unknown_types.py`. Found
none — all 4 scripts are fully independent siblings, each in its own subdirectory, none importing
another. Ran an AST longest-function scan across all 4 files before touching anything: only
`01_unknown_types.py`'s `write_report` was over 50 lines anywhere in the directory. The other 3
were NOT modified.

**Two of the three untouched scripts are already broken and NOT run this session.**
`memory_profile/01_cache_growth.py` and `parsing_profile/01_multipass_cost.py` both import
`from src.jsonl_parser import ...` — this module no longer exists (moved to `src/jsonl/` at some
point since these scripts were last touched), so both raise `ModuleNotFoundError` on the current
tree. This is pre-existing, documented in `DOCS.md`'s Gotchas already, and outside this
milestone's scope (only `format_stability/01_unknown_types.py` had a size/function violation) —
did not attempt to fix the import, did not run either broken script. `io_profile/
01_poll_cycle_cost.py` imports `src.session_finder` which DOES exist, so that one is presumably
still runnable, but wasn't run either since it had no violation and running it wasn't needed for
this task's verification.

## Hazard classification

`format_stability/01_unknown_types.py` is READ-ONLY: reads every session JSONL file under
`~/.claude/projects/`, writes only its own timestamped report to
`format_stability/01_reports/` (created on demand — this is the path the CODE actually uses; the
existing `md/` directory in this folder holds older reports from before the path drifted, per the
pre-existing Gotcha already in `DOCS.md` — not something this session touched or needed to fix).
No desktop/tmux/hotkey/monitor interaction anywhere in the file. Confirmed by reading the full
file before editing. Safe to run — did run it directly against real production data
(`~/.claude/projects/`, ~411K lines across the whole tree, ~4.5s) both before and after the split.

## Behaviour-unchanged proof

Two layers, both passed:

1. **Real-data run, before and after**, structural comparison. `~/.claude/projects/` is live —
   other Claude Code sessions (including the one running this task) continuously append to their
   own session JSONL files, so two consecutive real runs of a full-tree scanner will never be
   byte-identical (same non-determinism hit in the `sleep_pattern_analysis` and `worker_pane_split`
   sessions earlier this batch). Ran the untouched pre-split script for real, then the fully-split
   script for real ~40 seconds later: every category (top-level types, content block types,
   unknown-type entries, CC versions found) matched in KIND and SET exactly — same type names,
   same "Yes"/"NO" handled-flags, same unknown-type file/example rows — with only the COUNT
   columns differing, and every count differed by a small POSITIVE amount consistent with pure
   appends during the ~40s window (never a count that dropped, never a type that appeared/
   disappeared). This is the expected signature of live-data drift, not a behavior regression.
   Deleted both generated `01_reports/` directories from the worktree before commit (git status
   confirmed clean both times — `01_reports/` is untracked, unlike some other pipeline
   subdirectories' `md/` folders which ARE tracked).
2. **Synthetic per-function check, for a byte-identical guarantee the live-data comparison alone
   can't give.** Loaded the pre-split backup via `importlib.util.spec_from_file_location`, built
   one synthetic `data` dict (covering known + unknown top-level types, known + unknown content
   block types, multiple CC versions) and called `pre.write_report(data)` vs.
   `post.write_report(data)` — identical report text apart from the `Date:` line (both call
   `datetime.now()` at report-build time; original, unmoved behaviour). Also checked a
   second, "nothing unknown, no versions found" synthetic case (`unknown_top`/`unknown_content`
   empty dicts, empty `Counter` for versions) since that's a distinct code branch in
   `versions_table`/`summary_lines` (the `if data['versions']: ... else: ...` and
   `if data['unknown_top'] or data['unknown_content']: ... else: ...` branches) not exercised by
   the real-data run's own content. Both cases matched exactly (`write_report` needed
   `REPORTS_DIR.mkdir()` called manually in the harness first, since calling it directly bypasses
   `main()`'s own mkdir step — a harness-only detail, not a code change).

Verification artifacts (`/tmp/pipeline_verify/`, both real-run-generated `01_reports/`
directories) were deleted or left outside the worktree, never staged.

## Files NOT touched

`io_profile/01_poll_cycle_cost.py`, `memory_profile/01_cache_growth.py`, and
`parsing_profile/01_multipass_cost.py` were read in full but already compliant (no function at or
above 50 lines, all files under 400 LOC) and were not modified. `dev/pipeline/*/md/*.md`
(pre-existing tracked reports) were left untouched.
