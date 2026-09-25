# src/

## Role

Root-level modules of the Monitor_CC terminal monitor shared by two or more pane packages (colors, constants, session discovery, search bar, error log, utils), plus the tmux launcher, janitor and entry scripts. Touch for cross-package shared code or startup; not for a single pane's rendering or input.

## Public Interface

`src/__init__.py` is empty. Actual entry points:
- `workflow.py` (project root, documented in the root `DOCS.md`) — the main process, and every pane subprocess (`workflow.py --mode <pane>`).
- mitmproxy — loads `src/proxy_addon.py` directly via `-s`.

## Flow

1. `workflow.py` parses `--mode` and dispatches: `all`/`restart-panes` → `tmux_launcher`; `menubar`/`gpu`/`news`/`news-log` → their own pane package; every other mode → `core/monitor.py`.
2. `tmux_launcher` spawns 8 panes, each its own `workflow.py --mode <X>` subprocess.
3. `core/monitor.py` discovers session files via `session_finder` and dispatches `tokens`/`warnings`/`worker-tokens`/`proxy`/`worker-proxy` to the matching pane package.
4. `claude_proxy_start.sh` launches mitmproxy (`-s proxy_addon.py`) + Claude Code; mitmproxy logs intercepted API traffic that the tokens/warnings/proxy panes tail independently.

## Modules

### colors.py (27 LOC)

**Purpose:** ANSI truecolor foreground/background color and style palette shared by all renderers.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** every rendering module in `format/`, `gpu_pane/`, `news_pane/`, `panes/`, `proxy_display/`, `workers/`, plus root `search_bar.py`, `session_finder.py`, `startup.py`, `utils.py`.
**Calls out:** none.

---

### constants.py (50 LOC)

**Purpose:** process-wide timing and size-limit values shared by two or more packages.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `gpu_pane/pane.py`, `news_pane/pane.py`, `panes/token_pane.py`, `panes/warnings_pane.py`, `panes/warnings_render.py`, `proxy/payload_helpers.py`, `proxy/tools.py`, several `proxy_display/` modules, `tmux_launcher.py`, `utils.py`, `workers/worker_tokens_pane.py`.
**Calls out:** none.

---

### frame_writer.py (38 LOC)

**Purpose:** flicker-free in-place frame output for pane loops, plus cursor hide/show brackets.
**Reads:** nothing (the built frame string is passed in).
**Writes:** stdout.
**Called by:** `panes/token_pane.py`, `workers/worker_tokens_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`.
**Calls out:** none.

---

### monitor_janitor.py (76 LOC)

**Purpose:** kills stale `monitor_cc_*` tmux sessions and logs one line per session.
**Reads:** `tmux list-sessions` output.
**Writes:** kills stale tmux sessions via `tmux_launcher.py`; appends to `<root>/src/logs/monitor_sweep.log`.
**Called by:** `claude_proxy_start.sh` (detached on every session start), `menubar/monitor_sweep_scheduler.py`, `dev/monitor_lifecycle/tests/test_monitor_sweep.py`.
**Calls out:** `tmux` (subprocess CLI).

---

### monitor_root.py (36 LOC)

**Purpose:** single resolver for the repo root (env var first, else file location), reporting the winning source once per process.
**Reads:** the root-override environment variable.
**Writes:** nothing; returns a path.
**Called by:** `monitor_janitor.py`, `proxy_display/forwarded_parser.py`, `ram_audit/instrument.py`, `dual_log_cli/discovery.py`, `proxy/proxy_error_log.py`, `menubar/paths.py`; `dev/monitor_root/test_monitor_root.py`.
**Calls out:** none.

---

### pane_error_log.py (38 LOC)

**Purpose:** exception-safe error and note sink that every pane loop guard writes to.
**Reads:** existing log file size.
**Writes:** `/tmp/monitor_cc_error.log` (size-capped).
**Called by:** `gpu_pane/pane.py`, `news_pane/log_pane.py`, `news_pane/pane.py`, `panes/token_pane.py`, `panes/warnings_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`, `workers/worker_tokens_pane.py`, `input/click_handler.py`.
**Calls out:** none.

---

### proxy_addon.py (36 LOC)

**Purpose:** thin mitmproxy shim that puts the import root (checkout root, or the per-session live directory holding a `src/` copy) on the import path and re-exports the addon.
**Reads:** its own file path and the two known layouts (checkout, per-session live copy).
**Writes:** mutates the import path.
**Called by:** `claude_proxy_start.sh` (copies it to a per-session live file, then launches mitmproxy with `-s`).
**Calls out:** `mitmproxy` (loaded via `-s`).

---

### claude_settings.py (35 LOC)

**Purpose:** Shared read, write and worktree guard for the user-level Claude settings file used by both hook-setup scripts.
**Reads:** the user-level Claude settings file.
**Writes:** the same file (atomic replace).
**Called by:** `hooks/hook_setup.py`, `menubar/hook_setup.py`.
**Calls out:** none

---

### copy_proxy_live.sh (33 LOC)

**Purpose:** Single owner of the proxy live-copy layout: copies the shim and a `src/` mirror (`__init__.py`, `constants.py`, `monitor_root.py`, `proxy/`) to the given targets.
**Reads:** `proxy_addon.py`, `__init__.py`, `constants.py`, `monitor_root.py`, `proxy/` next to itself.
**Writes:** the live addon file and the live directory given as arguments.
**Called by:** `claude_proxy_start.sh`; iterative-dev `src/spawn/worker_proxy.sh` via the monitor root in the proxy marker.
**Calls out:** none

---

### search_bar.py (147 LOC)

**Purpose:** shared search-bar state, rendering, key and mouse handling, and search-highlight embedding used by every pane.
**Reads:** nothing (all state passed as arguments).
**Writes:** mutates the passed-in search state.
**Called by:** `format/token_format.py`, `gpu_pane/pane.py`, `news_pane/pane.py`, `panes/token_pane.py`, `panes/warnings_pane.py`, `panes/warnings_render.py`, `proxy_display/format.py`, `proxy_display/pane.py`, `proxy_display/proxy_pane_shared.py`, `proxy_display/render_turn.py`, `proxy_display/worker_proxy_pane.py`, `workers/worker_tokens_pane.py`.
**Calls out:** none.

---

### session_finder.py (64 LOC)

**Purpose:** enumerates Claude Code session JSONL files (including subagent transcripts), optionally per project, newest first.
**Reads:** `~/.claude/projects/` directory tree.
**Writes:** nothing.
**Called by:** `core/monitor.py`, `menubar/discover.py`, `workers/worker_tmux.py`, `dev/pipeline/io_profile/01_poll_cycle_cost.py`.
**Calls out:** none.

---

### startup.py (43 LOC)

**Purpose:** CLI argument parsing, shutdown signal handlers and startup/shutdown console messages.
**Reads:** `sys.argv`.
**Writes:** stdout; exits the process on shutdown signal.
**Called by:** `workflow.py`.
**Calls out:** none.

---

### tmux_launcher.py (258 LOC)

**Purpose:** launches the tmux split-screen layout, self-heals missing windows and panes, and owns tmux session and key-binding setup.
**Reads:** tmux session, pane, window and option listings.
**Writes:** creates and kills tmux sessions, windows and panes; sets tmux options and key bindings.
**Called by:** `workflow.py` (`all` and `restart-panes` modes), `monitor_janitor.py`, `menubar/system.py`.
**Calls out:** `tmux` (subprocess CLI).

---

### utils.py (170 LOC)

**Purpose:** shared no-I/O formatting primitives: timestamps, cell-width-aware truncation and wrapping, highlighting, right-aligned time column.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `format/token_format.py`, `gpu_pane/gpu_render.py`, `news_pane/pane.py`, `panes/token_pane.py`, `panes/token_search.py`, `panes/warnings_pane.py`, `panes/warnings_render.py`, `proxy_display/format.py`, `proxy_display/render_messages.py`, `proxy_display/render_turn.py`, `proxy_display/search.py`, `proxy_display/worker_proxy_pane.py`, `search_bar.py`, `workers/worker_switch_header.py`, `workers/worker_tokens_pane.py`.
**Calls out:** none.

---

### claude_proxy_start.sh (205 LOC)

**Purpose:** shell entry point that launches mitmproxy plus Claude Code with the proxy environment; orchestrates the sourced janitor and marker libraries.
**Reads:** the model-selection rules file, existing log files, per-project marker files.
**Writes:** per-session live proxy-addon copy (made by `copy_proxy_live.sh`), marker files, the active-plugins file of the project.
**Called by:** invoked directly (main session start); the command `ccwrap/wrapper.py` wraps.
**Calls out:** `mitmproxy`, `jq`, worker-cli (iterative-dev project).

---

### proxy_start_janitor.sh (112 LOC)

**Purpose:** sourced library with the janitor functions that remove orphan live copies and rotate or purge dual-logs at session start.
**Reads:** the dual-log directory, the proxy source files for the version hash.
**Writes:** deletes stale logs and live copies, writes the proxy version marker.
**Called by:** `claude_proxy_start.sh` (sourced).
**Calls out:** none.

---

### proxy_start_markers.sh (78 LOC)

**Purpose:** sourced library with the marker staleness check, heartbeat and exit cleanup functions of the proxy launcher.
**Reads:** the per-project and `/tmp` marker files, forwarded dual-log mtimes.
**Writes:** the per-project and `/tmp` marker files; removes owned markers and live copies on exit.
**Called by:** `claude_proxy_start.sh` (sourced), `dev/proxy/marker_race_repro.sh`.
**Calls out:** none.

---

## State

Runtime state (active project filter, active mode) lives in `core/monitor.py` as module-level variables; see `core/DOCS.md`. Pane packages read it through a lazy import of that module to avoid circular imports.
