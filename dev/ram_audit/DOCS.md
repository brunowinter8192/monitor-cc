# dev/ram_audit/

## Role
Investigation tooling for pane process RSS growth over long sessions — captures live RAM snapshots
(gc object counts, tracemalloc top allocators, module-level state sizes) from a running pane process
on demand. Touch when adding a new RAM-dump section or verifying a `src/ram_audit/instrument.py`
refactor; not a regression suite for pane behavior itself.

## Flow
A running pane process registers a `SIGUSR1` handler via `src.ram_audit.instrument.register_ram_dump`
at startup. Sending the signal (directly or via `dump_all.sh`) writes a dump file to `dumps/`; nothing
in this directory triggers a dump automatically.

## Modules

### dump_all.sh (44 LOC)

**Purpose:** Triggers a `SIGUSR1` RAM dump on every running monitor_cc pane in one shot — iterates
`/tmp/.monitor_cc_pid_*` PID files, sends the signal to each live one, then lists freshly created
dump files.
**Reads:** `/tmp/.monitor_cc_pid_*` PID files (written by each pane's run loop at startup, removed on
exit).
**Writes:** nothing directly — triggers each pane's own dump write to `dumps/`.
**Called by:** none — manual CLI, run via `dev/ram_audit/dump_all.sh` from project root.
**Calls out:** stdlib bash + `kill` only.

---

### dump_byte_identity.py (114 LOC)

**Purpose:** Byte-identity harness for `register_ram_dump`/`_handle_ram_dump`'s report-section
split — calls `register_ram_dump` with a fake pane name and fixed module state, sends itself
`SIGUSR1`, reads the resulting dump file, normalizes out inherently non-deterministic lines
(timestamp/pid/rss header, gc/tracemalloc row values), and hashes what remains.
**Reads:** its own freshly-written dump file under `dumps/`.
**Writes:** a scratch PID file and dump file, both deleted before exit — stdout only (one `HASH:`
line, plus `register_ram_dump`'s own `[ram-dump] wrote <path>` line on stderr).
**Called by:** none — manual regression harness, run before and after a `register_ram_dump`/
`_handle_ram_dump` refactor.
**Calls out:** `src.ram_audit.instrument` (`register_ram_dump`) — imported via a dedicated function,
not a module-level `from src.` line, per the `block_dev_imports_src` hook.

---

## Gotchas
- To trigger a dump on a live pane: `kill -USR1 $(cat /tmp/.monitor_cc_pid_<pane>)`. The handler
  prints `[ram-dump] wrote <path>` to stderr, visible in the pane's tmux output.
- A dump file has four sections: header (timestamp/pid/rss), top-30 gc objects by class, top-30
  tracemalloc allocations by source line (requires `tracemalloc.start(25)` at module import), and
  per-pane module-level state (len + sizeof for containers, scalar values for numbers/strings).
