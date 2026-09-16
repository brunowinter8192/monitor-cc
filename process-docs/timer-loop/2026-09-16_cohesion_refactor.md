# 2026-09-16 — Cohesion refactor of dev/timer-loop/

## Task

`dev/timer-loop/` had two size-threshold violations against the project code standard: a file
at or above 400 LOC, and functions at or above 50 lines. Measured before this session:

```
466 p1_scan_bg_completion_wordings.py  [_build_report 221]
243 p3_project_scope_incident_probe.py [test_writer_stamps_project_e2e 53]
122 test_abort_stamp_scope.py          [test_abort_stamp_scope_workflow 58]
```

Goal: every module under 400 LOC, every function under 50 lines, behavior unchanged, no
comments/docstrings added beyond what already existed.

## What changed

- `p1_scan_bg_completion_wordings.py` split into three files by concern:
  - `p1_scan_bg_completion_wordings.py` (67 LOC) — entry script, INFRASTRUCTURE + ORCHESTRATOR
    only (`main()`), imports everything else.
  - `bg_completion_scan.py` (175 LOC) — corpus-scanning concern: candidate-block extraction,
    TN/bare structural filters, dedup, mechanism-verdict evaluation. Utility module
    (INFRASTRUCTURE + FUNCTIONS, no orchestrator).
  - `bg_completion_report.py` (275 LOC) — report-building concern. `_build_report` (was 221
    lines) split into one function per markdown `##` section (`_report_header_and_corpus`,
    `_report_method_and_contamination`, `_report_q1`, `_report_q1b`, `_report_q2`, `_report_q3`,
    `_report_q4`, `_report_exit_anomaly`, `_report_dedup`), each returning a list of lines that
    `_build_report` concatenates. Longest function in the whole directory after the split:
    `_report_q3` at 42 lines.
- `p3_project_scope_incident_probe.py` (243 -> 248 LOC, same file, no split needed — it was
  already under 400): pulled the fixture classes/functions (`_FakeHeaders`, `_FakeRequest`,
  `_FakeFlow`, `_ack_text`, `_payload_with_user_text`) that were nested inside
  `test_writer_stamps_project_e2e` (53 lines) out to module level. The test function itself is
  now 15 lines. This is a pure code move — the extracted fixtures do not touch the two imports
  (`proxy.pending_bg_state`, `proxy.addon`) that make this script dead code (see Gotchas below),
  so moving them out doesn't change reachability at all.
- `test_abort_stamp_scope.py` (122 -> 142 LOC): `test_abort_stamp_scope_workflow` (58 lines)
  split into `_spawn_test_fixtures`, `_run_abort_and_checks`, `_teardown_fixtures`,
  `_print_summary`, called in sequence from the now-9-line orchestrator. try/finally structure
  preserved exactly (proc_killed/proc_live still initialized to `None` before the try, so a
  setup failure still tears down safely — I did not fold setup into the try body via a
  ctx-returning helper because that would have changed the None-guard behavior on setup failure,
  which is an untested edge case I did not want to touch).

## Hazard classification (all three scripts)

None of the three scripts touch the macOS desktop (no window moves, no Space switches, no
hotkeys, no monitor restart):

- `p1_scan_bg_completion_wordings.py` — read-only. Reads dual-log jsonl, writes a report file.
- `p3_project_scope_incident_probe.py` — dead code. Both imports it needs
  (`src/hooks/block_timer_pending_bg.py`, `src/proxy/pending_bg_state.py`) were removed in
  earlier milestones (see `process-docs/timer-loop/2026-08-17_*`). Confirmed neither file exists
  on this tree before touching anything. Calling `test_writer_stamps_project_e2e()` — old or new
  — raises `ModuleNotFoundError: No module named 'proxy.pending_bg_state'` immediately, before
  ever reaching the fixture classes. This was true before my change too (the import statement
  was always the first thing in the function body).
- `test_abort_stamp_scope.py` — mutating, but only against its own fixtures. Read
  `src/menubar/bg_timer.py` (`_abort_bg_sleep_timers`, `_resolve_pid_output_file`) before running
  anything: it only calls `os.kill()` on the exact PIDs passed to it by the caller, and only
  writes a stamp to a `.output` file resolved via `lsof -p <pid>` for that same PID. The test
  passes it only the PID of a `sleep` subprocess it spawned itself. The one real side effect is
  an appended line in the real menubar app-support log (`_MENUBAR_LOG`) — this was already true
  before my change (see DOCS.md, unchanged) and is not a desktop-driving action. I ran it.

## Verification method (per file)

- **p1**: built a synthetic 2-file jsonl corpus in `/tmp` covering both TN-family and bare-family
  candidates, one canonical-timer command, one non-canonical command, and one exit-code-144
  anomaly (to exercise every `_build_report` section including the anomaly branch). Ran the
  pre-split backup (temporarily copied into `dev/timer-loop/` itself, because `WORKTREE_ROOT =
  Path(__file__).resolve().parents[2]` depends on the file living at the same directory depth —
  copying it to `/tmp` directly breaks that path math) and the post-split entry script against
  the same corpus, diffed the two generated reports with the `Generated:` timestamp line
  stripped. First diff caught a real transcription mistake on my part (`"this covers the
  completion side"` vs the original `"this is the completion side"` — I mistyped it moving the
  text into `bg_completion_report.py`). After the fix: byte-identical.
  **If you touch this module again**: the pre-split-backup-must-live-at-the-real-relative-depth
  gotcha will bite you again immediately if you copy it to `/tmp`. Copy it into the real
  directory under a throwaway name, run it, delete it before committing.
- **p3**: `test_writer_stamps_project_e2e` can't run its real logic either before or after (dead
  import, see above), so there's no meaningful diff-the-output test. Instead: loaded both the
  pre-split backup and the post-split file via `importlib.util.spec_from_file_location`, called
  `test_writer_stamps_project_e2e()` on both, and asserted the caught exception's
  `(type(e).__name__, str(e))` tuple matches — it does. Also directly diffed (dedented) the
  extracted class/function bodies against the pre-split versions to confirm the move didn't
  alter a single character of the fixture logic.
- **test_abort_stamp_scope.py**: this one is a real, currently-functional integration test that
  spawns real subprocesses (see hazard classification above), so I ran the pre-split backup and
  the post-split file back to back and compared stdout structurally (6 `[OK ]` lines in the same
  order, `All 6 checks passed.`, exit code 0 both times). The only differing substrings are PIDs,
  timestamps, and the random `mkdtemp` suffix — all expected to vary run-to-run even without any
  code change.

## Gotchas / things I'd tell my replacement

- `dev/timer-loop/` files import sibling modules as *plain* module names (`from
  bg_completion_scan import ...`), not as a package (`dev.timer_loop.bg_completion_scan` would
  fail — the directory name has a hyphen, which is not a valid Python package-path segment
  anyway). This works because Python auto-adds the running script's own directory to
  `sys.path[0]`; the entry script also does it explicitly
  (`sys.path.insert(0, str(Path(__file__).resolve().parent))`) so it's not fragile to how it's
  invoked (e.g. from a different cwd).
- `p1`, `p3` keep their number-prefixed filenames because they are the documented CLI entry
  points (`Usage:` in their own docstrings) — the milestone prompt is explicit that entry scripts
  keep their exact filenames including the prefix, and that *new* sibling modules must NOT get a
  number prefix (a leading digit is not a valid Python identifier for a plain-name import, which
  is exactly the import style this directory uses).
- `p3_project_scope_incident_probe.py` is dead code end to end (confirmed again this session —
  see `src/hooks/`, `src/proxy/` — neither `block_timer_pending_bg.py` nor
  `pending_bg_state.py` exists). I did not attempt to make it runnable; that's explicitly out of
  scope (Negative scope: no features, no behavior changes beyond the split).
- I did not touch `p2_*` (`md/p2_pending_bg_state_probe_*.md` reports exist under `md/` but there
  is no `p2_*.py` script in the directory — it was presumably already deleted in an earlier
  milestone; its reports are historical data, not something this refactor's scope touches).

## Result

```
     275 bg_completion_report.py
     175 bg_completion_scan.py
      67 p1_scan_bg_completion_wordings.py
     248 p3_project_scope_incident_probe.py
     142 test_abort_stamp_scope.py
```

All under 400 LOC. Longest function directory-wide: `_report_q3` in `bg_completion_report.py` at
42 lines. All under 50.
