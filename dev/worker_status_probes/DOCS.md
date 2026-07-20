# dev/worker_status_probes/

Probe suite for empirically evaluating three candidate tmux activity sensors as replacements
for the JSONL-mtime demote rule in `_worker_detect_status` (iterative-dev plugin: `tmux_spawn.sh`, bash — not in `src/`). Produces raw CSVs and a
side-by-side comparison report.

## Usage

From project root:
```bash
./venv/bin/python dev/worker_status_probes/run_all.py [--duration N]
```
`run_all.py` discovers the Opus main session dynamically and launches all three probes
concurrently. The comparison report lands in `md/`; raw per-probe CSVs land in `csv/`.

## Modules

### run_all.py (121 LOC)

**Purpose:** Orchestrator. Discovers Opus main session (most recently active non-worker
window), launches probe_a/b/c as concurrent subprocesses with a shared timestamp.
**Reads:** tmux `list-windows` to find Opus session.
**Writes:** nothing directly — delegates to probe scripts.
**Called by:** user / Opus directly.
**Calls out:** `probe_a.py`, `probe_b.py`, `probe_c.py` via subprocess.

---

### probe_a.py (80 LOC)

**Purpose:** Polls `#{window_activity}` (Unix timestamp) for each target session every
1 second. Logs delta=1 when the window received bytes since the last sample, delta=0
when silent.
**Reads:** tmux `display-message -t <session>:0 -p '#{window_activity}'` per tick.
**Writes:** `csv/raw_probe_a_<ts>.csv` (cols: elapsed_sec, session, window_activity_ts, delta).
**Called by:** `run_all.py`.
**Calls out:** tmux CLI only.

---

### probe_b.py (135 LOC)

**Purpose:** Activates `tmux pipe-pane` for each target session; routes pane output through
`byte_touch.py` which touches an activity file and logs cumulative byte count. Samples both
every 1 second.
**Reads:** `/tmp/probe-b-<name>.activity` mtime; `/tmp/probe-b-<name>.bytecount` total.
**Writes:** `csv/raw_probe_b_<ts>.csv` (cols: elapsed_sec, session, activity_mtime, bytecount_total, bytes_last_sec).
**Called by:** `run_all.py`.
**Calls out:** tmux `pipe-pane`; spawns `byte_touch.py` via pipe-pane.

---

### byte_touch.py (51 LOC)

**Purpose:** stdin reader helper for probe_b. On each non-empty read: `os.utime(state_file)`
+ overwrites bytecount_file with cumulative total. Invoked by tmux pipe-pane; uses system
python3 (stdlib only).
**Reads:** stdin (pane output piped by tmux).
**Writes:** state_file mtime (touch); bytecount_file (overwrite with total).
**Called by:** tmux `pipe-pane` command, not directly.
**Calls out:** stdlib `os` only.

---

### probe_c.py (169 LOC)

**Purpose:** Spawns `tmux -C attach-session` per target session (no PTY needed on macOS).
Reader threads parse `%output` / `%extended-output` events filtered to window 0 pane IDs.
Samples event+byte counters each second.
**Reads:** `proc.stdout` line-by-line per session (control mode protocol stream).
**Writes:** `csv/raw_probe_c_<ts>.csv` (cols: elapsed_sec, session, events_last_sec, bytes_last_sec).
**Called by:** `run_all.py`.
**Calls out:** tmux `-C` subprocess; `threading.Thread` per session.

---

## Output

```
csv/
├── raw_probe_a_<ts>.csv    — window_activity timeseries (360 rows for 3 sessions × 120s)
├── raw_probe_b_<ts>.csv    — pipe-pane byte timeseries
└── raw_probe_c_<ts>.csv    — control-mode event timeseries
md/
└── comparison_<ts>.md      — side-by-side analysis + per-sensor verdicts + recommendation
```

## Gotchas

- Probe B leaves `tmux pipe-pane` active if the process is SIGKILL'd without running atexit.
  Recovery: `tmux pipe-pane -t <session>:0` (no args) stops piping. Verify with
  `tmux display-message -t <session>:0 -p '#{pane_pipe}'` == `0`.
- Probe C `bytes_last_sec` is tmux escaped-payload length, NOT actual byte count (~1.65×
  larger than pipe-pane byte count due to octal escaping). Use `events_last_sec` as the
  primary signal for Probe C.
- `run_all.py` targets window 0 of non-worker sessions to avoid bead-tracker noise from
  windows 3–4 of monitor_cc_* sessions.
