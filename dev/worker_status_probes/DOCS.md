# dev/worker_status_probes/

## Role
Probe suite for empirically evaluating three candidate tmux activity sensors as replacements for the
JSONL-mtime demote rule in the iterative-dev plugin's worker-status detection (`tmux_spawn.sh`, bash,
not in this repo's `src/`). Produces raw CSVs and a side-by-side comparison report. Touch when
re-evaluating a tmux activity-sensing approach; not a regression suite.

## Flow
`run_all.py` discovers the Opus main session and launches all three probes as concurrent
subprocesses with a shared timestamp; each probe polls its own tmux signal every second and writes a
raw CSV, then a comparison report is produced from all three.

## Modules

### run_all.py (121 LOC)

**Purpose:** Orchestrator — discovers the Opus main session (most recently active non-worker window)
and launches `probe_a.py`/`probe_b.py`/`probe_c.py` as concurrent subprocesses with a shared
timestamp.
**Reads:** tmux `list-windows` to find the Opus session.
**Writes:** nothing directly — delegates to the probe scripts.
**Called by:** none — manual CLI, run via
`./venv/bin/python dev/worker_status_probes/run_all.py [--duration N]`.
**Calls out:** `probe_a.py`, `probe_b.py`, `probe_c.py` via subprocess; tmux CLI.

---

### probe_a.py (80 LOC)

**Purpose:** Polls `#{window_activity}` (a Unix timestamp) for each target session every second,
logging a delta flag when the window received bytes since the last sample.
**Reads:** tmux `display-message -t <session>:0 -p '#{window_activity}'` per tick.
**Writes:** `csv/raw_probe_a_<timestamp>.csv`.
**Called by:** `run_all.py`.
**Calls out:** tmux CLI only.

---

### probe_b.py (135 LOC)

**Purpose:** Activates `tmux pipe-pane` for each target session, routing pane output through
`byte_touch.py`, which touches an activity file and logs cumulative byte count; samples both every
second.
**Reads:** an activity file's mtime and a byte-count file, both under the system temp directory.
**Writes:** `csv/raw_probe_b_<timestamp>.csv`.
**Called by:** `run_all.py`.
**Calls out:** tmux `pipe-pane`; spawns `byte_touch.py` as the pipe-pane target.

---

### byte_touch.py (51 LOC)

**Purpose:** stdin reader invoked by `tmux pipe-pane` — on each non-empty read, touches the activity
file's mtime and overwrites the byte-count file with the cumulative total.
**Reads:** stdin (pane output piped by tmux).
**Writes:** the activity file (mtime touch); the byte-count file (overwrite).
**Called by:** `probe_b.py`, spawned via `tmux pipe-pane` (not imported).
**Calls out:** stdlib `os` only.

---

### probe_c.py (169 LOC)

**Purpose:** Spawns `tmux -C attach-session` per target session; reader threads parse
`%output`/`%extended-output` control-mode events filtered to window 0 pane IDs, sampling event and
byte counters each second.
**Reads:** the control-mode subprocess's stdout, line by line, per session.
**Writes:** `csv/raw_probe_c_<timestamp>.csv`.
**Called by:** `run_all.py`.
**Calls out:** tmux `-C` (control mode) subprocess.

---

## Gotchas
- Probe B leaves `tmux pipe-pane` active if the process is killed without running its atexit
  handler. Recovery: `tmux pipe-pane -t <session>:0` with no arguments stops piping; verify with
  `tmux display-message -t <session>:0 -p '#{pane_pipe}'` returning `0`.
- Probe C's `bytes_last_sec` is the tmux escaped-payload length, not actual byte count (roughly 1.65x
  larger than pipe-pane's byte count due to octal escaping) — use `events_last_sec` as the primary
  signal for Probe C.
- `run_all.py` targets window 0 of non-worker sessions specifically to avoid bead-tracker noise from
  other windows of monitor_cc sessions.
