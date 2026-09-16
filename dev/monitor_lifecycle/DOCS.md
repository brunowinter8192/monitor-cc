# dev/monitor_lifecycle/

## Role
Load visibility and regression coverage for the monitor's tmux-session lifecycle: each project's
`monitor_cc_<hash>` session runs nine panes indefinitely until something kills it
(`src/monitor_janitor.py`). Touch when changing the sweep, the sweep's daily-tick gate, or when
investigating a suspected pane CPU/age overload.

## Public Interface
No `__init__.py` in this directory. Entry paths: `./venv/bin/python
dev/monitor_lifecycle/probe_monitor_load.py`, `./venv/bin/python
dev/monitor_lifecycle/tests/test_monitor_sweep.py`, `./venv/bin/python
dev/monitor_lifecycle/tests/test_monitor_sweep_scheduler.py`.

## Flow
`probe_monitor_load.py`: live tmux/`ps` state in -> one row per pane (mode/PID/age/CPU) -> stdout
table + dated report under `reports/`. The two `tests/` scripts: synthetic or throwaway-fixture
input in -> real `src.monitor_janitor`/`src.menubar.monitor_sweep_scheduler` functions under
test -> PASS/FAIL lines to stdout, `sys.exit(1)` on any failure.

## Modules

### probe_monitor_load.py (128 LOC)

**Purpose:** Snapshots every pane of every live `monitor_cc_*` tmux session (mode, PID, age, CPU)
and saves the same data as a dated markdown report.
**Reads:** live tmux state (`tmux list-panes -a`) and live process state (`ps`) — no files.
**Writes:** stdout table; `reports/<date>_monitor_load_baseline.md`.
**Called by:** none — run manually.
**Calls out:** none (stdlib `subprocess`/`re`/`pathlib` only).

---

### tests/test_monitor_sweep.py (90 LOC)

**Purpose:** Regression test for `src/monitor_janitor.py` — creates three real throwaway tmux
sessions, sweeps only the fixture pair, and asserts kill/spare/untouched outcomes.
**Reads:** live tmux state.
**Writes:** three throwaway tmux sessions (removed in a `finally`); appends to this checkout's
real sweep log via `monitor_janitor._log_path()`.
**Called by:** none — run manually; regression guard for `monitor_janitor.py`.
**Calls out:** `src.monitor_janitor` (`/tests/` + `test_*.py` naming exempts this file from the
`block_dev_imports_src` hook).

---

### tests/test_monitor_sweep_scheduler.py (158 LOC)

**Purpose:** Gate-only regression test for `src/menubar/monitor_sweep_scheduler.py`'s
at-most-once-per-24h check, the re-entry guard, and the attempt-timestamp-persisted ordering.
**Reads:** nothing outside its own isolated temp state files.
**Writes:** isolated temp state files (own tempdir per case, not explicitly cleaned up).
**Called by:** none — run manually; regression guard for `monitor_sweep_scheduler.py`.
**Calls out:** `src.menubar.monitor_sweep_scheduler` (`/tests/` + `test_*.py` naming exempts this
file from the `block_dev_imports_src` hook).

---

## State
`reports/` holds dated `probe_monitor_load.py` output, one file per run, owned solely by that
script (`write_report`) — no other module reads or mutates it. Both `tests/` scripts own and
mutate only their own isolated temp files / throwaway tmux sessions per run; neither persists
state across runs.
