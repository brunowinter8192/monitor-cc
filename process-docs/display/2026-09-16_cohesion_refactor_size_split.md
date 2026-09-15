# 2026-09-16 — cohesion refactor: split every function over 50 lines in dev/display/

## Task

Five functions violated the 50-line threshold: `scan_jsonl` in `scan_jsonl_rules.py` (58),
`jsonl_exploration/01_map_message_types.py` (94), `jsonl_exploration/02_map_content_blocks.py`
(146), `jsonl_exploration/03_scan_instructions.py` (130), and `test_stripped_msg_pair_alignment` in
`test_hover_map.py` (68). Bring every function under threshold with zero behaviour change. No file
in this directory was near the 400 LOC file-split threshold (largest was `test_hover_map.py` at
342), so this task was pure in-file function extraction — no new modules, no file split, unlike the
`dev/proxy_instrumentation/` cohesion refactor immediately before this one (see
`process-docs/proxy_instrumentation/` for that one's notes, which this task's approach mirrors).

## Note: the incoming prompt's claim about `jsonl_exploration/DOCS.md` was wrong

The task prompt asserted `dev/display/jsonl_exploration/` has no DOCS.md and that the area DOCS.md
covers both directories. Neither is true: `jsonl_exploration/DOCS.md` exists (pre-dates this task)
and the top-level `dev/display/DOCS.md` even says so ("see its own DOCS.md"). Flagged this in the
first response before implementing; got confirmation to update the existing file's LOC numbers only
(no new DOCS.md, no moving files between the two directory levels) — that's what happened. If a
future prompt about this area repeats the "no DOCS.md" claim, it's still wrong; check the directory
directly rather than trusting the prompt.

## Split pattern (repeated across all four report-building scripts)

Every one of the four `scan_jsonl` functions (in `scan_jsonl_rules.py` and the three
`jsonl_exploration/0N_*.py` scripts) has the exact same shape: an accumulation loop over JSONL lines
building several `Counter`/`defaultdict`/`dict` structures, followed by a markdown-lines builder with
2-5 independently-readable `##`-headed sections. The mechanical fix applied everywhere: pull the
accumulation loop into its own `_collect_*_stats(filepath) -> tuple` (or, for
`scan_jsonl_rules.py`, `_collect_rule_locations(filepath) -> list`, since that one only builds a
single list), then pull each markdown section into its own `_*_lines(...) -> list` function, then
make `scan_jsonl`/`scan_jsonl` itself just call collect + each section builder + join. Where a loop
body itself still cleared 50 lines even after this first split (`02_map_content_blocks.py`'s
per-block loop, `03_scan_instructions.py`'s pattern-search sub-loop), extracted a second inner
helper (`_process_content_blocks`, `_record_pattern_hits`) called from inside the collector.

`test_hover_map.py`'s `test_stripped_msg_pair_alignment` split differently since it isn't a
report-builder: `_resolve_dual_log_dir()` (the worktree-then-main-repo-root fallback path lookup,
returns `None` if neither exists) and `_collect_stripped_pair_entries(dual_dir)` (the
fwd_candidates scan + pane.py-mirrored overlay wiring, up to 5 entries) came out as the two
extracted helpers; the test function itself kept only the two skip-guards and the final
`render_messages`/assert loop.

## Gotcha — I dropped 6 pre-existing section-header comments on the first pass, caught it with a comment-multiset diff

Mechanically slicing a big function into `lines.append(...)` chunks is easy to get wrong on the
COMMENT lines that sit between statements, because they don't obviously "belong" to either side of
a cut. On the first pass I dropped `# Summary table` and `# Detailed sections` from
`02_map_content_blocks.py`, and `# Pattern hits summary` / `# isMeta messages` / `# file-history-
snapshot` / `# Detailed pattern hits` from `03_scan_instructions.py` — six comments that existed
in the original file and quietly vanished during extraction, which is exactly the kind of thing the
task forbids in the opposite direction (never ADD a comment) but is just as real a spec violation
when it happens by DELETION.
**How I caught it:** `diff <(grep -oE '#.*' old.py | sort) <(grep -oE '#.*' new.py | sort)` for
every touched file, run right after editing and again after the fix, comparing the full multiset of
comment substrings (not just unique lines — some comment text like `# isMeta messages` appears
TWICE in the same file, once on the collector's inline check and once on the report section header;
a naive `diff` on deduplicated sets would have hidden the loss of one of the two identical-text
occurrences). Zero diff on all five touched files is the actual proof this task needed; run it
before claiming the "no new comments" requirement is satisfied, because a `grep -n "^#"` sweep alone
(which is enough to catch ADDED comments, and what I used successfully in the prior
`proxy_instrumentation` milestone) does NOT catch comments deleted internally to a function you're
splitting — the previous milestone had no such loss to catch, this one did.
**Fix:** the six comments went back exactly at the top of the extracted section-builder function
they used to sit above, e.g. `# Summary table` now sits as the first line inside
`_summary_table_lines`, immediately above the `lines.append(f'## Summary')` it always annotated.

## Verification method and results

All 8 `.py` files in this directory are read-only (no tmux mutation, no desktop/window/Space
interaction, no monitor restart) — `screenshot_panes.py` only calls `tmux capture-pane` (a read op)
and `termshot`, neither sends input; confirmed by reading before touching anything.
- **`scan_jsonl_rules.py`**: this script has no path argument, it always auto-discovers "newest
  project dir, newest JSONL in it" by mtime — since the live corpus is actively growing (this very
  session's own JSONL is the newest one, and it grows every turn), a naive before/after run against
  the "live" path showed a false byte-size mismatch purely from file growth between the two
  invocations. Fixed by freezing one snapshot (`cp` to `/tmp/frozen_session.jsonl`) and pointing
  both the pre-split backup and the post-split file at that frozen copy directly — stdout then came
  back byte-identical.
- **`jsonl_exploration/01`/`02`/`03`**: these DO accept `argv[1]`, so no freezing needed — resolved
  one concrete path once, passed it explicitly to both backup and split versions via
  `importlib.util.spec_from_file_location`, diffed the returned report string with the `Scanned:`
  timestamp line excluded. All three identical.
- **`test_hover_map.py`**: this one has a real trap for a `spec_from_file_location`-loaded backup.
  The dual-log lookup does `Path(__file__).parent.parent.parent`, then falls back to
  `.parent.parent.parent.parent.parent.parent` (six `.parent`s total across both attempts) to escape
  a git worktree (`.claude/worktrees/<name>/dev/display/file.py`) back to the main repo root where
  the real `src/logs/dual_log/` data lives (worktrees never carry this gitignored runtime data — see
  the pre-existing Gotcha in this same DOCS.md, and the identical corpus-rotation gotcha documented
  for `dev/proxy_instrumentation/`). Loading the backup from an arbitrary `/tmp/` path breaks this
  chain silently: the fallback still "succeeds" in the sense of not crashing, it just resolves to
  filesystem root and finds nothing, so the dual-log-dependent sub-test SKIPS instead of running —
  a false pass, not a real behavioural match, and the diff against the post-split run (which DOES
  reach the real data) showed 4 fewer PASS lines and a different final count, which looked at first
  like a genuine regression. **Fix: for any file whose logic depends on its OWN `__file__` depth
  relative to a repo root, don't load the backup via a relocated `spec_from_file_location` path at
  all — temporarily copy the backup INTO the exact same real directory under a throwaway filename
  (`dev/display/_verify_old_test_hover_map.py`), run it there via a normal subprocess invocation, diff,
  then delete it.** This is simpler than reconstructing a fake nested directory tree with symlinks
  (which is what I did for the previous `proxy_instrumentation` milestone's `p1` verification, and
  which also works, but is more setup for the same result when the file doesn't need to be imported
  as a Python module — only run as `__main__`). After that fix, stdout came back byte-identical
  (33 passed, 0 failed, both runs, including 5 real `stripped_pair` sub-assertions against the
  worktree's actual `src/logs/dual_log/` — nothing skipped).
- All 5 touched files pass `python -m py_compile`; an AST sweep for `FunctionDef`/
  `AsyncFunctionDef` nodes with `end_lineno - lineno + 1 >= 50` returns empty across the whole
  `dev/display/` tree (including `jsonl_exploration/`); `wc -l` on every file stays comfortably
  under 400 (largest touched file is `test_hover_map.py` at 358).
- No report/artifact directories were left behind: `jsonl_exploration/0N_reports/` directories that
  verification runs would have created were never actually written (backup and split runs called
  `scan_jsonl()` directly and captured the returned string, bypassing the `main()`/`REPORTS_DIR.
  mkdir()` file-write path entirely) — confirmed via `git status --short dev/display/` showing only
  the 5 intentionally-edited `.py` files plus the two `DOCS.md` files, nothing untracked. A stray
  `__pycache__/` from the `importlib`-based runs was removed too (already gitignored, cleaned up
  anyway for tidiness).

## Cross-reference

See `process-docs/proxy_instrumentation/` for the immediately-prior cohesion-refactor milestone this
one's approach and verification method are modeled on, including the `block_dev_imports_src` hook's
column-0-only regex behavior (relevant here too, though no file in `dev/display/` needed a new
sibling module, so it never actually came up in practice this time).
