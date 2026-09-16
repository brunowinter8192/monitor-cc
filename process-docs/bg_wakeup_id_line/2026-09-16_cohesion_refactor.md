# Cohesion refactor of dev/bg_wakeup_id_line/ (2026-09-16)

## Task

Split `p1_scan_launch_ack_wordings.py` (291 LOC, `_build_report` 93 LOC) to satisfy the
50-LOC-function threshold. No behaviour change allowed. Full task text lives in the issue that
spawned this session, not repeated here.

## Scope was smaller than the previous 3 sessions in this batch — no multi-file split needed

Unlike `cc_injection_inventory`, `tool_use_errors`, and `sleep_pattern_analysis` (all handled in
prior sessions this batch), `p1_scan_launch_ack_wordings.py` was 291 LOC — under the 400-LOC
file threshold already. Only the function threshold was violated (`_build_report`, 93 LOC). The
milestone's own "Desired result" is "every module under 400 LOC and every function under 50
lines" — it does NOT mandate a multi-file split when the file itself isn't oversized. Extracted
6 report-section helper functions (`_report_header_and_corpus`, `_report_contamination_trap`,
`_report_dedup_importance`, `_report_live_observed_crosscheck`, `_report_distinct_wordings`,
`_report_additional_wordings_note`) INSIDE the same file instead of inventing sibling modules —
that would have been a cosmetic split for a file that was never oversized. Final file: 327 LOC,
longest function 36 lines (`_scan_file`, pre-existing, untouched — already compliant).

**Lesson for whoever runs the next one of these:** check the file's own LOC first. If it's
already under 400 and only a function is oversized, extracting helpers in place is the correct
scope — don't manufacture new files just to mirror the pattern from a bigger prior split.

## p2 and p3 in this directory: read in full, confirmed compliant, left untouched

Both `p2_bg_escape_probe.py` (339 LOC) and `p3_strip_interrupt_marker_probe.py` (243 LOC) were
read in full per the task's file-reading requirement (checking whether they import anything from
`p1` — they don't; all three `p1`/`p2`/`p3` scripts are independent siblings sharing only the
`md/` output directory and the DOCS.md file). Neither has a function at or above 50 lines
(longest: `test_real_tmux_roundtrip` in p2 at 36 lines). Confirmed via the same AST longest-
function scan used in every prior session of this batch (`ast.walk` for `FunctionDef`, `end_lineno
- lineno + 1`). Neither was modified.

## Hazard classification (done before running anything)

- **p1** (the only file actually split): READ-ONLY. Reads `src/logs/dual_log/*_original.jsonl`
  (main-repo checkout), writes one markdown report. No desktop/tmux/hotkey/Space interaction.
- **p2**: MUTATING, but scoped and self-contained — `test_real_tmux_roundtrip` spawns a real
  detached tmux session (`__bg_escape_probe_<unix-ts>__`), sends a real Escape byte into it via
  the PRODUCTION `_send_escape_key()`, verifies via `tmux capture-pane`, then kills the session in
  a `finally` block. This is a tmux multiplexer session, not a macOS window/Space — no
  `osascript`, no window manager interaction, no hotkey delivered to any of the user's real panes.
  Did NOT run this script this session since p2 needed no changes — noted here only because the
  task requires classifying every script in the directory before running anything, and a future
  agent touching p2 needs this classification on record.
- **p3**: READ-ONLY. Builds all fixtures in-process, no subprocess/filesystem/tmux calls beyond
  writing its own report. Did not run (no changes needed).

## Verification could not use a live real-input diff — the hardcoded corpus is gone

`p1`'s `CORPUS_FILES` is a hardcoded list of 4 specific dual-log filenames from 2026-07-29
(`api_requests_opus_monitor_cc_1785336796_original.jsonl` etc.). Checked all 4 against the real
`src/logs/dual_log/` in the main repo before attempting anything — none exist anymore (the dual-
log directory rotates/gets cleaned; this is documented as expected behaviour in other areas'
process-docs, e.g. `cc_injection_inventory`). Running `p1.main()` unmodified against production
paths would raise `FileNotFoundError` for both the pre-split and post-split code equally — not
useful for a diff-based proof. Treated this as the "no real input exists" case the milestone
prompt explicitly anticipates.

**Second constraint that shaped the verification approach:** `p1`'s output filename is a fixed
literal (`launch_ack_wordings_20260729.md`, NOT timestamped like p2/p3's reports) and that exact
file is already committed/tracked in `dev/bg_wakeup_id_line/md/`. A naive "just run the real
script" verification would have overwritten a tracked file with synthetic-corpus output. Backed
up the tracked file to `/tmp/bwil_verify/launch_ack_wordings_20260729_ORIGINAL_TRACKED.md` before
touching anything, and — more importantly — never pointed the real module's own `REPORT_DIR` at
the real `md/` directory during verification at all: every full-pipeline test run monkeypatched
`LOG_DIR`/`CORPUS_FILES`/`REPORT_DIR` to `/tmp/bwil_verify/...` paths on the loaded module object
(both pre-split and post-split), so the tracked file was never at risk of being overwritten in
the first place. Verified after the fact with a diff against the backup anyway (`diff` exit 0) —
belt and suspenders.

## Behaviour-unchanged proof

Two layers, both passed:

1. **Synthetic per-function check on the split target.** Loaded the pre-split backup
   (`/tmp/bwil_verify/p1_pre_split.py`) via `importlib.util.spec_from_file_location`, with `src/`
   seeded onto `sys.path` first (the pre-split module's own `WORKTREE_ROOT`-derived `sys.path`
   insert resolves to `/tmp` when the file is loaded from a `/tmp` backup path, which is wrong —
   `sys.path` must be seeded by the TEST HARNESS before `exec_module`, not left to the loaded
   module to fix up itself). Built a synthetic `findings` dict (2 distinct wordings, one with 2
   occurrences across sessions) and called `pre._build_report(...)` vs. post-split
   `_build_report(...)` — identical output apart from the `Generated: <timestamp>` line (both
   pre- and post-split call `datetime.now(timezone.utc)` at report-build time; this is original,
   unmoved behaviour). Also checked the `findings == {}` empty-corpus branch separately (it has
   its own early text path — "0 candidate launch-ack blocks found"). Both matched exactly with
   the timestamp line excluded.
2. **Full-pipeline `main()` run with a synthetic corpus file**, for confidence beyond the report-
   builder alone (covers `_scan_file`'s dedup-by-message-count-delta logic and the
   INFRASTRUCTURE/ORCHESTRATOR/FUNCTIONS reordering — see next section — actually wiring
   correctly at runtime, not just resolving names). Wrote a 2-line synthetic dual-log JSONL
   (`/tmp/bwil_verify/fake_corpus/fake_session_original.jsonl`) with one message repeated
   cumulatively (to exercise the delta-dedup) plus one second wording. Ran `main()` from both the
   pre-split and post-split module objects with `LOG_DIR`/`CORPUS_FILES`/`REPORT_DIR`
   monkeypatched to isolated `/tmp` paths. Both produced "2 distinct wording(s), 2 requests
   scanned" and byte-identical report files (timestamp line excluded, `diff` exit 0).

## Section-order fix folded into the same rewrite

The pre-existing file had `# FUNCTIONS` BEFORE `# ORCHESTRATOR` (all helper functions, then
`main()` at the very bottom under its own later `# ORCHESTRATOR` marker) — this violates the
mandated INFRASTRUCTURE -> ORCHESTRATOR -> FUNCTIONS order. Since the milestone instructions
require this order "in every file you create or rewrite" and this file was being rewritten
anyway to fix the function-length violation, moved `main()` up to directly follow INFRASTRUCTURE
under its own `# ORCHESTRATOR` marker, with `# FUNCTIONS` and all helpers following after. This
is purely a physical reordering — Python resolves names at call time, not definition time, so
`main()` calling `_scan_file`/`_build_report` (defined further down in the file) is not a forward-
reference error. No behaviour change; confirmed by both proofs above still passing after the move.

## Files NOT touched

`dev/bg_wakeup_id_line/md/*.md` (all pre-existing tracked reports, including the one `p1` would
normally overwrite on a real run) were left untouched — confirmed via `diff` against a pre-edit
backup. `p2_bg_escape_probe.py` and `p3_strip_interrupt_marker_probe.py` were read in full but not
modified (already compliant, see above).
