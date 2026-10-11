# Sessions tab: clipped wait badge, worker background indicator

Date: 2026-10-11. Area: menubar. Worktree branch: barfix.

## Observed (user screenshot, project monitor-cc, workers patchview and pdfmeasure)

1. Main row showed no wait timer; only the red `abort` label.
2. Main row badge rendered as `[B` (closing bracket missing).
3. Worker rows showed no background indicator although pdfmeasure held a long-running background shell.

## Causes

**Symptoms 1 and 2 are one defect: the badge text is wider than its grid column.**
- The timer is the countdown badge `[B M:SS]` on the main row (remaining = timeout minus elapsed), not the `abort` label. The label has been static text since 2026-05-21 (before that it was `⊗ M:SS`).
- At observation time the live process was `worker-cli wait --timeout 7200`, so the badge reads `[B 120:00]` = 10 characters = 78.3 pt in Menlo 13.
- Column 4 was 72 pt, sized for `[B 54:59]` (70.4 pt, default wait timeout 3300 s). A 78 pt title in a 72 pt NSButton wraps at the space; the second line is clipped. Only `[B` stays visible.
- Reproduced headless (no window): `[B 54:59]` in a 72 pt button renders in full, `[B 114:47]` renders as `[B` only.
- Not caused by the 2026-09-25 menubar refactors. `git diff 23d5353b HEAD` on panel.py, panel_manager.py, bg_timer.py, discovery_worker.py, sessions_controller.py is moves and absolute imports only. The installed bundle (built 2026-10-04 18:18, commit 3d2413c5) has panel.py and panel_manager.py byte-identical to HEAD at that time.

**Symptom 3 is old, intended-by-omission behaviour, not a regression.**
- 2026-05-20 (2b32814c): badge visibility switched from `SessionInfo.has_bg` to `bg_by_project[project]`. `has_bg` stayed computed but unread.
- 2026-05-21 (23a70a9a): worker-row badge dropped entirely.
- `has_bg` for a worker is correct: `/tmp/claude-<uid>/<encoded worktree dir>/<session>/tasks/*.output` held open by the shell, matched by `_has_active_bg`.

## Decisions (user)

- Timer stays only in the main-row badge; no timer in the `abort` label.
- Worker rows show `[B]` for their own background shell, no countdown. The project wait countdown is not shown on workers (it belongs to the main session).
- Width fix: widen column 4. `PANEL_WIDTH` untouched (saved settings hold 422; the flexible name column absorbs the difference).
- The intermittent `[bg_timer] ps failed ... TimeoutExpired` in menubar.log (9 lines, 5 on 2026-10-10) is NOT part of this change. While it lasts, `bg_by_project` is empty for a cycle and badge plus abort flicker away.

## Changes

- `panel_grid.py`: `_GRID_COL4_W` 72 -> 84 pt. Fits up to 10 characters, i.e. `[B 120:00]`. A timeout of 6000 s or more has a 3-digit minute value; 100 minutes or more is the threshold that needs 10 characters.
- `panel_manager.py`: `_add_worker_row` puts `_format_bg_badge(None)` (`[B]`) in column 4 when `s.has_bg`, wired to `focusWorker:`. `_PanelLookups.worker_bg_names` records which workers got one. New `worker_bg_changed(sessions)`. `update_inplace` no longer applies the project countdown to a worker badge.
- `app.py`: `_tick_panel_open` rebuilds also on `worker-bg-change`; without it `update_inplace` cannot add a badge that was not built.

## Test

`dev/menubar/test_session_row_strings.py` (headless, home isolated, never shows the panel). Run: `./venv/bin/python dev/menubar/test_session_row_strings.py`. Cases: wait with 7200 s remaining, 300 s remaining, no wait. Each pins all 7 cell titles of the main row and two worker rows (with and without bg), the abort label, and that every fixed-column title fits its laid-out button width. Plus `worker_bg_changed` for unchanged, gained, lost.
Negative check done: with `_GRID_COL4_W = 72` the test fails on `[B 120:00]` (`titles fit buttons`).

## Import route for dev scripts

A hook blocks `Write` of dev scripts that import `src.` directly. The sanctioned route in this directory is `p5_common.load(<module>)`. The test uses it.

## Deploy

Not done here. After merge: `cd /Users/brunowinter2000/Documents/ai/monitor-cc && ./venv/bin/python setup_py2app.py py2app`.
