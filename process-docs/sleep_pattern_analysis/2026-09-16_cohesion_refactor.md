# Cohesion refactor of dev/sleep_pattern_analysis/ (2026-09-16)

## Task

Split `analyze.py` (361 LOC, `_build_report` 103 LOC, `_sleep_contexts` 52 LOC) to satisfy the
400-LOC-file / 50-LOC-function thresholds. `classify.py` (92 LOC, longest function 41 LOC) was
already compliant and untouched except for one doc-reference update (see below). No behaviour
change allowed. Full task text lives in the issue that spawned this session, not repeated here.

## Hazard classification (done before running anything)

`analyze.py` is READ-ONLY with respect to the machine: it reads session JSONL files under
`~/.claude/projects/*/*.jsonl` and writes one markdown report to `--out` (default a stale
hardcoded path under `dev/sleep_pattern_analysis/`). No `osascript`, no `tmux`, no window/pane/
hotkey/Space APIs, no monitor restart. Confirmed by reading the full file before editing. Safe to
run for verification, EXCEPT for one caveat that changed how verification was done — see next
section.

## Why this split used a synthetic fixture instead of a live real-data diff

Unlike the two prior cohesion-refactor sessions in this area (`cc_injection_inventory`,
`tool_use_errors`), this script's real input — `~/.claude/projects/*/*.jsonl` — is NOT a static
corpus. It's live: every Claude Code session on the machine (including THIS worker session, and
any concurrent session the user is running, per the task's own hazard warning) continuously
appends to files under this tree. `_collect_events`'s file selection is an mtime filter
(`if mtime < cutoff: continue`), not a content-timestamp filter — so a file that ANY concurrent
session touches between two verification runs changes the result set, independent of whatever
code change is being verified. A "run before, run after, diff" proof would be comparing two
different inputs, not proving the code split preserved behaviour.

Treated this the same as "no real input exists" (the milestone prompt's explicit fallback
clause) and built a small, fully-controlled fixture instead:
`/tmp/spa_verify/fixture_projects/projA/session1.jsonl` — 6 synthetic BLOCKED
`block_chained_sleep` events covering the shapes that actually occur in this codebase's own hook
patterns: plain chain (`echo hi && sleep 5 && echo done`), `kill`/`pgrep` load-bearing pattern,
a `for` loop body, a heredoc-embedded fake sleep, the canonical `sleep N && echo done` form, and
a `VAR=val sleep N` assignment-prefixed form. `PROJECTS_DIR` is a module-level `Path` constant
read at call time inside `_collect_events`, not a CLI arg — reassigning
`sleep_events.PROJECTS_DIR = Path("/tmp/spa_verify/fixture_projects")` after import (module
monkeypatch, in the throwaway verification script only, never in committed code) redirects the
whole pipeline without touching the production code path or its CLI surface.

**One fixture-construction trap:** the hook-block detection requires the LITERAL string
`block_chained_sleep` to appear in the raw JSONL line (pre-filter: `TARGET_HOOK not in line`) AND
inside the `_BLOCK_RE`-captured hook-path group specifically (`TARGET_HOOK not in m.group(1)`).
A first fixture draft used a generic `/path/to/hook.py` placeholder and silently produced zero
events — not an error, just an empty result, easy to mistake for "no sleep patterns in this
window" instead of "fixture doesn't match the matcher". Renamed the placeholder to
`/path/to/block_chained_sleep.py` and events appeared. **Lesson: when a fixture-based check
returns an empty/zero result, verify the fixture actually threads the needle the code's own regex
requires before trusting the zero as a real finding.**

## Module split (final)

| File | LOC | Concern |
|---|---|---|
| `analyze.py` | 54 | entry: CLI arg parsing, orchestrator |
| `sleep_events.py` | 108 | walk session JSONL, resolve BLOCKED `block_chained_sleep` events to triggering commands (two-pass tool_use_id/uuid map) |
| `sleep_parsing.py` | 116 | extract per-sleep context (cmd_before/after, chain_op, in_loop, is_canonical, in_heredoc) from one command string |
| `sleep_report.py` | 134 | build the markdown report section by section, delegate final section to `classify.add_classification()` |
| `classify.py` | 92 | unchanged — token classification constants + `add_classification()` |

Dependency direction: `analyze -> {sleep_events, sleep_parsing, sleep_report}` (fan-out from the
orchestrator), `sleep_report -> classify` (unchanged from before the split — `classify.py` was
already a sibling of `analyze.py`, now a sibling of `sleep_report.py` instead, same bare-import
mechanism). No cycles.

## `_sleep_contexts` split preserved the mutate-in-place report pattern

`_build_report`'s split (103 -> 6 functions: `_build_report`, `_report_header`,
`_build_cmd_before_section`, `_build_cmd_after_section`, `_build_loop_canonical_section`,
`_build_duration_section`) reused the exact "mutate a `lines: list` passed by reference" style
already established by `classify.add_classification(lines, before_counts)` in the pre-existing
code — none of these section-builders return the lines list, they append to it in place (except
`_report_header`, which creates it fresh and returns it since there's nothing to append to yet,
and `_build_cmd_before_section`, which returns `before_counts` because `classify.
add_classification` needs it later). This wasn't an invented pattern — it's what the file already
did, extended consistently.

One thing to get right when splitting this function: the original had a single `n = len(shell_recs)`
computed once and reused across the "in-loop vs naked" text AND the duration-distribution
percentage math further down. Splitting into two separate functions means `n` needs to be
recomputed (cheap, `len()` on an already-materialized list) inside `_build_duration_section`
too — easy to miss since the original defines it once, uses it twice, far apart.

`_sleep_contexts` (52 LOC) split into `_sleep_contexts` (thin loop) + `_build_sleep_context`
(per-match dict) + `_resolve_chain_before` (chain_op/cmd_before) + `_resolve_cmd_after`
(cmd_after) — the last two existed as inline comment-delimited blocks in the original
(`# chain_op and cmd_before`, `# cmd_after: first token after the operator following sleep`),
so the split boundary was already marked by the pre-existing comments.

## Pre-existing doc inaccuracy noted, NOT silently fixed in code

`analyze.py`'s `--out` default is a stale hardcoded path with a fixed date baked in
(`dev/sleep_pattern_analysis/01_reports/sleep_audit_2026-05-24.md`) — clearly a copy-paste
leftover from whenever this script was first written, since the actual `md/` output directory in
this folder holds a file at that exact stale-default path
(`md/sleep_audit_2026-05-24.md` — note: NOT `01_reports/`, a second inconsistency, meaning even
the default path's directory component doesn't match where output ends up when someone forgets to
pass `--out`). Left the CODE untouched per negative scope ("do not change output paths" /
"do not change CLI arguments") — did NOT get explicit approval to fix this one, unlike the
`tool_use_errors` session in this same batch of refactors where the user explicitly authorized a
DOCS-only path correction. Documented the actual default verbatim in the updated `DOCS.md`
instead of restating the old (also wrong) `md/sleep_audit_<date>.md` claim. Also corrected one
Gotcha bullet claiming `cd` into this directory is required for `import classify` to resolve —
empirically false (tested `./venv/bin/python dev/sleep_pattern_analysis/analyze.py` from the
project root, worked fine): Python adds the EXECUTED SCRIPT's own directory to `sys.path[0]`
regardless of the caller's cwd, which is what actually makes the bare sibling imports resolve.
This matters more now since 3 new sibling modules rely on the identical mechanism.

## Behaviour-unchanged proof

Two layers, both passed:

1. **Fixture-based full-pipeline run + diff.** Backed up the pre-split files to
   `/tmp/spa_verify/analyze_pre_split.py` and `/tmp/spa_verify/classify_pre_split.py` before any
   edit (the latter wasn't modified, backed up only for completeness). Built the synthetic fixture
   described above. Ran the pre-split module (loaded via
   `importlib.util.spec_from_file_location`, with `sys.path` seeded so its
   `from classify import add_classification` resolves against the REAL `classify.py`, and its
   `PROJECTS_DIR` monkeypatched to the fixture dir) through `_collect_events` ->
   `_parse_all_sleeps` -> `_build_report` with a fixed `since_dt`. Ran the equivalent through the
   post-split modules (`sleep_events`/`sleep_parsing`/`sleep_report`, same fixture, same
   monkeypatch target on `sleep_events.PROJECTS_DIR`). Both produced `events=6 records=7`. The two
   report strings differed in exactly one line — `Generated: <HH:MM>` — because `_build_report`
   calls `datetime.now()` at report-build wall-clock time in BOTH the pre-split and post-split
   code (this is original, unmoved behaviour, not something the split introduced). Diffing with
   that one line excluded (`grep -v "^Generated:"` both sides) gave `diff` exit 0.
2. **Synthetic per-function check on the largest/highest-risk split**
   (`_sleep_contexts`/`_build_sleep_context`/`_resolve_chain_before`/`_resolve_cmd_after`). Called
   pre-split `_sleep_contexts(cmd)` vs. post-split `sleep_parsing._sleep_contexts(cmd)` across 12
   hand-picked command strings covering every branch this function has: chained ops
   (`&&`/`;`/newline), no-op ("start") chain, loop body, heredoc-embedded false positive, canonical
   form, `VAR=val` assignment prefix, a MIXED-classification token (`rag-cli server restart`),
   sub-second duration (`0.5`), a `./script.sh` relative-path token, a `path/binary` absolute-path
   token needing basename normalization, an `||` fallback op, and a leading-newline "start" case.
   All 12 produced identical list-of-dict output (`assert pre_out == post_out`) —
   `SYNTHETIC _sleep_contexts MATCH: True, 12 cases`.

Verification artifacts (`/tmp/spa_verify/`, including the frozen fixture) were left outside the
worktree, never staged. `dev/sleep_pattern_analysis/__pycache__/` (created by running the split
modules directly during verification) was deleted before commit.

## Files NOT touched

`dev/sleep_pattern_analysis/md/*.md` (pre-existing tracked reports, including the
stale-default-named `sleep_audit_2026-05-24.md`) were left untouched.
