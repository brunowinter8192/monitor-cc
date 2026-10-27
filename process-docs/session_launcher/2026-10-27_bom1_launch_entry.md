# BOM1 added to the Launch tab (2026-10-27)

Worker on branch `launcher-bom1` (based on `integration`, HEAD `40588fb2` at start), area `session_launcher`. Task: a Launch entry for `/Users/brunowinter2000/Documents/wise2627/BOM1`, behaving like the other projects, appended as the LAST entry (index 11, after canvas). Same change as the canvas entry in this area, one project later.

## Change (commit `4bc40709`)

- `src/menubar/launch_config.py`: `LAUNCH_PROJECTS` has 12 entries, BOM1 last. Indices 0-10 stay stable, so the tests that address `_EXPECTED_PROJECTS[0]`, `[7]`, `[9]`, `[10]` stay valid.
- No other production file changed. Validation (`session_launch._validate_request`), panel height (`launch_controller.rebuild`, from `len(LAUNCH_PROJECTS)`) and the label (`launch_panel_ui._project_label`, basename -> `BOM1`) derive from the tuple. Start command: `cd <MONITOR_CC_ROOT> && PATH="$HOME/.local/bin:$PATH" ./src/claude_proxy_start.sh --project /Users/brunowinter2000/Documents/wise2627/BOM1`.
- `/Users/brunowinter2000/Documents/wise2627/BOM1` exists and is NOT a git repo; its parent `wise2627` is not one either and already works in the list. Nothing in `session_launch.py` or `launch_controller.py` stats or git-checks a project path (see the earlier B21 trace in this area), so being a non-repo has no code path to hit.

## Pinned places that moved (the checklist for entry number 13)

- `dev/session_launcher/t2_fixtures.py:_EXPECTED_PROJECTS`: one more path (must equal `LAUNCH_PROJECTS`, asserted in `project_rows`).
- `t2_launch_cases.py:_case_project_rows`: count 12, tags `range(12)`, `want` list ends with `'BOM1'`, result text "12 rows".
- `t2_launch_cases.py:_case_click_handling`: the out-of-range probe moved from `handle_launch_project(11)` to `handle_launch_project(12)`. New assertion before it: launching index 11 on desktop 5 yields `(5, BOM1)` and the path ends with `/wise2627/BOM1`; afterwards `len(launched) == 3`. The assertions use list slices of `launched` (`launched[1:]` for canvas, `launched[2:]` for BOM1), which depend on the order of the clicks in that case; a new click must be inserted before the out-of-range probe.
- `t2_workflow_cases.py:_case_start_command`: only the result text ("12 commands"); the loop over `_EXPECTED_PROJECTS` covers the new project on its own.
- LOC headings: `src/menubar/DOCS.md` launch_config 17; `dev/session_launcher/DOCS.md` t2_fixtures 64, t2_launch_cases 187 (t2_workflow_cases stays 73). Neither DOCS.md contains a project count.
- Report `dev/session_launcher/md/t2_launch_tab.md` changes in two lines (project_rows, start_command) because the reports are deterministic.

## Test results (2026-10-27, headless, isolated HOME, no screen movement, no Ghostty)

| suite | before the change | after the change |
|---|---|---|
| `t2_launch_tab` | 11 of 11 PASS | 11 of 11 PASS (project_rows: 12 rows, last `BOM1`; start_command: 12 commands; click_handling includes the BOM1 click) |
| `t1_autojump_removal` | PASS | PASS |
| `t3_tab_click` | 5 of 6, `wiring` FAIL | 5 of 6, same `wiring` FAIL |

`t3 wiring` fails with `AttributeError("'types.SimpleNamespace' object has no attribute '_status_item_button'")`. It failed identically at the start of this session before any edit, and is described in the canvas entry of this area. Not fixed (out of scope). `t3` rewrites `md/t3_tab_click.md` on every run, so that report was reset with `git checkout` before committing.

Mutation checks (both on `t2_launch_tab`, both restored afterwards):
- BOM1 line removed from `launch_config.py`: `project_rows` FAIL ("project buttons 11"), `click_handling` FAIL (launched list holds only the wise2627 and canvas entries).
- Out-of-range probe moved back to `handle_launch_project(11)`: `click_handling` FAIL (BOM1 launched twice, so the probe launches instead of being rejected).

Pitfall observed: after the second mutation the restore (`cp` of the backup) still produced a failing `click_handling` although the file content was correct. Cause: stale bytecode. Mutation (`sed` 12 -> 11) and restore happened within the same second and the file size is identical, so Python reused the `__pycache__` entry (pyc validation is mtime in seconds plus size). Deleting the `__pycache__` directories under `dev/session_launcher` and `src/menubar` fixed it. For mutation checks that swap equal-length text, delete `__pycache__` between the steps. Note that the `grep FAIL` filter also matches the PASS row of `workflow_failures` (its text contains `FAILED`); read the `RESULT:` line.

Not run on purpose: `s0`, `s1`, `s2` (switch screens / open Ghostty windows), `p2_panel_snapshot`, `dev/model_selector/verify_four_tab_ring.py` (real NSPanels). The bundle was not built from this worktree.

## Verification still open (done by the user after the merge)

Rebuild from the MAIN checkout (`PROJECT_ROOT` comes from `__file__` and the build uses relative `dist/` paths, so a worktree build would make every launch command `cd` into the worktree):

```
cd /Users/brunowinter2000/Documents/ai/monitor-cc
./venv/bin/python setup_py2app.py py2app
```

This one command builds, installs to `~/Applications/monitor-cc-menubar.app`, signs, writes the plist and runs `launchctl bootout` + `bootstrap` (one retry after 1 s) for `com.brunowinter.monitor-cc-menubar`; no separate restart is needed. Expected output lines: `signed-with: monitor-cc Code Signing` and `bootstrap com.brunowinter.monitor-cc-menubar: ok` (signing identity and TCC grant survival are documented in the `menubar_build` area). Then click BOM1 in the real Launch tab (the panel is one row, 21 px, taller). On success `menubar.log` gets an `[launch] OK desktop=.. project=.../BOM1 stage=open_window ...` line, on failure `[launch] FAILED ... stage=<validate|switch|open_window>`.
The result of that verification is not part of this entry.
