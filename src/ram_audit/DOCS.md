# src/ram_audit/

## Role

Pane instrumentation for RAM diagnostics. Provides a single helper (`register_ram_dump`) that
wires `tracemalloc` + a SIGUSR1 signal handler into any pane's run loop. Each pane calls it once
at run-loop entry; the running process then responds to `kill -USR1` by writing a four-section
snapshot to `dev/ram_audit/dumps/`. Touch this package when adding a new pane that needs RAM
profiling or when changing the dump format. Do NOT touch it for normal pane logic changes.

## Public Interface

`register_ram_dump(pane_name, module_state_provider)` — wires `tracemalloc.start(25)` (only when
`MONITOR_CC_RAM_AUDIT=1`), a PID file at `/tmp/.monitor_cc_pid_<pane_name>` (with atexit cleanup),
and a SIGUSR1 handler that writes `dev/ram_audit/dumps/<ts>_<pane_name>.txt`.

## Flow

Pane calls `register_ram_dump(name, provider)` once at startup → `kill -USR1 <pid>` (manual, or via
`dev/ram_audit/dump_all.sh`) → the registered handler assembles header + gc + tracemalloc +
module-state sections → writes one `.txt` file per dump.

## Modules

### instrument.py (103 LOC)

**Purpose:** Shared RAM-dump helper — tracemalloc start, PID file write, SIGUSR1 handler registration, dump-file writer. `register_ram_dump` composes the report from `_rss_line()`, `_gc_top_lines()`, `_tracemalloc_lines()`, and `_module_state_lines(provider)`; `_resolve_dump_path` resolves the dump directory under `MONITOR_CC_ROOT` (or two directories above this file) plus `dev/ram_audit/dumps/`.
**Reads:** `module_state_provider()` callback for pane globals; `/proc/<pid>` or macOS `resource.getrusage` for RSS.
**Writes:** `/tmp/.monitor_cc_pid_<pane_name>` (PID file on entry, removed on exit); `dev/ram_audit/dumps/<YYYYmmdd_HHMMSS>_<pane_name>.txt` (dump on SIGUSR1).
**Called by:** `core/monitor.py`, `panes/token_pane.py`, `panes/warnings_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`, `workers/worker_pane.py`.
**Calls out:** `psutil` (optional — RSS source, falls back to stdlib `resource` if absent).

---

## Dump format

Each dump contains four sections:

1. **Header** — `timestamp`, `pid`, `rss` (bytes + MB; `psutil` if available, else `resource.getrusage` with macOS/Linux byte vs. KB normalization).
2. **Top-30 gc objects by class** — 2-column table: class name | count.
3. **Top-30 tracemalloc by lineno** — 3-column table: file:line | size_bytes | count. Requires `tracemalloc.start(25)` (started at registration when `MONITOR_CC_RAM_AUDIT=1`).
4. **`<pane_name>` module state** — containers (`list`/`dict`/`set`) rendered as `len=N sizeof=M`; scalars as `name = value`. Shape driven by each pane's own `module_state_provider` callback.

## Gotchas

- `tracemalloc` only starts when `MONITOR_CC_RAM_AUDIT=1` is set in the environment at process start — a SIGUSR1 dump taken without that env var still writes the RSS/gc/module-state sections, but the tracemalloc section reports "not active".
- The dump directory resolves via `MONITOR_CC_ROOT` if set, else two directories above `instrument.py`'s own `__file__` — same worktree-vs-main-checkout caveat as `monitor_janitor.py`.
