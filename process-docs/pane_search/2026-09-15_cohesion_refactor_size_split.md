# 2026-09-15 — dev/pane_search/ cohesion refactor (400-LOC / 50-line-function split)

## Task
Every module in `dev/pane_search/` had to drop under 400 LOC, and every function under 50 lines.
Seven files were over budget: `p1_full_sweep_cost_probe.py` (403, plus two oversized functions),
`p2_search_feature_regression_test.py` (471), `p3_drag_select_regression_test.py` (406),
`p5_worker_proxy_pane_parity_test.py` (543), `p6_tokens_pane_parity_test.py` (515),
`p7_workers_pane_parity_test.py` (596), `p8_warnings_gpu_news_parity_test.py` (584). Behaviour
had to stay identical — same CLI invocation, same output paths, same PASS/FAIL results.

## Approach taken
Split each `pN_*` script into an entry file (kept at its ORIGINAL path/name, so
`./venv/bin/python dev/pane_search/pN_....py` still works unchanged) plus sibling helper modules
in the same directory:
- `pN_..._fixtures.py` — module loads (`importlib.import_module`), the shared `check()`/`_RESULTS`
  list, and fixture-builder/state-reset functions. Utility-module shape: `INFRASTRUCTURE` +
  `FUNCTIONS` only, no `ORCHESTRATOR`.
- `pN_..._cases.py` (or `_cases_<concern>.py`, `_cases_<pane>.py` when one file would still exceed
  400 lines) — the `test_*` functions, same utility shape.
- The entry file itself now holds only `INFRASTRUCTURE` (imports of the test functions + `_RESULTS`
  from the sibling modules) and `ORCHESTRATOR` (`run_probe_workflow`/`probe_workflow`) — it defines
  zero functions of its own.

This exact split pattern (`_fixtures.py` / `_cases.py` / `_cases_w3.py` / `_report.py` + a thin
entry file) already exists in `dev/proxy_dual_log/` — copied that precedent rather than inventing
a new shape. Sibling `pN_*` files import each other with plain `from pN_..._fixtures import name`;
this is NOT blocked by `src/hooks/block_dev_imports_src.py`, which only regexes for a literal
`^from src.`/`^import src.` line — confirmed by reading the hook source before starting.

Concern boundaries used for the multi-cases-file splits (p5/p6/p7 needed 2, p8 needed 3):
- p5/p6/p7: "mechanics" (2-row header, drag-select, editor-style deletion, render) vs.
  "search"/"matching" (Enter-triggered search, match-key semantics, sentinel/regression checks,
  n/N nav, session/worker-switch reset).
- p8: the file already had `# ==== WARNINGS/GPU/NEWS TESTS ====` banner comments marking the
  3-pane bundle — split along that pre-existing boundary.

## p1's two oversized functions
`_sweep_parse` (61 lines) and `_build_report_md` (110 lines) needed real extraction, not just a
file move. Two small helpers (`_next_forwarded_delta`, `_merge_messages_delta`) pulled duplicate
per-line-read and messages-delta-merge logic out of both `_sweep_parse` and `_lazy_load_one`, which
had near-identical inline blocks. `_build_report_md`'s 90-line f-string got split into 4 section
builders (`_build_report_header`/`_build_wall_time_section`/`_build_ram_section`/
`_build_conclusion_section`) plus a `_compute_report_metrics` helper, joined with `'\n\n'.join(...)`
in the final assembler. All new functions are under 50 lines; the split modules live in
`p1_full_sweep_reconstruct.py` (parse engine) and `p1_full_sweep_report.py` (stats + report text).

**Getting the join separators byte-exact was the fiddly part.** The original was ONE f-string; I
had to work out, line by line, exactly how many `\n` characters sat between each `## Section`
heading (always 2: the previous line's own newline + one blank line) and reconstruct that with
`'\n\n'.join([...])` where each section function returns its text WITHOUT a trailing blank line,
except the last section (`_build_conclusion_section`), which needed its own trailing `\n` because
the original string ended with a real newline before the closing `"""`. Do not trust "looks right"
here — I verified with an actual diff, see below.

## Verification method
1. **p1 (can't run end-to-end here — real forwarded log is gitignored, dev-machine-only path):**
   Loaded the pre-refactor file (`git`-clean copy, saved to `/tmp/p1_original_backup.py` before any
   edits) via `importlib.util.spec_from_file_location` in an isolated namespace, called
   `_build_report_md`/`_sweep_parse`/`_lazy_load_one` with identical synthetic inputs against both
   old and new code, asserted the return values were EQUAL (dicts/lists) or IDENTICAL strings
   (report md — `assert md_old == md_new`, not just "looks similar"). Also ran a full
   `probe_workflow` end-to-end on both old and new code against the same small synthetic
   forwarded-delta JSONL fixture and diffed the two reports — only the wall-clock timing numbers
   differed (expected: `time.perf_counter()`/`tracemalloc` are real measurements, not deterministic
   across runs even for the SAME unmodified script run twice).
2. **p2/p3/p5/p6/p7/p8 (all runnable here):** `os.get_terminal_size()` is called deep inside these
   panes' render paths and raises `OSError: Inappropriate ioctl for device` under a plain
   (non-tty) Bash tool invocation — even `script -q logfile cmd` doesn't help once stdout itself is
   redirected to a file (fd 1 stops being a tty the moment you redirect it). The fix: run inside a
   sized detached tmux session (`tmux new-session -d -x 220 -y 50`), send the command with
   `tmux send-keys`, and read output back with `tmux capture-pane -p -S -5000` — NEVER redirect the
   pane's own stdout to a file. Captured a baseline PASS/FAIL check-list (every `  PASS  <label>` /
   `  FAIL  <label>` line, in order) for all 6 scripts BEFORE touching any file, then re-captured
   the same list after each split and ran `diff` — every one came back byte-identical
   (`CHECK-LIST IDENTICAL`), including exact counts: p2 48/48, p3 62/62, p5 77/77, p6 78/78,
   p7 83/83, p8 82/82.
3. Grep-checked nothing outside `dev/pane_search/` imports these files by path (only prose mentions
   of "pane_search" exist elsewhere, in other process-docs/DOCS.md files — no code import).

## Section-order correction (read this before touching module layout elsewhere in dev/)
My first draft kept the pre-existing `dev/`-wide convention of `INFRASTRUCTURE` → `FUNCTIONS` →
`ORCHESTRATOR` (orchestrator last), because that is what literally every file in this directory
(and in `dev/proxy_dual_log/`) already does. The user corrected this: `src/` modules
(`src/proxy/rules.py`, `src/panes/token_pane.py`, `src/panes/warnings_pane.py`) DO follow the
documented standard order `INFRASTRUCTURE` → `ORCHESTRATOR` → `FUNCTIONS`; only `dev/` deviates,
and a consistent deviation across many files is still a deviation, not a second valid convention.
**The rule wins over the current state of dev/.** Every file touched in this task now has entry
files shaped `INFRASTRUCTURE` then `ORCHESTRATOR` with no `FUNCTIONS` section at all (they define
zero functions of their own — everything callable lives in the sibling `_fixtures`/`_cases`
modules, which correctly use the `INFRASTRUCTURE` + `FUNCTIONS` utility-module shape with no
`ORCHESTRATOR`). Files NOT touched in this task were left as they were — the correction applies
to files you create or rewrite, not a blanket repo-wide reorder.

## Things that cost time / would help a successor
- `/tmp/` is NOT stable across tool calls in this environment — a directory created and populated
  in one `Bash` call can be gone by the next call (other concurrent workers/sessions apparently
  share and sweep `/tmp/`). Do multi-step temp-file work (write fixture, run old, run new, diff) in
  ONE `Bash` invocation chained with `&&`/`;`, not across several calls assuming state persists.
- A stray shell hook in this environment intercepts some Bash invocations and prints
  `add redirect: ... > /tmp/name.md 2>&1` to stderr with no useful explanation when a heredoc'd
  Python script is piped in a particular way; switching to explicit `> file 2>&1` redirection in
  the same command made it go away. Not fully root-caused; if you hit the literal string
  `add redirect:` in stderr, just restructure the command with explicit redirects rather than
  investigating further — did not cost more than one retry each time.
- The dev/pane_search/md/ report files ARE tracked in git (not gitignored) despite being
  timestamped regression-run output — any verification run in this directory leaves an untracked
  `.md` file behind that must be `rm -f`'d before committing, and `p1_full_sweep_cost_report.md`
  specifically is a git-tracked file that a real (non-fixture) run overwrites — `git checkout --`
  it back if you run p1 against a real log during verification.

## Result
26 `.py` files now in `dev/pane_search/` (was 7), longest is 285 LOC
(`p2_search_feature_regression_cases.py`), longest function is 49 lines
(`run_probe_workflow` in `p8_warnings_gpu_news_parity_test.py`). No new file imports anything
outside its own `pN_*` family — see `dev/pane_search/DOCS.md` for the per-module map.
