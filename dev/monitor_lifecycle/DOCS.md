# dev/monitor_lifecycle/

## Role
Load visibility and regression coverage for the monitor's tmux-session lifecycle: each project's monitor session runs nine panes until something kills it. Touch when changing the janitor sweep, the daily-tick gate, or when investigating pane CPU or age overload.

## Public Interface
No `__init__.py`. Entry paths: `./venv/bin/python dev/monitor_lifecycle/probe_monitor_load.py` and the two scripts under `tests/`.

## Flow
The probe reads live tmux and process state and prints a per-pane table plus a dated report. The tests feed synthetic or throwaway fixtures to the real janitor and scheduler functions, one strand per case group, each failing at its first failed check.

## Modules

### probe_monitor_load.py (128 LOC)

**Purpose:** Snapshots every pane of every live monitor tmux session (mode, PID, age, CPU) and saves a dated Markdown report.
**Reads:** live tmux and process state; no files.
**Writes:** stdout table; `reports/<date>_monitor_load_baseline.md`.
**Called by:** none; run manually.
**Calls out:** none.

---

### tests/test_monitor_sweep.py (101 LOC)

**Purpose:** Regression test for the janitor: throwaway tmux sessions on a private server, asserts kill, spare and untouched outcomes.
**Reads:** the private tmux server only.
**Writes:** the private tmux server and a scratch sweep log, both removed on exit.
**Called by:** none; run manually.
**Calls out:** `src.monitor_janitor`.

---

### tests/test_monitor_sweep_scheduler.py (144 LOC)

**Purpose:** Gate-only regression test for the scheduler's at-most-once-per-day check, re-entry guard and attempt-timestamp ordering.
**Reads:** nothing outside its own temp state files.
**Writes:** isolated temp state files, removed on exit.
**Called by:** none; run manually.
**Calls out:** `src.menubar.monitor_sweep_scheduler`.

---

## State
`reports/` holds dated probe output, one file per run, owned solely by the probe. The tests own only their isolated temp files and private tmux server; neither touches the default tmux server or the live sweep log.
