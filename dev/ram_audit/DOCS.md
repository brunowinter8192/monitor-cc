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

*(none yet — add analysis scripts here as `A_*.py` per dev/ convention when Phase 2 starts)*
