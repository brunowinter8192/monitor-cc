# dev/skill_picker/

## Role
Tests and a read-only probe for the menubar's skill dropdown (`src/menubar/skill_discovery.py`, `skill_insert.py`, `skill_controller.py` and the `skill` grid column in `panel_manager.py`). Touch when changing skill naming rules, the inserted text, the AppleScript or the row button.

## Public Interface
No `__init__.py`. Run from the project root: `venv/bin/python -m dev.skill_picker.t1_skill_picker` and `venv/bin/python dev/skill_picker/p1_real_discovery.py`. `t1_skill_picker.py` imports `test_env` from `dev/session_launcher/`, `p1_real_discovery.py` imports its helpers from there as well.

## Flow
Fixture `.claude` directories and projects are built in a temp directory, the real `src/menubar` modules are imported via `importlib` under an isolated `HOME`, and results go to a PASS/FAIL table under `md/`. Nothing types into a terminal and no menu is popped up.

## Modules

### t1_skill_picker.py (114 LOC)

**Purpose:** Runner for twelve parallel subprocess cases (one isolated HOME each) that owns the case table and writes the PASS/FAIL report.
**Reads:** the case functions of the three `t1_*_cases.py` modules.
**Writes:** `md/t1_skill_picker.md`.
**Called by:** none — run manually after skill picker changes; does not touch a terminal.
**Calls out:** `t1_discovery_cases.py`, `t1_insert_cases.py`, `t1_panel_cases.py`; `dev/session_launcher/test_env.py`.

---

### t1_fixtures.py (80 LOC)

**Purpose:** Fixture builders for the cases — fake `.claude` directory, plugins, project skills, log capture.
**Reads:** nothing external.
**Writes:** files in the temp directory the caller passes in.
**Called by:** the three `t1_*_cases.py` modules.
**Calls out:** none.

---

### t1_discovery_cases.py (122 LOC)

**Purpose:** Five cases for skill discovery — plugins, missing manifest, tripwires, naming rules, project and personal skills.
**Reads:** real `src/menubar/skill_discovery.py` (via `importlib`) with fixtures.
**Writes:** temp directories it removes.
**Called by:** `t1_skill_picker.py`.
**Calls out:** `t1_fixtures.py`.

---

### t1_insert_cases.py (72 LOC)

**Purpose:** Three cases for the inserted text, the AppleScript (compile only via `osacompile`) and the insert failure paths.
**Reads:** real `src/menubar/skill_insert.py` (via `importlib`).
**Writes:** temp directory it removes.
**Called by:** `t1_skill_picker.py`.
**Calls out:** `t1_fixtures.py`.

---

### t1_panel_cases.py (109 LOC)

**Purpose:** Four cases for the skill menu, the grid column, the controller and log isolation.
**Reads:** real `src/menubar` skill controller, panel manager and discover modules (via `importlib`), never shown on screen.
**Writes:** nothing.
**Called by:** `t1_skill_picker.py`.
**Calls out:** `t1_fixtures.py`.

---

### p1_real_discovery.py (61 LOC)

**Purpose:** Read-only probe that lists what the picker would show for two real project cwds against the real `~/.claude`.
**Reads:** real `~/.claude` settings, installed plugins, plugin manifests and skill files; the `general` and `monitor-cc` project skill directories.
**Writes:** `md/p1_real_discovery.md`; picker log lines go to a temp log because `HOME` is isolated.
**Called by:** none — run manually to see the current real skill lists.
**Calls out:** `src/menubar/skill_discovery.py`, `menubar_log.py` (via `importlib`); `dev/session_launcher/test_env.py`.

---

## State
None. Reports in `md/` are overwritten on every run.
