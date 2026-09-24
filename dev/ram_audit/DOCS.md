# dev/ram_audit/

## Role
Investigation tooling for pane process RSS growth over long sessions — captures live RAM snapshots (gc object counts, tracemalloc top allocators, module-level state sizes) from a running pane process on demand. Touch when adding a RAM-dump section or verifying a `src/ram_audit/instrument.py` refactor; not a regression suite for pane behavior itself.

## Public Interface
No `__init__.py` in this directory. Entry points are direct invocation: `dev/ram_audit/dump_all.sh` and `./venv/bin/python dev/ram_audit/dump_byte_identity.py`.

## Flow
A running pane process registers a `SIGUSR1` handler via `src.ram_audit.instrument.register_ram_dump` at startup. Sending the signal (directly or via `dump_all.sh`) writes a dump file to `dumps/`; nothing in this directory triggers a dump automatically.

## Modules

### dump_all.sh (44 LOC)

**Purpose:** Triggers a `SIGUSR1` RAM dump on every running monitor_cc pane in one shot, then lists freshly created dump files.
**Reads:** `/tmp/.monitor_cc_pid_*` PID files (written by each pane's run loop at startup, removed on exit).
**Writes:** nothing directly — triggers each pane's own dump write to `dumps/`.
**Called by:** none — manual CLI, run via `dev/ram_audit/dump_all.sh` from project root.
**Calls out:** stdlib bash + `kill` only.

---

### dump_byte_identity.py (89 LOC)

**Purpose:** Byte-identity harness for `register_ram_dump`/`_handle_ram_dump` — registers a fake pane, signals itself, reads the resulting dump, normalizes non-deterministic lines, and hashes what remains.
**Reads:** its own freshly-written dump file under `dumps/`.
**Writes:** a scratch PID file and dump file, both deleted before exit — stdout only (one `HASH:` line, plus `register_ram_dump`'s own `[ram-dump] wrote <path>` line on stderr).
**Kind:** verification aid, not a test: it prints a hash and asserts nothing, a human compares two runs taken before and after a change. Input is synthetic, but the run signals itself, waits a fixed 0.2 s, writes into `dev/ram_audit/dumps/` and uses the fixed PID file `/tmp/.monitor_cc_pid_byteidentity`, so two concurrent runs collide.
**Called by:** none — manual regression harness, run before and after a `register_ram_dump`/`_handle_ram_dump` refactor.
**Calls out:** `src.ram_audit.instrument` (`register_ram_dump`) — imported via a dedicated function, not a module-level `from src.` line, per the `block_dev_imports_src` hook.

---

## State
`dump_byte_identity.py` owns no persistent state — its scratch dump file and PID file are created and deleted within a single run. `dump_all.sh` owns no state of its own; it reads PID files written and removed by each pane process's own run loop, which lives outside this directory.
