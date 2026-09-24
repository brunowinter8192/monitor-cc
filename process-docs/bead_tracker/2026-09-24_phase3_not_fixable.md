# bead_tracker, Phase 3 B17 not applied (2026-09-24)

The finding was to run `dev/bead_tracker/smoke.py` against a scratch `bd` database instead of the live `.beads/dolt`. It cannot be done on this tree:
- `bd` is not installed (`/opt/homebrew/bin/bd` missing, `which bd` empty).
- The hook the script fires, `src/menubar/bead_tracker_hook.py`, does not exist (removed in commit "remove Beads tab + bead code from menubar (decommissioned)"), so every case degrades to comparing against an empty label set. The DOCS.md of the directory already flags the script as dead code.

Nothing was changed. Options for a later session: delete `dev/bead_tracker/` together with its DOCS.md, or restore the hook and `bd` first.

Decision (2026-09-24, same session): `dev/bead_tracker/` was deleted with its DOCS.md. `dev/DOCS.md` contained no reference to it.
