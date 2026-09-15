# 2026-09-16 — cohesion refactor: split every file/function in dev/proxy_instrumentation/ over the 400 LOC / 50-line thresholds

## Task

Five files violated the project's size thresholds (400 LOC per file, 50 lines per function):
`p1_measure_full_replacement_blast_radius.py` (541 LOC, `_build_report` 207 lines),
`p6_no_flow_extra_prepend_probe.py` (`_check_session` 56 lines),
`p7_blocklist_258_probe.py` (`main` 105 lines), `p4_blocklist_223_probe.py` (`main` 67 lines),
`response_model_corpus_report.py` (`_compute_stats` 64, `_write_report` 68). Bring every file and
function under threshold with zero behaviour change, keeping entry-script filenames exact.

## Module split (only p1 needed a file split — the other four stayed single-file, function-only splits)

`p1_measure_full_replacement_blast_radius.py` (541 -> 59 LOC) now only owns the corpus file list and
`main()`. Three new sibling modules (no number prefix, per the project's "leading digit is not a
valid module name" rule) hold the extracted concerns:
- `blast_radius_engine.py` — the pass-driving/classification engine (`_scan_file`, `_drive_passes`,
  `PASS_CLASS`/`FIRST_PASS_BRANCH_CLASS`).
- `blast_radius_analysis.py` — ratio/trim/distribution math + the real `compose_block` +
  `_render_span_content` render comparison.
- `blast_radius_report.py` — `_build_report` split into one function per markdown section
  (corpus/method/per-pass-counts/blast-radius/edge-case/ratio/structural/examples), composed by a
  slimmed `_build_report(records, total_requests, corpus_files, excluded_files)` — note the two new
  trailing params: the backup's `_build_report` read `CORPUS_FILES`/`EXCLUDED_FILES` as module
  globals, the split version takes them as arguments since the entry script now owns those
  constants and the report module must not reach back into it.

p4/p6/p7/response_model_corpus_report.py: pure function extraction inside the same file, no new
module. Pattern used everywhere: pull the report-writing tail into its own `_write_report(...)`,
pull each independent check-block into its own `_check_*`/`_run_checks` function, orchestrator
just calls them in sequence and concatenates results.

## Gotcha 1 — I violated "no new comments on extracted helpers" on the first pass, caught it myself

When first extracting `_below_window_indices`/`_badge_silence_stats` (p6) and
`_check_newly_blocked_extension`/`_check_rw_extension` (p7) I added a one-line purpose comment above
each new `def`, e.g. `# Checks 1-4: the CC 2.1.258 SendFeedback/ListAgents extension, ...`. The task
explicitly forbids this ("Do NOT add comments or docstrings that were not already there. Not even a
one-line purpose comment on an extracted helper."). Caught it on a `grep -n "^#"` sweep across the
three new p1 modules right after writing them (clean there) and then re-checked the in-place edits
and found the violation. Fixed by deleting the added comment lines; where an *original* comment
existed above the code being moved (e.g. p7's `# --- Edit/Write milestone ... ---`), that one stays,
relocated with its code, since relocating an existing comment is not "adding" one.
**Lesson for the next agent: after any extraction, `grep -n "^#\|^    #" <file>` and diff the result
against the original file's comment set — anything not present verbatim in the original is a
fabricated comment and must go, even a purely mechanical section-header line.**

## Gotcha 2 — the `block_dev_imports_src` hook only blocks column-0 `from src.`/`import src.`

`_SRC_IMPORT = re.compile(r'^(?:from\s+src\.|import\s+src\.)', re.MULTILINE)` — `^` with MULTILINE
matches right after a newline, so an INDENTED `from src.proxy_display... import ...` inside a
function body does NOT match (the line doesn't start with "from" at column 0, it starts with
whitespace). This is why `p6_no_flow_extra_prepend_probe.py` already had several
`from src.proxy_display....` imports *inside* its functions before this refactor, and why they were
safe to leave untouched. It also means: a brand-new sibling module created via `Write` (which sends
the FULL file content to the hook, unlike `Edit`'s `new_string`-only content) must not have a
top-level (column-0) `from src.`/`import src.` line, but can freely use the dynamic
`importlib.import_module('src.proxy_display....')` pattern at module level (already the existing
convention in `p1`, reused verbatim in `blast_radius_analysis.py`) or an indented `from src....`
inside a function body. Confirmed empirically: none of the three new p1 sibling modules trip the
hook (`grep -nE "^(from|import)\s+src\." *.py` in the directory returns nothing).

## Gotcha 3 — no `__init__.py` in this directory; sibling imports are flat, exactly as in `dev/tool_use_analysis/`

`dev/proxy_instrumentation/` has no `__init__.py` (confirmed via `find dev -maxdepth 2 -name
__init__.py`, only `dev/jsonl/` and `dev/proxy_analysis/` have one). The established precedent for
splitting one big dev script into several files while keeping it runnable via
`./venv/bin/python dev/<dir>/<script>.py` lives in `dev/tool_use_analysis/`
(`extract_patterns.py` + `extract_patterns_collect.py` + `extract_patterns_report.py`, and three
more triples in the same directory) — plain `from <sibling_module_name> import ...`, no `sys.path`
manipulation for the sibling import itself, because Python auto-inserts the running script's own
directory at `sys.path[0]`. Copied this exactly for `blast_radius_engine.py`/`_analysis.py`/
`_report.py`. Each new module still does its OWN `sys.path.insert(WORKTREE_ROOT / 'src')` (and, for
`blast_radius_analysis.py`, `WORKTREE_ROOT` itself for the `proxy_display` subpackage import) rather
than relying on the entry script having already done it — matches every existing file in this
directory, which is defensively self-contained the same way (see e.g. `p6`/`p7`/`p9`/`p10`/`p11`,
which all repeat the identical `WORKTREE_ROOT = Path(__file__).resolve().parents[2]` +
`sys.path.insert` block rather than sharing it).

## Gotcha 4 — this directory's section-marker order is INCONSISTENT, and I deliberately did not fix it

The code standard says INFRASTRUCTURE -> ORCHESTRATOR -> FUNCTIONS. `p8`/`p9`/`p10`/`p11`/
`response_model_corpus_report.py` (all newer) follow that order. `p1`/`p4`/`p6`/`p7`/
`render_recorded_request.py` (all older) have FUNCTIONS *before* ORCHESTRATOR — the reverse. This
refactor is explicitly scoped to size only ("do not refactor code... beyond the prompt scope" /
negative scope section), so every new helper function extracted from `p4`/`p6`/`p7` was inserted
into the EXISTING FUNCTIONS section of that file (which precedes ORCHESTRATOR there), preserving
each file's own pre-existing marker order rather than normalizing it. The three brand-new p1 sibling
modules have no ORCHESTRATOR at all (correct per the milestone instruction: "Helper modules without
an orchestrator keep INFRASTRUCTURE then FUNCTIONS"), so this inconsistency doesn't apply to them.
**If a future task's scope explicitly includes marker-order normalization, `p1`/`p4`/`p6`/`p7`/
`render_recorded_request.py` are the four files that still need FUNCTIONS and ORCHESTRATOR swapped.**

## Verification method and results

Real dual-log corpus at `/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log/` rotates
by mtime (see the pre-existing p4 Gotcha about the same problem) — every hardcoded stem/filename
`p1`, `p5`, `render_recorded_request.py` reference had already aged out by the time of this task.
- **p4, p6 (via its own argv-overridable stems), p7, response_model_corpus_report.py**: ran the
  pre-split backup (copied to `/tmp/instr_backup/` before any edit) and the post-split file against
  the CURRENT real corpus (p6 with two live main-session stems passed as argv), diffed stdout and the
  written `md/` report byte-for-byte. All four came back identical except for the (expected,
  unavoidable) absolute path in the "Report written" line and, for `response_model_corpus_report.py`
  only, the `Generated:` wall-clock timestamp line — every other line matched exactly.
- **p1**: the four corpus files it hardcodes are ALL gone from the live corpus, so no real run-based
  diff was possible pre- or post-split (this is a pre-existing limitation of the script, not
  something this refactor introduced). Followed the task's fallback instruction verbatim: loaded the
  pre-split backup via `importlib.util.spec_from_file_location`, called its `_scan_file`/
  `_build_report` against a small synthetic 2-request JSONL corpus (one `role='system'` message that
  reliably produces one `_apply_role_system_strip` FULL record, one no-op follow-up request), then
  called `blast_radius_engine._scan_file` / `blast_radius_report._build_report` (passing the
  backup's own `CORPUS_FILES`/`EXCLUDED_FILES` constants so the Corpus-section text lines up) against
  the identical synthetic input. `records`, `total_requests`, and the full report string all compared
  equal. **One non-obvious trap here**: the backup module is loaded via `spec_from_file_location`
  from wherever the backup copy physically sits — since it computes `WORKTREE_ROOT =
  Path(__file__).resolve().parents[2]`, the backup copy MUST be placed two directories deep
  (mirroring `dev/proxy_instrumentation/`) or that computation silently resolves to the wrong root
  and every downstream `sys.path`/log-path calculation breaks. Set up
  `/tmp/instr_backup_root/dev/proxy_instrumentation/<file>.py` plus a `src -> <worktree>/src` symlink
  at `/tmp/instr_backup_root/src` to satisfy this, for every backup-vs-split comparison in this task
  (not just p1).
- All twelve `.py` files pass `python -m py_compile`; an AST sweep for `FunctionDef`/
  `AsyncFunctionDef` nodes with `end_lineno - lineno + 1 >= 50` returns empty across the whole
  directory; `wc -l` on every file is under 400 (largest is `post_restart_verification.py` at 350,
  untouched, already compliant before this task).
- Verification runs against p4/p6/p7/response_model_corpus_report.py wrote real content into the
  directory's TRACKED `md/*.md` report files (these are committed artifacts of this directory, not
  gitignored — confirmed via `git check-ignore`). Reverted all four with `git checkout --` before
  committing, since refreshing report content was a side effect of verification, not a deliverable.

## Cross-reference

See `process-docs/proxy_instrumentation/` for the pre-existing corpus-rotation problem this task hit
again (already documented for `p4` in the 2026-09-14 entry) and for the rest of this area's history.
