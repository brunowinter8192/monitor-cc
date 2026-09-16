## Salvage from dev/worker_status_probes/byte_touch.py

```
"""Stdin byte counter helper for probe_b pipe-pane.

Usage (invoked by tmux pipe-pane, not directly):
    python3 byte_touch.py <state_file> <bytecount_file>

On every non-empty stdin read: touches state_file mtime, overwrites bytecount_file
with cumulative byte total. probe_b.py polls both files every 1s.
"""
```

## Salvage from dev/worker_status_probes/probe_a.py

```
"""Probe A: window_activity timestamp polling.

Polls #{window_activity} for window 0 of each target session every 1 second.
Logs delta (0 or 1) indicating whether the window was written since the last sample.

Usage:
    python3 probe_a.py --sessions S1 S2 S3 --duration 120 --outfile /path/to/out.csv

CSV columns: elapsed_sec, session, window_activity_ts, delta
    delta=1  → window_activity changed since last sample (pane received bytes)
    delta=0  → no change (pane was silent this second)
"""
```

## Salvage from dev/worker_status_probes/probe_b.py

```
"""Probe B: tmux pipe-pane byte-rate sensor.

For each session, activates pipe-pane on window 0's active pane, routing output
through byte_touch.py which touches an activity file and logs cumulative byte count.
Samples the activity file mtime and byte count every 1 second.

Usage:
    python3 probe_b.py --sessions S1 S2 S3 --duration 120 --outfile /path/to/out.csv

CSV columns: elapsed_sec, session, activity_mtime, bytecount_total, bytes_last_sec
Cleanup: deactivates pipe-pane on exit (atexit + signal handlers).
"""
```

```
# session → (activity_file, bytecount_file, pane_target)
```

## Salvage from dev/worker_status_probes/probe_c.py

```
"""Probe C: tmux -C control-mode event stream.

Spawns `tmux -C attach-session -t <session>` per target session. A reader thread
parses %output and %extended-output events, filtering to panes in window 0 only
(avoids bead-tracker noise from windows 3/4 of multi-window sessions). Counters
(events, bytes) are sampled and reset every 1 second.

Usage:
    python3 probe_c.py --sessions S1 S2 S3 --duration 120 --outfile /path/to/out.csv

CSV columns: elapsed_sec, session, events_last_sec, bytes_last_sec
Cleanup: sends detach-client to each subprocess stdin, then kills.

Protocol reference: vonbai/goalx cli/tmux_control_watcher.go
                    Handfish/Geppetto docs/WATCHER_ACTIVITY_DETECTION.md
"""
```

```
# session → subprocess
```

```
    """Read %output / %extended-output lines and update per-second counters."""
```
(docstring on `_reader_thread`)

```
    """Return (pane_id, payload) for %output and %extended-output lines, else (None, None)."""
```
(docstring on `_parse_output_event`)

## Salvage from dev/worker_status_probes/run_all.py

```
"""Orchestrator: launch probe_a, probe_b, probe_c concurrently against target sessions.

Discovers the Opus main session dynamically (most recently active non-worker window).
Targets:
  - worker-Monitor_CC-ccwrap-phase1   (idle — completed Phase B)
  - worker-searxng-filter-cli          (idle — context limit)
  - <opus-main-session>                (working — active conversation)

Usage (from project root):
    ./venv/bin/python dev/worker_status_probes/run_all.py [--duration N]
"""
```

```
    """Return session name with the most recently active non-worker window."""
```
(docstring on `_find_opus_session`)

```
        # Only window 0 (CC conversation window); skip bead-tracker windows 3,4
```

## Salvage from dev/worker_status_probes/DOCS.md

Nothing cut — the pre-existing `## Role`, `## Flow`, and `## Modules` sections already fit the required format. The pre-existing `## Gotchas` section has no home in the new fixed format and moved here in full:

```
## Gotchas
- Probe B leaves `tmux pipe-pane` active if the process is killed without running its atexit
  handler. Recovery: `tmux pipe-pane -t <session>:0` with no arguments stops piping; verify with
  `tmux display-message -t <session>:0 -p '#{pane_pipe}'` returning `0`.
- Probe C's `bytes_last_sec` is the tmux escaped-payload length, not actual byte count (roughly 1.65x
  larger than pipe-pane's byte count due to octal escaping) — use `events_last_sec` as the primary
  signal for Probe C.
- `run_all.py` targets window 0 of non-worker sessions specifically to avoid bead-tracker noise from
  other windows of monitor_cc sessions.
```

## Notes for successor

- 5 files, 3 comments + 8 docstrings — matches the measured state exactly. Docstring distribution: `byte_touch.py` 1 (module), `probe_a.py` 1 (module), `probe_b.py` 1 (module), `probe_c.py` 3 (module + `_reader_thread` + `_parse_output_event`), `run_all.py` 2 (module + `_find_opus_session`). Comment distribution: `probe_b.py` 1, `probe_c.py` 1, `run_all.py` 1; `byte_touch.py` and `probe_a.py` have zero non-marker comments.
- No load-bearing docstrings: grepped `__doc__` across the whole directory — zero hits. `probe_a.py`/`probe_b.py`/`probe_c.py`/`run_all.py` all pass a separate literal string to `argparse.ArgumentParser(description=...)`, never `__doc__`. All 8 docstrings deleted outright.
- **Run directly** (safe), with synthetic input:
  - `byte_touch.py`: piped `echo -n "hello world" | python3 byte_touch.py <state> <count>` — it's a plain stdin-to-file byte counter, no tmux/desktop interaction at all. Confirmed output count file matches input length before and after the edit.
  - `probe_a.py`: run with `--sessions __fake_session__ --duration 1 --outfile <tmp>` — `_get_window_activity` only ever calls read-only `tmux display-message`, which returns empty/non-digit stdout for a nonexistent session and is treated as `0`; no real session is required or touched. Confirmed identical CSV output before/after.
- **Not run** (token-skeleton diff instead): `probe_b.py`, `probe_c.py`, `run_all.py`. `probe_b.py` calls `subprocess.run(["tmux", "pipe-pane", "-t", pane_target, cmd], ...)` — a real, state-mutating tmux verb (even against a fake session name, this is the kind of live-tmux-server side effect the milestone's rule about not driving real, shared runtime state is meant to guard against). `probe_c.py` spawns `tmux -C attach-session -t <session>` (a real control-mode client process) via `subprocess.Popen`. `run_all.py` discovers a REAL session via `tmux list-windows` (targeting the actual currently-active Opus main session and named worker sessions) and then launches `probe_b.py`/`probe_c.py` as real subprocesses against it — running it as designed would touch this very live working session. All three classified unsafe; verified via the same token-skeleton method as `dev/bead_tracker/smoke.py` (see that area's notes for the exact mechanism) — `tokenize` output with `COMMENT` tokens and all docstring spans (located via `ast`) stripped, plus structural tokens dropped, compared before vs. after. All three byte-identical.
- DOCS.md rewrite: the `## Gotchas` section (probe B's pipe-pane cleanup recovery command, probe C's byte-count caveat, and `run_all.py`'s window-0 targeting rationale) has no home in the new fixed format, moved here in full — all three facts remain true and load-bearing for anyone re-running this probe suite.
