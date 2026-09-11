# dev/bead_tracker/

## Role

Smoke test for a `bd`-tracking PostToolUse hook — piped crafted payloads at the hook and checked
the resulting bead labels. The hook it exercises is gone from the tree (see Modules); do not treat
this script as a working regression guard without first restoring or relocating the hook.

## Modules

### smoke.py (169 LOC)

**Purpose:** Creates two temporary beads, pipes four crafted `PostToolUse` payloads (single `bd
show`, two chained `bd show` calls, one with a wrong `--db`, one piped to `head`) to
`src/menubar/bead_tracker_hook.py`, and verifies via `bd label list --json` that exactly the
expected bead(s) got the `tracked` label for each case, then deletes both beads.
**Reads:** `.beads/dolt` (walked up to 6 parent levels from the project root); `bd`'s own stdout.
**Writes:** two temporary beads and their `tracked` label (created and removed within the run);
stdout (per-case PASS/FAIL, final summary).
**Called by:** none — DEAD CODE. `HOOK = PROJECT_ROOT / 'src' / 'menubar' / 'bead_tracker_hook.py'`
does not exist anywhere in `src/` (confirmed: no file of that name under `src/`, only this script
and `process-docs/bead_tracker/` reference it) — every case in this suite fires the hook via
subprocess against a path that is not there, so `_fire_hook` silently does nothing and every case
degrades to comparing against an empty label set.
**Calls out:** none (stdlib only; shells out to the `bd` CLI at `/opt/homebrew/bin/bd`).
