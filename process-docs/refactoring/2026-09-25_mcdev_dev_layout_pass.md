# mcdev: dev/ module layout pass (2026-09-25)

Branch mcdev (based on integration 9cd11f70). Scope: every Python module under `dev/` brought to INFRASTRUCTURE, ORCHESTRATOR, FUNCTIONS layout, one orchestrator that only calls functions, stepdown order, absolute imports of project code. Zero behaviour change of every script and test, except the intended cases listed under "Decisions and rules for a successor" (two probe guards, import-time registration in `verify_proxy_start_equivalence.py`) and the working `analyze_latency.py`.

## Rules as implemented in the scan (dev/refactoring/layout_scan.py)

The scan is an AST script. It reads all `.py` under `dev/`, writes `dev/refactoring/md/layout_scan_report.md`, exits 1 while violations exist. Rules:

- L1 a module with code has no section marker.
- L2 markers duplicated or not in the order INFRASTRUCTURE, ORCHESTRATOR, FUNCTIONS.
- L3 INFRASTRUCTURE holds only imports, assignments, plain expression statements (sys.path setup, atexit, mkdir); FUNCTIONS holds only defs and classes. Anything before the first marker is a violation.
- L4 the ORCHESTRATOR section is exactly one function.
- L5 that function contains no loops, try, with, nested defs, augmented assignment, delete, imports, comprehensions, lambdas, arithmetic, boolean operators, comparisons or conditional expressions. `if` statements are allowed, their test may be a comparison or boolean expression (but no comprehension).
- L6 the `if __name__` guard body is exactly one statement; no module-level call statements outside INFRASTRUCTURE; a script (guard whose body is not a strand runner call) with two or more functions has an ORCHESTRATOR.
- L7 stepdown: the functions reachable from the orchestrator appear in depth-first order of first reference. A definition needed at import time by another definition (decorator, base class, class-body expression, default argument, annotation) is pulled above its user.
- L8 relative imports, `import src.x`, and bare imports of a `src` top-level name (`from proxy.rules import ...`, `from constants import ...`).

Measured before (2026-09-25): 412 files scanned, 706 violations in 206 files (L1 6, L2 25, L3 62 after allowing expression statements, L4 21, L5 335 items, L6 33 guard bodies plus 2 module-level calls plus 3 scripts without orchestrator, L7 96, L8 101 bare imports plus 1). Result after: 413 files, 0 violations. The list of the four-eyes scan (25 files order, no-marker 6, dev part of the 285 orchestrators) was a subset: real numbers were 8 files without marker (2 of them empty `__init__.py`, so 6 real), 25 order, 59 orchestrator sections not exactly one function, 107 files with logic in the orchestrator.

## Classification of modules without ORCHESTRATOR

Rule (from Main): a module run as a script, or with an entry workflow that executes several steps, has exactly one ORCHESTRATOR function that only calls functions. A pure library whose functions are separate entry points called by other modules has only INFRASTRUCTURE and FUNCTIONS. Pytest style test modules are libraries of independent entry points: no ORCHESTRATOR. The `if __name__` guard stays at file end.

Measured on 2026-09-25 after the pass, 413 files: 246 have an ORCHESTRATOR, 2 are empty `__init__.py`, 165 have none:

- 143 helper libraries imported by other dev modules (import found by module stem name)
- 11 single function or none
- 11 pytest style test modules (`test_*.py`, no guard)
- 0 scripts with a guard but no orchestrator

The earlier "155 files with several functions and no ORCHESTRATOR" were 142 no-guard modules (libraries), 10 pytest style and 3 real scripts (`probe_sys_tool_original_chars`, `test_header_capture`, `strip_tracking_audit`), those three got an orchestrator. Strand-runner tests (guard calls `strand_workflow`) keep their per-case workflow function as ORCHESTRATOR where they had one.

## What was changed, in order (four commits)

1. Bare imports. 40 files imported `proxy.x`, `constants`, `menubar...` after putting `src/` on sys.path. Now `from src.proxy.x import name`. `import proxy.x as y` became `from src.proxy import x as y`. Where the script only put `src/` on the path (four `tool_use_analysis` scripts, `hotkey_latency/analyze_latency.py`), the repo root is put on the path instead. `blast_radius_analysis.py` used `importlib.import_module(_src_pkg + '...')`; now a plain import. Effect for mcsrc: nothing in dev/ depends on the `proxy` top-level package name any more, so its conversion to `from src.x` cannot double-load modules. dev scripts that still use `importlib.import_module('src....')` (click_ui, gpu_pane, input, menubar byte identity, constants) already use the `src.` prefix.
2. Section order and stepdown, mechanical (a relayout tool: nodes moved verbatim, sorted by depth-first call order, guard last, shebang kept; asserted by comparing the multiset of top-level ast dumps before and after). About 125 files. Then hand cases (see below).
3. Guard bodies with more than one statement (31 files: `ok = run_probe_workflow(); sys.exit(0 if ok else 1)` in 8 probes, argparse in the guard in about 20) moved into a new `main()` that becomes the ORCHESTRATOR; the former workflow function became a normal function. Not moved if the guard variables are read as globals by functions (none left after excluding parameter name collisions).
4. Logic in orchestrators extracted (about 290 new functions in 107 files). Extraction unit: a whole hard statement (`for`, `while`, `try`, `with`, `del`, import, augmented assignment, `assert`, `raise`, or an expression statement containing logic), or the value expression of an `Assign`/`Return`, or an `if` test that contains a comprehension. Parameters: names used in the unit, defined earlier in the orchestrator and read before being rebound in the unit. Return values: names stored in the unit that are read later on a path with no intervening rebinding. Text of the unit is copied verbatim.

## Decisions and rules for a successor

- Liveness must be scope aware. First run of the extraction ended with `return ok` for a function whose loop variable was only read again inside a later list comprehension that rebinds `ok` (`dev/setup_py2app/exit_on_failure_checks.py`). That would raise UnboundLocalError for an empty list and passed a meaningless parameter. Fix: reads inside a comprehension or lambda of a name bound by that comprehension or lambda are not reads of the outer name. The whole stage was reverted to the previous commit and rerun. If you change the extraction, rerun from the commit before it, do not patch by hand.
- Insertion point of new functions must come from the AST, not from a text search for `if __name__`. `dev/refactoring/strand_runner_selftest.py` keeps a fake script in a triple quoted string that contains `if __name__ == "__main__"`; the first run put the new functions into the string and only the undefined-name check caught it. The check used: `symtable` over each module, report global names that are referenced in a function but neither defined at module level nor builtin, compared with the same check on the base commit.
- Import time statements and definitions. INFRASTRUCTURE may not hold defs or classes, so constants computed by a helper function were rewritten: walk-up loops (`while _AREA_ROOT.name != 'proxy_dual_log'`) became `next(p for p in Path(__file__).resolve().parents if p.name == '...')` (16 files), the `_main_checkout_root` helper became a conditional-expression constant (5 files), `if (repo/'src'/'logs').is_dir(): ... else:` became a conditional expression (2 files), `_ts` in `test_log_janitor.py` became a format constant, `_write_fixture` in `test_block_po_read.py` became two `Path.write_bytes` calls, two ctypes Structure classes in `hotkey_latency/probe_get_event_time.py` became `type(name, (ctypes.Structure,), {...})` assignments (same class, same fields), `importlib.import_module` alias blocks with `del` in three replay scripts became plain `from src... import` lines. Two identical `_resolve_main_project` resolvers and `_resolve_repo_root` went to `dev/refactoring/repo_roots.py`, imported through the repo root on `sys.path` (the same way as `dev.refactoring.strand_runner`).
- Tables that refer to functions defined below (`CASES`, `_SCENARIOS`, `SCENARIOS`, `_seed_and_run`, `DESKTOP_METHODS`, `_CASES`, `STRANDS = [n for n in globals() ...]`) cannot sit in INFRASTRUCTURE. They became functions returning the same object (`cases()`, `scenarios()`, ...). `DESKTOP_METHODS` is imported by `session_launcher/s1_switch_probe.py` and `s2_ghostty_window_probe.py`; both now import `desktop_methods` and call it. The module-level registration loop in `verify_proxy_start_equivalence.py` (`globals()[f'case_{name}'] = ...`) became `register_case_strands(namespace)` called from the guard line, which strand_workflow needs before it reads `globals()`.
- Module-level `main()` calls in `cursor_edges/probe.py` and `nsgridview_migration/probe.py` became `if __name__ == '__main__': main()`. Running the script is unchanged; importing the module no longer opens a window (the hazard noted in the 2026-09-16 pass).
- Orchestrators with `try/finally` around a `return` (`test_proxy_start_fallbacks.fallback_workflow_case`) and with a `return` inside a loop (`s2_ghostty_window_probe.main`) were restructured by hand: the loop moved into `_run_cycles` which returns the results, the abort branch and the normal path write the same report (identical text in both), so behaviour is the same.
- `verbosity/extract_turns.py` was a script without functions. Now three functions and an orchestrator; the statements are verbatim. Same output file bytes (md5 identical, run before and after against the real session files).
- Function local imports: superseded by the review round below (this pass first left all 227 in place).

## Proof

Harness (in /tmp, not committed): build a base tree from the base commit and an after tree from the worktree, both placed next to the worktree with the same directory depth (`.claude/worktrees/mcdev_base`, `mcdev_after`, gitignored, deleted at the end), run every touched script in both with the venv python, 8 in parallel, stdin closed, 150 s timeout. Compared: return code, stdout, stderr (normalized: tree root, temp paths, timestamps, durations, line numbers), and every file created or changed in the tree (names with long digit runs normalized). For modules without a guard the harness imports them with `runpy` under a non-main name and compares the sorted global names with the repr of simple values.

Result on the final tree, 206 touched files: 178 executed, 28 not executed (live infrastructure).

- 145 identical output, 14 identical apart from the traceback frames of a baseline failure (compared by last exception line and stdout: SAMEX).
- `dev/hook_smoke/run_all.py` rc 0 before and after, identical; `dev/menubar/p5_run_all.py` rc 0 before and after, identical; `dev/hook_smoke/test_bg_task_detection.py` runs and passes (the menubar import cycle fix on integration is in the base).
- 19 differences, all explained: timestamps in report names or live data (`A_extract_cache_turns_proof`, `post_restart_verification`, `session_analysis/01_extract`, `cc_injection_inventory`), three lib-mode comparisons where the module now defines `_MAIN_CHECKOUT_ROOT`/`_PROJECT_PARTS` and lost `_main_checkout_root`, `strand_runner` gained `compute_exit_code`, `blast_radius_analysis` lost `importlib`/`_render_messages_mod`, `strip_audit_classify` has `_root_dir` instead of `_src_dir`, `repo_roots` is new, the SyntaxWarning line number in `scan_sr_catalog` (an invalid escape in the script, present before), tracebacks of scripts that fail before and after (missing corpus, missing `src.proxy.pending_bg_state`, no tty).
- Two flaky scripts under 8-way load fail in one of the two trees and pass in the other run: `verify_proxy_start_equivalence` (first_run_ca) and `test_proxy_start_fallbacks` (mitmdump_start_failure_aborts). Repeated 4 times per tree in parallel, each 4 of 4 passed for both trees. Count fixed before the run.
- Not executed (denied list: real windows, real tmux sessions, real hotkeys, launchctl, live proxy): `desktop_allocation`, `session_launcher`, `menubar_nspanel`, `cursor_edges`, `nsgridview_migration`, `coteditor`, `hook_error_correlation`, `monitor_lifecycle`, `tmux_launcher`, `worker_pane_split`, `worker_status_probes`, `skill_picker`, `setup_py2app`, plus `hotkey_latency/probe_get_event_time.py`, `model_selector/verify_three_tab_ring.py`, `hook_smoke/probe_bg_task_live.py`, `bg_wakeup_id_line/p2_bg_escape_probe.py`, `menubar_per_project/test_open_or_focus_monitor.py`. Proof for these: the extraction is verbatim by construction plus a statement-multiset comparison base versus after (every statement of the base that is not in the after file is one of the replaced call statements; listed and read for the largest changes: `hook_error_correlation/analyze.py`, `s2_ghostty_window_probe.py`, `t3_tab_click.py`, `exit_on_failure_checks.py`, `p2_bg_escape_probe.py`, `t1_skill_picker.py`) and the undefined-name check (0 new).
- Final state of the scan: 413 files, 0 violations. Also 0 modules of 400 LOC or more, 0 functions of 50 lines or more, 0 comments other than the three markers and shebangs, 0 docstrings in dev/.

## Findings for Main (not fixed)

- Dead scripts: `dev/pipeline/memory_profile/01_cache_growth.py` and `dev/pipeline/parsing_profile/01_multipass_cost.py` import `src.jsonl_parser`, a module that was split into `src/jsonl/` long ago; the imported functions (`parse_jsonl_lines`, `extract_tool_calls`, `extract_user_prompts`, `extract_user_media`, `extract_thinking_blocks`, `extract_skill_activations`) no longer exist anywhere in `src/`. Fixing the module path would not make the scripts run; left as is. Also dead before and after: `timer-loop/bg_completion_scan.py` and `p3_project_scope_incident_probe.py` (`src.proxy.pending_bg_state` does not exist), the 176 ack case modules without their entry script.
- mcsrc coordination: run with the src of branch mcsrc (base tree with my dev and integration src, after tree with my dev and mcsrc src, all 413 dev files): 334 executed, everything identical except `dev/proxy/test_live_copy_bootstrap.py`, which fails against mcsrc's `proxy_addon.py` (live copy now needs `.proxy_live_<id>/src/proxy`, error `proxy package not found under ...`). mcsrc's branch changes that test itself; `git merge-tree` of mcdev with mcsrc reports one conflict, `dev/refactoring/DOCS.md`, and merges `test_live_copy_bootstrap.py` cleanly. mcsrc adds eight dev/refactoring modules (`ast_import_equivalence`, `ast_reorder_equivalence`, `hook_matrix`, `import_smoke`, `live_proxy_sandbox`, `orch_diff_cases`, `pinned_harness_runner`, `stepdown_reorder`) that violate my scan (12 L5, 3 L7). They must be brought to the layout after both branches are merged into integration.
- Variance in the base: `test_proxy_start_fallbacks` and `verify_proxy_start_equivalence` are flaky under heavy parallel load in the base tree too.

## Hints

- `sed` on macOS has no `\b`; the first attempt to rename `DESKTOP_METHODS` did nothing silently. Use Python.
- `gcommit` stages everything in the worktree; run it from the worktree root.
- The scan treats `if` tests as free logic on purpose (the standard lets the orchestrator decide with a condition); everything else that computes is extracted.

## Review round (four-eyes findings F3 to F11, same day)

Scan rules added (`layout_scan.py`, with the import rules split into `layout_scan_imports.py` because the scan grew past 400 LOC): `raise` and `assert` are logic statements in an orchestrator (F3); subscripts and f-strings count as expression logic there (F7); an assignment of a literal (constant, tuple or non-empty list, dict, set of literals) in an orchestrator is a violation, empty `[]`/`{}` accumulators are not (F7); every function local import is a violation unless one of the reasons below holds (F4); `scan_workflow()` takes no argv and the report no longer carries a date, so reruns leave `md/layout_scan_report.md` unchanged (F11). Before the fixes the extended scan reported 149 violations in 76 files (22 literal assignments, 101 f-strings, 23 subscripts, 2 raises, 1 stepdown) and 222 local imports in 61 files; after: 0 violations on 414 files.

Fixes and how they were made:
- F3/F7: the extraction tool was rerun from the previous commit with the wider rules. Literal constants assigned once in an orchestrator (about 20) became module constants in INFRASTRUCTURE (`x = 5` becomes `DEFAULT_X`/`X` at the end of INFRASTRUCTURE, uses renamed); literal lists and dicts and every f-string or subscript statement moved into helpers; the two `raise RuntimeError(...)` (`cc_injection_inventory`, `attribution_coverage`) are helpers that raise, the orchestrator keeps only `if not ...:` and the call.
- F8: the numbered and misleading helpers were renamed by reading each body: `install_signal_handler_2` became `install_sigint_exit_handler` (the SIGTERM twin `install_sigterm_exit_handler`), `update_lines*` became `append_whole_tool_coverage`, `append_tool_content_stability`, `append_system_stability`, `append_recording_pattern`, `update_rows*` became `append_forwarded_rows`/`append_transcript_rows`, `print_project_without_a` became `print_missing_project_value_verdict`, `print_build_variants` became `run_variants_until_return_fails`, the three `compute_value` became `make_fixed_clock`, `make_terminal_size_getter`, `compute_grand_total` (and `compute_fix_with_leaf_rects` in `cursor_edges/probe.py`), `run_step` (returns an emitter) became `make_emitter`, `check_condition` (any case failed) became `any_case_failed`, `raise_error` became `raise_no_log_files_matched`/`raise_no_pairs_found`, and so on in `render_recorded_request`, `07_quartet_prefix_diff`, `p5_mid_turn_user_msg_preserve_probe`, `rs_truncation_preserve_replay`. Identical small helpers (`exit_with_status`, `collect_results`, `compute_exit_code`, `write_report_text`) stay copied per module: the scripts are independent.
- F4: function local imports moved into INFRASTRUCTURE (stdlib always; project imports when nothing at runtime depends on their order). Helpers that only hosted an import (`load_imports` in four modules) were deleted together with their call sites. Where a base helper returned an imported name and the caller assigned it under another name (`is_nuke_text`, `render_pane`, `toggle_state`, `button_regions`, `format_warnings_pane`, `proxy_addon_cls`) the top level import keeps that name through `as`; the helpers `_import_gpu`, `_import_panes`, `_shape_classifier` remain and return the now global names. A first version of the move used a weaker rule and broke 15 scripts in the before/after run (`No module named 'src'` because a loader function or the caller sets `sys.path` later, `PROXY_LOG_ID is not set` because a function sets the environment between the helper call and the import). The whole round was reverted to the previous commit and redone with the rule below. A second slip was caught by the same run: `import traceback; traceback.print_exc()` sat on one line in `green_overlay_probe.py`, the move removed both statements; the three `traceback.print_exc()` calls were restored. Lesson: a statement multiset comparison must also list lost expression statements, not only assignments.
- Remaining function local imports, all justified (scan rule in `layout_scan_imports.local_import_allowed`, the first line of each block is the reason, lines refer to the final tree):

```
module has no sys.path setup; the caller or a loader function puts the repo root on the path
  dev/click_ui/proxy_copy_probe_shared.py:18
  dev/proxy/test_strip_fix_cases_badge.py:33
  dev/proxy/test_strip_fix_cases_badge.py:47
  dev/proxy/test_strip_fix_cases_badge.py:179
  dev/proxy/test_strip_fix_cases_badge.py:183
  dev/proxy/test_strip_fix_cases_badge.py:183
  dev/proxy/test_strip_fix_cases_badge_nudge.py:90
  dev/proxy/test_strip_fix_cases_badge_nudge.py:105
  dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_spans_cases.py:31
  dev/proxy_dual_log/test_composition_invariant/composition_probe_passes.py:27
module mutates os.environ/sys.path/sys.modules at runtime; the import order relative to that mutation is behaviour
  dev/jsonl/test_jsonl_reader.py:59
  dev/jsonl/test_jsonl_reader.py:73
  dev/jsonl/test_jsonl_reader.py:86
  dev/jsonl/test_jsonl_reader.py:103
  dev/jsonl/test_jsonl_reader.py:118
  dev/monitor_root/test_monitor_root.py:71
  dev/monitor_root/test_monitor_root.py:80
  dev/monitor_root/test_monitor_root.py:88
  dev/monitor_root/test_monitor_root.py:94
  dev/monitor_root/test_monitor_root.py:105
  dev/monitor_root/test_monitor_root.py:119
  dev/pane_flicker/scenario_lib.py:245
  dev/pane_flicker/scenario_lib.py:38
  dev/pane_flicker/scenario_lib.py:39
  dev/pane_flicker/scenario_lib.py:40
  dev/pane_flicker/scenario_lib.py:100
  dev/pane_flicker/scenario_lib.py:212
  dev/panes/test_display_tripwires.py:60
  dev/panes/test_display_tripwires.py:78
  dev/panes/test_display_tripwires.py:87
  dev/panes/test_display_tripwires.py:109
  dev/panes/test_display_tripwires.py:110
  dev/panes/test_display_tripwires.py:121
  dev/proxy/addon_hook_byte_identity.py:87
  dev/proxy/test_proxy_env_and_family.py:144
  dev/proxy/test_proxy_env_and_family.py:165
  dev/proxy/test_proxy_env_and_family.py:167
  dev/proxy_display/test_forwarded_tripwires.py:64
  dev/proxy_display/test_forwarded_tripwires.py:75
  dev/proxy_display/test_forwarded_tripwires.py:94
  dev/proxy_display/test_forwarded_tripwires.py:102
  dev/proxy_display/test_pd10_lazy_messages.py:63
  dev/proxy_display/test_pd10_lazy_messages.py:71
  dev/proxy_display/test_pd10_lazy_messages.py:72
  dev/proxy_display/test_pd10_lazy_messages.py:73
  dev/proxy_display/test_pd10_lazy_messages.py:74
  dev/proxy_display/test_pd10_lazy_messages.py:82
  dev/proxy_display/test_pd10_lazy_messages.py:96
  dev/proxy_display/test_pd10_lazy_messages.py:111
  dev/proxy_display/test_session_marker_states.py:65
  dev/proxy_display/test_session_marker_states.py:66
  dev/proxy_display/test_session_marker_states.py:76
  dev/proxy_display/test_session_marker_states.py:96
  dev/proxy_display/test_session_marker_states.py:111
  dev/proxy_display/test_session_marker_states.py:112
  dev/proxy_display/test_session_marker_states.py:113
  dev/proxy_display/test_session_marker_states.py:123
  dev/workers/test_worker_probes.py:61
  dev/workers/test_worker_probes.py:70
  dev/workers/test_worker_probes.py:71
  dev/workers/test_worker_probes.py:99
  dev/workers/test_worker_probes.py:114
optional dependency guarded by ImportError
  dev/pane_flicker/scenario_lib.py:57
  dev/pane_flicker/scenario_lib.py:60
target module or names do not exist (dead import)
  dev/timer-loop/p3_project_scope_incident_probe.py:140
```

- F5: bare sibling imports (`from case_strands import ...`, `from hook_runner import ...`, 270 statements in 157 files) stay. Documented exception: dev scripts are started by path (`python3 dev/<area>/<script>.py`, from any working directory), Python puts the script directory on `sys.path[0]`, so the sibling is found under its bare module name; an absolute form would need `dev/<area>` to be a package with `__init__.py` files (there are none, and the area directory names contain hyphens: `native-model-start`, `timer-loop`) plus the repo root on the path in every script, and would break the direct `python3 script.py` runs that the DOCS.md files describe. Imports of project code from `src/` and the shared dev helpers (`dev.refactoring...`) are absolute. The scan exempts a bare import only when a `.py` file or directory with that name exists next to the script (`is_local_sibling`); a bare import of a `src` top-level name is a violation (L8).
- F6 (not requested, recorded): INFRASTRUCTURE still holds executed statements (sys.path and environment setup that must precede the imports, `atexit.register`, `os.makedirs`, two `Path.write_bytes` fixtures in `test_block_po_read.py`). The scan allows plain expression statements there by decision.
- F9: the first paragraph and step 4 of this file were corrected (see the changed lines above); with the scan rules of this round `assert` and `raise` in orchestrators are counted.
- F10: `dev/refactoring/DOCS.md` was checked: the Public Interface wording (strand runner, check group, repo-root resolvers) is right, `check_group.py` exists as a separate module next to `check` in `strand_runner.py`. The DOCS gained `layout_scan_imports.py`; LOC headings equal `wc -l`.

Proof for the round (2026-09-25): 187 touched scripts executed against the base commit 9cd11f70: 145 identical, 14 identical up to traceback frames of baseline failures, 28 differences, all explained (report file names with timestamps, live corpus growth in `session_analysis/01_extract`, `replay_*_strip`, `render_byte_identity` (rerun with a frozen corpus copy through `RENDER_BYTE_IDENTITY_LOG_DIR`: identical HASH), modules that now define constants or import names at top, dead scripts failing the same way). `hook_smoke/run_all.py` and `menubar/p5_run_all.py` identical. Undefined-name check: 0 new. Run with the src of branch mcsrc: same picture as before, `test_live_copy_bootstrap.py` still needs mcsrc's own update of that test. The eight new mcsrc modules in `dev/refactoring/` were left to mcsrc as instructed.

## Review round 2 (defects R2-1 to R2-3, notes R2-7, R2-8)

- R2-1 (`desktop_allocation/03_field_availability_probe.py`): the extraction turned `ghostty_detail: List[Dict] = []` into a helper that assigned a local and returned nothing, so the name was unbound when `ghostty_pid` is falsy. Cause: the liveness rule treated the conditional store `if ghostty_pid: ghostty_detail = ...` as a rebinding that kills liveness of the earlier store. Now one helper `collect_ghostty_detail(cid, ghostty_pid, raw_ptr)` returns the list (empty without pid). Audit of all new helpers of the branch for "assigns a local at helper top level, does not return it, the caller loads it without a top-level store": this was the only hit (two other hits were subscript and attribute stores on globals). Not executed, the script needs live windows.
- R2-2 (`pane_flicker/bench_hover_render.py`) and R2-3 (`timer-loop/p3_project_scope_incident_probe.py`): the moved local imports were restored to their functions. In `bench_hover_render.py` the tree that `src` comes from is chosen by `--root` at runtime (`Sim`/`load_root` puts it on the path); in the timer-loop probe `src.proxy.addon` builds `ProxyAddon()` at import and needs `PROXY_LOG_ID`, which `mock.patch.dict(os.environ, ...)` sets inside the test function. `composition_probe.py` (R2-4) was restored the same way: `sys.path.insert(0, ".")` makes the import depend on the working directory, so it stays in `load_imports`; only its stdlib `import traceback as tb` moved to the top.
- Scan rule (`layout_scan_imports.py`): environment or path setup that a local import may depend on now includes `patch.dict`, `patch.object`, `setenv`, `environ.pop`, `load_root`, and the header expressions of `with` statements (the miss was that only assignments and expression statements were inspected, so `with mock.patch.dict(os.environ, ...)` was invisible). A `sys.path` statement counts as path evidence only if it names the repo root (`parents[`, `.parent.parent`, `ROOT`, `WORKTREE`, `'..'`, `MONITOR_CC_ROOT`); inserting the script's own directory does not (that was the miss for `bench_hover_render.py`). The rule stays heuristic: it allows a local import when the module has any such setup anywhere, it does not order the import against the setup; a top-level import that should have stayed local is not detectable by the scan, only by running the script.
- Every import moved in the review round was re-checked with fresh interpreters: for each of the 114 files that changed between the reviewed commit 77305631 and the working tree, `env -i` (PATH and HOME only, project venv), import via `runpy` with the working directory at the script directory and at the repo root, and `--help` for the scripts that use argparse and are not live probes; return code and last stderr line compared with the reviewed commit; 245 runs. First run: 3 differences (`composition_probe` import from the script directory, and the two new modules that did not exist before). After the fixes: 243 same, only `layout_scan_imports.py` differs (new file). Against the round-1 state of the four files above the differences are the fixes themselves (`RuntimeError: PROXY_LOG_ID is not set` and `No module named 'src'` disappear).
- Before/after run of the 12 executable files touched in this round against base 9cd11f70: 8 identical or same failure, the remaining one (`p3_project_scope_incident_probe`) differs only by the message of its dead import (`src.proxy.pending_bg_state` instead of `proxy.pending_bg_state`).
- R2-8: ten helpers that only returned a constant (`compute_total_requests`, `compute_total_checks`, `compute_all_pass`, `compute_attribution`, `compute_orig_by_flow`, `compute_total_parse_errors`, `compute_total_written`) became INFRASTRUCTURE constants `INITIAL_<NAME>` and the helpers were deleted; the scan flags such a helper (L9). Cause of the leftover: the value went through a rebinding `x = 0; x = f(x)` that the literal-assignment rule cannot see. Weak names listed in R2-8 (`assign_values` and others) are unchanged.
- `strand_runner.py` and `strand_runner_selftest.py`: both orchestrators already call only functions (`compute_exit_code`, `run_selftests`). mcsrc's `src_layout_scan.py` (branch mcsrc) run over the files of `dev/refactoring/` of this branch reports no findings. The `0 if all(...) else 1` in the orchestrator that the mcsrc copy of `strand_runner.py` still carries is the one that was moved out here.

## Review round 3 and recap

Round 3 of the four-eyes review found 0 defects. The bare sibling imports (round-1 F5, R2-6) stay as the documented exception described above. Inventory at recap: 223 `.py` files differ from integration, 61 DOCS.md files changed (LOC headings and the two `dev/refactoring` entries), all headings equal `wc -l`, layout scan 414 files with 0 violations, working tree clean. Open for a later session: after mcsrc is merged into integration, merge integration into mcdev and bring mcsrc's eight new `dev/refactoring/` modules to the layout; `test_live_copy_bootstrap.py` needs mcsrc's own update.

## Merge of integration with mcsrc (2026-09-25)

Conflicts: only DOCS.md files (`dev/refactoring`, `dev/proxy`, `dev/model_selector`); entries of both sides kept, Role of `dev/refactoring` rewritten to cover scan, helpers and proof harnesses, LOC headings re-checked with `wc -l` (0 mismatches, every dev module documented). `dev/proxy/test_live_copy_bootstrap.py` merged cleanly: mcsrc's live-copy layout update plus this branch's helper extraction. The layout scan flagged 17 violations in 10 files that came from integration (mcsrc's eight `dev/refactoring` modules plus `test_api_errors_ts.py` and `verify_apply_flash_layout.py`): stepdown order (7), orchestrator logic (5), one literal assignment, four stdlib local imports in `orch_diff_cases.py`; fixed with the same relayout, extraction and import-move tools; mcsrc's own `src_layout_scan.py` reports nothing for `dev/refactoring`. After: scan 425 files, 0 violations; undefined-name check 0 new. Runs in a copy against merged integration: `hook_smoke/run_all.py`, `menubar/p5_run_all.py`, `proxy/test_live_copy_bootstrap.py` identical (rc 0). Fresh-interpreter import comparison of all 425 dev modules (`env -i`, import from script dir and repo root, `--help` where argparse): 890 runs, 869 identical, 21 differences all explained: new files of this branch, `cursor_edges/probe.py` and `nsgridview_migration/probe.py` (no longer run `main()` on import), `analyze_latency.py` and `rs_truncation_preserve_replay.py` (now importable), and dead scripts whose `proxy` import became `src`.
