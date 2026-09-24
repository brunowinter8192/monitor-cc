# t1_skill_picker split under the 400 LOC limit — 2026-09-24

`dev/skill_picker/t1_skill_picker.py` was 444 LOC. It is now a 96 LOC runner plus `t1_fixtures.py`, `t1_discovery_cases.py`, `t1_insert_cases.py`, `t1_panel_cases.py` (all under 125 LOC). The case bodies were moved as text slices, not retyped; only imports were adjusted.

## Facts a successor needs

- Each case still runs in its own subprocess: `_spawn_case` calls `python -m dev.skill_picker.t1_skill_picker --case <name>`. The case modules are imported at the top of the runner, after `sys.path` gets the project root. `dev/` has no `__init__.py`; absolute `dev.skill_picker.*` imports work through namespace packages.
- `isolate_home()` must run before the first `src.menubar` import. The fixtures and case modules import `src.menubar` lazily through `_imp`, so importing them at runner start does not break that.
- The runner dropped the unused `write_report` import.

## Equivalence proof

Run before and after with the venv python, `python -m dev.skill_picker.t1_skill_picker`, diff of stdout with the `- time:` line removed. The 12-row table is identical except one detail cell that prints the random temp HOME name (`session_launcher_home_<random>`) in the `isolation` case. Running the script overwrites the tracked `md/t1_skill_picker.md`; it was restored with `git checkout` after each run.
