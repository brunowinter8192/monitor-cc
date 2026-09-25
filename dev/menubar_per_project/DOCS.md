# dev/menubar_per_project/

## Role
Unit-test coverage for the per-project monitor button's branch logic in `src/menubar/system.py`: launch-command construction, kill-then-relaunch and Homebrew python resolution, without real Ghostty or osascript I/O. Touch when changing that launch path.

## Public Interface
No `__init__.py`. Entry path: `python3 dev/menubar_per_project/test_open_or_focus_monitor.py`.

## Flow
Every case builds its own synthetic state, drives the `src.menubar.system` functions with the real I/O boundary monkeypatched out, and asserts on return values, call records and one real subprocess. Cases run as parallel fail-fast strands.

## Modules

### test_open_or_focus_monitor.py (163 LOC)

**Purpose:** Proves session-name reuse, kill-then-relaunch of an existing session, cwd quoting, launchd-PATH python resolution and absence of a Ghostty fallback.
**Reads:** nothing external; monkeypatches module-level functions and restores them per case; one case spawns a subprocess with a temp plist.
**Writes:** stdout per check and strand; `md/test_open_or_focus_monitor.md`; exits 1 if a strand aborts.
**Called by:** none; run manually.
**Calls out:** `src.menubar.system`, `src.tmux_launcher` via `importlib`; the strand runner in `dev/refactoring/`.

---

## State
No persistent state. Each case patches and restores module functions within its own call.
