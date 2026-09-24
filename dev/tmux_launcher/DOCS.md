# dev/tmux_launcher/

## Role
Regression harness for `src/tmux_launcher.py`'s window/pane layout. Add a script here when a
`tmux_launcher.py` refactor needs a correctness proof of the exact `subprocess.run` argv sequence
it issues — this package never invokes real tmux. A plain hash of the whole argv stream is not
enough on its own: it proves stability but not correctness, and can hide a fixture/production
mismatch behind an unrelated-looking hash change (see Gotchas). Prefer explicit, named,
readable checks over a single opaque digest.

## Public Interface
No `__init__.py` in this directory. Entry point is direct invocation: `./venv/bin/python dev/tmux_launcher/layout_regression_checks.py`.

## Flow
Runs each of three scenarios as its own parallel fail-fast strand (one subprocess via `dev/refactoring/strand_runner.py`), in which it monkeypatches `subprocess.run` to record every argv list issued and return scenario-appropriate
canned output via a stateful fake tmux, drives `launch_split_screen`/`restart_panes` through the strand's scenario, and asserts named, human-readable properties of the recorded argv sequences (creation
order and targets, pane titles, `M-*` binding targets, zero-create invariants, self-heal argv).

## Modules

### layout_regression_checks.py (287 LOC)

**Purpose:** Regression checks for `launch_split_screen`/`restart_panes` across three scenarios:
fresh-session launch (asserts the exact 7-window/8-pane creation sequence, pane-title map, and
`M-*` binding targets); `restart_panes` with every window/pane already present (asserts zero
`new-window`/`split-window` calls — pure respawn); and `restart_panes` with one window missing
entirely plus another window missing one pane (asserts the exact recreate-from-scratch and
single-missing-pane split argv, and that healing lands on exactly 8 respawned panes).
**Reads:** nothing external — all fixtures are constructed inline.
**Writes:** stdout (one `PASS`/`FAIL` line per check inside a strand, one verdict per strand) and `md/layout_regression_checks.md` (fixed name); exits 1 if any strand aborts.
**Called by:** none — manual regression harness, run before and after a `tmux_launcher.py` refactor.
**Calls out:** `src.tmux_launcher` (`launch_split_screen`, `restart_panes`, `_build_mode_commands`)
— imported via a dedicated function, not a module-level `from src.` line, per the
`block_dev_imports_src` hook.

---

## State
No persistent state. `_FakeTmux` instances are created fresh per scenario call and discarded; `subprocess.run` is monkeypatched and restored within each `_capture_*` function's own `try`/`finally`; since every scenario runs in its own process, neither the patch nor the `TMUX` env pop is visible to another scenario.

## Gotchas
- Before the 2-window-split layout change (window `workers` -> `w-tokens`/`w-proxy`), the "every
  window/pane already present" restart fixture had a `--mode workers` typo where it meant
  `--mode worker-tokens`. Because `restart_panes` matches presence by the `--mode` value extracted
  from `#{pane_start_command}`, the mismatch made that scenario silently emit an extra
  `split-window` call even though the module's own claim (and this file's, at the time) was "pure
  respawn, zero create calls". The single combined `HASH:` line changed along with every real
  refactor, so this stayed invisible — nothing ever asserted the "zero create calls" invariant on
  its own. Fixed by writing fixture pane commands with mode strings that actually match
  `_WINDOW_LAYOUT`, and by asserting that invariant explicitly instead of folding it into a hash.
