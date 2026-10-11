# Sessions tab: background indicator on main rows

Date: 2026-10-11. Area: menubar. Worktree branch: mainbg.

## Observed (user, 2026-10-11 14:05)

- Main session websearch had a background task running. Its row `[4] * websearch  [ ]  mon skill` showed no `[B]`. Other main rows were the same.

## Verification of `SessionInfo.has_bg` on live data (14:06-14:20)

Method: the real `discover.list_alive_sessions()` run with `p5_common.load`, HOME isolated for logs, `session_finder.CLAUDE_PROJECTS_DIR` pointed at the real `~/.claude/projects` (read-only listing). Without that override the isolated HOME hides all project dirs and the session list is empty.

| Row | has_bg before fix | Truth |
|---|---|---|
| websearch main (session 51731b00) | True | `rag-cli index` shell held `/tmp/claude-501/-Users-...-cli-websearch/51731b00.../tasks/bcqeubm2j.output` open |
| monitor-cc main (session 61919409) | **False** | `worker-cli wait` shell held `/tmp/claude-501/-Users-...-ai-monitor-cc/61919409.../tasks/b1i92i3e7.output` open |
| general main | False | no open task file |
| mainbg worker | True | open task file |

So for websearch the flag was right and the row simply never read it: `_add_main_row` only looked at `bg_by_project`.

## Detection bug found: path case

- `~/.claude/projects` holds the project dir under the legacy name `-Users-brunowinter2000-Documents-ai-Monitor-CC`. The tasks dir that Claude Code creates is `/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc`.
- Both names resolve to the same inode (`ls -di`, APFS case-insensitive), so `iterdir()` returns the capitalised name and `encoded_dir` carries it.
- `_has_active_bg` did a case-sensitive `startswith` and never matched the monitor-cc main. websearch and general have no case difference.
- `discover._proc_cwd_for_encoded_dir` already compares with `.lower()`, so case-insensitivity was a known property of these names.

## Decisions (user)

- A running project countdown always wins on a main row: `[B M:SS]`.
- Without a countdown, `[B]` when the main's own `has_bg` is true; otherwise the cell stays empty.
- Case-insensitive match in `_has_active_bg` is in scope.

## Changes

- `proc_cache._has_active_bg`: the expected tasks-dir prefix and each open path are lowercased before `startswith`.
- `panel_manager._add_main_row`: badge text from `_main_badge_text(s, proj_bg)` (countdown, else `[B]`, else none). Wired to `focusSession:` as before.
- `panel_manager`: `worker_bg_names` became `static_bg_names` (rows built with the static `[B]`, workers and mains). `worker_bg_changed(sessions)` became `bg_indicator_changed(sessions, bg_by_project)`: compares the set of rows that should carry a static `[B]` (`has_bg` and (worker or no countdown for its project)) with the built set.
- `app._tick_panel_open`: rebuild reason `worker-bg-change` renamed `bg-change`.
- Not changed: `_tick_panel_closed` rebuilds only on session-set change. That is enough because opening the panel always rebuilds (`panel_lifecycle`, call to `app.panel.rebuild`).
- A countdown starting or ending is still caught by `abort-flap`; `bg_indicator_changed` additionally fires then when the main has its own bg, which is harmless (one rebuild already happening).

## Test

`dev/menubar/test_session_row_strings.py`, run `./venv/bin/python dev/menubar/test_session_row_strings.py` (headless, no window).
- Row strings, main column 4: wait 7200 s + bg -> `[B 120:00]`; wait 300 s + bg -> `[B 5:00]`; wait 300 s without bg -> `[B 5:00]`; no wait + bg -> `[B]`; no wait without bg -> empty.
- Change detection: worker gained/lost; main gained/lost without countdown; main gaining bg under a countdown needs no rebuild; countdown ending while main has bg is detected.
- `_has_active_bg` with open path `.../-Users-x-ai-monitor-cc/sess1/tasks/a.output` and encoded dir `-Users-x-ai-Monitor-CC`: True; other session id: False.
- Negative check: with the old `proc_cache.py` the case test fails.
- Also green: `dev/hook_smoke/test_bg_task_detection.py` (5/5), `dev/menubar/p5_run_all.py` (all 8 strands), `panel_manager_byte_identity.py` runs.
- Live re-check after the fix: monitor-cc main, websearch main and the mainbg worker report `has_bg=True`, general False.

## Not done

- No menubar rebuild or deploy. After merge: `cd /Users/brunowinter2000/Documents/ai/monitor-cc && ./venv/bin/python setup_py2app.py py2app`.
- Hypothesis, never observed: `has_bg` is an open-handle check, so a main with a finished-but-still-open shell reads true until the handle closes. Not addressed.
