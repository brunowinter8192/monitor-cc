# 2026-09-16 — dev/strip_fp_tool_result/ cohesion split

## What happened

`dev/strip_fp_tool_result/audit_tool_result_sr_strips.py` was a single 659-LOC file
with two functions over the 50-line threshold (`_render_report` at 246 lines,
`_scan_file` at 73 lines). Split into four files with no behavior change:

- `audit_tool_result_sr_strips.py` (54 LOC) — entry script, keeps its exact filename.
  Kept the original module docstring verbatim. INFRASTRUCTURE (two `from X import`
  lines) + ORCHESTRATOR (`main()`), no FUNCTIONS section — matches the
  `dev/desktop_detection/01_probe.py` pattern (entry script that only wires
  sibling-module functions together has an empty FUNCTIONS section).
- `audit_scan.py` (301 LOC) — owns the `importlib`-loaded real pass functions and
  regex registries, `PASSES`/`_ASSERT_NO_DESCEND`/`_FIXED_MOD_MAP`, corpus discovery,
  and the per-request/per-pass/per-block scan loop, plus the git-lock ground-truth
  check.
- `audit_report.py` (387 LOC) — owns rendering: one function per report section
  (`_render_corpus_section`, `_render_ground_truth_table`,
  `_render_ground_truth_narrative`, `_render_assertion_section`,
  `_render_occurrence` + `_render_occurrences_section`, the aggregate-table trio,
  the genuine-injection trio) composed by a 15-line `_render_report`.
- `audit_verdicts.py` (53 LOC) — pure-constants module (`_MANUAL_VERDICTS` +
  the `_MC`/`_PO`/`_W2`/`_CR` filename keys), INFRASTRUCTURE only, no FUNCTIONS/
  ORCHESTRATOR section — matches the `dev/cursor_edges/cursor_edges_constants.py`
  pattern for constants-only modules.

Longest function after the split: `_process_block_ops` in `audit_scan.py` at 41
lines (was part of the 73-line `_scan_file`). All four files are under 400 LOC.

## How the split was actually done — read this before repeating this kind of split

The safe way to move ~250 lines of prose-heavy markdown-report-building code
(backticks, curly em-dashes, escaped apostrophes) between files is **not** to
retype it by hand. Retyping risks silent corruption of the exact string content,
which nobody would catch since Python doesn't error on a wrong-but-valid string.

Instead: back up the original file, then write a throwaway Python script (I used
`/tmp/build_split*.py`, never staged) that does `L = f.readlines()` on the backup
and slices exact 1-indexed line ranges (`''.join(L[a-1:b])`) straight into new
function bodies. Every `lines.append(...)` block in the original `_render_report`
was already indented at exactly 4 spaces (the function's own body indent) or 8
spaces (inside a `for`/`if` one level in) — extracting a 4-space range needs zero
transformation, and extracting an 8-space range needs a single `dedent4()` helper
(strip exactly 4 leading spaces per line, continuation lines included — they were
indented 22 spaces to align under the opening quote, so dedenting by 4 leaves
valid-but-unaligned continuation indentation, which Python accepts fine inside
parens). This made a mechanically-verifiable split possible: I diffed the final
generated file against the manually-read original text side by side and it matched
byte for byte, because it *was* the same bytes, just relocated.

Concretely reusable ranges (1-indexed, inclusive, against the pre-split file) if
anyone needs to re-derive this: module docstring 1-36; importlib bootstrap 37-81;
`LOGS_DIR`/`OUT_FILE`/`SELF_SESSION_MARKER` 83-89; `PASSES` 91-104; `_SR_FAMILY_PASSES`
106-112; `_ASSERT_NO_DESCEND` 119-122; `_FIXED_MOD_MAP` 124-134; `_MANUAL_VERDICTS`
136-186; `_render_report` body 410-655 with section boundaries at lines 417
(Corpus), 442 (Ground-truth), 491 (Assertion), 506 (Occurrences), 542 (Aggregate),
597 (Genuine injection).

One nested function had to be promoted to module level: `_verdict_of` was defined
*inside* `_render_report` (closure over nothing, just organizational) and used both
in the aggregate section and the genuine-injection section. Splitting those two
sections into separate top-level functions means `_verdict_of` can no longer be a
closure — it became an ordinary top-level function in `audit_report.py`. This is
a mechanical de-nesting, not a logic change (verified: same lookup, same default).

One dead variable was deliberately kept: `sr_genuine = sr_verdicts.get('genuine CC
injection', 0)` in the original was computed and never read anywhere in the
function. I kept the equivalent dead assignment in `_render_sr_verdict` rather than
"cleaning it up" — removing it would be an uninstructed improvement outside this
milestone's scope, and the milestone explicitly forbids behavior changes.

## Verification — what was actually run, and why not the obvious thing

The obvious verification ("run the script before and after against the real
corpus and diff") does not work here: by the time this split started, the real
corpus at `/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log/` had
grown to 20+ files, several hundred MB to 570MB each (`sweepitdev` alone is
477MB), all live-growing sessions (including this very worker's own dual-log).
Running the full script against that corpus would take a long time and produce a
different result on every invocation regardless of code correctness, since new
requests get appended between runs — the module's own docstring already documents
this liveness problem for the ORIGINAL 5-file corpus, and it is much worse now.

What I did instead, per the milestone's explicitly allowed second option (call
pre-split and post-split functions with identical synthetic input, load the
pre-split backup via `importlib.util.spec_from_file_location`):

1. Loaded the pre-split file (backed up to `/tmp/audit_orig_backup.py` before any
   edits) via `importlib.util.spec_from_file_location`, with `sys.path` and
   `MONITOR_CC_ROOT` set up manually first — the backup file's own
   `os.path.dirname(__file__)`-based bootstrap breaks when loaded from `/tmp`, so
   `os.environ['MONITOR_CC_ROOT']` must be set (not `setdefault`'d) to the real
   repo root *before* `exec_module` runs the backup's top-level code.
2. Patched `LOGS_DIR` (both the backup module's own `LOGS_DIR` AND, on the
   post-split side, **both** `audit_scan.LOGS_DIR` and `audit_report.LOGS_DIR`)
   to a small frozen `/tmp/frozen_sample/` directory. Gotcha: `audit_report.py`
   does `from audit_scan import LOGS_DIR`, which copies the name at import time —
   patching `audit_scan.LOGS_DIR` after import does **not** change what
   `audit_report.py` sees. Both must be patched for a test harness. This is not a
   real bug (production code never reassigns `LOGS_DIR` at runtime), purely a
   test-harness gotcha worth remembering for the next split verification.
3. Ran `backup.main()` and the new `audit_tool_result_sr_strips.main()` against
   the same frozen files, with `OUT_FILE` on both sides patched to separate `/tmp`
   paths, and diffed the two output strings.

Two frozen inputs were used, built up incrementally:
- 90 lines of *real* production dual-log data (5-line heads of two small real
  worker session logs) — produced 0 tool_result-level occurrences on both sides,
  proving the full pipeline (discovery → per-pass scan → ground-truth check →
  every report section in its empty/zero state) byte-identical, but not
  exercising the occurrence-recording code path at all.
- One hand-built synthetic JSONL line (`/tmp/frozen_sample/sample_e_original.jsonl`)
  with a `tool_result` block whose content starts with a real
  `PreToolUse:Bash hook error: [python3 /path/to/hook.py]: ` prefix (matches
  `strip_hook_prefix.py`'s `_HOOK_PREFIX_RE` exactly) — this reliably triggers
  `_apply_hook_prefix_strip` and exercises `_process_block_ops`,
  `_render_occurrence`, the non-empty occurrences table, and the non-SR aggregate
  table. Report output was byte-identical (`OLD LEN 7496 NEW LEN 7496`, string
  equality `True`) after fixing the `LOGS_DIR` double-patch gotcha above.

What was NOT exercised by a real trigger: the SR-family "found" verdict branch
(`_render_sr_found`) and the "pending manual review" branch (`_render_sr_pending`).
Triggering `_apply_first_pass`'s SR branches requires a role='user' top-level text
block matching one of `strip_sr.py`'s fixed templates positioned so it also shows
up as a tool_result pre-pass block type — the audit's own report says this
happened exactly once in ~660 real requests across 5 sessions, and reproducing it
synthetically would require reverse-engineering `_apply_first_pass`'s branch
conditions in `message_passes.py` in detail for marginal additional confidence.
I judged this not worth the time given these two functions were produced by the
same mechanical line-slice-and-dedent extraction described above (byte-for-byte
copy from the original, visually diffed against the original source and
confirmed identical) rather than retyped — the risk profile for an untested
mechanically-extracted function is much lower than for hand-written code.

## Hazard classification (for the record)

`audit_tool_result_sr_strips.py` (and its three new sibling modules) are
**read-only**: they only glob and read `*_original.jsonl` files and write a
markdown report under `dev/strip_fp_tool_result/md/`. No desktop automation, no
window/Space control, no hotkeys, no monitor restart. Safe to run/import, subject
only to it being slow against the current multi-hundred-MB corpus.

## Pointers

- Concern-boundary reasoning and the module-format exceptions used
  (entry-script-with-empty-FUNCTIONS, constants-only-module-with-no-FUNCTIONS)
  are drawn from real examples already in the repo: `dev/desktop_detection/01_probe.py`
  and `dev/cursor_edges/cursor_edges_constants.py`. Look there first before
  inventing a new shape for a similar split.
- The `_MANUAL_VERDICTS` table in `audit_verdicts.py` is keyed by filenames from
  the OLD 5-file corpus (`_MC`/`_PO`/`_W2`/`_CR`) that no longer exist in the
  current `src/logs/dual_log/` — that's expected, it's a frozen historical
  finding, not something to "fix" against the current corpus.
