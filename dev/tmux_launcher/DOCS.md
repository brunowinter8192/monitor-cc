# dev/tmux_launcher/

## Role
Byte-identity regression harness for `src/tmux_launcher.py`. Add a script here when a
`tmux_launcher.py` refactor needs a before/after correctness proof of the exact `subprocess.run`
argv sequence it issues — this package never invokes real tmux.

## Flow
Monkeypatches `subprocess.run` to record every argv list issued and return scenario-appropriate
canned output via a stateful fake tmux, drives `launch_split_screen`/`restart_panes` through three
scenarios, and hashes the recorded argv sequences.

## Modules

### argv_byte_identity.py (177 LOC)

**Purpose:** Byte-identity harness for `launch_split_screen`/`restart_panes` — three scenarios,
hashed together: fresh-session launch (no existing session, so `kill_session` is never called);
`restart_panes` with every window/pane already present (pure respawn, zero create calls); and
`restart_panes` with one window missing entirely plus another window missing one pane (exercises both
the recreate-from-scratch and single-missing-pane split paths).
**Reads:** nothing external — all fixtures are constructed inline.
**Writes:** nothing — stdout only (`HASH:` line).
**Called by:** none — manual regression harness, run before and after a `tmux_launcher.py` refactor.
**Calls out:** `src.tmux_launcher` (`launch_split_screen`, `restart_panes`) — imported via a dedicated
function, not a module-level `from src.` line, per the `block_dev_imports_src` hook.
