# dev/skill_picker/

## Role
Tests and a read-only probe for the menubar's skill dropdown (`src/menubar/skill_discovery.py`, `skill_insert.py`, `skill_controller.py` and the `skill` grid column in `panel_manager.py`). Touch when changing skill naming rules, the inserted text, the AppleScript or the row button.

## Public Interface
No `__init__.py`. Run from the project root: `venv/bin/python -m dev.skill_picker.t1_skill_picker` and `venv/bin/python dev/skill_picker/p1_real_discovery.py`. Both import helpers from `dev/session_launcher/` (`space_lib`, `test_env`).

## Flow
Fixture `.claude` directories and projects are built in a temp directory, the real `src/menubar` modules are imported via `importlib` under an isolated `HOME`, and results go to a PASS/FAIL table under `md/`. Nothing types into a terminal and no menu is popped up.

## Modules

### t1_skill_picker.py (444 LOC)

**Purpose:** Twelve parallel subprocess cases covering discovery (plugin, project, personal, name rules, tripwires, per-project filtering), the inserted text, the AppleScript, insert failure paths, the menu, the grid column, the controller and log isolation.
**Reads:** real `src/menubar` skill modules with fixtures, fakes and patches; `osacompile` (compile only).
**Writes:** `md/t1_skill_picker.md`.
**Called by:** none — run manually after skill picker changes; does not touch a terminal.
**Calls out:** `src/menubar/skill_discovery.py`, `skill_insert.py`, `skill_controller.py`, `panel_manager.py`, `discover.py` (via `importlib`); `dev/session_launcher/space_lib.py`, `test_env.py`.

---

### p1_real_discovery.py (49 LOC)

**Purpose:** Read-only probe that lists what the picker would show for two real project cwds against the real `~/.claude`.
**Reads:** real `~/.claude` settings, installed plugins, plugin manifests and skill files; the `general` and `monitor-cc` project skill directories.
**Writes:** `md/p1_real_discovery.md`; picker log lines go to a temp log because `HOME` is isolated.
**Called by:** none — run manually to see the current real skill lists.
**Calls out:** `src/menubar/skill_discovery.py`, `menubar_log.py` (via `importlib`); `dev/session_launcher/test_env.py`.

---

## State
None. Reports in `md/` are overwritten on every run.
