# monitor_lifecycle test structure, Phase 3 fixes (2026-09-24)

## test_monitor_sweep.py

Before: three fixed-name tmux sessions on the user's default tmux server (each pre-killed by name), a 2 s wall-clock wait to make one session old, the last 20 lines of the live sweep log as evidence.

After: no change to `src/` was needed. The seams already existed as environment variables:
- `TMUX_TMPDIR=<scratch dir under /tmp>` plus `TMUX` removed gives a private tmux server (use `/tmp`, not `$TMPDIR`, because unix socket paths are limited to about 104 bytes on macOS).
- `MONITOR_CC_ROOT=<scratch dir>` moves `monitor_janitor._log_path()` into the scratch dir.
- Age: `list_monitor_sessions()` still reports the real creation times; the test subtracts 1000 s from the "old" session's created value and sweeps with a 500 s threshold instead of sleeping.
- Cleanup is `tmux kill-server` on the private server plus removal of the scratch dir.

Proof: hash of `tmux ls` output on the default server identical before and after two runs; size of the live `src/logs/monitor_sweep.log` unchanged (18770 bytes before and after); 11 of 11 checks pass.

## test_monitor_sweep_scheduler.py

Before: `tempfile.mkdtemp` dirs never removed, `time.sleep(0.1)` between trigger and assertion, three module globals saved and restored by hand in each case.
After: `_isolated_scheduler` context manager (`patch.object` for the state file, `_last_sweep_ts`, `_sweep_in_progress`, `_run_sweep`, `TemporaryDirectory`). Presence or absence of a triggered sweep is decided without sleeping: `Thread.start()` returns after the thread is registered, so the test joins all threads named `monitor-sweep` and then reads the stub's event (`_sweep_fired`). Six strands, one per former case group, through `dev/refactoring/strand_runner.py`; 6 of 6 pass in three consecutive runs.

## Both

`_check` raises at the first failed check (strand aborts, verdict `ABORT`). Reports go to `md/<script>.md`, fixed names.
