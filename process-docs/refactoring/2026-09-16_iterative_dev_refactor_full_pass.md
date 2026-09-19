# Full iterative-dev-refactor pass over src/ and dev/ — 2026-09-16

Orchestrator-level record of one session that ran Phases 1 to 3 of the refactor-scan skill to completion across the whole project, and produced the Phase 4 finding list. Phase 4 decisions were explicitly deferred to a later session with the user.

## Starting state, measured 2026-09-15

- `src/`: 365 Python modules. Zero files at or above 400 LOC, zero functions at or above 50 lines, zero comments, zero docstrings. It was already conformant and stayed untouched by Phases 1 and 2.
- `dev/`: 191 Python modules across 54 area directories.
  - Phase 1 hits: 82 modules in 26 areas.
  - Phase 2 hits: 180 modules in 45 areas, carrying 3009 comments and 192 docstrings.
  - Phase 3 hits: 2 `DOCS.md` at or above 400 lines, `dev/proxy_dual_log` at 408 and `src/proxy` at 406.

The single largest module in the project was `dev/proxy/test_strip_fix.py` at 1820 LOC.

## Ending state, measured 2026-09-16

- Phase 1 closed. Rescan of `src/` and `dev/` returns zero hits on both thresholds.
- Phase 2 closed. Rescan returns zero comments and zero docstrings outside the three section markers and shebangs. Every one of the 45 areas has a verbatim salvage file under its own `process-docs/<area>/`.
- Phase 3 closed for `dev/`. `dev/proxy_dual_log/` is split into eight unit subfolders, its area `DOCS.md` went from 408 to 151 lines, the eight new ones range from 57 to 89.
- `src/proxy/DOCS.md` remains at 406 lines. See the section on it below.
- 124 commits on `integration`.

## The rule that produced most of the value: salvage before delete

The skill says a comment is relocated into a dated process-docs file and then deleted. At 3009 comments the temptation is to triage, keep the good ones and drop the noise. That triage was explicitly rejected at the start of the session, on the grounds that it is 3009 individual judgment calls and every one of them is a chance to lose something.

The mechanical rule is: every comment and every docstring goes into `process-docs/<area>/<date>_comment_salvage.md`, verbatim, grouped under one `## Salvage from dev/<area>/<file>.py` heading per file, in source order. Then all of them are deleted. The worker decides nothing.

This worked. The salvage files are large, `dev/proxy` produced 2521 lines and `dev/proxy_dual_log` 2270, but they are complete, and no session ever had to argue about whether a specific comment was worth keeping.

## Docstrings that are read at runtime

Three of the 192 docstrings were load-bearing, and deleting them would have changed user-visible output:

- `dev/proxy_dual_log/verify_delta.py` — `epilog=__doc__`
- `dev/proxy_dual_log/diff_strip_inject.py` — `epilog=__doc__`
- `dev/proxy_dual_log/tt_delta_skip_replay.py` — `description=__doc__`
- `dev/cc_injection_inventory/cc_injection_inventory.py` — `description=__doc__`
- `dev/session_analysis/04_cache_validation.py` — `description=__doc__`

The fix is the same in each: the text moves to a module-level string constant in INFRASTRUCTURE, named `_MODULE_DOC` or `_MODULE_DESCRIPTION`, and the argparse call references the constant. `--help` output is then diffed before and after to prove it is byte-identical.

Grep for `__doc__` before deleting anything in a directory. A grep for `argparse` alone is not enough, because many scripts pass a plain string literal to `description=` and those are not docstrings at all.

## Verification methods that held up, ranked by strength

1. **Run the script before and after against identical input, diff the output byte for byte.** Always preferred where the script is runnable and the input is stable.
2. **Freeze the corpus first.** `src/logs/dual_log/` grows while the session runs, because the session's own traffic lands in it. Two consecutive runs of a corpus-scanning probe differ for that reason alone. Copy the corpus to a temp directory once and point both runs at the copy. Several scripts have a purpose-built env-var seam for exactly this, for example `RENDER_BYTE_IDENTITY_LOG_DIR` and `PANES_BYTE_IDENTITY_JSONL`.
3. **Token-skeleton diff, for scripts that must not run.** Tokenize both versions, drop every `COMMENT` token and the docstring `STRING` tokens identified by AST position, and prove the remaining token sequence is byte-identical. This proves no code token moved, and it needs no execution at all. It is the right tool for anything that opens a window.
4. **Normalized traceback comparison, for scripts that are already broken.** Many probes hardcode a log stem that has since rotated off disk and fail deterministically. That failure is perfectly good evidence, but the line numbers shift the moment comments are deleted. Compare exception type, message and the frame sequence by file and function name, never by line number.
5. **Synthetic-input function comparison.** Load the pre-edit file via `importlib.util.spec_from_file_location`, call the same function in both versions with identical synthetic input, assert equal return values.

## Hazards in dev/ that must not be executed

The session ran on the user's working machine. These are the scripts found that drive real state, with what they actually do:

- `dev/cursor_edges/probe.py` and `dev/nsgridview_migration/probe.py` call `main()` at module scope with no `if __name__ == '__main__':` guard. Importing them is enough to open a real window and enter a blocking AppKit run loop. The usual "load the backup via importlib to compare" method is itself the hazard here.
- `dev/desktop_allocation/04`, `05` and `06` move real windows between Spaces and open and close real Ghostty and CotEditor windows. `01_probe.py` writes an OSC-2 escape sequence into a live session's tty, changing a visible terminal's title.
- `dev/menubar_nspanel/p1_nspanel_probe.py` registers a real system-wide Cmd+L hotkey via Carbon. `dev/hotkey_latency/probe_get_event_time.py` registers Cmd+Shift+9 the same way and then blocks.
- `dev/menubar_nspanel/menubar_debug.py` runs `launchctl bootout` against the live menubar service.
- `dev/model_selector/verify_three_tab_ring.py` constructs real `PanelManager` and `ModelController` instances and calls the real `_open_*_panel` functions, which call `orderFrontRegardless()`.
- `dev/hook_error_correlation/analyze.py` executes real hooks by subprocess, and several of those append to the production `src/logs/hook_firing.jsonl`.

Two classes were examined and found safe:

- `dev/menubar/*_byte_identity.py` construct real `NSPanel` and `NSGridView` objects but never show them. Settling that question took a grep for `orderFront`, `orderFrontRegardless`, `makeKeyAndOrderFront` and `setIsVisible_` across the actual `src/menubar/` code paths those harnesses reach, which returned zero hits outside `panel_lifecycle.py`, which they do not import.
- `dev/click_ui/*` despite the name sends no real mouse event. Every click is a direct call to a pane's `_handle_*_mouse` with fabricated coordinates.

Two tests create and destroy their own tmux sessions, `dev/bg_wakeup_id_line/p2_bg_escape_probe.py` and `dev/monitor_lifecycle/tests/test_monitor_sweep.py`. Both were allowed to run. The second one needed a trace down to the call site to establish safety: `sweep_sessions` iterates only the list handed to it and never re-enumerates, the test filters to its own fixture names first, and `kill_session` is a single-target call with no wildcard. A fixture session may flicker through the user's monitor pane while such a test runs.

## The pty requirement

`dev/pane_search/p6`, `p7` and `p8` fail under a plain non-tty shell with `OSError: [Errno 25] Inappropriate ioctl for device`, because the production code under test calls bare `os.get_terminal_size()` with no fallback. Run them inside `tmux new-session -x 220 -y 50` using `send-keys`, and read the result with `capture-pane`. Redirecting stdout to a file breaks the fd-to-tty link and reintroduces the failure, so the redirect is not an option.

## Depth-dependent path resolution, the trap in Phase 3

Before `dev/proxy_dual_log/` could be split into subfolders, every path resolution that counted parent directories from `__file__` had to go, because every count is wrong the moment the file moves one level deeper.

An AST or grep pass for `parents[` finds most of them but not all. Two real breakages in that directory used different syntax: `os.path.join(os.path.dirname(__file__), '..', '..', 'src')` and a chained `.parent.parent.parent`. Seven more were output directories anchored at `Path(__file__).parent`, which is not a depth count at all but relocates the report directory into the subfolder along with the file.

The mechanism that worked: walk up from `Path(__file__).resolve()` until a directory literally named after the area is found, giving `AREA_ROOT` at any depth, then `PROJECT_ROOT = AREA_ROOT.parent.parent`.

That does not solve the log lookup, and conflating the two is the mistake to avoid. `src/logs/` is gitignored and exists only in the main checkout, never in a worktree. The `parents[4]` and `parents[5]` variants in the old code were not about depth at all, they were about reaching the main checkout from a worktree. The correct marker-driven form is: take `PROJECT_ROOT` and, if its tail is `.claude/worktrees/<name>`, strip those three components.

## src/proxy cannot be split by the unit rule

`src/proxy/DOCS.md` is 406 lines, six over the threshold, and the skill's remedy is to split the directory into unit subfolders. The closure analysis says that is not possible here.

A unit is one entry script plus the modules reached only by that script's closure, and an entry script is one that no other module in the directory imports. In `src/proxy/` there is exactly one such module, `addon.py`, and its closure covers all 32 other modules exclusively. There are zero shared modules and zero unowned modules. The directory is one single unit.

Applying the rule mechanically would move all 33 modules into `src/proxy/addon/`, which adds no information and breaks the `mitmproxy -s` entry path. The directory was therefore left flat, and this is recorded as a deliberate exception rather than an oversight.

For comparison, `dev/proxy_dual_log/` split cleanly because it has 13 entry scripts, eight of which own exclusive modules, with zero shared modules between them.

## Phase 4 finding list

Two independent scans were run over `src/`.

An AST pattern scan by the orchestrator found 85 broad exception handlers that produce a substitute value, 30 handlers whose body is `pass`, one import fallback and two exists-else path choices, heaviest in `src/hooks` with 44 and `src/menubar` with 23 broad handlers.

A reading scan by a worker found 253 entries, written to `dev/refactoring/md/2026-09-16_src_control_flow_scan.md`. The distribution is `src/menubar` 73, `src/hooks` 53, `src/proxy` 30, `src/proxy_display` 25, `src/dual_log_cli` 21, `src/gpu_pane` 18, `src/news_pane` 8, `src/panes` 6, `src/` top level 7, `src/input` 4, `src/workers` 3, `src/jsonl` 2, `src/ram_audit` 2, `src/format` 1, and zero in `src/core` and `src/ccwrap`.

Across all 253 entries:

- 66 name which path produced the result in the artifact that carries it. 187 do not.
- **Zero fail loudly outside the observed case.** Not one of the 253.

Three findings worth carrying into the next session:

- The same "env var, else compute from `__file__`" two-source choice appears independently in at least 12 places with no shared helper, across `src/monitor_janitor.py`, `src/proxy_addon.py`, `src/ram_audit/instrument.py`, `src/dual_log_cli/discovery.py`, `src/proxy_display/parser.py` five times, `src/proxy_display/forwarded_parser.py`, `src/proxy_display/side_logs.py`, `src/menubar/setup_menubar.py` and three modules under `src/proxy/`. None names which path it used.
- `src/proxy_display/parser.py` `get_proxy_session_start_ts` returns `time.time()` when the session marker file is missing or unreadable. The substitute is a different kind of value than the thing it replaces: the current moment standing in for a session's real start.
- `src/jsonl/jsonl_parser.py` is the one place in the whole scan where a keep-going handler names its path. A malformed line goes into a separate `malformed_lines` list returned alongside the parsed messages, instead of being dropped without trace.

The scan states facts only. No entry was classified as a fallback or a tripwire, and nothing was changed. That work belongs to the next session.

## Orchestration notes for whoever runs this next

**Four workers died of context exhaustion**, all of them in Phase 2, all for the same reason: verification output was read into the worker's own context. The rules that stopped it were, write reports to files and print only the `diff` verdict, and do the `DOCS.md` rewrite right after the strip instead of saving it for last. One worker died mid-rewrite with the whole area verified and nothing committed, which is the worst possible moment.

**A dead worker's uncommitted work is discarded, every time.** It is unverified by definition. The successor gets a prompt carrying the dead worker's findings, which makes the redo fast, and one of those redos finished an entire area in a single pass.

**Two workers in parallel on disjoint areas is safe and roughly halves the wall time.** `worker-cli wait` wakes on all project workers finishing, so both are reviewed in the same turn.

**Bundle the tail.** The last 15 areas held 129 comments between them. Four areas per milestone worked fine, with each area keeping its own salvage file and its own `DOCS.md` rewrite.

**Workers corrected the orchestrator repeatedly, and were right every time.** The count of mutating probes in `dev/desktop_allocation`, the existence of `dev/display/jsonl_exploration/DOCS.md`, the distinction between a comment and a `#` inside a string literal, and the file counts in several areas. State a measured number as a floor and say so, rather than as a target.

**One review caught real damage.** A worker's verification runs regenerated two tracked report artifacts under `dev/proxy/md/` against today's rotated corpus, overwriting the record of the window they were originally measured in. Those reports are evidence, not regenerable output. Every later prompt carried an instruction to back up and restore any tracked artifact a run could touch, and to delete only by explicit filename, never with a wildcard under a report directory. One worker had already destroyed 14 tracked report files with a wildcard `rm` and recovered them himself.
