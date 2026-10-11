# Worker row click silently ignored: empty tmux session name frozen at rebuild (2026-10-11)

## Observed

2026-10-11 19:44:39 the user clicked the worker row `haikutest` in the panel; no window came to the front and `menubar.log` had no line for that click. The only `focus_worker` line in the window 19:44 to 19:47 names `worker-monitor-cc-pdfwf` (and later `viewerbg2`, `pdfwf`). Over the whole window there is not a single `focus_worker` line for `haikutest` or `stripmcp`. The bundle in use was the py2app build of integration that already contained the viewer-app change; the cause is independent of it.

## Cause

1. `discover._worker_session_info` took a worker's tmux session name from the `cwd` field in the last 8192 bytes / last 10 non-empty lines of its JSONL. Each turn ends with 5 short lines that carry no `cwd` (`last-prompt`, `ai-title`, `mode`, `permission-mode`, `atis-latch`), and the line before them is often a large assistant message (observed 148980 bytes) that the 8192-byte window cuts mid-line, so it does not parse. Result: no `cwd`, the row falls to the `mtime` route and gets `tmux_session_name = ''`.
   Offline reproduction with a synthetic JSONL: small assistant line then the 5 metadata lines gives `worker-monitor-cc-haikutest`; a 150 KB assistant line then the same 5 lines gives `''`.
2. `PanelManager._add_worker_row` copied that string into `worker_tag_map[tag]` at rebuild time. The panel rebuilds only when the set of session names changes, so a route flip does not refresh the map.
3. `focusWorker_` did `if tmux_session_name:` and returned silently on `''`.

Timeline in the log: `haikutest` on the `mtime` route from 19:41:59 until 19:44:20, `stripmcp` appeared at 19:43:48 and forced a rebuild while `haikutest` was on the `mtime` route, so the empty name was frozen from then on. `stripmcp` and `viewerbg2` flip routes every few seconds while working; `pdfwf` (idle) is stable on `tmux` since 17:52 and its clicks were logged normally.

Not found, checked and ruled out: a stale or different row list (a headless rebuild against live discovery gave tags, titles and map in agreement), a leftover old grid in the stack (exactly one grid after repeated rebuilds). It is not known which row produced the `pdfwf` line at 19:44:39.

## Changes

- `discover.py`: the worker identity (display name, project, tmux session name) is remembered per `session_id` once a worktree `cwd` was read, and reused when a later tail has none. If a session has no remembered identity, one wider scan (last 1 MiB, no line cap) runs, at most once per JSONL mtime. A remembered identity is still dropped by the existing tmux-session-exists check, so a dead worker is not resurrected.
- `panel_manager.py`: the lookup `worker_tag_map` became `worker_dir_by_tag` and stores the row's `encoded_dir` (stable) instead of the tmux name.
- `sessions_controller.py`: `tmux_session_for(encoded_dir)` returns the name from the latest snapshot.
- `app.py` `focusWorker_`: resolves the tmux session at click time via `tmux_session_for`; an unknown tag or an empty name logs `focus_worker NO-OP reason=no_tmux_session tag=<n> encoded_dir=<dir>` instead of returning silently.
- `menubar_log.py`: opens, reads and writes the log with `encoding='utf-8'`. Under launchd the default encoding is ASCII, and `/tmp/monitor-cc-menubar.err` shows `UnicodeEncodeError('ascii', ... [hotkey] cmd+4 → focus ...)` for every message containing the arrow, so those lines never reached `menubar.log`.

## Verification (2026-10-11)

- `dev/menubar/test_worker_row_click.py`: 11 checks. The ASCII-locale check fails without the `menubar_log.py` change (negative control run: `UnicodeEncodeError` on stderr) and passes with it.
- `p5_run_all.py` (all groups exit 0), `test_ghostty_viewer_app.py`, `test_session_row_strings.py` pass. The two byte-identity harnesses were adapted to the new names (`_cwd_from_jsonl_wide` patched, caches cleared per scenario, `worker_dir_by_tag`).
- Live discovery with the new code: 365 worktree identities cached on the first cycle, no wide scans needed, warm cycle 33 to 47 ms (the same as before the change); cold first cycle 4.5 s versus 3.7 s before, which is filesystem cache noise (the wide scan never ran).
- Not verified: the real click on a worker whose viewer lives in GhosttyViewer inside the running bundle. That needs the merged code in a rebuilt py2app bundle.

## Hypothesis, not observed

A worker that `cd`s out of its worktree for a long time would keep the remembered identity, which is the wanted behaviour. A worker whose JSONL never contained a worktree `cwd` in its last MiB at first sight still gets an empty name until a narrow scan succeeds; the click then logs the NO-OP line.
