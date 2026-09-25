# 2026-09-25 - DOCS.md cleanup against the module rules (docs-drift-check rewrite)

The rewritten docs-drift-check (one check per DOCS.md rule) reported 5 DOCS.md pages that describe no module of their own directory, a root title of the wrong form, 7 Purpose texts over 25 words and 6 Called by entries naming files that do not exist. Owner decisions: delete the five pages, fix the rest.

## Salvage: the five deleted DOCS.md pages, verbatim

The pages describe no module. Each is kept below in full so nothing is lost. `dev/DOCS.md` is an area map; the per-area descriptions also live in each area's own DOCS.md where one exists. Other DOCS.md and code do not reference these five files (checked with grep over dev/, src/ and all DOCS.md; only historical process-docs mention them).

### dev/DOCS.md

````markdown
# dev/

## Role
Development, measurement and regression scripts for `src/`. Every script runs manually; nothing in `src/` imports from `dev/`. Each subdirectory is one area: a regression harness for a `src/` package, a smoke suite, or a standalone probe. Commands assume the project root as working directory.

## Public Interface
No `__init__.py` at this level. Each area is entered through its own scripts; see the area's own `DOCS.md`.

## Flow
A script reads real logs, session JSONLs or live state, or builds synthetic fixtures in-process, drives real `src/` code and either asserts pass/fail to stdout or writes a report under the area's `md/`, `json/` or `reports/` directory. The dev-imports-src hook forbids module-level `src` imports from `dev/`; scripts load `src` lazily or via `importlib` (details in process-docs).

## Modules
No `.py` files live at this level. The areas below are covered by this map; other `dev/` areas exist and are described in their own `DOCS.md`.

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
- `monitor_root/` — tests for the single repo-root resolver `src/monitor_root.py` and its reporters.
- `news_pane/` — failure-path and running-state checks for `src/news_pane/`.
- `session_launcher/` — desktop-switch and Ghostty-window-placement probes (macOS 26.6.2) plus regression tests for the menubar Launch tab, the clickable tab header and the Auto-Jump removal.
- `setup_py2app/` — exit-code checks for `setup_py2app.py` via AST extraction (the build script is never run).
- `skill_picker/` — tests and a read-only real-machine probe for the menubar skill dropdown (skill discovery, inserted text, Ghostty AppleScript, menu and grid).
- `workers/` — regression checks for worker status probes, selection IPC and the `list_workers` shape (fakes only, no tmux).

## State
None at this level. State ownership is documented per area.
````

### dev/cc_internals/DOCS.md

````markdown
# dev/cc_internals/

## Role
Research artifacts from Claude Code binary and source analysis: env-var inventories extracted from npm binaries and cross-referenced against community decompile repos. Add a new dated file under `md/` when extracting from a new binary version. No scripts live here.

## Public Interface
No `__init__.py` and no `.py` files. The directory holds Markdown reports under `md/` only.

## Flow
A binary version is inspected by hand, the findings are written as one dated report under `md/`, and the report is read by later sessions. No processing chain exists.

## Modules
None. `md/20260428_env_var_inventory_v2.1.121.md` is a standalone report with no producing script. Sources and method are in the process-docs of this area.

## State
None.
````

### dev/pipeline/DOCS.md

````markdown
# dev/pipeline/

## Role
Standalone measurement scripts that profiled filesystem call cost and message-type coverage of the core monitor pipeline, feeding early design decisions. Touch only when re-measuring one aspect against a changed pipeline; not a regression suite.

## Public Interface
No `__init__.py`. Each script is its own entry point: `python3 dev/pipeline/<subdir>/<script>.py`.

## Flow
Each script scans real session JSONL files under the user's Claude Code projects directory (one measures all files, the others the newest). Each measures one aspect and writes one timestamped Markdown report to a `01_reports/` directory it creates beside itself.

## Sub-directories

- `io_profile/`: Counts filesystem calls per poll cycle of the session finder. See its own `DOCS.md`.
- `format_stability/`: Scans all session JSONL files for top-level and content-block types outside a known set. See its own `DOCS.md`.

## State
None. The path-method patching in the poll-cost script is restored before its cycle function returns.
````

### dev/rag_helpfulness/DOCS.md

````markdown
# dev/rag_helpfulness/

## Role
Holds a rag-cli call inventory report over proxy JSONL logs. No producing script remains here; the extraction logic was superseded by a script in `dev/tool_use_analysis/`.

## Public Interface
No `__init__.py` and no `.py` files. The directory holds one Markdown report under `md/`.

## Flow
Not applicable. The directory holds one historical report and nothing else.

## Modules
None. `md/01_inventory.md` is a standalone report with no producing script in this directory.

## State
None.
````

### dev/tool_injection/ToolsSystemPrompts/DOCS.md

````markdown
# dev/tool_injection/ToolsSystemPrompts/

## Role
Captured reference corpus of Claude Code's built-in tool definitions and one system-prompt segment, snapshotted to size the tool-injection and stripping budget. Reference data, not a script area. Touch when re-measuring against a new CC version.

## Public Interface
No `__init__.py` and no `.py` files. The directory holds Markdown snapshots only.

## Flow
Not applicable. Snapshots are captured by hand and read by later sessions.

## Modules
None. The files are a size index, a strip analysis, one capture per built-in tool, captured MCP tool schemas and the captured system-prompt segment.

## State
None. Char counts are specific to the CC version of the capture; re-capture rather than trust stale figures.
````

