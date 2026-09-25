# dev/worker_status_probes/

## Role
Probe suite for empirically evaluating three candidate tmux activity sensors as replacements for the
JSONL-mtime demote rule in the iterative-dev plugin's worker-status detection (`tmux_spawn.sh`, bash,
not in this repo's `src/`). Produces raw CSVs and a side-by-side comparison report. Touch when
re-evaluating a tmux activity-sensing approach; not a regression suite.

## Public Interface
No `__init__.py` in this directory. Entry point is direct invocation: `./venv/bin/python dev/worker_status_probes/run_all.py [--duration N]`.

## Flow
`run_all.py` discovers the Opus main session and launches all three probes as concurrent
subprocesses with a shared timestamp; each probe polls its own tmux signal every second and writes a
raw CSV, then a comparison report is produced from all three.

## Modules

### run_all.py (122 LOC)

**Purpose:** Orchestrator — discovers the Opus main session (most recently active non-worker window)
and launches `probe_a.py`/`probe_b.py`/`probe_c.py` as concurrent subprocesses with a shared
timestamp.
**Reads:** tmux `list-windows` to find the Opus session.
**Writes:** nothing directly — delegates to the probe scripts.
**Called by:** none — manual CLI, run via
`./venv/bin/python dev/worker_status_probes/run_all.py [--duration N]`.
**Calls out:** `probe_a.py`, `probe_b.py`, `probe_c.py` via subprocess; tmux CLI.

---

### probe_a.py (74 LOC)

**Purpose:** Polls `#{window_activity}` (a Unix timestamp) for each target session every second,
logging a delta flag when the window received bytes since the last sample.
**Reads:** tmux `display-message -t <session>:0 -p '#{window_activity}'` per tick.
**Writes:** `csv/raw_probe_a_<timestamp>.csv`.
**Called by:** `run_all.py`.
**Calls out:** tmux CLI only.

---

### probe_b.py (128 LOC)

**Purpose:** Activates tmux pipe-pane per target session, routing output through the byte-touch helper, and samples the activity file and byte count every second.
**Reads:** an activity file's mtime and a byte-count file, both under the system temp directory.
**Writes:** `csv/raw_probe_b_<timestamp>.csv`.
**Called by:** `run_all.py`.
**Calls out:** tmux `pipe-pane`; spawns `byte_touch.py` as the pipe-pane target.

---

### byte_touch.py (42 LOC)

**Purpose:** stdin reader invoked by `tmux pipe-pane` — on each non-empty read, touches the activity
file's mtime and overwrites the byte-count file with the cumulative total.
**Reads:** stdin (pane output piped by tmux).
**Writes:** the activity file (mtime touch); the byte-count file (overwrite).
**Called by:** `probe_b.py`, spawned via `tmux pipe-pane` (not imported).
**Calls out:** stdlib `os` only.

---

### probe_c.py (156 LOC)

**Purpose:** Spawns a tmux control-mode client per target session; reader threads count output events and bytes for window 0 panes, sampled each second.
**Reads:** the control-mode subprocess's stdout, line by line, per session.
**Writes:** `csv/raw_probe_c_<timestamp>.csv`.
**Called by:** `run_all.py`.
**Calls out:** tmux `-C` (control mode) subprocess.

---

## State
No module owns persistent state across runs. The pipe and process registries of the second and third probes are process-local, populated during setup and cleared by each script's own exit handler.
