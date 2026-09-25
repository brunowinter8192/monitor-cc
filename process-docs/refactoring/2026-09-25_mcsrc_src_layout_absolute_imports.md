# src/ module layout pass: absolute imports, section order, call-only orchestrators (2026-09-25, worker mcsrc)

Scope: every module under `src/` plus `workflow.py` and `setup_py2app.py`. Goal: the Code-Standards module layout with zero behavior change. Branch `mcsrc`, based on `integration` at `9cd11f70`.

## Convention change: relative imports are no longer the project convention

The process-docs of desktop_allocation, pane_error_log and hotkey_latency recorded relative imports (`from .x import y`) as the convention. The Code-Standards now say `from src.module.submodule import name`. 420 relative imports in 120 files were converted; `grep "from \."` over `src/` finds none. Do not reintroduce relative imports.

## Measured start state (scanner `dev/refactoring/src_layout_scan.py` run against `9cd11f70`)

| Rule | Findings at start | At end |
|---|---|---|
| relative imports | 420 | 0 |
| orchestrator with logic | 50 | 0 |
| orchestrator section shape wrong (class, 2 functions, empty, module-level call) | 10 | 0 |
| section order wrong | 2 | 0 |
| code before first marker (imports above `# INFRASTRUCTURE`) | 12 | 0 |
| constants or functions in the wrong section | 28 | 1 (`panes/log_janitor.py`, owned by worker mcfix, not touched) |
| files without any marker | 9 (`__init__.py` re-export files) | 0 |
| top-level executable statements | 3 (plus 32 hook bootstraps) | exceptions listed below |

The four-eyes list (`P2-3` ... `P2-12`) was a starting point only; the numbers above are re-measured. The scanner's orchestrator test is strict: an orchestrator body may only contain assignments of call results or constants, calls, `if/elif/else` on simple conditions, and `return`. Loops, `try`, comprehensions, lambdas, arithmetic and f-strings count as logic.

## Classification rule for "needs an ORCHESTRATOR" (decided by Main for all workers)

- A module that is run as a script, or that has an entry workflow executing several steps, gets exactly one ORCHESTRATOR function that only calls functions.
- A pure library module whose functions are separate entry points called from other modules gets only INFRASTRUCTURE and FUNCTIONS. About 95 modules are in this class (dual_log_cli renderers, proxy helpers, proxy_display renderers, utils).
- Test modules are libraries of independent entry points: no ORCHESTRATOR.
- The `if __name__ == '__main__'` guard stays at the file end as the entry line.

Classes that mitmproxy or the hotkey code need (`ProxyAddon`, `HotkeyController`) sit in FUNCTIONS; their callback methods only delegate (`_guarded("request", _process_request, self, flow)`). Those two modules have no ORCHESTRATOR.

## How each file is started (needed before converting imports)

| File | Start | Consequence |
|---|---|---|
| `src/hooks/*.py` | `python3 /abs/src/hooks/x.py` from `settings.json`, cwd arbitrary | `sys.path[0]` is `src/hooks`. Each script now does `sys.path.insert(0, <repo root>)` and `from src.hooks._fire_log import log_fire`. This one top-level line is the unavoidable bootstrap. |
| `src/menubar/hook_writer.py` | `python3 /abs/src/menubar/hook_writer.py` from `settings.json` | stdlib only; imports `src` lazily in `_log_failure` with its own path insert. Unchanged. |
| `hooks/hook_setup.py`, `menubar/hook_setup.py` | run by hand | got the same repo-root bootstrap because both now import `src.claude_settings`. |
| `src/menubar/menubar_main.py` | py2app `APP` entry, frozen bundle | already used `from src.menubar import run`. |
| proxy | `mitmdump -s src/logs/.proxy_addon_live_<id>.py`, a copy of `src/proxy_addon.py` | see next section. |
| ccwrap, dual_log_cli, monitor_janitor | `python3 -m src.<pkg>` | absolute imports need nothing new. |
| panes | `python3 workflow.py --mode <m>` inside tmux | absolute imports need nothing new. |

## Proxy live copy: layout change (Q1, decided by Main)

Before: `claude_proxy_start.sh` copied only `src/proxy/` to `src/logs/.proxy_live_<id>/proxy/`; the shim imported it as top-level `proxy.*` and took `src.constants` and `src.monitor_root` from the live checkout.

Absolute `from src.proxy.x import` inside the proxy would load `src.proxy` from the repo root and silently defeat the frozen copy (edits and merges would reach a running proxy). Therefore:

- `_copy_live_proxy` now copies `__init__.py`, `constants.py`, `monitor_root.py` and `proxy/` into `src/logs/.proxy_live_<id>/src/`.
- `src/proxy_addon.py` puts exactly one directory on `sys.path`: the live directory (live shim) or the repo root (checkout shim), and imports `src.proxy.addon` and `src.proxy.rules`.
- `constants.py` and `monitor_root.py` are now frozen with the copy too. `MONITOR_CC_ROOT` is always exported by the start script, so `monitor_root` still resolves the checkout. If it were unset it would resolve the live directory and fail loudly (the old dev case `env_unset_resolves_mirror_root` was removed for that reason; the condition never occurs in the start script).
- Workers spawned before this merge keep the old shim and the old `proxy/` copy; both are consistent with each other. Nothing crosses generations.

Proof (nothing live touched): `dev/refactoring/live_proxy_sandbox.py` builds a live layout in a temp dir that has no `src/proxy` at all, starts a real `mitmdump` on private ports 18931/18932 with a local upstream, sends a POST with `Host: api.anthropic.com`, and gets back all five dual-log files (`original`, `injected`, `stripped`, `forwarded`, `response`) plus the `[monitor_root] source=env` line. `dev/proxy/test_live_copy_bootstrap.py` (4 cases) and `verify_proxy_start_equivalence.py` (12/12) pass with the new layout.

### What Main must check at the next real proxy start

1. `ls src/logs/.proxy_live_<newid>/src/` shows `__init__.py constants.py monitor_root.py proxy`.
2. `src/logs/proxy_error.log` has a fresh `[monitor_root] source=env root=<checkout>` line and no traceback (a wrong layout raises `FileNotFoundError: proxy package not found under ...` from the shim).
3. The first real request produces the six dual-log files under `src/logs/dual_log/` with the new session id.
4. Only then respawn workers; old worker proxies keep working until killed.

## Zero-behavior-change proof, and what each proof caught

All proofs run against snapshots or sandboxes, never the live menubar, monitor or proxy.

| Proof | Script | Baseline | Result |
|---|---|---|---|
| 11 byte-identity harnesses (proxy pipeline, addon hook, panes, proxy_display, gpu_pane, three menubar, constants split, worker probes, pane_flicker m2), pinned to a copied `dual_log` snapshot in `/tmp/mcsrc_snap` | `dev/refactoring/pinned_harness_runner.py` | run twice, identical (determinism check) | identical after every commit. Hashes: pipeline `16a8dbcc...`, addon hook `35e0f830...`, panes `0c0da71e...`, proxy_display `ef2aa5e5...`, gpu `6828b158...`, discover `0395eddc...`, panel_manager `b65e982a...`, constants `21386b14...`. `pane_flicker/m2_byte_identity_test.py` fails on the same step before and after (pre-existing) and rewrites its md report, which must be `git checkout`ed afterwards. |
| Import smoke: every module, fresh interpreter, solo plus 5 random orders (177 -> 179 jobs) | `dev/refactoring/import_smoke.py` | original tree | 0 failures, identical to baseline. Guards against the `menubar_log -> paths -> monitor_root -> root_report -> menubar_log` style cycle. |
| Import commits are import-only | `dev/refactoring/ast_import_equivalence.py` | previous commit | 0 mismatches except the intended `proxy_addon.py`. |
| Reorder commit changes no node | `dev/refactoring/ast_reorder_equivalence.py` | previous commit | 0 mismatches over 98 files (sorted top-level AST dumps equal). |
| 30 hooks x 440 payloads (400 real commands from a copy of `hook_firing.jsonl` plus 40 synthetic), run as `python3 /abs/path` from a cwd holding a decoy `src/hooks/_fire_log.py` that raises | `dev/refactoring/hook_matrix.py` | original tree, run twice, identical | 13200 runs identical in return code, stdout, stderr, normalized fire log. Also run once from cwd `/`. `block_rag_cli_document_repeat` is excluded (10-minute state window makes it non-deterministic); `dev/hook_smoke` covers it. |
| Differential scenarios: 11 strip passes x 17 content shapes incl. identity flags, bg escape, tool injection, discover, ghostty, desktop detection cache, sweep scheduler, skills, hook writer (real subprocess, temp HOME), both hook_setup CLIs (temp HOME, temp git repo, 4 settings variants, run twice), 8 pane loops with scripted I/O and a stop exception, gpu status, monitor dispatch, tmux launcher, ccwrap argv and a real pty run (291 cases) | `dev/refactoring/orch_diff_cases.py` | original tree | identical JSON. |
| `dev/hook_smoke/run_all.py` | | 23/23 | 23/23 |
| `dev/menubar/p5_run_all.py` | | 8 strands, 111 checks | same output hash |
| 44 further dev suites (ccwrap, tmux_launcher, monitor_root, gpu/input/news checks, panes and proxy_display tripwires, dual_log_cli tests, setup_py2app exit checks) | `/tmp/mcsrc_devtests.sh` (throwaway) | original tree | identical except `dev/proxy/test_role_keyed_rules.py`, see merge dependency below |

Observed flake: `dev/hook_smoke/test_hook_trace_lines.py` `case_worker_cli_rc` failed twice in a row under machine load 30 (a freshly written `#!/bin/sh` stub took more than the hook's 3 second timeout) and passed 3 of 3 afterwards and in `run_all`. Not caused by this pass.

### Baseline trap I fell into

I compared "before" against a checkout that already contained the proxy commit. The comparison said SAME while `dev/proxy/test_role_keyed_rules.py` was already broken. Always take the baseline from the commit before the first change (`9cd11f70`), not from an intermediate commit.

## Merge dependency on worker mcdev (must be handled by Main)

Many dev scripts import `proxy.rules`, `proxy.rules_config` and similar as top-level `proxy.*` (sys.path hack). After this pass `proxy.rules` itself imports `src.proxy.rules_config`, so such a test patches a different module object than the one under test (observed: `test_role_keyed_rules` `e2e: main context lands main rules in system[2]` fails). Worker mcdev converts these dev imports to `src.proxy...` (commit `91a70c41` and others). Verified in a throwaway merge of `mcsrc` and `mcdev`: 35 dev suites (proxy, proxy_dual_log, bg_wakeup_id_line, proxy_instrumentation, proxy_display, panes, hook_smoke, p5) give the same output as `mcdev` alone with 0 failures. Merge `mcdev` and `mcsrc` together; `mcsrc` alone breaks every dev script that still uses `from proxy import ...`.

Trial merges (aborted, nothing committed):

- `mcsrc` + `mcfix`: one conflict in `src/menubar/model_controller.py`, the import block. Resolution: absolute form (`from src.menubar.model_selection import ...`, `from src.menubar.model_panel_ui import ...`) with mcfix's shorter name list (mcfix dropped `_APPLY_BTN_W` and `_APPLY_SUCCESS_W`). `addon_dual_log.py` and `log_janitor.py` merged automatically.
- `mcsrc` + `mcdev`: one conflict in `dev/refactoring/DOCS.md` (both added module entries). Keep both sets of entries; `test_live_copy_bootstrap.py` auto-merged and passes.

## Decisions and their reasons

- **Shared strip walk.** Four of the seven `_strip_*` block walks were identical except for the text function and whether an unchanged text block is rebuilt (`strip_po` always rebuilds). They now share `src/proxy/strip_walk.py` with a `rebuild_text` flag. The other three (`sn_notice`, `sr`, `bg_completed`) differ in their `'.'` fallback and stay separate, only split out of the orchestrator.
- **Hook orchestrators.** Every hook now has the shape `parse -> exit if none -> predicate -> _block(...) -> exit 0`. The predicates return the same verdict as the inline loops, including short-circuit order (`_record_and_count` in `block_rag_cli_document_repeat` still runs only until the first hit).
- **Pane loops.** The `while True` body is a guarded iteration function, loop state lives in a dict, and `_loop_until_closed` owns the `try/finally` terminal restore. On an exception mid-iteration, state changes before the failing call persist exactly as they did with local variables (tuple assignment is still atomic).
- **`claude_settings.py`.** `_load_settings`, `_save_settings`, the worktree guard and the settings path were duplicated in both `hook_setup.py` scripts (finding P2-11). They moved to `src/claude_settings.py`; the guard takes `__file__` so its message still names the calling script.
- **`menubar_main.py`** keeps an unconditional `main()` at the end instead of an `if __name__` guard, because py2app loads the `APP` script in its own boot namespace and the current file also ran unconditionally. The `APP` entry in `setup_py2app.py` is unchanged; nothing was built.
- **`setup_py2app.py`** now has `setup_workflow` and a `__main__` guard. `dev/setup_py2app/exit_on_failure_checks.py` loads its functions by AST and still passes 5/5. The bundle whitelist (`_BUNDLE_SRC_KEEP`, `includes`) was re-derived from the import closure of `src.menubar`: `colors`, `constants`, `monitor_janitor`, `monitor_root`, `session_finder`, `tmux_launcher`. Unchanged, the conversion added no dependency. `hook_setup.py` (menubar) now imports `src.claude_settings`, which is not in the bundle; nothing in the app imports `hook_setup`.
- **Spec dictionaries in `message_passes_simple.py`** called `_any_marker_guard` and `_sn_notice_skip` at import time from FUNCTIONS. Both helpers moved (`payload_helpers.py`, `strip_sn_notice.py`) so the specs can live in INFRASTRUCTURE. Moving specs first without moving the helpers gave `NameError` in the import smoke test.
- **Stepdown.** `dev/refactoring/stepdown_reorder.py` orders FUNCTIONS depth-first from the orchestrator (or, without one, from functions no sibling references), classes first. 92 files changed; residual back references (14) are callees with several callers or the public orchestrator called by later wrappers, which cannot be above all callers.

## Accepted exceptions to "no top-level statements"

| File | Statement | Reason |
|---|---|---|
| `src/hooks/*.py` (32), `hooks/hook_setup.py`, `menubar/hook_setup.py` | `sys.path.insert(0, <repo root>)` | script started by absolute path |
| `src/proxy_addon.py` | `bootstrap_paths()` and two imports after it | mitmproxy `-s` module; the imports need the path set first |
| `src/proxy/addon.py` | log filter registration, `addons = [ProxyAddon()]` | mitmproxy reads the module-level `addons` |
| `src/menubar/menubar_main.py` | `main()` | py2app entry, see above |
| `src/menubar/paths.py` | `_APP_SUPPORT.mkdir(...)` | import-time directory creation, not converted |
| `src/gpu_pane/status.py` | `_configure_logger()` at file end | logger was configured at import before |
| classes (NamedTuple, exceptions, ctypes structures) in INFRASTRUCTURE of about 10 modules | | types used by import-time state; not moved |

## Not changed, reported

- Emojis in production code (not part of this issue), 7 files, one line each: `src/format/token_format.py:154`, `src/panes/token_pane.py:332`, `src/panes/warnings_render.py:171`, `src/proxy_display/format.py:121`, `src/proxy_display/render_messages.py:63`, `src/proxy_display/render_turn.py:105`, `src/workers/worker_tokens_pane.py:385`.
- Dead code (P2-9), silent `except: pass` (P5), shell script comments and length (P1-1, P2-1), `.disabled` hook sources, `session_finder._last_session_count`.
- `src/menubar/model_controller.py`, `src/proxy/addon_dual_log.py`, `src/panes/log_janitor.py` belong to worker mcfix: only their import lines were converted; `log_janitor.py:27` still has a module-level assignment after FUNCTIONS and `stepdown_reorder.py` skips all three files.
- The earlier finding that `src/menubar/DOCS.md` is 452 lines (P4-1) is unrelated to this pass.

## Where the tools live

`dev/refactoring/`: `src_layout_scan.py` (rule scanner, exit 1 on hard violations), `pinned_harness_runner.py`, `import_smoke.py`, `hook_matrix.py`, `orch_diff_cases.py`, `live_proxy_sandbox.py`, `ast_import_equivalence.py`, `ast_reorder_equivalence.py`, `stepdown_reorder.py`. Each takes a root directory or base ref, so a baseline is produced by `git archive <ref> | tar -x -C /tmp/x` plus a `venv` symlink.

## Review round 1 fixes (2026-09-25)

- **Stepdown for single-caller pairs.** The first stepdown tool only reordered when a function called a function; it missed class callers and mutual recursion. Fixed by hand in `launch_controller`, `skill_controller`, `panel_views`, `panel_manager` (functions moved below the class that calls them), `addon_dual_log` and `panel_lifecycle`. `panel_lifecycle` has a call cycle (`_register_ring_arrows` -> `_deferred_close_open` -> `_open_panel` -> `_open_main_panel` -> `_register_ring_arrows`); the back edge sits on `_register_ring_arrows`, which has four callers. `proxy_error_log.log_proxy_error` stays above its wrapper because it is the module ORCHESTRATOR. Check to repeat: for every callee with exactly one caller, the callee must be defined below it.
- **Pass-through wrappers removed** (`_current_document`, `_messages_or_empty`, `_transcript_result`, `_personal_skills`, `_concat_skills`, `_resolve_templates`). Defaults moved into the callee (`_locate_msgs`, `_strip_sr_content`); list joins use `[*a, *b, *c]`; a path join uses `claude_dir.joinpath('skills')`. `_replace_with_dot` stays: it is the callback `_walk_replace_marker_blocks` calls, with no underlying function.
- **Orchestrator scan covers `dev/refactoring/`.** The nine scripts written in this pass had list comprehensions, `with`, lambdas and f-strings in their orchestrators; each moved into a function. Indexing (`sys.argv[1]`) counts as allowed in the scanner. `strand_runner.py` and `strand_runner_selftest.py` still show up; they belong to worker mcdev.
- **Scanner pitfall.** The emoji regex written with `\U0001F300` escapes inside a shell heredoc ended up as raw symbol characters in the file and flagged the scanner itself. Build such ranges with `chr()`.
- Docs: LOC headings of the root `DOCS.md`, `dev/proxy/DOCS.md` and `dev/refactoring/DOCS.md` were stale (edited files, not re-counted); `src/hooks/DOCS.md` now says the directory is imported as an implicit namespace package.
- Proofs after the round: pinned harnesses, import smoke (179/0), 291 differential cases, hook matrix (13200 runs), `hook_smoke` 23/23, `p5` hash and 44 dev suites all identical to the original tree. Trial merge with mcdev now also conflicts in `dev/proxy/DOCS.md` (LOC headings); take mcdev's text and re-count.

## Production failure: a second copier of the live copy (2026-09-25)

The layout change in this pass broke every worker spawn: iterative-dev `src/spawn/worker_proxy.sh` `_proxy_launch` had its own copy step (`cp proxy_addon.py`, `cp -r src/proxy .proxy_live_<id>/`), unknown to this pass because the importer survey only searched monitor-cc. The new shim raised `proxy package not found`, mitmdump exited at startup, spawn aborted with `Worker proxy for <name> did not come up`. Lesson: before changing a layout that is copied at runtime, grep every repo under `~/Documents/ai` and the plugin cache for the file names (`proxy_addon`, `proxy_live`), not only the repo being changed.

Fix: one owner. `src/copy_proxy_live.sh <live_addon_path> <live_dir_path>` copies the shim and the `src/` mirror. `claude_proxy_start.sh` calls it; iterative-dev `_proxy_launch` calls `<monitor_cc_root>/src/copy_proxy_live.sh` (root from marker line 3) and aborts the spawn cleanly if the script is missing. Shebang is `#!/bin/bash`, not `env bash`: the start-script sandbox restricts PATH to a tool list without `env`'s target.

Proof: `dev/refactoring/worker_proxy_sandbox.py <iterative-dev tree>`: with iterative-dev `integration` it reproduces the failure (`setup_rc=1`, `did not come up on port 18941`); with branch `mcsrcid` it starts the worker proxy, forwards a request and writes the five dual-log files. `dev/refactoring/live_proxy_sandbox.py` now builds its live layout through the script (main path, five dual-log files). `verify_proxy_start_equivalence.py` 12/12 (its fixture copies the new script), `test_live_copy_bootstrap.py` 4/4, `test_proxy_start_fallbacks.py` 7/7.

Other readers of `proxy_addon.py` or `.proxy_live_` found under `~/Documents/ai`: monitor-cc `proxy_start_janitor.sh` (hashes the sources, removes `.proxy_live_*` recursively, layout independent), monitor-cc dev tests (`test_version_purge.sh` stubs `proxy_addon.py` for the hash, `test_proxy_start_fallbacks.py` checks leftovers, `addon_hook_byte_identity.py` imports the class), iterative-dev `dev/worker_spawn/test_spawn_flow.sh` (fake monitor root, adapted with a stub copy script). Only `worker_proxy.sh` copied. The plugin cache holds a stale copy of `worker_proxy.sh`, its test and process-docs; it needs the plugin republished.

## Later work in this session (2026-09-25)

### One owner for the proxy live copy

`src/copy_proxy_live.sh <live_addon_path> <live_dir_path>` copies the shim and the `src/` mirror; `claude_proxy_start.sh` calls it and iterative-dev `_proxy_launch` calls `<monitor_cc_root>/src/copy_proxy_live.sh` (root from marker line 3, aborts cleanly when missing). The script has the three section markers and one orchestrator (`copy_proxy_live_workflow`); its shebang is `#!/bin/bash` because the start-script sandbox has no `env` target on PATH. Details, the production failure and the proofs are in the section "Production failure: a second copier of the live copy" above.

### Copy-flash marker: check mark replaced by `v`

The 7 emoji scan hits were all `✓` (U+2713), the flash shown for a moment after a copy click; the normal copy symbol `⎘` is unchanged. Now `COPY_FLASH_SYMBOL = 'v'` in `src/constants.py`, used by `format/token_format.py`, `proxy_display/render_messages.py` and `proxy_display/render_turn.py`; `src/utils.py` has `is_copy_row(line, pane_width)` for the row detection in `panes/token_pane.py`, `panes/warnings_render.py`, `workers/worker_tokens_pane.py` and `proxy_display/format.py`.

- **Width trap.** `utils._cell_width` counts anything in U+2600..U+27BF as 2 cells, so `✓` counted 2 while `⎘` and `v` count 1. The pad before a flash symbol grows by one space: the flash glyph now sits in the same column as `⎘` (before it sat one column left) and a flash row is `pane_width` wide instead of `pane_width - 1`. Example at pane width 60 from the differential case: old ` ...   ✓` becomes ` ...    v`, one more space, nothing else.
- **Detection trap.** The old test `'⎘' in line or '✓' in line` relied on the glyph being unique. `'v' in line` would match nearly every row. `is_copy_row` keeps `'⎘' in line` and accepts the flash symbol only when the ANSI-stripped line ends in `' v'` and its computed width equals `pane_width` (the exact place `append_copy_symbol` puts it).
- **Residual case (hypothesis, not observed in real output).** A key row whose natural text ends in `' v'` at exactly `pane_width` is detected as a copy row. Consequence: a harmless extra click target on that row. The synthetic line `'x' * (width - 2) + ' v'` in `orch_diff_cases.py` (`flash_rows:*`, copy-row index 5) shows it; that is the only differing case.
- **Proof.** 17 flash cases in `dev/refactoring/orch_diff_cases.py` (row functions of tokens, worker-tokens and warnings at three widths, `format_cache_tracker` and `format_proxy_block` on the snapshot log, flash on and off). After mapping old `✓` to "one extra space plus `v`", old and new are equal, including the real proxy copy-row sets. Pinned harnesses: only `dev/panes/render_byte_identity.py` changed (`0c0da71e...` to `8bd148c7...`, its cache-tracker fixture renders a flash); all others unchanged. `dev/pane_flicker/m2_byte_identity_test.py` compares against an old git ref and fails on flash steps by design (it already failed before).
- **Pitfall.** A "before" baseline must come from a stash of the working tree, not from an old result directory: the first comparison showed proxy hash changes that were only earlier `integration` work.
- The `p2_copy_click_probe.py` asserts now use `is_copy_row(line, 10)`; `'v' not in line` would have been meaningless. The three `proxy_copy_*_probe.py` files only had the glyph in a printed label.

### Tiny tokens pane: `IndexError` in `_compute_cache_viewport`

`token_pane._build_tokens_output` gives `format_cache_tracker` `pane_height = terminal lines - 2` (one line lost, one for the search bar). With `viewport_lines = pane_height - 1 <= 0` the sticky-header loop indexed `line_keys[start]` past the end. Evidence in a real tmux pane (private socket, rows set at creation): 2 and 3 rows raised, 4 and 5 rows rendered. Direct calls raise for pane heights -1, 0 and 1 at every width; proxy and warnings formatters do not raise. The pane loop's `except Exception` hid it as one logged error per rebuild. Fix: `viewport_lines = max(1, pane_height - 1)`; heights of 2 and up are byte-identical. Test: `dev/panes/test_tiny_pane_viewport.py` (three parallel strands; two fail without the fix).

`p2_copy_click_probe.py` had hit the same error only because it ran under a pty of 0 rows and 0 columns (a width of 0 also caused a later `ZeroDivisionError` in the worker-tokens header, impossible in tmux). The probe now pins `os.get_terminal_size` to 100x40 and passes 21/21 without a tty. Check to repeat: run such probes inside `script -q out sh -c 'stty rows 40 cols 100; ...'` or pin the size, never rely on the default pty size.

### Sandboxes never touch the real `~/.mitmproxy`

mitmdump writes its CA files under `$HOME/.mitmproxy`. `live_proxy_sandbox.py` and `worker_proxy_sandbox.py` now start it with `HOME` set to a directory inside their temp tree; `find ~/.mitmproxy -mmin -10` found nothing after both runs.

### Docs state

Every DOCS.md LOC heading (root, `src/**`, `dev/**`) matches `wc -l` at the end of this session; the layout scan (`dev/refactoring/src_layout_scan.py`) reports no findings, including 0 emoji lines in `src/`.
