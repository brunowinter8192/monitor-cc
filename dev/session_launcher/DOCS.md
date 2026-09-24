# dev/session_launcher/

## Role
Experiments and regression tests for the menubar Launch tab (`src/menubar/launch_*.py`, `session_launch.py`, `space_switch.py`) and the Auto-Jump removal. The `s*` scripts measure how to switch the active desktop and where a new Ghostty window lands; the `t*` scripts guard the implemented behavior without moving the screen.

## Public Interface
No `__init__.py`. Run from the project root as modules, e.g. `venv/bin/python -m dev.session_launcher.s0_preflight` (the `s*`/`t2` scripts import `dev.session_launcher.space_lib`); `t1_autojump_removal.py` also runs directly.

## Flow
`s*` scripts drive real macOS APIs (CGS space queries, CGEventPost, osascript) and write a table under `md/`; `s1` and `s2` visibly switch desktops and are run only with the user's go. `t*` scripts first isolate `HOME` (`test_env.py`), import the real `src/menubar` modules via `importlib`, use fakes and patches, and write a PASS/FAIL table under `md/`.

## Modules

### space_lib.py (309 LOC)

**Purpose:** Shared ctypes helpers for the experiments — space queries, Ghostty window lists, event posting (hotkey, swipe), return-to-home switching, report writer.
**Reads:** CGS/CoreGraphics state (active space, space list, window list, TCC preflight).
**Writes:** synthetic key and gesture events; `md/<script>.md` via `write_report`.
**Called by:** `s0_preflight.py`, `s1_switch_probe.py`, `s2_ghostty_window_probe.py`, `t1_autojump_removal.py`, `t2_launch_tab.py`.
**Calls out:** `ctypes`, `subprocess` (osascript, ps).

---

### test_env.py (19 LOC)

**Purpose:** Redirects `HOME` to a throwaway temp directory before any `src.menubar` import, so tests never touch the production app-support dir, log or settings.
**Reads:** nothing.
**Writes:** a temp directory (removed at exit); the `HOME` environment variable of the calling process.
**Called by:** `t1_autojump_removal.py`, `t2_launch_tab.py` (each `t2` case subprocess isolates itself).
**Calls out:** `tempfile`, `shutil`.

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

### t1_autojump_removal.py (131 LOC)

**Purpose:** Regression guard (with isolated HOME) that no Auto-Jump identifier remains in `src/` or `dev/`, that an old settings file still loads, and that save/`FocusController`/`PanelSettings` carry no Auto-Jump remnants.
**Reads:** all `.py` under `src/` and `dev/`; tempdir settings files.
**Writes:** `md/t1_autojump_removal.md`.
**Called by:** none — run manually after menubar changes; does not move the screen.
**Calls out:** `src/menubar/app_settings.py`, `focus_controller.py`, `app.py`, `.space_lib`.

---

### t2_launch_tab.py (91 LOC)

**Purpose:** Runner for eleven parallel subprocess cases (each with its own isolated HOME) that owns the case table and writes the PASS/FAIL report.
**Reads:** the case functions of the three `t2_*_cases.py` modules.
**Writes:** `md/t2_launch_tab.md`.
**Called by:** none — run manually after Launch tab changes; does not move the screen.
**Calls out:** `t2_launch_cases.py`, `t2_workflow_cases.py`, `t2_space_switch_cases.py`; `.space_lib`, `.test_env`.

---

### t2_fixtures.py (62 LOC)

**Purpose:** Shared fakes and constants for the cases — fake app and sessions, session builder, expected project list, header text reader.
**Reads:** real `src/menubar/discover.py` (via `importlib`).
**Writes:** nothing.
**Called by:** the three `t2_*_cases.py` modules.
**Calls out:** none.

---

### t2_launch_cases.py (181 LOC)

**Purpose:** Seven cases for header texts, occupied-desktop marking, tick and selection, project rows, click handling, the PostEvent request on tab open, and log isolation.
**Reads:** real `src/menubar` launch, panel, rag and model controllers with fakes and patches.
**Writes:** nothing.
**Called by:** `t2_launch_tab.py`.
**Calls out:** `t2_fixtures.py`.

---

### t2_workflow_cases.py (73 LOC)

**Purpose:** Four cases for the exact start command and the launch workflow success and failure stages.
**Reads:** real `src/menubar/session_launch.py` and `space_switch.py` with patches.
**Writes:** nothing.
**Called by:** `t2_launch_tab.py`.
**Calls out:** `t2_fixtures.py`.

---

### t2_space_switch_cases.py (77 LOC)

**Purpose:** The `space_switch` unit case, composed of five check functions (PostEvent access, desktop to space id, hotkey key codes, wait until active).
**Reads:** real `src/menubar/space_switch.py` with a mocked CoreGraphics layer.
**Writes:** nothing.
**Called by:** `t2_launch_tab.py`.
**Calls out:** `t2_fixtures.py`.

---

### t3_tab_click.py (292 LOC)

**Purpose:** Six parallel subprocess cases for the clickable tab header — header pieces and ring keys, header structure, pixel equivalence with the old single-button header, wiring, click routing via `performClick_`, and re-centering on panel resize.
**Reads:** real `src/menubar` panel controllers built with a fake app; nothing is shown on screen and no real mouse event is sent.
**Writes:** `md/t3_tab_click.md`.
**Called by:** none — run manually after header or ring changes; does not move the screen.
**Calls out:** `src/menubar/panel.py`, `panel_tabs.py`, `panel_lifecycle.py`, `app.py`, `panel_manager.py`, `rag_controller.py`, `model_controller.py`, `launch_controller.py` (via `importlib`); `.space_lib`, `.test_env`.

---

### p2_panel_snapshot.py (195 LOC)

**Purpose:** Before/after proof for the shared side-panel refactor — snapshots the constructed Sessions/RAG/Models/Launch panels (style, level, collection behavior, frames, full subview tree) and compares two snapshots.
**Reads:** real `src/menubar` controllers built with a fake app and fake status items under an isolated HOME; `/tmp/session_launcher_p2_panel_snapshot/p2_panel_snapshot_before.json` and `..._after.json` in compare mode.
**Writes:** `/tmp/session_launcher_p2_panel_snapshot/p2_panel_snapshot_<label>.json` (with `--label`, not part of the repo); `md/p2_panel_snapshot.md` (compare mode, needs both snapshots present); nothing is shown on screen.
**Called by:** none — run manually with `--label before` on the old code, `--label after` on the new code, then without arguments to compare.
**Calls out:** `src/menubar/panel_manager.py`, `rag_controller.py`, `model_controller.py`, `launch_controller.py`, `panel_lifecycle.py` (via `importlib`); `.space_lib`, `.test_env`.

---

## State
None. Each script is stateless; reports in `md/` are overwritten on every run.
