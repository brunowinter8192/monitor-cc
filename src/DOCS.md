# src/

## Role

`src/` is the entire Monitor_CC application — a real-time terminal monitor for Claude Code
sessions, driven as 8 dedicated tmux panes plus a background mitmproxy addon. This directory
holds the root-level modules shared by two or more pane packages (colors, constants, session
discovery, the shared search bar, pane-error logging, rendering utils), the tmux window/pane
launcher, the monitor-session janitor, and the shell/py entry points that start the whole thing.
Every pane-specific package (`core/`, `panes/`, `workers/`, `gpu_pane/`, `news_pane/`,
`proxy_display/`, `proxy/`, `format/`, `input/`, `jsonl/`, `ram_audit/`, `ccwrap/`, `menubar/`,
`hooks/`) documents itself in its own DOCS.md. Touch this level when changing a constant, color,
or util shared by 2+ packages, the tmux window/pane layout, or process startup. Do NOT touch it
to change a single pane's own rendering or input handling — that lives in the pane's own package.

## Public Interface

`src/__init__.py` is empty. Actual entry points:
- `workflow.py` (project root) — the main process, and every pane subprocess (`workflow.py --mode <pane>`).
- mitmproxy — loads `src/proxy_addon.py` directly via `-s`.

## Flow

1. `workflow.py` parses `--mode` and dispatches: `all`/`restart-panes` → `tmux_launcher`; `menubar`/`gpu`/`news`/`news-log` → their own pane package; every other mode → `core.monitor.run_monitor`.
2. `tmux_launcher.launch_split_screen` spawns 8 panes, each its own `workflow.py --mode <X>` subprocess.
3. `core.monitor.run_monitor` discovers session files via `session_finder` and dispatches `tokens`/`warnings`/`worker-tokens`/`proxy`/`worker-proxy` to the matching pane package.
4. `claude_proxy_start.sh` launches mitmproxy (`-s proxy_addon.py`) + Claude Code; mitmproxy logs intercepted API traffic that the tokens/warnings/proxy panes tail independently.

## Modules

### colors.py (27 LOC)

**Purpose:** ANSI truecolor foreground/background color and style constants (Catppuccin Mocha palette).
**Reads:** nothing.
**Writes:** nothing.
**Called by:** every rendering module in `format/`, `gpu_pane/`, `news_pane/`, `panes/`, `proxy_display/`, `workers/`, plus root `search_bar.py`, `session_finder.py`, `startup.py`, `utils.py`.
**Calls out:** none.

---

### constants.py (50 LOC)

**Purpose:** process-wide timing/size-limit constants and `TOOL_BLOCKLIST`.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `gpu_pane/pane.py`, `news_pane/pane.py`, `panes/token_pane.py`, `panes/warnings_pane.py`, `panes/warnings_render.py`, `proxy/payload_helpers.py`, `proxy/tools.py`, several `proxy_display/` modules, `tmux_launcher.py`, `utils.py`, `workers/worker_tokens_pane.py`.
**Calls out:** none.

---

### frame_writer.py (38 LOC)

**Purpose:** `write_frame(output)` writes one pane frame in place (cursor home, per-row erase-to-EOL, erase below) wrapped in synchronized output (mode 2026), replacing clear-then-print; every frame also hides the terminal cursor, and `hide_cursor`/`show_cursor` bracket a pane loop.
**Reads:** nothing (the built frame string is passed in).
**Writes:** stdout (one write and flush per frame).
**Called by:** `panes/token_pane.py`, `workers/worker_tokens_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`.
**Calls out:** none.

---

### monitor_janitor.py (76 LOC)

**Purpose:** `sweep_workflow()` — kills every `monitor_cc_*` tmux session older than 24h and logs one line per session (name, age, KILLED/SPARED/KILL_FAILED); a failed `list-sessions` logs `NOSESSIONS rc=<n>`.
**Reads:** `tmux list-sessions` output.
**Writes:** kills stale tmux sessions via `tmux_launcher.kill_session`; appends to `<root>/src/logs/monitor_sweep.log`.
**Called by:** `claude_proxy_start.sh` (detached `python3 -m src.monitor_janitor` on every session start), `menubar/monitor_sweep_scheduler.py` (`sweep_workflow`, its own daily tick), `dev/monitor_lifecycle/tests/test_monitor_sweep.py`.
**Calls out:** `tmux` (subprocess CLI).

---

### monitor_root.py (36 LOC)

**Purpose:** Single resolver for the repo root — env var first, else the location of this file — raising on a missing directory and reporting the winning source once per process to a caller-supplied channel.
**Reads:** `MONITOR_CC_ROOT` (or the env var name the caller passes, `PROJECT_ROOT` for the menubar).
**Writes:** Nothing — returns a `Path`; calls the injected `report(root, source)` once per distinct resolution.
**Called by:** `monitor_janitor.py`, `proxy_display/forwarded_parser.py`, `ram_audit/instrument.py`, `dual_log_cli/discovery.py`, `proxy/proxy_error_log.py`, `menubar/paths.py`; `dev/monitor_root/test_monitor_root.py`.
**Calls out:** —

---

### pane_error_log.py (38 LOC)

**Purpose:** `log_pane_error(pane_name)` — exception-safe sink every pane's `except Exception:` guard calls; `log_pane_note(pane_name, message)` writes a one-line note to the same capped log.
**Reads:** existing log file size (to decide truncation).
**Writes:** `/tmp/monitor_cc_error.log` (appends traceback; truncates to a fixed tail once past the max size).
**Called by:** `gpu_pane/pane.py`, `news_pane/log_pane.py`, `news_pane/pane.py`, `panes/token_pane.py`, `panes/warnings_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`, `workers/worker_tokens_pane.py`.
**Calls out:** none.

---

### proxy_addon.py (36 LOC)

**Purpose:** thin mitmproxy shim — puts the `proxy/` package directory (checkout copy or per-session live copy) and the repo root on `sys.path`, raising when `proxy/` is absent, and re-exports `ProxyAddon`/`addons`/`apply_modification_rules`.
**Reads:** its own `__file__` path and the two known layouts (`src/proxy_addon.py`, `src/logs/.proxy_addon_live_<session_id>.py` beside `.proxy_live_<session_id>/`).
**Writes:** mutates `sys.path`.
**Called by:** `claude_proxy_start.sh` (copies this file to `src/logs/.proxy_addon_live_<id>.py`, then launches mitmproxy with `-s` against the copy).
**Calls out:** `mitmproxy` (loaded via `-s`).

---

### search_bar.py (147 LOC)

**Purpose:** shared search-bar mechanics — `SearchState`, `render_search_bar`, `handle_search_input`/`_cancel`, drag-select mouse handlers, and the `_BG_RESTORE_SENTINEL`/`resolve_bg_restore` pair every pane's zebra/hover row loop uses to embed then resolve search highlights.
**Reads:** nothing (all state passed as arguments).
**Writes:** mutates the passed-in `SearchState` instance.
**Called by:** `format/token_format.py`, `gpu_pane/pane.py`, `news_pane/pane.py`, `panes/token_pane.py`, `panes/warnings_pane.py`, `panes/warnings_render.py`, `proxy_display/format.py`, `proxy_display/pane.py`, `proxy_display/proxy_pane_shared.py`, `proxy_display/render_turn.py`, `proxy_display/worker_proxy_pane.py`, `workers/worker_tokens_pane.py`.
**Calls out:** none.

---

### session_finder.py (77 LOC)

**Purpose:** `find_active_sessions(project_filter)` — enumerates `~/.claude/projects/**/*.jsonl` (including the subagent transcripts under each project's subagents directory), optionally filtered by project, sorted newest-first.
**Reads:** `~/.claude/projects/` directory tree.
**Writes:** nothing.
**Called by:** `core/monitor.py`, `menubar/discover.py`, `workers/worker_tmux.py` (`encode_project_path`), `dev/pipeline/io_profile/01_poll_cycle_cost.py`.
**Calls out:** none.

---

### startup.py (43 LOC)

**Purpose:** CLI argument parsing (`--project`/`--session`/`--mode`), SIGINT/SIGTERM handlers, startup/shutdown console messages.
**Reads:** `sys.argv`.
**Writes:** stdout (startup/shutdown messages); calls `sys.exit(0)` on shutdown signal.
**Called by:** `workflow.py`.
**Calls out:** none.

---

### tmux_launcher.py (250 LOC)

**Purpose:** launches the 7-window, 8-pane tmux split-screen layout (`launch_split_screen`) and self-heals missing windows/panes on Ctrl+R (`restart_panes`); owns the window layout table (`_WINDOW_LAYOUT`) and every tmux key-binding/status-bar setup call.
**Reads:** `tmux list-sessions`/`list-panes`/`list-windows`/`show-options` output.
**Writes:** creates/kills tmux sessions, windows, panes; sets tmux options and key bindings.
**Called by:** `workflow.py` (`--mode all` / `--mode restart-panes`), `monitor_janitor.py` (`kill_session`), `menubar/system.py` (`generate_session_name`, `check_session_exists`, `kill_session`).
**Calls out:** `tmux` (subprocess CLI).

---

### utils.py (169 LOC)

**Purpose:** shared formatting/rendering primitives with no I/O — timestamp formatting, cell-width-aware truncation/wrapping, ANSI-safe substring highlighting, copy-symbol placement, `right_align_time` (cuts a row to a cell budget, keeps a right-aligned `HH:MM:SS` in a fixed column, 3 cells from the right edge), header-rule sizing.
**Reads:** nothing (pure functions on passed-in strings/values).
**Writes:** nothing.
**Called by:** `format/token_format.py`, `gpu_pane/gpu_render.py`, `news_pane/pane.py`, `panes/token_pane.py`, `panes/token_search.py`, `panes/warnings_pane.py`, `panes/warnings_render.py`, `proxy_display/format.py`, `proxy_display/render_messages.py`, `proxy_display/render_turn.py`, `proxy_display/search.py`, `proxy_display/worker_proxy_pane.py`, `search_bar.py`, `workers/worker_switch_header.py`, `workers/worker_tokens_pane.py`.
**Calls out:** none.

---

### workflow.py (39 LOC, project root)

**Purpose:** single process entry point — parses `--mode`, dispatches to `tmux_launcher` (`all`/`restart-panes`), `menubar`, `gpu_pane`, `news_pane`, or `core.monitor.run_monitor` (every other mode).
**Reads:** `sys.argv` (via `startup.parse_arguments`).
**Writes:** nothing directly.
**Called by:** invoked directly (main session start); `tmux_launcher.py`'s own generated pane commands (`python3 {script_path} --mode <X>`).
**Calls out:** none.

---

### claude_proxy_start.sh (402 LOC, project root)

**Purpose:** shell entry point that launches mitmproxy + Claude Code with the proxy env — handles per-project log rotation/purge, a per-project marker with a liveness guard, model-flag precedence, and fires the background janitors (`monitor_janitor.py` and the worker-cli janitor from the iterative-dev project) on every session start.
**Reads:** `~/.claude/shared-rules/model_selection.json` (model precedence); existing log files (rotation/purge decisions); per-project marker files.
**Writes:** `src/logs/.proxy_addon_live_<id>.py` (live proxy-addon copy); rotated/purged log files; per-project marker files (`src/logs` + `/tmp`).
**Called by:** invoked directly (main session start); the command `src/ccwrap/wrapper.py` wraps.
**Calls out:** `mitmproxy`, `jq`, `tmux`, worker-cli (iterative-dev project).

---

## State

Runtime state (`active_project_filter`, `active_mode`) lives in `core/monitor.py`
as module-level variables — see `core/DOCS.md`. Every pane package reads it via
`from ..core import monitor as _monitor` (lazy, to avoid circular imports).

## Gotchas

- `search_bar._BG_RESTORE_SENTINEL` (`'\033[999m'`) must be resolved via `resolve_bg_restore` by every renderer that embeds it, or it leaks into terminal output as a literal escape code.
- `search_bar.KILL_LINE_CHAR` (`'\x15'`, Ctrl-U) is an unconfirmed mapping guess for Cmd+Backspace's terminal encoding — a rebind after live testing is a one-line change.
- `monitor_janitor.py`'s log path follows `monitor_root.resolve_monitor_cc_root` (`MONITOR_CC_ROOT` if set, else the checkout the module sits in) — a manual run from a worktree checkout without the env var set writes into that worktree's own `src/logs/`; the first `ROOT source=...` line in `monitor_sweep.log` states which source won.
- `monitor_janitor.py`'s log path follows `MONITOR_CC_ROOT` if set, else two directories above its own `__file__` — a manual run from a worktree checkout without the env var set writes into that worktree's own `src/logs/`, not the main checkout's.
- `tmux_launcher.restart_panes` self-heals only a pane whose spec parent pane is present; an unplaceable pane raises `RuntimeError` instead of splitting an arbitrary pane. Structural tmux calls run with `check=True`, so a failed call raises. `get_global_history_limit` returns `None` when tmux has no server (rc != 0) and the launch then skips the history-limit restore.
- `pane_error_log.log_pane_error` swallows its own write failures silently (`except Exception: pass`) — a full disk or permissions error here never propagates and never kills the calling pane loop.
- `session_finder.encode_project_path` must stay byte-identical to however Claude Code itself encodes project directory names, or `matches_project_filter` silently matches nothing.
- `utils._cell_width` treats emoji and CJK ranges as width-2 cells — every truncation/padding function across every pane depends on this being correct, or ANSI row-fill columns drift by one cell per wide character.
