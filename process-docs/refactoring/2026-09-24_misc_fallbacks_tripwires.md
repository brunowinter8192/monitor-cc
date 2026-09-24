# Fallback and tripwire fixes: tmux, janitor, py2app, ccwrap, input, news_pane, gpu_pane, dual_log_cli (2026-09-24)

Worker mcfix-misc, branch mcfix-misc. Input: Phase 5 findings P04-P10, P16, P18, CW01, I01-I05, NP02-NP07, G04, G05, G07-G10, G13, G16, G19, D05-D08, D10, D12, confirmed by Main. Out of scope and done elsewhere: env-else-computed root lines (X-ROOT), `gpu_pane/errors.py` reader (G02), `dual_log_cli/reader.py iter_jsonl` (D09), `dual_log_cli/discovery.py` (D01), `src/proxy_addon.py` (P06).

## Decision rule applied

A fallback whose trigger was never recorded as observed (checked with `git log -S` and process-docs) was removed or turned into a raise. A swallowed error was narrowed to the observed exception or reported into the existing channel of the component (pane loop: `log_pane_error`/`log_pane_note`; CLI: stderr; janitor: its sweep log).

## Facts found that changed a finding

- **P07 (history limit).** With no tmux server, both `tmux show-options -gv history-limit` and `tmux set-option -g history-limit` return rc=1 ("error connecting to ..."). Every first launch hits this. Before the fix the launcher read `""`, substituted `"2000"`, the `-g` set failed silently, `new-session` started the server, and the restore then wrote 2000 onto the fresh server. "Abort on rc != 0" would have aborted every cold start. Implemented: `get_global_history_limit` returns `None` on rc != 0 and prints one stderr line (`history-limit: show-options rc=1 (no tmux server), restore skipped`); the orchestrator skips the restore on `None`. Behaviour change: a fresh server no longer gets its history-limit overwritten with 2000. The `set-option -g` before `new-session` stays best-effort because it fails on a cold start by design of tmux.
- **P09 (`pct or "50%"`, first-pane fallback).** Introduced in commit 5c5b9001 (2026-04-27, "ctrl-r self-heals missing panes") with no recorded observation. A spec with `split_from=None` that is missing in an existing window (for example `news` missing while `news-log` is present) has `pct=None`, so dropping `or "50%"` alone would have produced `-l None`. Implemented: `_fill_missing_panes` raises `RuntimeError` when `split_from` is not in the present panes (this includes `None`); `_create_missing_window` raises when the parent cannot be resolved. `restart_panes` is run by tmux `run-shell` (Ctrl+R), so the exception text lands in tmux's run-shell output.
- **NP07.** `_is_running_via_log` (60 s mtime window plus start/end markers) came in with the run button (d2eaf62f) with no recorded lost-handle case. Removed together with `LOG_RUNNING_RECENT_SECS` and `RUN_END_MARKER` (dead afterwards). Consequence: a pipeline started outside the pane (cron, CLI) no longer greys the button. Accepted by Main.
- **G19.** The rag state files (`~/.rag-locks/server-port-*.json`) hold pid, port, model_path, model_name, mode, start_time, log_path, name. No idle-timeout value. `IDLE_TIMEOUT` stays `env RAG_SERVER_IDLE_TIMEOUT` else 3600. Documented as a coupling in `src/gpu_pane/DOCS.md`; no code change (decision by Main).
- **G09, G10.** Malformed state file and dead pid are already traced skips (anomaly line in the pane plus `gpu_pane.log`). No code change.

## Changes per finding

| Finding | Change |
|---|---|
| P10 | `check=True` on new-session, new-window, split-window, respawn-pane, list-windows/list-panes inside restart and create paths. Styling, bind-key, select-*, display-message, the history-limit set/restore and attach-session stay unchecked. Argv sequences unchanged (fake-tmux harness identical). |
| P05 | `kill_session` returns bool. Sweep writes `KILLED`, `KILL_FAILED` or `SPARED`; the returned dict's `killed` is the real result. |
| P04 | `list-sessions` rc != 0 writes `NOSESSIONS rc=<n>` to `monitor_sweep.log`. |
| P08, P09 | Raise on unplaceable pane (see above). |
| P16, P18 | `setup_py2app.py`: missing bundle src lib, failed codesign and failed final bootstrap print and `sys.exit(1)`. The single bootstrap retry stays. |
| CW01 | `--project` as the last argument prints an error and exits 2. |
| I01 | `set_raw_stdin` no longer catches: a non-tty stdin raises `termios.error` at pane start. `wait_for_input`'s `time.sleep` branch (only reachable when setup had failed) deleted. |
| I02 | `restore_terminal` failure goes to `log_pane_error('input')`. |
| I03, I04 | `read_mouse_event`: try around `os.read` removed; malformed SGR fields raise (`int()` or unpack `ValueError`). The `[<` prefix check and the non-mouse `None` stay. |
| I05 | `pbcopy` runs with `check=True`; a failure raises before the caller's copy flash. |
| NP02 | `read_last_run_ts` catches `FileNotFoundError` only. |
| NP04, NP05 | rag-cli fetch failures (`FileNotFoundError`, `TimeoutExpired`, rc != 0, `JSONDecodeError`, collection not listed) write one `log_pane_note` per state change; the pane still shows `?`. |
| NP06 | Moot after NP07 (function removed). |
| G04 | A state file whose `port` is not an int becomes a `missing_port` anomaly and is skipped in `all_statuses`. The `int(key[5:])` guard in `_expire_toggle_states` is removed, so a `port-None` key raises. |
| G05 | A toggle that expires by timeout writes a `log_pane_note`. |
| G07 | `PRESET_NAMES` starts empty; `_ensure_preset_names` fills the same list object in place on every `all_statuses` tick while it is empty. A failure is a `presets_unavailable` anomaly (each tick) and a `gpu_pane.log` line (on cause change only). Import no longer runs `rag-cli`. Cost: a hung rag-cli blocks a tick for up to 3 s until discovery succeeds. |
| G08 | Logger-handler `OSError` goes to `log_pane_error('gpu_status')`. The anomaly line still says "see logs/gpu_pane.log" in that case. |
| G13 | `_state_file_idle` catches `FileNotFoundError` only. |
| G16 | `_fetch_collections` returns `None` on failure (noted once per state change); `gpu_render` shows `?`, `[]` still shows `(none indexed)`. |
| D05 | `search`/`reqs` skip a session only on `FileNotFoundError`/`ValueError` and print `timeline: <stem>: <Type>: <message>` on stderr. Other exceptions propagate. |
| D06 | `project_map` narrowed to `OSError`/`ValueError`, reports the path. |
| D07 | `local_datetime`: empty -> `None`, non-empty unparseable -> `ValueError`. `test_local_time.py` asserted `None` for `"garbage"`; that assertion was synthetic, not an observation, and now asserts the raise. |
| D08 | A malformed line in `load_last_request` is reported on stderr (`reader: <file>@<offset>: malformed line skipped`). |
| D10 | Swallows in `usage.py` narrowed to `OSError` and reported. `resolve_transcript` now returns `(path, flow_status, reason)`; `numbering` carries `reason` for the boundaries path; the stderr line reads `...: <stem> (<reason>)`. |
| D12 | `render_reqs`: a REQ marker without a timestamp raises instead of being dropped. |

New module `src/dual_log_cli/diagnostics.py`: `report_skip(source, target, reason)`, prints once per identical line per process (`resolve_transcript` rebuilds the project index per session, so without dedup one unreadable directory would repeat).

## Verification

- tmux: `dev/tmux_launcher/layout_regression_checks.py` (fake tmux) output identical before and after (7 checks). New `dev/tmux_launcher/fallback_tripwire_checks.py` runs the real tmux binary on the private socket `-L mcfixprobe` through a PATH shim (12 checks). Do not run `dev/monitor_lifecycle/tests/test_monitor_sweep.py` casually: it creates `monitor_cc_test*` sessions on the default server.
- setup_py2app: never imported (import calls `setup()`). The check parses the file, executes only the function defs with fake `subprocess` and a fake `Path.home`. Diff against the pre-edit file shows exactly three hunks.
- gpu_pane: `render_byte_identity.py` hash `e33158d6...` identical before and after; 17 new checks with a fake `rag-cli` on PATH.
- dual_log_cli: stdout byte-identical before and after on a frozen APFS clone (`cp -c`) of `src/logs/dual_log` used through `MONITOR_CC_ROOT` for `sessions`, `sessions --since`, `reqs`, `reqs --merged`, `reqs --main --gap 5`, `search`, `msgs`, `expand`, `reqs <stem> --rebuild`. Exit codes identical. Only stderr changed, as intended. Observed on the clone: 3 sessions skipped by `reqs`/`search` now print `ValueError: no non-haiku request line in <stem>_original.jsonl`; the one boundaries-fallback session now prints `no transcript contains request req_...`. No `local_datetime` raise and no other exception type fired on real data. All 19 files in `dev/dual_log_cli/tests/` pass.
- New checks: `dev/input`, `dev/news_pane`, `dev/ccwrap`, `dev/setup_py2app`, `dev/dual_log_cli/tests/test_skip_reporting.py`.

## Open points for a successor

- `src/dual_log_cli/DOCS.md` is 435+ lines (over the 400 limit before this session as well).
- `IDLE_TIMEOUT` coupling (G19) is documented only.
- The gpu anomaly line always says "see logs/gpu_pane.log", also when the log handler could not be created (G08).
