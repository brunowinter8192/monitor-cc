# dev/monitor_lifecycle/

## Role

Load visibility and regression coverage for the monitor's tmux-session lifecycle: each project's
`monitor_cc_<hash>` session runs nine panes indefinitely until something kills it (see
`src/monitor_janitor.py`). This directory holds the load probe used to establish a CPU/age
baseline, the regression test for the sweep that ends stale sessions, and the gate test for the
daily-tick trigger that runs that sweep (`src/menubar/monitor_sweep_scheduler.py`).

## Modules

### probe_monitor_load.py (136 LOC)

**Purpose:** Snapshots every pane of every live `monitor_cc_*` tmux session (mode, PID, pane age,
CPU time, %CPU from `ps`) plus each session's own age, prints a table sorted by CPU time
descending, and saves the same data as a dated markdown report.
**Reads:** live tmux state (`tmux list-panes -a`) and live process state (`ps`) — no files.
**Writes:** stdout table; `reports/<date>_monitor_load_baseline.md`.
**Called by:** none — run manually, e.g. before/after a suspected overload, comparing against a
prior dated report in `reports/`.
**Calls out:** none (stdlib `subprocess`/`re`/`pathlib` only).

---

### tests/test_monitor_sweep.py (102 LOC)

**Purpose:** Regression test for `src/monitor_janitor.py` — creates three real throwaway tmux
sessions (`monitor_cc_testold`, `monitor_cc_testnew`, `worker-testkeep`), ages `testold`, sweeps
only the fixture pair through `sweep_sessions()` directly (never the real `monitor_cc_*` sessions
on the machine). Asserts `list_monitor_sessions()` finds both fixtures and excludes the
`worker-*` one, and that only `testold` gets killed (pane's PID reaped, no orphan) with the
decision recorded in the sweep log.
**Reads:** live tmux state.
**Writes:** three throwaway tmux sessions (removed in a `finally`); appends to this checkout's
real sweep log via `monitor_janitor._log_path()` — running from a worktree writes into that
worktree's `src/logs/monitor_sweep.log`, not the main checkout's, unless `MONITOR_CC_ROOT` is set.
**Called by:** none — run manually; regression guard for `monitor_janitor.py`.
**Calls out:** `src.monitor_janitor` (`/tests/` + `test_*.py` naming exempts this file from the
`block_dev_imports_src` hook).

---

### tests/test_monitor_sweep_scheduler.py (177 LOC)

**Purpose:** Gate-only regression test for `src/menubar/monitor_sweep_scheduler.py`'s
at-most-once-per-24h check — covers the pure `_is_sweep_due(last_ts, now)` boundary cases (fresh
state, 1h ago, 25h ago, exactly-24h) and the full `maybe_run_sweep_workflow(now)` integration
against an isolated temp state file. `_run_sweep` (the real tmux/subprocess work, already covered
by `test_monitor_sweep.py`) is stubbed for every case, so this file touches no real tmux state.
Also covers the re-entry guard (a concurrent tick during an in-progress sweep must not
double-trigger) and that the attempt timestamp lands on disk before a slow sweep finishes.
**Reads:** nothing outside its own isolated temp state files.
**Writes:** isolated temp state files (own tempdir per case, not explicitly cleaned up).
**Called by:** none — run manually; regression guard for `monitor_sweep_scheduler.py`.
**Calls out:** `src.menubar.monitor_sweep_scheduler` (`/tests/` + `test_*.py` naming exempts this
file from the `block_dev_imports_src` hook).

---

## State

`reports/` holds dated `probe_monitor_load.py` output, one file per run — kept as a trail so a
later overload investigation can compare its own probe run against the closest prior report.

## Gotchas

**The daily sweep has no dedicated LaunchAgent** — it runs through
`monitor_sweep_scheduler.py`'s tick inside the menubar app, because a standalone LaunchAgent for
the sweep hit a TCC Full Disk Access wall under launchd. See `process-docs/monitor_lifecycle/`.
