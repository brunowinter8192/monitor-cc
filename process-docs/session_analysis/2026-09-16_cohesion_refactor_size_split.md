# 2026-09-16 — dev/session_analysis/ cohesion refactor (400-LOC / 50-line-function split)

## Task
Same milestone shape as the two prior cohesion-refactor passes (`dev/pane_search/`,
`dev/proxy/` — see those areas' process-docs for the general method). Every module in
`dev/session_analysis/` had to drop under 400 LOC, and every function under 50 lines. Measured
hits: `07_quartet_prefix_diff.py` (811 LOC — `build_findings_summary` 115, `build_pair_section`
106, `build_report` 75, `analyze_pair` 51), `05_req_breakdown.py` (687 — `build_report` 207,
`compute_rule_edits` 71, `compute_prefix_attribution` 69, `tokenize_segments` 61),
`02_cache_timeline.py` (478 — `detect_anomalies` 81), `06_char_token_ratio.py` (455 —
`build_report` 130, `load_session_events` 52), `03_cache_rebuild_context.py` (415 —
`format_rebuild_block` 50), `04_cache_validation.py` (144, under 400 already — `main` 62,
`analyze_request` 58). This pass's constraint was the strictest of the three: **no comments at
all on extracted helpers, not even a one-line purpose comment** — only the three section
markers were allowed.

## Numeric filename prefixes block plain sibling imports — read this first
Every numbered script in this directory (`01_`, `02_`, ... `07_`) has a filename starting with a
digit. `from 02_cache_timeline_parse import x` is a **SyntaxError** — Python's `from ... import`
grammar requires the module name to be a valid dotted identifier, and identifiers cannot start
with a digit. This is different from the previous two milestones, where sibling files used a
letter prefix (`p1_`, `p2_` in pane_search) or no numeric scheme at all (proxy) and plain
`from sibling import x` just worked.

Two ways around this exist and both already run somewhere in this project:
`importlib.import_module('02_cache_timeline_parse')` (works — `importlib` takes a plain string,
never parsed as Python source, so the leading digit is irrelevant; verified empirically in
`/tmp` before touching any real file: a throwaway `02_foo.py` + `importlib.import_module('02_foo')`
resolved and ran fine), or dropping the numeric prefix on the sibling files entirely and using a
plain `from sibling import x` statement. **I chose the second option** for every split in this
area: the entry scripts keep their exact `0N_name.py` filename (required by the milestone), and
every sibling module is named `<topic>_<concern>.py` with NO leading digit (e.g.
`cache_timeline_parse.py`, `req_breakdown_attribution.py`, `quartet_prefix_diff_findings.py`).
This keeps the import style a plain, ordinary `from x import y` — no importlib indirection
anywhere in this area — which is simpler and matches how every other split module in `dev/`
already imports its siblings. **First attempt actually wrote the sibling files WITH the `02_`
prefix by mistake** (typo carried over from the entry-file name) and only caught it because the
entry file's `from cache_timeline_parse import ...` line didn't match any file on disk — fixed
with `mv` before running anything. If you add a new numbered script's sibling module in this
directory, double-check the filename has no leading digit before writing any import statement
against it.

## Per-file split summary
- **`02_cache_timeline.py`** → entry (66 LOC) + `cache_timeline_parse.py` (session discovery/
  parsing) + `cache_timeline_analysis.py` (cache-status classification + `detect_anomalies` split
  into its 3 independent detector loops — STUCK_CACHE / FAILED_RESUME / PREMATURE_TTL, each
  already a self-contained loop over `turns` in the original, so the split was a pure lift, no
  logic reshuffling) + `cache_timeline_render.py` (all `format_*` functions).
- **`03_cache_rebuild_context.py`** → entry (75 LOC) + `cache_rebuild_context_parse.py` +
  `cache_rebuild_context_detect.py` + `cache_rebuild_context_render.py` (the 50-line
  `format_rebuild_block` split into `_format_rebuild_header` and `_format_context_row`, the
  latter called once per context row instead of building each line inline).
- **`04_cache_validation.py`** — stayed a single file (144 LOC, nowhere near 400); extracted
  `_find_cc_breakpoints`/`_find_modifiable_indices` out of `analyze_request`, and
  `_load_entries`/`_print_request_rows` out of `main`. Added the three section markers — this
  file had NONE before (not even `# INFRASTRUCTURE`).
- **`05_req_breakdown.py`** → entry (55 LOC) + `req_breakdown_load.py` (proxy/session loading +
  `tokenize_segments` split into `_tokenize_system`/`_tokenize_tools`/`_tokenize_messages`) +
  `req_breakdown_attribution.py` (`compute_prefix_attribution` split into `_tokens_around_drift`
  and `_locate_segment_and_heading`, plus the pre-existing `_find_byte_drift`/
  `_build_drift_context` helpers) + `req_breakdown_rule_edits.py` (`compute_rule_edits` split into
  `_fetch_git_log`/`_scan_mtime_files`/`_cross_check_drift_match`) + `req_breakdown_report.py`
  (`build_report`'s 207 lines split into 6 section-builder functions, `_build_attribution_lines`
  further split into a table half and a context half since the first split alone left it at 66
  lines).
- **`06_char_token_ratio.py`** → entry (41 LOC, `INFRASTRUCTURE`+`ORCHESTRATOR` only, zero own
  functions) + `char_token_ratio_load.py` (log/session auto-detection + `load_session_events`
  split into `_parse_assistant_usage`/`_flush_pending`, since the original nonlocal-closure
  dedup-merge loop needed a real state-machine extraction, not just a lift) +
  `char_token_ratio_compute.py` + `char_token_ratio_report.py` (`build_report`'s 130 lines split
  into 4 section builders).
- **`07_quartet_prefix_diff.py`** → entry (86 LOC) + `quartet_prefix_diff_load.py`
  (ground-truth/forwarded-chain/original-log loading + pair detection) +
  `quartet_prefix_diff_diff.py` (the diff engine: `diff_messages` split into
  `_diff_common_message_rows`/`_diff_added_removed_message_rows` threading `first_diff` through
  both calls; `analyze_pair`'s order/first-divergence computation extracted into
  `_diff_order_and_first_divergence`) + `quartet_prefix_diff_report.py` (`build_report` + the
  106-line `build_pair_section` split into 5 section builders) + `quartet_prefix_diff_findings.py`
  (`build_findings_summary`'s 115 lines split into `_proven_from_bytes_flags`/
  `_build_proven_from_bytes_lines`/`_gather_original_attribution_rows`/
  `_build_original_attribution_summary_lines`/`_build_recoveries_lines`/
  `_build_interpretation_lines`, plus `original_log_used`). `quartet_prefix_diff_report.py`
  imports `build_findings_summary` from `quartet_prefix_diff_findings.py` to assemble the full
  report — a real cross-file call, not just data sharing.

## Bugs I introduced and caught before committing — read before trusting a "split" blind
Two silent-behavior-change mistakes happened while extracting section-builder functions from
`build_report`-shaped functions, both caught by the direct-call diff tests, NOT by reading the
diff:
1. In `req_breakdown_report.py`, the original `_build_attribution_lines` used the OUTER `cr`/`cc`
   ground-truth values (not attribution-derived) in the `KPI D5 CR`/`KPI D5 CC` table rows. My
   first extraction didn't pass `cr`/`cc` into the new helper and I patched around it with a
   nonsensical `f'...'.replace(...) if False else f'...'` placeholder that happened to produce
   the right STRING by accident but was unreadable garbage — caught on a second read-through of
   my own diff before ever running a test, not by the test itself. Fixed by adding `cr, cc` as
   real parameters. **Lesson: when an extracted helper needs a value from the enclosing
   function's OTHER parameters (not just its own return values), add it as a parameter
   immediately — don't leave a "TODO fix this" placeholder in code you're about to test, even
   for one edit-cycle.**
2. In `char_token_ratio_report.py`, the original `build_report` computed
   `clean_count = len(msg_ratios)` — NOT derived from the three discard counters computed two
   lines above it (`total_req - discarded_no_token - discarded_thinking - discarded_no_delta`,
   which is what I wrote first, since it superficially "looks like" the natural definition of
   "clean"). These are NOT the same number in general (`msg_ratios` also excludes REQ#1, which
   the discard counters don't account for). This one did NOT show up in my visual review — I
   only caught it because I diffed the ORIGINAL file's exact source line by line against my
   rewritten section function before running anything, specifically because I'd already been
   burned once in the same session (mistake #1 above). **Lesson: for any report-building split,
   diff the original literal source lines against the new section function line by line before
   testing — a plausible-looking "equivalent" computation is not proof of equivalence; only the
   original literal expression is.**

Both were caught before any test run, but the general pattern — an extracted section function
silently recomputing a value differently than the original monolithic function did — is exactly
the class of bug the direct-call verification below is designed to catch if a review pass misses
it, so treat "the split compiles and runs" as zero evidence; only the diff proves it.

## Verification method
- **`01_extract.py`** — untouched (not in the hit list, no function ≥50, already
  `INFRASTRUCTURE`→`ORCHESTRATOR`→`FUNCTIONS`). Not re-verified beyond the directory-wide AST
  sweep.
- **`02_cache_timeline.py`, `03_cache_rebuild_context.py`** — real data available in this
  environment (`~/.claude/projects/.../*.jsonl` session files, `--project`/`--all` scans of the
  same). Ran the pre-split backup and the post-split entry script side by side against the same
  real session file/project path across every CLI mode (`--session`, `--aggregate`,
  `--anomalies-only`, `--project`, `--project --workers`, `--all`, `--summary-only`, `--context`)
  and diffed stdout byte-for-byte — all identical, no exceptions.
- **`04_cache_validation.py`** — the old single-file `raw_payload` proxy-log format no longer
  exists anywhere on this dev machine (superseded by the dual-log quartet). Built a small
  synthetic fixture JSONL (breakpoints in system/tools/messages, one modifiable message before a
  breakpoint) and ran the pre-split and post-split scripts against it under plain, `--limit 1`,
  and `--rebuilds-only` — stdout byte-identical in all three modes.
- **`05_req_breakdown.py`** — same old-format problem, PLUS this script's own report embeds a
  wall-clock `**Timestamp:**` line, so even a byte-identical run differs by that one line. Built
  a synthetic proxy-log pair (prev/curr, deliberately drifting mid-message so the byte-diff
  attribution logic has real work to do) plus a session JSONL ground-truth line, ran pre- and
  post-split with and without `--prev-proxy-log`, and diffed the two generated reports — the ONLY
  differing line in both runs was the timestamp; every KPI/table/attribution/rule-edit line
  matched exactly.
- **`06_char_token_ratio.py`** — no CLI arguments at all (auto-detects paths from hardcoded
  `PROXY_LOG_DIR`/`SESSION_DIR` constants), and the old proxy-log format doesn't exist under
  `src/logs/` either. Rather than write a fixture file into `src/logs/` (out of this task's
  directory scope), monkeypatched the constants in both the pre-split backup module and the new
  `char_token_ratio_load` module to point at temp-dir fixtures, then called every pipeline
  function directly (`load_proxy_rows`, `load_session_events`, `pair_rows`, `compute_ratios`,
  `compute_tiktoken_drift`, `build_report`) old vs. new and asserted the intermediate values AND
  the final report string are equal — all equal (the report string happened to match exactly
  including the timestamp header, since both runs landed in the same wall-clock minute; the
  `ts_header` format is `%Y-%m-%d %H:%M`, minute-resolution, not a coincidence to rely on if you
  rerun this slower).
- **`07_quartet_prefix_diff.py`** — this one DOES have real matching data available
  (`src/logs/dual_log/*_forwarded.jsonl` plus a `~/.claude/projects/.../*.jsonl` session file) —
  ran pre- and post-split against real files first as a smoke test (no crash, structurally valid
  report, mostly-unmatched pairs since the picked session/log pair weren't from the same actual
  conversation — acceptable, this only proves no exception path broke). The REAL proof is a
  hand-built synthetic fixture: a 2-request forwarded-delta chain with a system[0] billing-header
  change, an evicted image in message 0, and an added message 2, plus a matching `_original`
  dual-log where the image survives in BOTH original snapshots (forcing the PROXY-SIDE
  attribution verdict branch) and a session-JSONL ground truth whose CR/CC satisfies the recovery
  identity. Ran both versions with `--req-range 1-2 --original-log ...` and diffed the two
  generated reports — the only differing line was `**Generated:** <timestamp>`; every table,
  every attribution verdict, every findings-summary sentence (including the recovery-identity
  HOLDS line and the image-eviction PROXY-SIDE summary sentence) matched byte-for-byte. This
  fixture exercises every branch the milestone's own hit list flagged
  (`analyze_pair`/`build_pair_section`/`build_findings_summary`/`build_report`), not just the
  happy path.
- Directory-wide: an AST sweep confirms all 24 `.py` files are under 400 LOC and zero functions
  anywhere in the directory are ≥50 lines.

## dev/session_analysis/md/ and 04_reports/ are git-tracked report dumps, not scratch space
`dev/session_analysis/md/` already held 9 real report files from actual past sessions (dated
2026-04 through 2026-08) BEFORE this task started, and they are git-tracked. A careless
`rm -rf dev/session_analysis/md/2026*.md` cleanup after a verification run deleted ALL of them
(the glob matched the pre-existing files too, not just the ones the verification run generated
minutes earlier under today's date) — caught immediately via `git status --porcelain` showing
9 unexpected `D` lines, restored with `git checkout -- dev/session_analysis/md/`. **Lesson: when
cleaning up verification-run output in an already-populated report directory, delete files by
their EXACT generated name/timestamp, never by a broad date glob — check `git status` before AND
after any bulk `rm` in a directory you didn't create from scratch.** `05_req_breakdown.py`'s and
`06_char_token_ratio.py`'s `04_reports/` output directory, by contrast, did not previously exist
in this worktree and was git-ignored/untracked scratch space — safe to `rm -rf` freely, and was
removed after verification.

## Section-order note (carried over from the two prior cohesion-refactor milestones)
Every file created or rewritten in this task is shaped `INFRASTRUCTURE` → `ORCHESTRATOR` →
`FUNCTIONS` (helper modules with no orchestrator use `INFRASTRUCTURE` → `FUNCTIONS` only, and
`06_char_token_ratio.py`'s entry file has no `FUNCTIONS` section at all since it defines zero
functions of its own — everything lives in its three sibling modules). This matches the
corrected order established in the `dev/pane_search/` and `dev/proxy/` recaps — see those areas
for the full reasoning (`src/` already uses this order; only `dev/` had drifted to
`FUNCTIONS`-before-`ORCHESTRATOR`). `01_extract.py` and `02_cache_timeline.py`'s original
(pre-split) file were ALREADY in the corrected order before this task touched them — not every
file in this project drifted.

## Result
24 `.py` files in `dev/session_analysis/` (was 7), longest is `01_extract.py` at 281 LOC
(untouched — was already compliant), longest touched/new file is `req_breakdown_report.py` at 242
LOC. Longest function in the whole directory is under 50 lines (AST-verified, zero hits). See
`dev/session_analysis/DOCS.md` for the per-module map; note its `06_char_token_ratio.py` entry
was also corrected to describe the SCRIPT'S ACTUAL current behavior (auto-detect, zero CLI args)
— the previous DOCS.md entry described a `--batch`/`--session-jsonl` CLI that does not exist in
the code, a pre-existing doc-drift bug unrelated to this refactor, fixed here because this task
was already rewriting that file's docs entry.
