# canvas added to the Launch tab (2026-09-25)

Worker on branch `launcher` (based on `integration`), area `session_launcher`. Task: a Launch entry for `/Users/brunowinter2000/Documents/ai/canvas`, behaving like the other projects.

## Change

- `src/menubar/launch_config.py`: `LAUNCH_PROJECTS` now has 11 entries; canvas is the LAST one (index 10), placement confirmed by the user. Appending keeps the indices 0-9 stable, so the tests that address `_EXPECTED_PROJECTS[0]`, `[7]`, `[9]` stay valid.
- No other production file changed. `session_launch._validate_request`, `launch_controller.rebuild` (panel height from `len(LAUNCH_PROJECTS)`) and `launch_panel_ui._project_label` (basename -> `canvas`) all derive from the tuple. Start command: `cd <MONITOR_CC_ROOT> && PATH="$HOME/.local/bin:$PATH" ./src/claude_proxy_start.sh --project /Users/brunowinter2000/Documents/ai/canvas`.

## Pitfall for the next entry added to the list

`t2_launch_cases.py:_case_click_handling` used `handle_launch_project(10)` as its "index out of range" probe. With 11 projects index 10 is valid, and the case fails with `assert len(launched) == 1`. The probe is now `handle_launch_project(11)`, and a new assertion launches index 10 on desktop 5 and expects `(5, canvas)`. Whoever adds a 12th project must move the probe to 12.
Other pinned places: `t2_fixtures._EXPECTED_PROJECTS` (must equal `LAUNCH_PROJECTS`, see `2026-09-24_t2_split_for_loc_limit.md` in this area), `_case_project_rows` (count, tag range, titles), `_case_start_command` result text.

## Test results (2026-09-25, headless, isolated HOME, no screen movement, no Ghostty)

- `t2_launch_tab`: 11 of 11 cases PASS (project_rows: 11 rows, last `canvas`; start_command: 11 commands; click_handling includes the canvas click).
- `t1_autojump_removal`: 7 of 7 PASS.
- `t3_tab_click`: 5 of 6 PASS, `wiring` FAILS with `AttributeError("'types.SimpleNamespace' object has no attribute '_status_item_button'")`. Reproduced identically on a clean `git worktree` at HEAD before my edits, so it predates this change and is unrelated to the project list. Not fixed (out of scope).
- Mutation: removing the canvas line from `launch_config.py` made `project_rows` ("project buttons 10") and `click_handling` fail; restored afterwards.
- Not run on purpose: `s0`, `s1`, `s2` (switch screens / open Ghostty windows), `p2_panel_snapshot`, `dev/model_selector/verify_four_tab_ring.py` (real NSPanels, needs the user's go). Bundle not built.

## Verification still open

After the merge the bundle must be rebuilt from the MAIN checkout (area `menubar_build`) and canvas clicked in the real Launch tab. The panel gets one row (21 px) taller; only checked headless.
