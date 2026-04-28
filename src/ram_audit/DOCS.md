# src/ram_audit/

## Role

Pane instrumentation for RAM diagnostics. Provides a single helper (`register_ram_dump`)
that wires `tracemalloc` + a `SIGUSR1` signal handler into any pane's run loop. Each pane
calls it once at run-loop entry; the running process then responds to `kill -USR1` by
writing a four-section snapshot to `dev/ram_audit/dumps/`. Touch this package when adding
a new pane that needs RAM profiling or when changing the dump format. Do NOT touch for
normal pane logic changes.

## Public Interface

`register_ram_dump(pane_name, module_state_provider)` — wires `tracemalloc.start(25)`,
PID file at `/tmp/.monitor_cc_pid_<pane_name>`, atexit cleanup, and a SIGUSR1 handler
that writes `dev/ram_audit/dumps/<ts>_<pane_name>.txt`.

## Modules

### instrument.py (97 LOC)

**Purpose:** Shared RAM-dump helper — tracemalloc start, PID file write, SIGUSR1 handler registration, dump file writer.
**Reads:** `module_state_provider()` callback for pane globals; `/proc/<pid>` or macOS `resource.getrusage` for RSS.
**Writes:** `/tmp/.monitor_cc_pid_<pane_name>` (PID file on entry, removed on exit); `dev/ram_audit/dumps/<YYYYmmdd_HHMMSS>_<pane_name>.txt` (dump on SIGUSR1).
**Called by:** `src/core/monitor.py`, `src/panes/token_pane.py`, `src/panes/warnings_pane.py`, `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py`, `src/metadata/metadata_pane.py` (×2), `src/workers/worker_pane.py`.
**Calls out:** `psutil` (optional — RSS source); stdlib `gc`, `tracemalloc`, `resource`, `signal`, `atexit`.

---

## Usage

Trigger a single pane:
```bash
kill -USR1 $(cat /tmp/.monitor_cc_pid_<pane>)
```

Trigger all running panes at once:
```bash
dev/ram_audit/dump_all.sh
```

## Dump format

Each dump contains four sections:

1. **Header** — `timestamp`, `pid`, `rss` (bytes + MB; `psutil` if available, else `resource.getrusage` with macOS/Linux byte vs. KB normalization).
2. **Top-30 gc objects by class** — 2-column table: class name | count. Covers all live Python objects at snapshot time.
3. **Top-30 tracemalloc by lineno** — 3-column table: file:line | size_bytes | count. Requires `tracemalloc.start(25)` (called at registration if not already tracing).
4. **`<pane_name>` module state** — containers (`list`/`dict`/`set`) rendered as `len=N sizeof=M`; scalars as `name = value`. Shape driven by each pane's `module_state_provider` callback.
