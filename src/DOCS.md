# Monitor_CC Source Modules

Live monitoring tool for Claude Code CLI conversations - captures all tool calls with full input/output.

## Working Directory

**CRITICAL:** All commands assume CWD = `Monitor_CC/` (project root, not src/)

```bash
cd Monitor_CC/
```

## Directory Structure

```
src/
├── __init__.py
├── proxy_pane.py         → Proxy pane + log parsing
├── core/                 → [DOCS.md](core/DOCS.md) Core monitoring loop subpackage
├── panes/                → [DOCS.md](panes/DOCS.md) Pane event loops subpackage
├── workers/              → [DOCS.md](workers/DOCS.md) Workers pane subpackage
├── hooks/                → [DOCS.md](hooks/DOCS.md) Hooks pane subpackage
├── metadata/             → [DOCS.md](metadata/DOCS.md) Metadata pane subpackage
├── subagents/            → [DOCS.md](subagents/DOCS.md) Subagents pane subpackage (deprecated)
├── format/               → [DOCS.md](format/DOCS.md) Formatting functions subpackage
├── jsonl/                → [DOCS.md](jsonl/DOCS.md) JSONL parsing subpackage
├── session_finder.py
├── input/                → [DOCS.md](input/DOCS.md) Keyboard/mouse input subpackage
├── constants.py
├── utils.py
├── startup.py
├── tmux_launcher.py
├── proxy_addon.py
├── proxy_launcher.sh
├── claude_proxy_start.sh
├── DOCS.md
└── logs/                 → Runtime log files (gitignored)
```

**Note:** Entry point workflow.py resides at project root and imports from this src/ package.

## Module Documentation

## utils.py

**Purpose:** Shared utilities for timestamp formatting used across all modules.

**Input:** ISO timestamp strings.

**Output:** HH:MM:SS formatted time strings.

---

## constants.py

**Purpose:** Single source of truth for colors, config values, tool names, modes, hook events, and patterns.

**Input:** —

**Output:** Constants imported by other modules:
- 256-color ANSI palette (RESET, RED, GREEN, YELLOW, BLUE, CYAN, MAGENTA, WHITE, PURPLE, ORANGE, PASTEL_BLUE, PASTEL_PURPLE, LIGHT_RED_BG, PASTEL_ORANGE, HOVER_BG)
- Config values (POLL_INTERVAL, INPUT_POLL_INTERVAL, LONG_OUTPUT_THRESHOLD, TMUX_HISTORY_LIMIT, EXPANDED_MAX_LINES)
- Tool names, mode strings (MODE_ALL, MODE_MAIN, MODE_SUBAGENT, MODE_RULES, MODE_WARNINGS, MODE_HOOKS, MODE_TOKENS, MODE_WORKERS, MODE_SUBAGENTS), hook event names
- Excluded tool set, regex patterns
- JSONL message type sets (KNOWN_MESSAGE_TYPES, KNOWN_IGNORED_TYPES)
- Pane header labels (PANE_HEADERS)

---

## startup.py

**Purpose:** CLI argument parsing, signal handling, and startup/shutdown messages for the monitor entry point.

**Input:** Command-line arguments (`--project`, `--mode`, `--ui`).

**Output:** Parsed argparse.Namespace; registered signal handlers; formatted startup/shutdown console messages.

**Usage:**
```python
from src.startup import parse_arguments, setup_signal_handlers, print_startup_message
args = parse_arguments()
setup_signal_handlers()
print_startup_message(args.project, args.mode)
```

---

## tmux_launcher.py

**Purpose:** Launches tmux split-screen session with separate panes for main agent, rules display, and subagent monitoring.

**Input:** `project_filter` (optional path), `ui` (bool for collapsible UI mode), `script_path` (absolute path to workflow.py).

**Output:** Creates and attaches to a tmux session with 5-window layout:
- Window 0 "main": Main (left 70%) + Tokens (right 30%)
- Window 1 "proxy": Proxy log (left 70%) + Metadata (right 30%)
- Window 2 "rules": Rules (left 50%) + Hooks (right 50%)
- Window 3 "workers": Workers + Worker-Proxy + Worker-Metadata (3-pane split)
- Window 4 "debug": Warnings (left 50%) + Waste-Calls (right 50%)

**Usage:**
```python
from src.tmux_launcher import launch_split_screen
launch_split_screen(project_filter="/path/to/project", ui=True, script_path="/path/to/workflow.py")
```

---

## core/

See [core/DOCS.md](core/DOCS.md).

**Modules:** `monitor.py` (session discovery + streaming loop), `monitor_session.py` (per-session JSONL processing), `monitor_display.py` (terminal output for main pane).

---

## panes/

See [panes/DOCS.md](panes/DOCS.md).

**Modules:** `token_pane.py` (token/cache tracker loop), `rules_pane.py` (active rules + hook log loop), `warnings_pane.py` (tool errors loop), `waste_pane.py` (proxy forensics loop).

---

## proxy_pane.py

**Purpose:** Proxy pane. Reads `api_requests_*.jsonl`, shows API request entries grouped by turn with two-level expand hierarchy.

**Input:** Proxy log file (discovered via marker file), session JSONL (for turn detection via `build_cache_turns` from token_pane.py), project filter.

**Output:** Two-level expand hierarchy:
- **Turn header (clickable):** `▶ Turn N [HH:MM] effort:X think:Yk(type) Δsys/Δtools/Δmsgs` — delta vs previous turn. Effort, thinking budget, and thinking type from API payload.
- **Baseline line:** `total: sys:Xk tools:Xk msgs:Xk` — cumulative totals from previous turn's last entry.
- **Expanded turn → Request metadata lines:** Compact one-liners per request (`#N model Xmsg BP:Y 🔧Z ⚠T/⚠S/⚠M Δmsgs`). Clickable for second-level expand.
- **Expanded request → Message lines:** New messages since previous request (or modified messages via backwards scan for same-count entries). Content preview auto-shown. Modified messages use `content_tail` field for showing appended content.

**REQ numbering:** Synced to session JSONL api_calls at turn boundaries. Helper requests (BP:0, non-haiku) get sub-numbers (#7.1, #7.2). Haiku labeled "H".

**Data enrichment:** `_extract_raw_payload_fields()` processes raw API payload into per-entry fields (system_blocks, tools_hash, schema_warnings, thinking_config, output_config) and enriches per-message data with `content_tail` (last 500 chars) for modified-message detection. Raw payload deleted after extraction.

---

## workers/

See [workers/DOCS.md](workers/DOCS.md).

**Modules:** `worker_pane.py` (event loop), `worker_format.py` (data extraction + rendering), `worker_tmux.py` (tmux session discovery + status detection).

---

## hooks/

See [hooks/DOCS.md](hooks/DOCS.md).

**Modules:** `hook_parser.py` (log parsing + filtering), `hooks_format.py` (display item building + block rendering), `hooks_persist.py` (persisted additionalContext enrichment), `hooks_pane.py` (event loop + scroll/click/hover).

---

## metadata/

See [metadata/DOCS.md](metadata/DOCS.md).

**Modules:** `metadata_format.py` (proxy entry formatting with change-tracking), `metadata_pane.py` (main + worker event loops).

---

## subagents/

See [subagents/DOCS.md](subagents/DOCS.md).

**Modules:** `subagent_pane.py` (event loop), `subagent_render.py` (cache-tracker rendering),
`subagent_ui.py` (state + list building), `subagent_ui_format.py` (entry formatting helpers).

---

## input/

See [input/DOCS.md](input/DOCS.md).

**Modules:** `click_handler.py` (keyboard + mouse stdin handling), `ui_mode.py` (subagent tracking + rules block rendering).

---

## session_finder.py

**Purpose:** Discovers active Claude Code session files in `~/.claude/projects` with optional project filtering. Includes subagent files from `*/subagents/agent-*.jsonl` subdirectories. `encode_project_path()` replaces `/`, `_`, and `.` with `-` to match Claude Code's directory naming convention (dot replacement required for paths containing `.claude/worktrees/`).

**Input:** `project_filter` (optional project path to match against encoded directory names).

**Output:** List of JSONL file paths sorted by modification time (most recent first).

**Usage:**
```python
from src.session_finder import find_active_sessions
sessions = find_active_sessions(project_filter="/path/to/project")
```

---

## jsonl/

See [jsonl/DOCS.md](jsonl/DOCS.md).

**Modules:** `jsonl_parser.py` (core JSONL parsing + tool call extraction), `jsonl_extractors.py` (typed extractors for prompts, media, thinking, skills, usage, unknown types), `jsonl_cache_turns.py` (cache turn grouping for token/subagent/worker panes).

---

---

## format/

See [format/DOCS.md](format/DOCS.md).

**Modules:** `formatter.py` (tool call formatting), `formatter_events.py` (event formatting), `token_format.py` (token/cache tracker rendering).

---


---

## proxy_addon.py

**Purpose:** mitmproxy addon that intercepts Claude Code API requests for logging and cache optimization. Logs full request payloads to JSONL. Applies content modifications (strip plan-mode, task-tools-nag, task-notification, rejection messages; replace system prompt; strip session-specific guidance; extract hook-injected rules to system block with `scope: "global"`). Strips unused tools via blocklist + trims Agent description. Strips `tool_reference` blocks that reference blocklisted tools (prevents 400 errors from ToolSearch returning references to stripped tools). Takes over cache_control placement from Claude Code: strips all CC-set markers, sets own 4 breakpoints on the modified payload (rules block or system[-1], last non-deferred tool, last stable message, last message). Tracks previous modified messages per model family for stable BP3 calculation. `_summarize_message()` builds per-block breakdown (type, chars, preview, has_cc) for proxy pane display.

**Input:** HTTP flows to `api.anthropic.com/v1/messages` via mitmproxy.

**Output:** Modified request payload sent to API; JSONL log entries to `src/logs/api_requests_<log_id>.jsonl`.

---

## claude_proxy_start.sh

**Purpose:** Combined launcher that starts mitmproxy with `proxy_addon.py` and then launches Claude Code with proxy env vars (`HTTPS_PROXY`, `NODE_EXTRA_CA_CERTS`, `SSL_CERT_FILE`). Generates per-proxy-start log IDs, writes per-session marker files to `/tmp/.monitor_cc_proxy_${SESSION_ID}` (3-line format: port, log_id, MONITOR_CC_ROOT) for worker proxy discovery. Creates per-session live-copy of proxy_addon.py (`.proxy_addon_live_${SESSION_ID}.py`) to prevent hot-reload conflicts between parallel proxy instances. Handles cleanup on exit.

**Input:** `--project <path>` (optional, defaults to CWD), additional Claude Code args.

**Output:** Running mitmproxy on a free port, Claude Code session with proxy configured.

**Usage:**
```bash
cd /path/to/project && /path/to/Monitor_CC/src/claude_proxy_start.sh
# or with explicit project:
/path/to/Monitor_CC/src/claude_proxy_start.sh --project /path/to/project
```

---

## proxy_launcher.sh

**Purpose:** Standalone proxy start script (without Claude Code). Used when proxy needs to run independently.

**Input:** Environment variables for configuration.

**Output:** Running mitmproxy instance.
