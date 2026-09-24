# t2_launch_tab split under the 400 LOC and 50 line limits — 2026-09-24

`dev/session_launcher/t2_launch_tab.py` was 442 LOC and held `_case_space_switch_units` at 59 lines. It is now a 92 LOC runner plus `t2_fixtures.py`, `t2_launch_cases.py`, `t2_workflow_cases.py`, `t2_space_switch_cases.py`.

## Decisions

- `_EXPECTED_PROJECTS` and `_ROOT_DIR` live in `t2_fixtures.py` because two case modules use them. `_EXPECTED_HEADERS` is used by one module and stays there.
- `_case_space_switch_units` is a caller of five `_check_*` functions. One `MagicMock` (`fake`) is created in the case function and passed to the checks in the original order, because the second check flips `CGPreflightPostEventAccess` to True and resets the request mock, and the third reuses the same object. Do not give each check its own mock without re-proving equivalence.
- The runner still calls `-m dev.session_launcher.t2_launch_tab --case <name>` per case; the report code and the `_CASES` table stayed in the runner.

## Equivalence proof

Before and after run of `python -m dev.session_launcher.t2_launch_tab`, stdout diff with the `- time:` line removed: identical except the random temp HOME path printed by the `log_isolation` case. The tracked `md/t2_launch_tab.md` is rewritten by every run and was restored with `git checkout`.
