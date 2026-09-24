# Phase 6, worker B (mc6b): confirmed four-eyes findings outside the shell scripts

Date: 2026-09-25. Branch mc6b (based on integration). Scope: findings P2-2, P2-8, P2-9, P3-1..P3-4, P4-2..P4-4, P5-3, P5-8. Module-layout findings were explicitly out of scope (tracked separately).

## Blocker found on integration (not fixed, out of scope)

`import src.menubar` (any submodule) raises `ImportError: cannot import name 'log_menubar' from partially initialized module 'src.menubar.menubar_log'`. Chain: `menubar/__init__` -> `system` -> `ghostty` -> `menubar_log` -> `paths` -> `resolve_monitor_cc_root(report_root, ...)` -> `root_report.report_root` -> `from .menubar_log import log_menubar` while `menubar_log` is still importing. Reproduced in the main checkout on branch integration, with and without venv, with and without `PROJECT_ROOT` set. Commit 380c0e27 introduced the resolver. Consequence: `dev/hook_smoke/test_bg_task_detection.py` cannot import `proc_cache` on integration (it already failed before my changes: run_all showed 24/25 with that strand aborted).

Workaround used only for proof runs: a `sitecustomize.py` on `PYTHONPATH` that pre-seeds `sys.modules['src.menubar.root_report']` with a no-op `report_root`. With it, `test_bg_task_detection` passes 5/5 and `verify_bg_task_detection_live.py` passes. Nothing of this stub is committed. Someone needs to fix the cycle in production (the menubar app cannot start with this import order).

## P2-2 disabled hooks

Deleted the 7 `src/hooks/*.py.disabled`. Deleted their smoke tests: `test_block_chained_sleep.py` and `test_block_non_canonical_edit.py` (both had `HOOK = ...py.disabled`), plus `verify_block_non_canonical_edit_corpus.py` and `_report.py` (they targeted the deleted hook and could not run). Removed their DOCS entries and the two names from `run_all.py`. `dev/hook_error_correlation/analyze.py` still checks for `.py.disabled` existence at runtime; left alone (reads, does not import).

## P2-8 emojis

Replacements, chosen to keep the display width (utils treats East Asian W/F as 2 columns; the brain and tool glyphs were 2 wide, the warning sign 1 wide):

- tool glyph -> `tl` (render_turn header badge `tl+9`, `tl-2`)
- brain -> `th` (render_turn header, token_format think indicator and `(3/5 th)` summary)
- warning sign -> `!` (`!T` tools-hash warning in render_turn, `! N anomalies` in gpu_render)

Proof: dev/proxy_display and dev/panes `render_byte_identity` main functions were run with the digest replaced by a recorder, on a frozen copy of a real dual-log (`api_requests_opus_general_1790253627_*`, 8.3 MB of rendered output, 116 glyph occurrences, all of them the brain; the tool glyph occurred 4 times, the warning sign 0 times). Old output with the glyphs mapped to the markers (raw and the JSON-escaped surrogate-pair form both) equals the new output byte for byte. The warning sign in gpu_render was checked by a direct call. `dev/thinking/render_brain_badge.py` asserted the brain glyph in the rendered header; it now tests `'th' in header.split()` (a plain `'th' in header` would match `think:64k`, found while reading the header format).

## P2-9 dead code

Removed after re-grepping the whole repo (only data files matched): `read_json_line`, `_get_tool_preview`, `is_known_cli_segment`, `_aggregate_bg`, `_extract_session_start_block`, `_format_tok_est`, `is_modified_since`, `get_modification_time`, `extract_worker_tool_calls`; constants `HOOKS_LOCK`, `GHOSTTY_CWD_UUID_FILE`, `ORCHESTRATOR_SIGNALS_FILE`, `INDENT`; the `_last_session_count` state in `session_finder`. A small AST script listed imports that became unused: removed `_chars_to_tokens` in `proxy_display/format.py` and `List, get_message_content, is_tool_use` in `workers/worker_format.py`. `_format_k` in `proxy_display/format.py` looks unused there but is re-exported (`render_sections*.py`, `render_turn.py` import it from `.format`): keep it. `_last_jsonl_count` in session_finder is a separate variable, not in the finding, untouched.

## P3-1 parallel strands

Shared runner: `dev/refactoring/strand_runner.py`. New helper `dev/hook_smoke/case_strands.py` turns table cases into strands named `case_<idx>_<slug>` (`run_case_strands`, `exit_code_runners`, `case_runners`, `function_runners`, `error_string_runners`, `fail_open_runner`, `report_case`). 21 hook_smoke files converted; case counts before and after are identical (e.g. broad_find 19/19, cli_chained 45/45, rag_corpus_read 29/29, rewrite_chained_sleep 31/31). Provoked failure: a copy of `test_block_broad_find.py` with one expected value flipped gave `18/19 strands passed`, only `case_01_...` aborted, the other 18 finished (fail-fast per strand, siblings unaffected).

Non-obvious points:
- `run_all.py` runs each test module with `runpy` inside its own strand; the modules now start their own strand runner, which reads `--strand` from `sys.argv`. `run_all._run_module` therefore patches `sys.argv` to just the module path for the `runpy` call, otherwise the inner runner tried to run the outer strand name.
- `test_block_worker_kill/send_while_working` and `test_hook_setup_main_branch_gate` were partly sequential-gated (later cases ran only if earlier passed); they are independent now.
- `dev/proxy/test_strip_fix.py` had 8 group strands running ~116 cases sequentially inside; it now has one strand per case (116). Count checked equal to the sum of the `_seq_*` lists.
- New `dev/refactoring/check_group.py` (`assert_checks`) lets the three `*_checks.py` scripts run each check group as a strand: gpu_pane 4 groups (3+6+5+3 = 17 checks, same as before), input 4 groups (11), news_pane 3 groups (12). gpu_pane `state_files` needed the preset shim primed first because the old sequence had filled `PRESET_NAMES` in an earlier group.
- `dev/dual_log_cli/tests/test_skip_reporting.py`: each `test_*` is a strand, 14 checks before, 14 after (plus the two new tests of P5-3).
- False positives in the finding, no change needed: `dev/pane_search/p2_search_feature_regression_cases.py` (its `_test.py` already runs strands), `dev/jsonl/test_jsonl_reader.py`, `dev/panes/test_display_tripwires.py`, `dev/proxy_display/test_forwarded_tripwires.py`, `test_pd10_lazy_messages.py`, `test_session_marker_states.py` (all already subprocess strands via a thread pool).

## P3-2 hermetic tests

- `test_bg_task_detection.py`: the real writer subprocess with real `lsof` is now `verify_bg_task_detection_live.py` (prints a verdict, exit code). The remaining 5 cases patch `proc_cache` globals and run one per strand process (not parallel-safe in-process, but each strand is its own process); `time.time()` replaced by a fixed constant.
- `test_hook_trace_lines.py`: the `sleep 6` fake `worker-cli` is gone. `case_worker_cli_timeout` runs a `python -c` snippet in a subprocess that loads the hook module, fakes `subprocess.run` to raise `TimeoutExpired` and asserts the trace `status subprocess failed for w1: TimeoutExpired` for both hooks. `case_status_fn_raises` runs the same way; no `os.environ` mutation in the test process (env goes to the subprocess). The `sleep 5` at the old :211 is only a payload string, never executed. The 17 cases run as strands (17/17).

## P3-3 unique paths

`dev/click_ui/p1_worker_selection_click_probe.py` and `dev/workers/test_worker_probes.py` use a per-run uuid in the project keys. In `test_worker_probes.py` the key must end in `/proj` because `list_workers` derives the tmux session prefix from the basename (a first try with `..._proj` failed for that reason). The click probe needs a tty with a size: `script -q /dev/null bash -c 'stty cols 200 rows 50; python3 dev/click_ui/p1_worker_selection_click_probe.py'` gives 75/75. It writes a timestamped report to `dev/click_ui/md/`; delete it after a proof run.

## P3-4 swallowed decode errors

Strict parsing (no `except ... pass`) in `test_block_unauthorized_background`, `test_rewrite_worker_wait` (all 16 and 22 cases still pass, so no `KeyError` shape was hidden), `test_fire_log._last_record`, `dev/display/A_format_cache_tracker_proof.py` and `dev/jsonl/A_extract_cache_turns_proof.py`. The two proof scripts read real session files: a live session with a half-written last line will now raise instead of being skipped. `test_rewrite_background_sleep` / `test_rewrite_chained_sleep` `_run_hook` also swallow `KeyError/JSONDecodeError` into `rewrite=None`; not listed in the finding, expected `None` is a legitimate case there, left as is.

## P4-2 / P4-3 / P4-4 docs

- New DOCS.md: `dev/dual_log_cli/tests`, `dev/monitor_lifecycle/tests`, `dev/proxy_tool_stripping/tests`, `dev/pipeline/{format_stability,io_profile,memory_profile,parsing_profile}`, and `DOCS.md` in the project root (workflow.py, setup_py2app.py; the workflow.py block was removed from `src/DOCS.md`, which keeps a pointer in Public Interface). Moved module blocks lost the `tests/` prefix in the heading; parents got a `## Sub-directories` list with one line per child. Every module heading LOC in every touched or new DOCS.md was checked against `wc -l` by script (34 files, 0 drift).
- Role at most 50 words (counted with whitespace split): `src/proxy` 50, `src/dual_log_cli` 48, `src/news_pane` 45.
- `src/menubar/DOCS.md`: Reads and Writes added for `panel_dims`, `panel_grid`, `bar_icons`, `panel_tabs`, `launch_config`.
- `dev/proxy_dual_log` and `dev/tool_injection`: the `### <subdir>/ (see its own DOCS.md)` headings moved out of Modules into `## Sub-directories`.

## P5-3 usage.py

`src/dual_log_cli/usage.py`: the `stat()` OSError `continue` and the malformed-line JSONDecodeError `continue` now call `report_skip("usage", <path>, ...)`. The malformed-line reason is a constant string (`JSONDecodeError: malformed line skipped`) so the reporter's dedup key collapses a whole corrupt file into one stderr line. Two new strands in `test_skip_reporting.py` failed before the fix (dangling symlink `.jsonl` with `since_epoch`, and a transcript with two bad lines and one good) and pass after; a clean transcript gives an identical result and empty stderr. `src/menubar/discover.py:114` was named in the finding text but not in the confirmed list: not touched.

## P5-8 dev analysis scripts

Eleven scripts got a module-level `_SKIPPED_LINES` counter, `_note_skipped_line()`, `_report_skipped_lines()` (prints `skipped undecodable lines: N` once at the end of the entry function): the three `jsonl_exploration` scripts, `scan_jsonl_rules`, `probe_sys_tool_original_chars` (5 sites), `observe_timestamp_order`, `replay_strip_v2` and `scan_sr_catalog` (their handler also catches `KeyError/TypeError`, so the count covers malformed as well as undecodable lines), `addon_hook_byte_identity`, `pipeline_byte_identity` (the new line sits before the `HASH:` line, so `HASH:` stays the last line), `01_session_summary`. `p1_full_sweep_reconstruct` exposes `skipped_line_count()` and `p1_full_sweep_cost_probe` prints it (counts skipped line reads across all passes, not distinct lines). `01_unknown_types` already counted decode errors; it now also counts and reports unreadable files (`OSError`). `p1_hotkey` is not an analysis script: its ctypes callback `except Exception: pass` now prints the exception to stderr. Proof: one fixture line pair per script (good line, bad line) through the collecting function: counter equals 1 and the report line is printed, 14 of 14 PASS (script in /tmp, not committed).

## Verification summary (2026-09-25)

- hook_smoke `run_all.py`: 23/23 with the sitecustomize stub, 22/23 without it (only the pre-existing menubar import cycle).
- Other touched suites, each rc 0: proxy_display (5 files), panes (2), jsonl reader, workers probes, pane_search p2, input/gpu_pane/news_pane checks, proxy `test_strip_fix` 116/116, dual_log_cli tests (all `test_*.py`).
- No comments or docstrings and no emojis in the 65 added or modified `.py` files (tokenize/AST check).

## Hints for a successor

- `gcommit "<msg>" <path>`: `.` resolves against the current directory of the shell; after `cd dev/x` it staged the wrong root and aborted ("staging failed"). Always run it from the worktree root.
- macOS `sed -i` needs a backup suffix argument; use Python for multi-line edits. zsh treats a leading `=` in `echo ====` as command expansion.
- `git grep` over the repo also matches the JSONL corpora in `dev/verbosity` and `dev/cache`; restrict with pathspecs (`'*.py' ':!dev/cache'`) or the output floods the context.
