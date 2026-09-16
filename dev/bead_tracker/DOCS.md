# dev/bead_tracker/

## Role
Smoke test for a `bd`-tracking PostToolUse hook — piped crafted payloads at the hook and checked the resulting bead labels. The hook it exercises is gone from the tree; do not treat this as a working regression guard without first restoring or relocating the hook.

## Public Interface
No `__init__.py` in this directory. Entry point is direct invocation: `./venv/bin/python3 dev/bead_tracker/smoke.py`.

## Flow
Creates two temporary beads via the `bd` CLI, pipes four crafted `PostToolUse` payloads to the (missing) hook script, checks resulting bead labels via `bd label list --json`, prints PASS/FAIL per case, then deletes both beads.

## Modules

### smoke.py (152 LOC)

**Purpose:** Creates two temporary beads, pipes four crafted `PostToolUse` payloads to the bead_tracker_hook script, and verifies the resulting `tracked` labels.
**Reads:** `.beads/dolt` (walked up to 6 parent levels from the project root); `bd`'s own stdout.
**Writes:** two temporary beads and their `tracked` label (created and removed within the run); stdout (per-case PASS/FAIL, final summary).
**Called by:** none — DEAD CODE. The bead_tracker_hook script this test targets, under `src/menubar`, does not exist anywhere in the tree, so `_fire_hook` silently does nothing and every case degrades to comparing against an empty label set.
**Calls out:** none (stdlib only; shells out to the `bd` CLI at `/opt/homebrew/bin/bd`).

---

## State
No module-level shared state beyond the process-global `BD_DB` path, set once by `_find_db()` at the start of `smoke_workflow()` and read by every helper thereafter. The only external state this script touches is the real `.beads/dolt` issue database, via the `bd` CLI — two beads are created and deleted within a single run, never left behind on success.
