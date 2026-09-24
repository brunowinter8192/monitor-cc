# dev/ram_audit/

## Role
Investigation tooling for pane process RSS growth over long sessions: captures live RAM snapshots from a running pane process on demand. Touch when adding a RAM-dump section or verifying a `src/ram_audit/` refactor; not a regression suite for pane behavior.

## Public Interface
No `__init__.py`. Entry points: `dev/ram_audit/dump_all.sh` and `./venv/bin/python dev/ram_audit/dump_byte_identity.py`.

## Flow
A running pane process registers a SIGUSR1 handler at startup. Sending the signal, directly or via the shell script, writes a dump file to `dumps/`. Nothing here triggers a dump automatically.

## Modules

### dump_all.sh (44 LOC)

**Purpose:** Triggers a RAM dump on every running monitor pane in one shot, then lists the fresh dump files.
**Reads:** the per-pane PID files under the temp dir, written by each pane at startup and removed on exit.
**Writes:** nothing directly; each pane writes its own dump to `dumps/`.
**Called by:** none; run from the project root.
**Calls out:** bash and `kill` only.

---

### dump_byte_identity.py (89 LOC)

**Purpose:** Verification aid, not a test: registers a fake pane, signals itself, normalizes the dump's non-deterministic lines and hashes the rest.
**Reads:** its own freshly written dump file under `dumps/`.
**Writes:** a scratch PID file and dump file, both deleted before exit; stdout only.
**Called by:** none; run before and after a dump refactor. It uses a fixed PID file path, so two concurrent runs collide.
**Calls out:** `src.ram_audit.instrument`, imported lazily to satisfy the dev-imports-src hook.

---

## State
No persistent state. Scratch files live within a single run; the shell script only reads PID files owned by the pane processes.
