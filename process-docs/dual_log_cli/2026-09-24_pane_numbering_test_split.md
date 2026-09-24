# test_reqs_pane_numbering split under the 400 LOC limit — 2026-09-24

`dev/dual_log_cli/tests/test_reqs_pane_numbering.py` was 591 LOC. It is now a 57 LOC runner plus `reqs_pane_numbering_fixtures.py` (270), `reqs_pane_numbering_basic_checks.py` (150), `reqs_pane_numbering_ownership_checks.py` (117), `reqs_pane_numbering_unmapped_checks.py` (40). The helper modules have no `test_` prefix so pytest does not collect them as test files.

## Decisions and traps

- `check()`, `PASS_LIST` and `FAIL_LIST` live in the fixtures module; the runner imports the same list objects, so it still reads the totals. The 19 `test_*` functions keep their names and call order.
- A hook rejects edits that add a `src` import to a new dev file. `_raises_text` first landed in the fixtures module and needed `UnknownRequestNumberError` there; it was moved into the ownership checks module (its only user), which already imports the exception.
- The runner inserts the project root into `sys.path` before importing the helper modules, because they import `src.*`.

## Equivalence proof

A wrapper loaded the pre-split file (`git show HEAD:`) and the new runner, ran `test_reqs_pane_numbering_workflow()`, and dumped the ordered `PASS_LIST`, `FAIL_LIST`, captured stdout and exit code to JSON. Both files are byte-identical (`cmp`): 70 passed checks, 0 failed, same names in the same order.

## Note on DOCS.md

The area DOCS.md had no entry for `test_reqs_pane_numbering.py` before this change; entries for the runner and the four new modules were added. Other LOC values in that file were not audited.

## Phase 3 additions (same session, later task)

- B9: `test_local_time.py` no longer depends on the host time zone or on `now()`. The two affected cases loop over `Asia/Tokyo` and `America/Los_Angeles` inside a `_fixed_zone` context manager (sets `TZ`, calls `time.tzset()`, restores) with fixed instants: `2026-09-04T18:16:02.582Z` is `2026-09-05 03:16:02` in Tokyo and `2026-09-04 11:16:02` in Los Angeles; `2026-09-04T15:30:00Z` lands on local day 09-05 in Tokyo, `2026-09-05T06:30:00Z` on local day 09-04 in Los Angeles. The old "differs from UTC digits" check was skipped on a UTC machine; the new checks always run. Proven by passing under `TZ=UTC`, `Asia/Kolkata`, `America/New_York`, and by a mutated copy (wrong expected clock) that failed one check.
- A1-A3: all 17 test files plus `test_reqs_pane_numbering.py` (19 strands; `reqs_pane_numbering_fixtures.py` has the raising `check`) are strand suites. `test_reqs_pane_numbering.py` is the runner whose strand names are the imported `test_*` functions. `strand_abort_probe.py` was added here and works on any converted suite in the other areas too.

Note: the pass counts of the 17 files before and after are equal (for example `test_turns.py` 27, `test_msgs_sys_delta.py` 26, `test_project_display.py` 23).
