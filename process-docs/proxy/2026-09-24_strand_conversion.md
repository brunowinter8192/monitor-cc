# Strand conversion of the dev/proxy test suites — 2026-09-24

Files: `test_strip_fix.py` (+ `test_strip_fix_fixtures.py`, whose `check` now raises), `poread_inject_tests.py`, `proxy_bgcomplete_tests.py`, `test_role_keyed_rules.py`, `test_sidecar_delta_chain.py`.

`test_role_keyed_rules.py` was a flat module-level script sharing one `TMP` directory and mutated `rules_config` globals. It is now six strands (role selection, model family, haiku short-circuit, degraded configs, exclude_projects, end-to-end); each strand creates its own temp directory through `_rules_dir()` and passes it to `install_config(config, tmp)`.

`proxy_bgcomplete_tests.py` used to print FAIL lines and always exit 0; its exit code now reflects failures (intended).

B15: `pipeline_byte_identity.py` and `addon_hook_byte_identity.py` are declared as verification aids in DOCS.md (Kind line). Their default input is the newest live `_original.jsonl` under `src/logs/dual_log`; env seams `PROXY_PIPELINE_BYTE_IDENTITY_LOG` and `ADDON_HOOK_BYTE_IDENTITY_LOG` pin it. Nothing else changed in them.

## How a suite was converted to strands

`dev/refactoring/strand_runner.py` provides `strand_workflow(globals(), __file__, _STRANDS, ...)`. Running `python <file>` starts one subprocess per name in `_STRANDS` (`python <file> --strand <name>`), runs them in a ThreadPoolExecutor, lets every sibling finish, prints `PASS <name>` or `ABORT <name>` per strand and exits 1 if any strand aborted.

Conversion recipe applied to every file below:
- The old module-level result lists (`PASS_LIST`, `FAIL_LIST`, `_RESULTS`, `PASS`, `FAIL`) are gone. `check(name, condition, detail="")` prints `  PASS  <name>` or `  FAIL  <name>: <detail>` and raises `AssertionError(name)`, so a strand stops at its first failing check.
- One strand is one test function (the old workflow called them in sequence). `test_strip_fix.py` uses one strand per case group instead (8 groups of the ~120 cases).
- The old workflow function became a one-line orchestrator returning `strand_workflow(...)`; the old summary/exit code code was deleted. Sections INFRASTRUCTURE, ORCHESTRATOR, FUNCTIONS were added where the file had none.
- Each strand is a fresh process, so module-level state (patched `rules_config`, cache lists) cannot leak between strands.

## Equivalence proof used

Before the change each old file was loaded with a wrapper (copy placed next to the original as `__old_<name>.py`, executed as `__main__`, stdout captured, removed afterwards). The ordered list of passed check names was taken from the module's result list, or from the `PASS` lines in the captured stdout where the check only printed. After the change the wrapper ran every strand of `_STRANDS` in parallel, parsed the `PASS` lines, and compared the ordered name list with the old one, plus the parent exit code 0. All 30 converted files matched name for name. Counts: `test_strip_fix.py` 322 names, `poread_inject_tests.py` 37, `test_reqs_pane_numbering.py` 70, `proxy_176_bg_launch_ack_tests.py` 78 (24 strands).

The intended change (a failing check aborts its strand, siblings finish, exit code 1) is shown by `dev/dual_log_cli/tests/strand_abort_probe.py`: it appends a strand `strand_injected_failure` that passes one print, then fails an assertion, to a temporary copy of the suite. Verdict OK for `test_reqs.py`, `test_strip_fix.py`, `test_standalone_sidecar.py`, `proxy_176_strip_tests.py`, `test_whole_stripped_tool_expand.py`, `p2_model_params_probe.py`, `poread_inject_tests.py`.

## Traps seen

- A hook rejects an Edit that adds a `src` import to a dev file; new dev code that needs a src symbol must import it in a module that already imports from src.
- The proxy test files put `src` on `sys.path` and import `proxy.*` bare. The converter adds the project root to `sys.path` before importing `dev.refactoring.strand_runner`; both roots coexist.
- Old `check()` functions returned a bool; no caller used it.
