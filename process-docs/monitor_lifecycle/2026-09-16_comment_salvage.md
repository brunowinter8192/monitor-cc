# 2026-09-16 — Comment/docstring salvage for dev/monitor_lifecycle/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/monitor_lifecycle/` (3 `.py` files, 415 LOC) into conformance with the
project's three-marker comment standard (`# INFRASTRUCTURE` / `# ORCHESTRATOR` / `# FUNCTIONS`,
nothing else). Every comment below was relocated here verbatim before deletion from the code.
Zero docstrings existed in this directory (verified by AST walk of every Module/FunctionDef/
ClassDef in all 3 files) and zero `__doc__`/`argparse` hits (`grep -rn "__doc__\|argparse"`), so
there was no load-bearing-docstring rewiring to do here, unlike the previous two areas.

**Counting method note for whoever re-measures this directory later:** plain `grep -n '#'`
over-counts in this directory because of tmux format strings like
`"#{session_name}|#{session_created}|..."` and one markdown-content string literal
(`"# Monitor pane load baseline"`) inside `probe_monitor_load.py`'s `write_report`. I used
Python's `tokenize` module (walks real COMMENT tokens only, immune to `#` characters inside
string literals) to get the exact count, which landed on exactly 49 — matching the milestone
brief's stated measured state precisely. If a future audit of this directory (or any other
`dev/` directory with tmux format strings) uses plain grep, expect an over-count; tokenize is the
reliable method.

**Live-monitor-visibility note (from Main, worth keeping for the next agent who runs this test):**
`tests/test_monitor_sweep.py` creates and destroys 3 real, uniquely-named throwaway tmux sessions
(`monitor_cc_testold`, `monitor_cc_testnew`, `worker-testkeep`) during its ~2-second run. Because
one of those names starts with the same `monitor_cc_` prefix the real monitor's own session-picker
UI matches on, the fixture sessions may flicker briefly through the user's live monitor pane
while the test runs, even though the test's own `sweep_sessions()` call is filtered to never
touch any *other* (real) `monitor_cc_*` session and the `finally` block always cleans up all 3
fixtures. This is expected, cosmetic, and self-resolving in under ~2s — not a bug to chase if
seen again.

I traced `sweep_sessions()` in `src/monitor_janitor.py` and `kill_session()` in
`src/tmux_launcher.py` before running this test for real: `sweep_sessions(sessions, max_age)`
iterates only the exact `sessions` list passed by the caller (never re-enumerates internally),
and the test explicitly filters `fixture_pair = [(n,c) for n,c in all_sessions if n in (_OLD_NAME,
_NEW_NAME)]` before calling it — so it is structurally impossible for this test to reach a real
production `monitor_cc_<hash>` session. `kill_session()` itself is a single-target
`tmux kill-session -t <exact-name>`, no wildcards. Confirmed via `tmux list-sessions` before and
after each run that the pre-existing real sessions were untouched and all 3 fixtures were gone
after the test's `finally` block ran, both before and after the comment-removal edit.

---

## Salvage from dev/monitor_lifecycle/probe_monitor_load.py

Was line 10 (above `_MODE_RE`):
```
# Same extraction as src/tmux_launcher.py::_parse_pane_modes — --mode <value> out of pane_start_command
```

Was line 15 (above `probe_monitor_load_workflow`):
```
# Snapshot every monitor_cc_* pane's mode/PID/age/CPU, print a table sorted by CPU time, save a report
```

Was line 24 (above `collect_pane_rows`):
```
# One row per pane across every monitor_cc_* tmux session, with mode/PID/ages/CPU already resolved
```

Was line 43 (above `list_monitor_panes`):
```
# List {session, session_created, pane_idx, pid, mode} for every pane of every monitor_cc_* session
```

Was line 70 (above `ps_stats`):
```
# ps snapshot for one pid: elapsed time, cpu time, %cpu — all as ps's raw strings + cpu_seconds for sorting
```

Was line 87 (above `parse_clock`):
```
# Parse a ps clock field ("MM:SS", "HH:MM:SS", or "DD-HH:MM:SS", cputime allows ".hh" fraction) to seconds
```

Was line 99 (above `print_table`):
```
# Print the pane table to stdout, one row per pane, already sorted by caller
```

Was line 111 (above `write_report`):
```
# Write the same table as a dated markdown report under reports/
```

## Salvage from dev/monitor_lifecycle/tests/test_monitor_sweep_scheduler.py

Was line 9 (above the `sys.path.insert` line):
```
# add project root to path so src.menubar is importable as `from src.` (see Import Convention)
```

Was line 11, trailing on the import statement:
```
from src.menubar import monitor_sweep_scheduler as sched  # noqa: E402
```
(the comment token itself is `# noqa: E402`)

Was line 13, trailing on the `_NOW` assignment:
```
_NOW = 1_000_000_000.0   # fixed epoch reference — arithmetic only, never compared to real wall time
```
(the comment token itself is `# fixed epoch reference — arithmetic only, never compared to real wall time`)

Was lines 17-21 (above `test_monitor_sweep_scheduler_workflow`):
```
# Gate-only coverage for monitor_sweep_scheduler.py's at-most-once-per-24h check. _run_sweep
# (the real tmux/subprocess work — already covered by test_monitor_sweep.py) is stubbed out for
# every case here, so this file never touches real tmux state. Each case gets its own isolated
# temp state file (never the real MONITOR_SWEEP_STATE_FILE under APP_SUPPORT) and a fresh module
# state reset. Exits 1 on any failed check.
```

Was line 41 (above `_check`):
```
# Print one check result; append to failures on FAIL
```

Was line 47 (above `_test_pure_gate_boundaries`):
```
# Pure _is_sweep_due(last_ts, now) — no file, no thread, no module state involved
```

Was line 58 (above `_test_fresh_state_runs`):
```
# No state file at all (equivalent to a fresh install / first tick after this feature ships)
```

Was line 63 (above `_test_run_1h_ago_does_not_run`):
```
# A state file recording a run 1h ago — well inside the 24h window
```

Was line 68 (above `_test_run_25h_ago_runs`):
```
# A state file recording a run 25h ago — past the 24h window
```

Was lines 73-74 (above `_test_reentry_guard_blocks_concurrent_trigger`):
```
# Two calls in the same due window: the second must not double-trigger while the first's
# (stubbed) sweep thread is still marked in-progress
```

Was line 94, trailing on a statement (inside `_test_reentry_guard_blocks_concurrent_trigger`):
```
        sched.maybe_run_sweep_workflow(_NOW)          # due → spawns the blocking stub
```
(the comment token itself is `# due → spawns the blocking stub`)

Was line 95, trailing on a statement (same function):
```
        time.sleep(0.1)                                # let the thread actually start and set the flag
```
(the comment token itself is `# let the thread actually start and set the flag`)

Was line 96, trailing on a statement (same function):
```
        sched.maybe_run_sweep_workflow(_NOW + 1)       # still "due" by time, but a sweep is already running
```
(the comment token itself is `# still "due" by time, but a sweep is already running`)

Was lines 106-107 (above `_test_attempt_timestamp_persisted_before_sweep_completes`):
```
# The on-disk attempt timestamp must be written BEFORE the (stubbed, slow) sweep finishes — a
# crashed/hung sweep must not cause the very next tick to re-fire it
```

Was line 126, trailing on a statement (inside `_test_attempt_timestamp_persisted_before_sweep_completes`):
```
        time.sleep(0.1)   # the stub is still blocked on release — sweep has NOT "completed"
```
(the comment token itself is `# the stub is still blocked on release — sweep has NOT "completed"`)

Was lines 137-139 (above `_invoke_with_isolated_state`):
```
# Point the module at an isolated temp state file (optionally pre-seeded), stub out _run_sweep
# (never touch real tmux), call maybe_run_sweep_workflow(now) once, wait for the (fast, no-op)
# stub to run if it was going to, then restore everything. Returns whether the stub fired.
```

Was line 167 (above `_wait_until`):
```
# Poll predicate() until True or timeout — used to wait for a background thread's cleanup
```

## Salvage from dev/monitor_lifecycle/tests/test_monitor_sweep.py

Was line 7 (above the `sys.path.insert` line):
```
# add project root to path so src.monitor_janitor is importable as `from src.` (see Import Convention)
```

Was line 9, trailing on the import statement:
```
from src.monitor_janitor import list_monitor_sessions, sweep_sessions, _log_path  # noqa: E402
```
(the comment token itself is `# noqa: E402`)

Was line 14, trailing on the `_OLD_AGE_WAIT` assignment:
```
_OLD_AGE_WAIT   = 2.0  # seconds to let testold "age" before the sweep
```
(the comment token itself is `# seconds to let testold "age" before the sweep`)

Was line 15, trailing on the `_TEST_THRESHOLD` assignment:
```
_TEST_THRESHOLD = 1.0  # sweep threshold used only by this test — production stays 24h, unconditional
```
(the comment token itself is `# sweep threshold used only by this test — production stays 24h, unconditional`)

Was lines 19-21 (above `test_monitor_sweep_workflow`):
```
# Create fixture sessions, sweep ONLY the fixture pair (never the live monitor_cc_* sessions
# already running on this machine), assert kill/spare/untouched + no orphaned pane process +
# log lines written, then clean up. Exits 1 on any failed check.
```

Was lines 37-38 (inside `test_monitor_sweep_workflow`, above the `sweep_sessions` call):
```
        # Sweep only the fixture pair — real monitor_cc_* sessions from other projects on this
        # machine must never see the test's 1s threshold (production always uses the 24h default).
```

Was line 63 (above `_check`):
```
# Print one check result; append to failures on FAIL
```

Was line 69 (above `_create_fixture_session`):
```
# Create a throwaway tmux session running a real child process; return its pane pid
```

Was line 71, trailing on a statement (inside `_create_fixture_session`):
```
    subprocess.run(["tmux", "kill-session", "-t", name], capture_output=True)  # clear stale leftovers
```
(the comment token itself is `# clear stale leftovers`)

Was line 79 (above `_session_exists`):
```
# True if the named tmux session still exists
```

Was line 83 (above `_pid_alive`):
```
# True if a process with this pid is still running
```

Was line 87 (above `_log_has`):
```
# True if the sweep log's tail has a line naming this session with this status
```

Was line 95 (above `_cleanup_fixtures`):
```
# Kill all three fixture sessions, ignoring any that are already gone
```

## Salvage from dev/monitor_lifecycle/DOCS.md

The pre-rewrite `DOCS.md` carried a trailing `## Gotchas` section that has no place in the
mandated DOCS.md format (Role / Public Interface / Flow / Modules / State only). Cut verbatim:

```
## Gotchas

**The daily sweep has no dedicated LaunchAgent** — it runs through
`monitor_sweep_scheduler.py`'s tick inside the menubar app, because a standalone LaunchAgent for
the sweep hit a TCC Full Disk Access wall under launchd. See `process-docs/monitor_lifecycle/`.
```

This content is preserved here in full; it is not carried into the rewritten DOCS.md.
