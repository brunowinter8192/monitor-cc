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
