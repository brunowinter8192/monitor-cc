# Phase 3 test-structure fixes, group 3 (dev/pane_search, pane_error_log, display, pane_flicker m1/m2, panes, menubar_per_project, model_selector, proxy_instrumentation, tmux_launcher) - 2026-09-24/25

Scope: findings A1-A3, A6, A7, B8, B11-B16, B18-B20 of the Phase 3 scan, in the directories above only. Every change was proven against a baseline taken before editing.

## Shared runner

`dev/refactoring/strand_runner.py` (own commit, cherry-picked by another worker) provides:
- `strand_workflow(globals(), __file__, names, report_path, title)`: without `--strand` it launches one subprocess per name (`sys.executable script --strand name`) in a ThreadPoolExecutor, prints `PASS`/`ABORT` per strand, lists aborted strands, writes a fixed-name markdown report (strand stdout verbatim), returns 0/1. With `--strand name` it runs that one function and returns 1 on any exception.
- `check(label, cond)`: prints `  PASS  label` / `  FAIL  label` and raises AssertionError on failure. This is the fail-fast unit; sibling strands are never cancelled.
- Test scripts list strand names as strings in INFRASTRUCTURE (functions are defined below the orchestrator) and their orchestrator is `sys.exit(strand_workflow(globals(), __file__, ...))`.
- One strand per subprocess also removes A3: singleton resets, `subprocess.run` swaps, `os.environ.pop('TMUX')`, `pel.PANE_ERROR_LOG_PATH` patches live only inside that process.

## Proof method that worked

Take the PASS label set of the old suite (stdout, sorted) and compare it with the label lines inside the new fixed-name report. Identical sets = same checks ran. Observed: pane_search p2/p3/p5/p6/p7/p8 = 48/62/77/78/83/82 labels, identical; tmux_launcher 7 labels; model_selector report bodies identical; m1 132/132 and m2 1328/1328 unchanged. Intended differences appear as explicit label diffs (removed `or True` checks, new fixture counts, new plist labels).

## Hazards and observations (all observed, not hypothetical)

- pane_search p2, p5-p8 fail without a tty because `os.get_terminal_size()` is called bare. `script -q` gives a 0x0 pty (ZeroDivisionError in worker_switch_header), so it is useless for baselines. A working baseline runner is a `pty.fork()` with `TIOCSWINSZ` set to 50x220 before reading. In the fixtures, `os.get_terminal_size = lambda fd=1: os.terminal_size((220, 50))` removes the tty requirement (each strand is its own process, so the global patch is safe).
- `pane_error_log` news_log check failed in the old suite whenever stdout was not a tty: `run_news_log_loop` calls `os.get_terminal_size()` before the injected `find_log_file`, so the log carried an OSError traceback instead of the marker. Same seam fixes it.
- p7 used a fixed project filter, so `/tmp/monitor_cc_selected_worker_<md5(filter)[:8]>.txt` was shared by all parallel strands. Filter now includes the pid and an atexit hook removes the file.
- Running `mitmproxy`-dependent tests (proxy_instrumentation p9-p11) needs the main checkout venv python (`/Users/brunowinter2000/Documents/ai/monitor-cc/venv/bin/python`); system python3 has no mitmproxy. Strands use `sys.executable`, so the interpreter propagates.
- `dev/display/test_strip_markers.py` was already dead: it imported `get_stripped_data`, `build_tool_result_strip_lookup`, `build_tool_id_strip_lookup`, none of which exist in `src/format/strip_marker.py`. Only `highlight_stripped` survives; two sections kept as strands, the rest deleted.
- m1 `start_pane` first version compared a byte offset from `stat().st_size` with a slice of the decoded str; multi-byte glyphs in the old tree output made the slice empty and every old strand timed out. Compare bytes with bytes.
- `pipe-pane` survives `respawn-pane -k`, so raw recording continues after the respawn.
- The tool wrapper reported the m1 run as timed out and moved it to the background although the script finished in about 17 s (tmux server processes keep the tool pipes open until kill-server). Read the output file instead of re-running. One interrupted run left `flicker_m1_*` in the temp dir; that one was removed by explicit name.
- `test_open_or_focus_monitor._test_launch_monitor_uses_native_path_only` calls the real `_launch_monitor`, which writes a line to the live `menubar.log`. Not changed (outside the findings).

## Decisions per finding

- A6 (m1): `wait_quiet` (raw size and captured screen unchanged for 0.6 s, poll 0.05 s, 30 s deadline, raises TimeoutError), `start_pane` (waits for `\033[?2026h` or `\033[2J` in the raw bytes after the offset recorded before sending the command, then quiet), `wait_flag` (polls `#{cursor_flag}`, returns the last value so a wrong flag becomes a failed verdict). The 0.6 s quiet equals the old fixed settle, so the wait is never shorter than before. The 0.05 s pause after every send-keys was removed; results unchanged.
- B14: `run_strand` kills the tmux server in a finally; the work dir is a `TemporaryDirectory`; `run_strand_guarded` turns a raising strand into `{'aborted': traceback}` and `evaluate` reports `<pane>: strands ran` as FAIL. Shown by `dev/pane_flicker/m1_strand_abort_test.py` (nonexistent tree root, 2 s deadline).
- B13: m2 sessions are `dev/pane_flicker/fixtures/many_calls.jsonl` and `many_turns.jsonl`, each the leading lines of the original session up to about 2 MB (decision by Main). Full session: many_calls 35 turns / 179 max calls per turn; excerpt 8 turns / 91 max calls. many_turns: 104 turns full, 7 in the excerpt.
- B8: frozen pair `dev/display/fixtures/api_requests_fixture_{forwarded,stripped}.jsonl` (a complete real dual-log pair, 202 KB, chosen as the smallest pair that yields 5 tested entries, 3 with rendered lines). The test asserts exactly 5 entries and at least 3 non-empty renders, so it cannot pass on an empty input.
- B15 (panes): `render_byte_identity.py` only ever hashed the first 300 lines, so the frozen default is `fixtures/session_prefix_300.jsonl` (first 300 lines of one session); HASH before (env override on the source session) equals HASH after (default), `670fbe75...b695`. Declared as verification in DOCS.md; env override kept.
- B16 (display `A_format_cache_tracker_proof.py`): declared verification on live sessions in DOCS.md, code untouched.
- B19: the subprocess snippet sets `m._PLIST_PATH` to a temp plist whose PATH points at a temp dir holding an executable fake `python3`; asserts the resolved path equals it. A second plist with an empty PATH must not resolve to it (negative check).
- B20 / model_selector: DOCS.md declares `verify_four_tab_ring.py` a macOS/WindowServer verification (one dependent flow, not split) and documents the `isolate_home` import from `dev/session_launcher/test_env.py` as a known cross-area coupling (decision by Main: document only). `verify_model_cycle_and_io.py` imports no AppKit (checked via `sys.modules`).
- A7: fixed report names everywhere in scope; `datetime.now()` removed from model_selector report titles; `verify_hook_writer_split` dropped the `updated_ts` wall-clock value from its report lines; `verify_launcher_model_precedence.sh` writes `md/verify_launcher_model_precedence.md` (body identical to the old dated report). m1/m2 report headers no longer carry the run time or the absolute worktree path. Old dated reports already tracked in `md/` were left alone (evidence).
- B12: `_tmp_jsonl` / `_tmp_paths` context managers (TemporaryDirectory) in p9/p10.
- B18: `os.environ['MONITOR_CC_ROOT'] = worktree root` (assignment) in all six pane_search fixtures; verified that an exported `MONITOR_CC_ROOT=/nonexistent` no longer affects a run.
- B11: `p1_shared.py` creates one `mkdtemp` per process (atexit rmtree) holding the probe, tiny and cap logs.
- Not converted on purpose: `verify_four_tab_ring`, `verify_hook_writer_split`, `verify_hook17_removal` (dependent sequential flows, already fail-fast via bare `assert`), `verify_launcher_model_precedence.sh` (shell, not python).

## Not done / open

- No repetition measurement was run (decision by Main); m1 timing sensitivity is now bounded by deadline polling only.
- `dev/refactoring/DOCS.md` was edited (strand runner modules) in a commit after the runner commit; another worker cherry-picking the runner may hit a DOCS conflict.

## Merge of integration into this branch (2026-09-25)

Conflicts: five DOCS.md (LOC headings only, recomputed with wc -l), `dev/pane_flicker/md/m1_frame_e2e_test.md` (regenerated by rerun), and `dev/menubar_per_project/test_open_or_focus_monitor.py`. Integration had deleted `_test_empty_cwd_is_noop` (source no longer has that guard); the strand version dropped that case and its strand name too.

Source changes on integration that broke tests of this scope, each a deliberate behaviour change, so the tests were adapted:
- `forwarded_parser._lazy_load_messages_forwarded` now returns None and raises `LookupError` on failure. `p2` `test_flow_id_lazy_load_fix` checks the entry's `messages_total_chars` after the call instead of a truthy return. (The old p2 suite failed the same way on a clean integration checkout.)
- `model_selection._load_proxy_rules_strict` no longer swallows a malformed `proxy_rules.json`: the write raises `JSONDecodeError` and leaves the file untouched. `verify_model_cycle_and_io` section 9 now asserts the raise, the byte-identical file and no leftover `.tmp`.
- The proxy pane shows a yellow "Session start unknown: ..." row 2 when no session start timestamp exists (explicit-state change). The m1 proxy strand failed 16 of 132 checks because the old tree draws the first REQ row there. `m1_frame_e2e_driver.py` (outside the original file list) now patches `core.monitor._get_session_start_ts` for the proxy pane, as integration's p2 fixtures do.
