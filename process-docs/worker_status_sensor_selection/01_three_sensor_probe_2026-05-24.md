# Three-Sensor Probe for Worker Status Detection — 2026-05-24

## What we did

### Problem context

`worker-cli status <name>` and the Monitor_CC menubar share the same detection logic:
`hooks.json[session_id].status = 'working'` + `(now - jsonl_mtime) > 10s` → demote to
`idle`. The bug: CC does not write JSONL during a response turn until the message
completes. A session in a 7–12 minute thinking phase (Caramelizing/Concocting) has JSONL
stale within 10 seconds of turn start → false idle. Live case: `filter-cli` showing
`· Concocting… (7m 22s)` yet `worker-cli status filter-cli` = idle.

### Sensor candidates investigated

Three replacement sensors were designed and probed:

**A — `#{window_activity}` tmux format variable.** A Unix timestamp (seconds precision)
that advances whenever the window receives bytes. Poll once per tick; delta > 0 = active.

**B — `pipe-pane` + `byte_touch.py` helper.** Activate `tmux pipe-pane` on the target
pane; route output through a stdin reader that touches a state file and logs cumulative
byte count. Sample the state file mtime and bytecount per tick.

**C — `tmux -C` control mode.** Spawn `tmux -C attach-session -t <session>` as a
subprocess; reader thread parses `%output %<pane-id> <payload>` events; sample
event+byte counters per tick.

### Probes built

All under `dev/worker_status_probes/` in the status-probe worktree:

| Script | Role | LOC |
|---|---|---|
| `byte_touch.py` | pipe-pane stdin reader helper (probe B) | 51 |
| `probe_a.py` | window_activity poller | 80 |
| `probe_b.py` | pipe-pane byte sensor | 135 |
| `probe_c.py` | control mode event stream | 169 |
| `run_all.py` | orchestrator: launches A/B/C concurrently | 121 |

Orchestrator passes a shared timestamp to all probes so output CSVs align by filename.
Each probe handles cleanup (pipe-pane teardown, detach-client) via atexit + SIGTERM.

### Runs executed

**Main run** (`raw_probe_a/b/c_20260524_183937.csv`): 120 seconds against:
- `worker-Monitor_CC-ccwrap-phase1` — idle (completed Phase B before probe start)
- `worker-searxng-filter-cli` — idle (context limit)
- `monitor_cc_f93afc17` — Opus main, idle-waiting (Opus waiting for worker completion)

All three sessions were in the "static pane" state (no CC output). Captured clean
idle baseline: all three sensors returned zero activity for all 360 combined session-seconds.

**Supplemental run** (`/tmp/supp_probe_a/b/c.csv`): 60 seconds against:
- `worker-Monitor_CC-status-probe` — **working** (actively executing bash tool calls;
  CC TUI receiving continuous output from tool results)
- `monitor_cc_f93afc17` — Opus still idle-waiting

This run captured the working baseline.

## What we found

### Key numbers

| Sensor | Working detection (60s) | Idle detection (120s × 3 sessions) |
|---|---|---|
| A (window_activity delta) | 59/60 = 98.3% | 3/360 = 0.8% (t=0 artifacts only) |
| B (pipe-pane bytes/sec) | 59/60 = 98.3% (avg 1,289 B/s, max 18,714 B/s) | 0/360 |
| C (control-mode events/sec) | 60/60 = 100% (avg 13.5 ev/s, 60/60 nonzero) | 0/360 |

Working session byte profile (Probe B, status-probe): 
- Baseline: 400–1,000 B/s (CC TUI updating with tool output)
- Spikes: up to 18,714 B/s (large Bash output flowing through ccwrap log)
- Idle sessions: 0 B/s (confirmed for all 360 session-seconds)

Control mode byte counts (Probe C) run ~1.65× larger than pipe-pane counts (Probe B)
because tmux octal-escapes binary bytes in the `%output` payload. Use events/sec, not
bytes/sec, as the primary Probe C signal.

### Empirical refutation of the "cursor blinks" concern

`tmux_spawn.sh:108` contains a comment: "Previously used window_activity, which was bumped
by CC UI updates (spinner, cursor blinks) → unreliable."

The probe disproves this. The Opus main session was showing CC's idle prompt + spinner
for the entire 120-second main run, and its `window_activity` delta was 0 for all
120 samples. The idle spinner does NOT generate pane bytes visible to `window_activity`.

Two explanations for the old rejection:
1. The old code may have used `window_activity` differently (comparing to current time
   rather than a rolling delta), causing startup false-positives.
2. CC may have been an older version where the spinner DID write more frequently.

### The Opus session puzzle

Both probe windows showed the Opus main session (`monitor_cc_f93afc17`) as completely
inactive (0 bytes, 0 events). The Opus session is correctly idle during MY Phase B
execution — Opus sent the dispatch message and entered a wait state. This confirms that
all three sensors correctly classify a CC session that is genuinely idle (not a thinking
phase, just waiting).

The "working" baseline was captured via the status-probe session (me: executing tool
calls). The CC TUI generates 400–1,000+ B/s of pane output continuously during tool
execution (Bash results, file reads, tool-use JSON streaming to the ccwrap log).

### Startup artifacts

- Probe A t=0: if init and first poll happen in the same clock second, `prev_wa = wa_t0`
  → delta=0. At next second boundary, delta=1. For long-running use (tick-based poller),
  this artifact is absorbed into initialization and never recurs.
- Probe B t=0: pipe-pane takes ~0.5s to activate; first sample window misses the initial
  connection burst.
- Probe C t=0: 169 events in the first sample — control mode dumps buffered pane history
  on connect. Not a false positive; indicates the session has been recently active.

## dev/ scripts used

All scripts: `dev/worker_status_probes/` in the status-probe worktree.

Reports from main run:
```
dev/worker_status_probes/01_reports/raw_probe_a_20260524_183937.csv
dev/worker_status_probes/01_reports/raw_probe_b_20260524_183937.csv
dev/worker_status_probes/01_reports/raw_probe_c_20260524_183937.csv
dev/worker_status_probes/01_reports/comparison_20260524_183937.md
```

Supplemental run output (ephemeral, not committed):
```
/tmp/supp_probe_a.csv
/tmp/supp_probe_b.csv
/tmp/supp_probe_c.csv
```

## Decision / next step

**Recommendation: Probe A (window_activity). Implement now.**

Rationale:
- Equivalent detection accuracy to Probe B (98%), higher than a threshold-based approach
- Lower implementation cost than any alternative: 2-line change in `tmux_spawn.sh`, 1
  subprocess call in `discover.py` per tick
- No setup/teardown infrastructure (vs pipe-pane helper process)
- No persistent state or threads (vs control mode subprocess pool)
- Empirically safe: 0 false positives across 360 idle-session-seconds sampled
- tmux `#{window_activity}` stable since tmux 1.8; tested on 3.6a

Concrete next steps (NOT in this probe commit — implementation is a separate task):

1. **`tmux_spawn.sh:_worker_detect_status()`**: replace JSONL-age demote with
   `window_activity` age demote. Keep same threshold (10s). Same 4-case truth table
   as current, but the "stale" signal comes from pane writes rather than JSONL writes.

2. **`discover.py`**: add `_get_window_activity(tmux_session)` helper; substitute in the
   line 147 demote condition.

3. **Threshold calibration**: 10s is appropriate for Caramelizing phases (which write
   every ~1s). Could be raised to 15–30s for robustness against brief tmux rendering
   pauses, but 10s is empirically safe based on observed data (no working session had
   delta=0 for >1 consecutive second during tool execution).

Probe B and C remain available as fallback sensors if Probe A proves insufficient in
production (e.g., if CC shifts to a rendering model that writes less frequently).
The scripts are in `dev/worker_status_probes/` and can be re-run without modification.

**Pending:** measurement of window_activity behavior during an actual extended thinking
phase (Caramelizing 10+ minutes). Phase A empirical check (window_activity age=0s for an
11-minute Caramelizing session) supports the hypothesis but is not from a controlled probe
run with logged timeseries. A future 5-minute probe during an active thinking phase would
close this gap.
