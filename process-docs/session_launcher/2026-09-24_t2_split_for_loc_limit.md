# t2_launch_tab split under the 400 LOC and 50 line limits — 2026-09-24

`dev/session_launcher/t2_launch_tab.py` was 442 LOC and held `_case_space_switch_units` at 59 lines. It is now a 92 LOC runner plus `t2_fixtures.py`, `t2_launch_cases.py`, `t2_workflow_cases.py`, `t2_space_switch_cases.py`.

## Decisions

- `_EXPECTED_PROJECTS` and `_ROOT_DIR` live in `t2_fixtures.py` because two case modules use them. `_EXPECTED_HEADERS` is used by one module and stays there.
- `_case_space_switch_units` is a caller of five `_check_*` functions. One `MagicMock` (`fake`) is created in the case function and passed to the checks in the original order, because the second check flips `CGPreflightPostEventAccess` to True and resets the request mock, and the third reuses the same object. Do not give each check its own mock without re-proving equivalence.
- The runner still calls `-m dev.session_launcher.t2_launch_tab --case <name>` per case; the report code and the `_CASES` table stayed in the runner.

## Equivalence proof

Before and after run of `python -m dev.session_launcher.t2_launch_tab`, stdout diff with the `- time:` line removed: identical except the random temp HOME path printed by the `log_isolation` case. The tracked `md/t2_launch_tab.md` is rewritten by every run and was restored with `git checkout`.

## Phase 3 additions (same session, later task)

- B21 traced: `_build_start_command(root, project)` is a pure string builder (`shlex.quote`), `session_launch.py` and `launch_controller.py` never stat any path of the project list, and `MONITOR_CC_ROOT` is only patched. So no code path is machine dependent through these strings. `_ROOT_DIR` in `t2_fixtures.py` is now the fake `/fake/monitor-cc-root`. `_EXPECTED_PROJECTS` stays the ten real paths on purpose: `project_rows` asserts it equals `launch_config.LAUNCH_PROJECTS`, which hardcodes the same ten paths in production code; a temp-dir replacement would break that assertion.
- A7: the `- time:` line was removed from the report bodies of `t1_autojump_removal`, `t2_launch_tab` and `t3_tab_click`, and the isolated-HOME temp path was removed from the detail cells (`t2` `log_isolation`, `t1_autojump` isolation now print `<home>/...` relative paths). Two consecutive runs of each produce byte-identical `md/` reports (cmp), all `RESULT: PASS`. The probes `s0`, `s1`, `s2`, `p2` still carry a time line; they are not tests.
