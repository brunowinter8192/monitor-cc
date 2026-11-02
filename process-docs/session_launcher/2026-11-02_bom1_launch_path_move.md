# BOM1 Launch entry points to the new project folder (2026-11-02)

Worker on branch `launcher-bom1-move` (based on `integration`), area `session_launcher`. The BOM1 project moved on 2026-11-02 from `/Users/brunowinter2000/Documents/wise2627/BOM1` to `/Users/brunowinter2000/Documents/BOM1` (a git repo). The entry stays the last one (index 11, label `BOM1`); only its path changed. The original entry is described in the BOM1 entry of this area (2026-10-27), which lists every pinned place.

## Change

- `src/menubar/launch_config.py`: last tuple element is now `/Users/brunowinter2000/Documents/BOM1`. Position, label and tuple length (12) unchanged. The label is derived from the basename, so it stays `BOM1`.
- `dev/session_launcher/t2_fixtures.py:_EXPECTED_PROJECTS`: last path changed identically (the fixture must equal `LAUNCH_PROJECTS`, asserted in `_case_project_rows`).
- `dev/session_launcher/t2_launch_cases.py:_case_click_handling`: the BOM1 assertion changed from `.endswith('/wise2627/BOM1')` to `== '/Users/brunowinter2000/Documents/BOM1'`. Equality instead of a suffix check, because a suffix like `/BOM1` would also match the old path.
- LOC unchanged (launch_config 17, t2_fixtures 64, t2_launch_cases 187), so no DOCS.md heading changed. Reports in `dev/session_launcher/md/` are unchanged: their text prints project basenames and the first path only, never the BOM1 path.

## Not changed on purpose

- `dev/hook_smoke/test_ask_rag_storage.py:15` builds `PINNED_HOME + "/Documents/wise2627/BOM1/Berichte"`. It belongs to the hook_smoke area, not to the launcher, and was outside this task. It will point at a deleted folder once the old folder is removed; whoever owns that area decides what to do.
- No code path stats or git-checks a launch project path (see the BOM1 entry of this area), so the move needs no other production change.

## Test results (2026-11-02, headless, isolated HOME, no Ghostty, no screen movement)

- `t2_launch_tab`: 11 of 11 PASS. `project_rows`: 12 rows, last `BOM1`. `click_handling`: index 11 on desktop 5 launches `(5, '/Users/brunowinter2000/Documents/BOM1')`; index 12 is still rejected with `index_out_of_range`.
- `t1_autojump_removal`: PASS.
- `t3_tab_click`: 5 of 6, `wiring` FAIL with `AttributeError("'types.SimpleNamespace' object has no attribute '_status_item_button'")`. Same failure as before this change (documented in the canvas and BOM1 entries of this area), not fixed, out of scope. `t3` rewrites `md/t3_tab_click.md` on every run; the report was reset with `git checkout` before committing.
- Mutation check on `t2_launch_tab`: `launch_config.py` set back to the old path (with `__pycache__` deleted before the run) gives `project_rows` FAIL and `click_handling` FAIL (launched list ends with `/wise2627/BOM1`). `start_command` stays PASS in that mutation, because its loop compares against whatever `_EXPECTED_PROJECTS` holds; it is not what pins the new path. Restored, `RESULT: PASS`.

Not run on purpose: `s0`, `s1`, `s2` (switch screens, open Ghostty windows), `p2_panel_snapshot`, `dev/model_selector/verify_four_tab_ring.py` (real NSPanels).

## Verification still open

The bundle was not built from this worktree (`PROJECT_ROOT` derives from `__file__` and the build uses relative `dist/` paths, so a worktree build would make every launch command `cd` into the worktree). After the merge the user rebuilds from the main checkout:

```
cd /Users/brunowinter2000/Documents/ai/monitor-cc
./venv/bin/python setup_py2app.py py2app
```

Then click BOM1 in the real Launch tab. Expected: `menubar.log` gets `[launch] OK desktop=.. project=/Users/brunowinter2000/Documents/BOM1 stage=open_window ...`; on failure `[launch] FAILED ... stage=<validate|switch|open_window>`. The result of that verification is not part of this entry.
