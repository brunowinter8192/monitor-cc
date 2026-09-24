# dev/monitor_lifecycle/tests/

## Role
Regression tests for the monitor janitor sweep and the scheduler's daily-tick gate, using a private tmux server and temp state files. Touch when changing `src.monitor_janitor` or the sweep scheduler; never point them at the default tmux server.

## Public Interface
No `__init__.py`. Entry paths: `./venv/bin/python dev/monitor_lifecycle/tests/test_monitor_sweep.py` and `dev/monitor_lifecycle/tests/test_monitor_sweep_scheduler.py`.

## Flow
Synthetic or throwaway fixtures feed the real janitor and scheduler functions, one strand per case group, each failing at its first failed check.

## Modules

### test_monitor_sweep.py (101 LOC)

**Purpose:** Regression test for the janitor: throwaway tmux sessions on a private server, asserts kill, spare and untouched outcomes.
**Reads:** the private tmux server only.
**Writes:** the private tmux server and a scratch sweep log, both removed on exit.
**Called by:** none; run manually.
**Calls out:** `src.monitor_janitor`.

---

### test_monitor_sweep_scheduler.py (144 LOC)

**Purpose:** Gate-only regression test for the scheduler's at-most-once-per-day check, re-entry guard and attempt-timestamp ordering.
**Reads:** nothing outside its own temp state files.
**Writes:** isolated temp state files, removed on exit.
**Called by:** none; run manually.
**Calls out:** `src.menubar.monitor_sweep_scheduler`.

---

## State
The tests own only their isolated temp files and private tmux server; neither touches the default tmux server or the live sweep log.
