# dev/

## Role

Development, measurement, and regression scripts for `src/`. Every script here runs manually
(no `src/` module imports any `dev/` script — `block_dev_imports_src` also blocks the reverse:
`dev/` scripts may not `import src.` at module level, only via `sys.path.insert` +
package-relative imports or `importlib`). Each subdirectory is one area: either a byte-identity/
regression harness for one `src/` package, a smoke-test suite for one class of hook or pane
feature, or a standalone investigation probe. Touch a `dev/<area>/` directory when adding a new
regression guard for that area's `src/` package, or when a `src/` refactor in that package needs
a before/after correctness proof. All commands assume CWD = the project root.

## Flow

A script reads real logs/session JSONLs/live state or builds synthetic fixtures in-process,
drives one or more real `src/` functions (via `importlib`, `sys.path.insert`, or package-relative
import), and either asserts pass/fail to stdout or writes a report under `dev/<area>/md/` (or
`json/`, `reports/`).

## Areas in scope of this map

- `bg_wakeup_id_line/` — CC background-launch-ack wording + tmux-Escape-on-launch-ack mechanism verification (`src/proxy/bg_escape.py`, `strip_bg_launch_ack.py`, `strip_interrupt_marker.py`).
- `ccwrap/` — exit-code check for `src/ccwrap/__main__.py` argument handling.
- `cc_injection_inventory/` — full-corpus text-class inventory over `src/logs/dual_log/` (COVERED/INJECTED/KEEP/OURS/UNCLASSIFIED classification against the real `src/proxy/rules.py` pipeline).
- `cc_internals/` — Claude Code binary/source research artifacts (env-var inventory), no `.py` scripts.
- `click_ui/` — pane-control mouse-click regression coverage (worker selection, copy-by-click, chrome buttons, gpu/news refresh).
- `constants/` — byte-identity harness for `src/constants.py`'s split into `src/colors.py`/`src/core/modes.py`/`src/pane_error_log.py`.
- `cursor_edges/` — standalone NSPanel cursor-rect probe (edge hover `↔`/`↕` behavior), no `src/` import.
- `desktop_allocation/` — Mission Control desktop-number detection pipeline probes (Ghostty AppleScript + CGS/SkyLight APIs), no `src/` changes.
- `display/` — display-layer tests (tmux layout, JSONL rule scanning, pane screenshots, cache-tracker/hover-map/strip-marker regressions); `display/jsonl_exploration/` maps session-JSONL structure.
- `gpu_pane/` — byte-identity harness plus failure-path checks for `src/gpu_pane/`.
- `hook_error_correlation/` — overlays `src/logs/tool_errors.jsonl` against hook-fire logs to classify current-config-relevant vs. stale hook errors.
- `hook_smoke/` — one smoke-test script per `src/hooks/*.py` hook, positive+negative subprocess cases.
- `hotkey_latency/` — menubar hotkey-lag measurement (Carbon `GetEventTime` probe + `menubar.log` `[latency]`-line analyzer).
- `input/` — failure-path checks for `src/input/click_handler.py` (non-tty stdin, mouse parsing, pbcopy).
- `jsonl/` — differential-proof harness for `src/jsonl/jsonl_cache_turns.py`.
- `menubar_nspanel/` — NSPanel sticky-toggle probe + foreground menubar debug launcher.
- `menubar/` — byte-identity harnesses for `src/menubar/` module splits.
- `model_selector/` — regression coverage for the menubar Models tab and the launcher/hook precedence chain that applies it.
- `monitor_lifecycle/` — load probe + regression/gate tests for `monitor_cc_*` tmux-session lifecycle (`src/monitor_janitor.py`, `src/menubar/monitor_sweep_scheduler.py`).
- `news_pane/` — failure-path and running-state checks for `src/news_pane/`.
- `session_launcher/` — desktop-switch and Ghostty-window-placement probes (macOS 26.6.2) plus regression tests for the menubar Launch tab, the clickable tab header and the Auto-Jump removal.
- `setup_py2app/` — exit-code checks for `setup_py2app.py` via AST extraction (the build script is never run).
- `skill_picker/` — tests and a read-only real-machine probe for the menubar skill dropdown (skill discovery, inserted text, Ghostty AppleScript, menu and grid).
- `workers/` — regression checks for worker status probes, selection IPC and the `list_workers` shape (fakes only, no tmux).

Other `dev/` areas exist outside this map's scope; see their own `DOCS.md`.
