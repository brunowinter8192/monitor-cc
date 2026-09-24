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

## Sub-directories

- `tests/`: Regression tests for the janitor sweep and its scheduler gate. See its own `DOCS.md`.

## State
`reports/` holds dated probe output, one file per run, owned solely by the probe. The tests own only their isolated temp files and private tmux server; neither touches the default tmux server or the live sweep log.
