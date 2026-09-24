# dev/session_launcher/

## Role
Experiments and regression tests for the menubar Launch tab (`src/menubar/launch_*.py`, `session_launch.py`, `space_switch.py`) and the Auto-Jump removal. The `s*` scripts measure how to switch the active desktop and where a new Ghostty window lands; the `t*` scripts guard the implemented behavior without moving the screen.

## Public Interface
No `__init__.py`. Run from the project root as modules, e.g. `venv/bin/python -m dev.session_launcher.s0_preflight` (the `s*`/`t2` scripts import `dev.session_launcher.space_lib`); `t1_autojump_removal.py` also runs directly.

## Flow
`s*` scripts drive real macOS APIs (CGS space queries, CGEventPost, osascript) and write a table under `md/`; `s1` and `s2` visibly switch desktops and are run only with the user's go. `t*` scripts import the real `src/menubar` modules via `importlib`, use fakes and patches, and write a PASS/FAIL table under `md/`.

## Modules

### space_lib.py (309 LOC)

**Purpose:** Shared ctypes helpers for the experiments — space queries, Ghostty window lists, event posting (hotkey, swipe), return-to-home switching, report writer.
**Reads:** CGS/CoreGraphics state (active space, space list, window list, TCC preflight).
**Writes:** synthetic key and gesture events; `md/<script>.md` via `write_report`.
**Called by:** `s0_preflight.py`, `s1_switch_probe.py`, `s2_ghostty_window_probe.py`, `t1_autojump_removal.py`, `t2_launch_tab.py`.
**Calls out:** `ctypes`, `subprocess` (osascript, ps).

---

### s0_preflight.py (112 LOC)

**Purpose:** Read-only preflight — TCC responsible-process chain, permission state, spaces, Mission Control settings, symbolic hotkeys, Ghostty windows.
**Reads:** `ps`, `defaults`, CGS APIs, `pgrep`.
**Writes:** `md/s0_preflight.md`.
**Called by:** none — run manually; does not move the screen.
**Calls out:** `.space_lib`.

---

### s1_switch_probe.py (140 LOC)

**Purpose:** Measures which techniques switch the active desktop (CGEventPost Ctrl+N variants, System Events, Ctrl+Arrow, synthetic swipe) and how fast.
**Reads:** active space via `space_lib`.
**Writes:** `md/s1_switch_probe.md`; MOVES the desktop and returns home after each variant.
**Called by:** none — run manually, only with the user's go.
**Calls out:** `.space_lib`.

---

### s2_ghostty_window_probe.py (178 LOC)

**Purpose:** After switching to a desktop, opens a Ghostty window via AppleScript and records which space it lands on, then closes it and returns home.
**Reads:** Ghostty window lists (CG and AppleScript), `CGSCopySpacesForWindows`.
**Writes:** `md/s2_ghostty_window_probe.md`; opens and closes Ghostty windows and MOVES the desktop.
**Called by:** none — run manually, only with the user's go; needs `--method a1`.
**Calls out:** `.space_lib`; `osascript`.

---

### t1_autojump_removal.py (141 LOC)

**Purpose:** Regression guard that no Auto-Jump identifier remains in `src/` or `dev/`, that an old settings file still loads, and that the header buttons are static.
**Reads:** all `.py` under `src/` and `dev/`; tempdir settings files.
**Writes:** `md/t1_autojump_removal.md`.
**Called by:** none — run manually after menubar changes; does not move the screen.
**Calls out:** `src/menubar/app_settings.py`, `focus_controller.py`, `app.py`, `panel_manager.py`, `rag_controller.py`, `model_controller.py` (via `importlib`); `.space_lib`.

---

### t2_launch_tab.py (369 LOC)

**Purpose:** Nine parallel subprocess cases covering header texts, occupied-desktop marking, project rows, exact start commands, launch workflow failure stages, click handling and `space_switch` units.
**Reads:** real `src/menubar` launch modules with fakes and patches.
**Writes:** `md/t2_launch_tab.md`.
**Called by:** none — run manually after Launch tab changes; does not move the screen.
**Calls out:** `src/menubar/launch_controller.py`, `session_launch.py`, `space_switch.py`, `panel_manager.py`, `rag_controller.py`, `model_controller.py` (via `importlib`); `.space_lib`.

---

## State
None. Each script is stateless; reports in `md/` are overwritten on every run.
