# 2026-09-24 - Phase 5 in src/menubar/: fallbacks, tripwires, swallowed errors

Worker session mcref-flow-a. Input: a scan of `src/menubar/` (findings MB01-MB50) and a review that
decided every open question. MB36 (root resolution in `paths.py`/`setup_menubar.py`) was left to
another worker; MB12, MB26 and MB51 were "no action". The hooks findings went to another worker.

## Rules that decided each change

- Unobserved fallback: search `git log -S` and the process-docs for the commit or entry that
  introduced it. Observation recorded -> keep the path and make it traceable. None recorded ->
  delete the second path so the condition aborts.
- Swallowed error: route it to `menubar.log` through `log_menubar`. Conditions that would fire
  every 1.5 s cycle go through `log_menubar_change(category, key, message)`, which logs only when
  the message for that key changes; `message=None` resets the key so a recurrence logs again.
- Config-load defaults stay (prior decision) but a missing file (`FileNotFoundError`) is silent and
  any other read error is logged.
- Never persist a default over an unreadable file.
- Dead handlers and unread state are deleted.

## What changed (finding -> outcome)

Logging and dedupe helper
- MB01 `menubar_log.py`: a failing append or retention pass prints one stderr line (a logger cannot
  log itself). New `log_menubar_change`. The per-line timestamp parse now catches only `ValueError`
  (`_is_expired`), a line that does not parse is still kept.

State and config
- MB02/MB03 `app_settings.py`: `panel_max_height` alias deleted (settings.json on the machine holds
  only `panel_min_height`); load failures other than missing file and save failures are logged.
- MB33/MB32 `model_selection.py`: `_read_json_dict` (missing silent, corrupt or non-object logged);
  `_next_in` logs when the current value is not in the choices before cycling to the first one.
- MB34/MB28 `_write_proxy_rules_model_params` uses `_load_proxy_rules_strict` (missing -> `{}`,
  anything else raises). `_PendingSelection.write` now writes the rules file first and the
  model-selection file second, so an unreadable rules file aborts before anything is written.
  Example: `proxy_rules.json` containing `{broken` -> Apply raises, the file bytes are unchanged,
  the wrapper logs `model selection apply failed`.
- MB27/MB28 `hook_writer.py`: `_load_state` returns `{}` only for a missing file; any other error
  aborts the write, which is logged (`state write skipped`). It runs as a standalone script
  (`python3 hook_writer.py`), so `_log_failure` puts the repo root on `sys.path` and imports
  `src.menubar.menubar_log` lazily, only in the failure path; if that import fails it prints to
  stderr. Note: the earlier "zero hook_writer errors in the menubar log" evidence could never have
  held one because this script had no logging path.
- MB35 `monitor_sweep_scheduler._read_last_sweep_ts`, MB45 `proc_cache._read_hook_state`, MB46
  `rag_controller._read_rag_status`/`_format_elapsed`: missing file silent, other errors logged
  (deduplicated), defaults unchanged.
- MB37 `paths.py`: both migration shims deleted. The `_APP_SUPPORT.mkdir(...)` line stays at import
  time because `system._acquire_singleton_lock` opens the PID file without creating the directory.

App, hotkeys, panels
- MB04 `_on_hotkey` logs. MB05 `_ensure_wired`: the try shrank to `_status_item_button`
  (status item access only, logs once per distinct message); wiring errors now propagate. MB06 the
  try/except around the snapshot read in `_tick` is deleted. MB07 `restartApp_` logs the route
  (`py2app` or `source`) and the duplicated `dest`/`cmd` lines were hoisted.
- MB38 `panel_lifecycle.py` errors go to `menubar.log`.
- MB29/MB30 hotkey files: handler exceptions are logged (handlers still return 0); OSStatus of
  `InstallEventHandler`, `RegisterEventHotKey`, `GetEventParameter` is checked through
  `_check_status` and logged on non-zero. Registration failure logs and keeps running (decided:
  raising at startup would kill the menubar over one hotkey conflict).
- MB31 `model_controller.py`: eight cycle handlers share `_guarded_cycle`; all failures log to
  `menubar.log`. The `setFrame_display_` defect in `_show_apply_success` is not fixed, only visible.
  Observed at the start: `/tmp/monitor-cc-menubar.err` held two
  `apply success flash failed: '_CursorlessButton' object has no attribute 'setFrame_display_'` lines.

Detection and discovery
- MB13 route logging on change for `single_name_match` and `unclaimed_space` (OSC2 route already logged).
- MB14 alternate CGS key spellings deleted: the probe of 2026-05 records `DisplayIdentifier` as
  never present. A missing `Display Identifier`, `Spaces` or `ManagedSpaceID` skips that entry and logs
  once per distinct problem set; `ManagedSpaceID == 0` is no longer treated as missing.
- MB15 `_cwd_desktop_lkg` (written, never read) deleted.
- MB16 skipped project directory logged once per distinct error, key re-arms after recovery.
  MB17 `_cwd_from_jsonl`: per-line skip narrowed to `(ValueError, AttributeError)` (the 8 KB tail
  starts mid-line), outer handler narrowed to `OSError` and logged.
- MB18/MB19 `discover._log_routes`: `alive_route` (`tmux`, `mtime`, `process`) and `status_route`
  (`hook`, `hook_tmux_demote`, `no_fresh_hook`, `mtime`, `proxy_override`) logged on change per session id.
- MB20 dead `or` defaults in `discover.py` deleted.
- MB21 `discovery_worker._worker_loop` logs cycle errors to `menubar.log`, deduplicated; no staleness check.
- MB39 `_reposition_tab_panel` guard deleted.

Processes and caches
- MB08/MB09/MB10/MB11 (`bg_task_orphans`, `bg_timer`), MB22-MB25 (`ghostty`), MB41/MB42 (`proc_cache`):
  subprocess failures are logged with dedupe; behaviour after the failure is unchanged (previous cache kept).
  `tmux list-sessions` non-zero return logs the rc and stderr; the emptied session cache stays.
- MB40 `_has_active_bg` lost its handler (nothing in the body does I/O).
- MB43 `_tmux_window_activity` returns `None` on failure and logs; `_worker_session_info` only
  demotes `working` to `idle` when the activity is known. Before, a failed tmux call read as "no
  activity" and silently downgraded a working worker.
- MB44 `_PROXY_LOG_DIR = MONITOR_CC_ROOT / 'src' / 'logs'`; a missing directory is logged. The
  stat race on a vanished file is logged too.

System and skills
- MB47 the singleton lock catches `BlockingIOError` only. MB48 `_resolve_launch_python3`: plist PATH,
  else env PATH, else `RuntimeError`; the route is logged; `_launch_monitor` logs `launch FAILED` and returns.
  The bare `'python3'` fallback is gone. MB49 `ps` failure in `_find_worker_viewer_tty` logged; the
  `if not cwd: return` guard in `_open_or_focus_monitor` deleted together with its test case
  `_test_empty_cwd_is_noop` in `dev/menubar_per_project/test_open_or_focus_monitor.py`.
- MB50 `skill_discovery`: fallback to the first install entry (no user-scope entry) and to the
  directory name (no frontmatter name) are logged. Both fallbacks are documented as designed.

## How it was verified

Never run: anything that shows a window, registers a hotkey, calls launchctl or touches tmux sessions.
- Python with AppKit is only in the main checkout's venv (`monitor-cc/venv/bin/python`); the system
  `python3` lacks `AppKit`.
- `dev/menubar/p5_run_all.py` runs eight strands in parallel subprocesses (one per group). Each strand
  points `menubar_log.MENUBAR_LOG` and the module globals at a temp directory and uses fakes
  (`subprocess.run` replacements, fake carbon objects, `MagicMock` apps). Test files avoid a literal
  `from src.` line (hook `block_dev_imports_src`) and avoid `except ...: pass` (hook `block_except_pass`).
- Before/after on identical input: `git archive HEAD src` into `/tmp/mb_old`, then `P5_ROOT=/tmp/mb_old`
  runs the same strand against the old tree. Normal-path outputs are printed as `DIFF <digest>` lines;
  these were identical for desktop detection (3), discover (2), caches (8), system (4), and the
  proxy-rules write bytes (`8724d000feb39a31`). `dev/menubar/discover_byte_identity.py` kept
  `HASH: 0395eddc436c042aea4b5fa2ca313f207248dc6efc70679e15520ecf6c636a37`, run with `HOME=/tmp/p5_home`
  so the new route logs do not reach the real `menubar.log`.
- Intended changes are shown by strand checks that fail against the old tree (for example
  `g1.write_failure_stderr` FAIL on `/tmp/mb_old`).

Pitfalls met
- `repr` of a `set` differs between processes (hash randomisation): sorted before hashing.
- Dedupe state (`_last_by_key`) is module-global: a test that logs the same message twice sees only the
  first; tests clear it or measure the log delta from their own start offset.
- A commit went in with one failing check (route test counted an earlier line). Run the strand before `gcommit`.

## Observed, not changed

- `system._acquire_singleton_lock` opens the PID file with mode `w` before trying the lock, so a
  second instance truncates the running instance's PID file.
- `panel._reposition_panel` and `_reposition_tab_panel` are now the same computation.
- `desktop_detection` logs `osc2_match` on every OSC2 resolution (about 280,000 lines in a week).
- The launchd stderr file `/tmp/monitor-cc-menubar.err` still receives `abort-log` and singleton
  messages by design (logger failing, or process exiting before logging).
