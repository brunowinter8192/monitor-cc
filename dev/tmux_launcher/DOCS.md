# dev/tmux_launcher/

## Role

Byte-identity regression harness for `src/tmux_launcher.py`. Add a script here when a
`tmux_launcher.py` refactor (helper extraction, LOC split) needs a before/after correctness proof
of the exact `subprocess.run` argv sequence it issues — this package never invokes real tmux.

## Modules

### argv_byte_identity.py (177 LOC, new 2026-09, remaining-thresholds milestone)

**Purpose:** Byte-identity harness for `launch_split_screen`/`restart_panes`'s function-LOC split.
Monkeypatches `subprocess.run` to record every argv list issued (real tmux never runs) and to
return scenario-appropriate canned stdout/returncode via a stateful `_FakeTmux` that tracks
`new-window`/`split-window` calls so a LATER `list-panes` call in the same run reflects them
(exactly like real tmux would — this is what exercises `restart_panes`'s own "refresh pane list so
subsequent iterations see the new pane" comment). Three scenarios, hashed together:
(1) `launch_split_screen` — session doesn't pre-exist (`has-session` returncode != 0, so
`kill_session` is never called), `attach-session` stubbed (the fake never blocks).
(2) `restart_panes` — all 6 windows + every layout pane already present → pure respawn path, zero
`new-window`/`split-window` calls.
(3) `restart_panes` — window 2 entirely missing (recreate-from-scratch path, exercises the
`pane_specs[1:]` split-after-create loop) AND window 5 present but missing its second pane
`'news-log'` (single-missing-pane split path).
**Reads:** Nothing external — all fixtures are constructed inline.
**Writes:** Nothing — stdout only (`HASH: <hex>`).
**Run:** `./venv/bin/python dev/tmux_launcher/argv_byte_identity.py`
**Calls out:** `src.tmux_launcher` (`launch_split_screen`, `restart_panes`) — imported via a
dedicated function (`_import_tmux_launcher`), not a module-level `from src.` line, per
`block_dev_imports_src`.

Status: hash `f3cc235e20ff81eb2193791f70f2e776555e448617932f7f8f1bb25f79cf5cb6` — identical before
and after the `launch_split_screen`/`restart_panes` LOC split (remaining-thresholds milestone,
2026-09).
