# dev/ram_audit/

## Problem

`waste_pane` process RSS grows over long sessions. Investigation module to capture live RAM snapshots and identify the top allocators.

## Trigger a dump

```bash
# Send SIGUSR1 to the running waste_pane process:
kill -USR1 $(cat /tmp/.monitor_cc_pid_waste)
```

- **PID file:** `/tmp/.monitor_cc_pid_waste` — written by `run_waste_loop()` at startup, removed on exit.
- **Dumps land in:** `dev/ram_audit/dumps/<YYYYmmdd_HHMMSS>_waste.txt`
- The handler prints `[ram-dump] wrote <path>` to stderr (visible in the pane's tmux output).

## Dump format

Each dump contains four sections:

1. **Header** — `timestamp`, `pid`, `rss` (bytes + MB, sourced from `resource.getrusage` on macOS).
2. **Top-30 gc objects by class** — 2-column table: class name | count. Covers all live Python objects at snapshot time.
3. **Top-30 tracemalloc by lineno** — 3-column table: file:line | size_bytes | count. Requires `tracemalloc.start(25)` (called at module import). Shows which source lines hold the most memory.
4. **waste_pane module state** — len + sizeof for every module-level list/dict; scalar values for floats/ints/strings. Reveals unbounded growth in `_waste_all_events`, `_waste_worker_all_events`, etc.

## Scripts

### dump_all.sh

Triggers a SIGUSR1 RAM dump on every running monitor_cc pane in one shot.

**Usage (from project root):**
```bash
dev/ram_audit/dump_all.sh
```

**What it does:**
1. Iterates all `/tmp/.monitor_cc_pid_*` PID files.
2. For each, verifies the process is alive (`kill -0`), then sends `SIGUSR1`.
3. Sleeps 1 s for handlers to write their dumps.
4. Lists freshly created dump files in `dev/ram_audit/dumps/`.
5. Prints summary: `N dumps written, see dev/ram_audit/dumps/`.

**Graceful handling:** skips stale PID files (process no longer running); exits cleanly with "No active pane PID files found" when no panes are instrumented.

**Equivalent per-pane trigger:**
```bash
kill -USR1 $(cat /tmp/.monitor_cc_pid_<pane>)
# e.g.:
kill -USR1 $(cat /tmp/.monitor_cc_pid_proxy)
kill -USR1 $(cat /tmp/.monitor_cc_pid_warnings)
```
