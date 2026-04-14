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
├── monitor.py            → Core polling orchestrator (~460 lines)
├── token_pane.py         → Token profiling pane
├── proxy_pane.py         → Proxy pane + log parsing
├── workers/              → [DOCS.md](workers/DOCS.md) Workers pane subpackage
├── hooks_pane.py         → Hooks pane + persisted context
├── rules_pane.py         → Rules pane + InstructionsLoaded routing
├── warnings_pane.py      → Warnings pane
├── subagent_pane.py      → Subagent pane
├── formatter.py          → Shared tool call formatting (~230 lines)
├── session_finder.py
├── jsonl_parser.py
├── hook_parser.py
├── ui_mode.py
├── subagent_ui.py
├── click_handler.py
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

**Output:** Creates and attaches to a tmux session with 4-window layout (main+tokens | rules+hooks | workers+subagents | warnings). Window 2 has 2 panes: Pane 2.0 (left 50%) = workers, Pane 2.1 (right 50%) = subagents.

**Usage:**
```python
from src.tmux_launcher import launch_split_screen
launch_split_screen(project_filter="/path/to/project", ui=True, script_path="/path/to/workflow.py")
```

---

## monitor.py

**Purpose:** Core polling orchestrator (~460 lines). Session discovery, streaming loop, tool call routing, task/subagent tracking. Delegates pane rendering to dedicated pane modules.

**Input:** `project_filter` (optional path), `mode` (main/subagent/all/rules/warnings/hooks/tokens/workers/subagents/proxy), `ui_mode` (bool).

**Output:** Formatted tool calls to console. Routes to pane-specific loops via `run_monitor()`.

**Session-Scoping:** `_get_session_start_ts()` extracts first message timestamp from newest main session JSONL minus 60s buffer as cutoff.

---

## token_pane.py

**Purpose:** Token profiling pane. Cache tracker with CR/CC/D per API call, grouped by turn.

**Input:** Session JSONL files (incremental parsing with position tracking).

**Output:** Formatted token display with expand/collapse, hover, scroll. Mouse + keyboard input. Sequential request numbering (independent of proxy pane).

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

## hooks_pane.py

**Purpose:** Hooks pane. Hook events with expand/collapse, persisted additionalContext enrichment.

**Input:** Hook log (`src/logs/hook_outputs.jsonl`), persisted hook files from `tool-results/` dirs.

**Output:** Scrollable hooks stream with expand/collapse.

---

## rules_pane.py

**Purpose:** Rules pane. Active rules display with [P]/[G] prefix, InstructionsLoaded routing from hook log.

**Input:** Hook log entries (InstructionsLoaded events).

**Output:** Rules list with expand/collapse, source labels.

---

## warnings_pane.py

**Purpose:** Warnings pane. Two sections: (1) Unknown JSONL message types from session parsing, (2) Tool errors detected from Proxy JSONL (expandable with full error text).

**Input:** Unknown type entries from session processing + Proxy JSONL entries (incremental read via `parse_proxy_log`).

**Output:** Interactive pane with mouse support (click expand/collapse, scroll). Format Warnings section (type counts) + Tool Errors section (timestamp, tool name, error summary, expandable full text).

---

## subagent_pane.py

**Purpose:** Subagent pane. Per-agent cache token view with expand/collapse.

**Input:** Subagent metadata, agent JSONL files.

**Output:** Collapsible agent list with cache-tracker per agent.

**Usage:**
```python
from src.monitor import run_monitor
run_monitor(project_filter="/path/to/project", mode="main", ui_mode=False)
```

---

## ui_mode.py

**Purpose:** UI mode loop with keyboard + mouse input, subagent tracking, and active rules display for interactive monitoring.

**Input:** Subagent metadata dicts, tool calls by agent, agent-to-task/type mappings, monitor callback, active rules dict.

**Output:** Collapsible UI rendered to terminal on each update; rules block with [P]/[G] prefixes. SGR mouse clicks toggle subagent expand/collapse, scroll wheel scrolls viewport, hover highlights clickable lines. State: `hover_row`, `subagent_scroll_offsets`. Dual poll intervals (50ms input / 500ms data).

**Usage:**
```python
from src.ui_mode import run_ui_loop
run_ui_loop(metadata, calls, agent_to_task, agent_to_type, monitor_fn, active_rules)
```

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

## jsonl_parser.py

**Purpose:** Parses JSONL conversation files and extracts correlated tool_use/tool_result pairs with metadata (usage, errors, user prompts, media, thinking, skill activations).

**Input:** `file_path` (JSONL session file), `last_position` (byte offset for incremental reads).

**Output:** Tool call dicts; new file position; malformed line warnings; user media items; thinking blocks; user prompts; skill activation items; unknown type detections; usage data entries.

**Usage:**
```python
from src.jsonl_parser import parse_new_tool_calls
tool_calls, new_position, warnings, user_media, thinking, user_prompts, skill_activations, unknown_types, usage_data = parse_new_tool_calls(file_path, last_position, cache)
```

---

## hook_parser.py

**Purpose:** Parses hook log file (`src/logs/hook_outputs.jsonl`) written by Claude Code hooks for display in the monitor. Provides project filtering (prefix match, includes worktree subdirectories) and timestamp filtering for session-scoping.

**Input:** `last_position` (byte offset for incremental reads).

**Output:** List of hook entry dicts (timestamp, cwd, hook_event, hook_script, output, tool_name); new file position.

**Usage:**
```python
from src.hook_parser import parse_new_hook_entries, filter_by_project, filter_by_timestamp
entries, new_position = parse_new_hook_entries(last_position)
filtered = filter_by_project(entries, project_path)  # startswith match, includes worktrees
filtered = filter_by_timestamp(filtered, since_ts)   # ISO 8601 cutoff
```

---

## formatter.py

**Purpose:** Shared tool call formatting (~230 lines). Formats tool calls, user prompts, hook annotations, thinking blocks, skill activations, and system messages as color-coded terminal strings. Pane-specific formatting (cache tracker, workers block, proxy block, hooks block) moved to respective pane modules.

**Input:** Tool call data (name, input dict, output string, timestamp, tool_use_id, agent metadata, is_error flag).

**Output:** Formatted ANSI-colored string for terminal display.

**Usage:**
```python
from src.formatter import format_tool_call, format_user_media, format_thinking
output = format_tool_call(name, input_params, output, timestamp, tool_id, is_subagent, is_error=False)
```

---

## subagent_ui.py

**Purpose:** Renders collapsible subagent list UI for interactive monitoring of subagent activity.

**Input:** `subagent_metadata` (agent_id → metadata dict), `tool_calls_by_agent` (agent_id → tool call list), `subagent_states` (agent_id → expanded bool), `hover_row` (optional), `scroll_offsets` (optional).

**Output:** Formatted terminal UI string with collapsible per-agent entries. Scrollable viewport (max 15 lines per block), compact tool call display (MCP → short_name + params, non-MCP → name + char count), hover-highlight on clickable lines.

**Usage:**
```python
from src.subagent_ui import render_subagent_list
ui_output = render_subagent_list(metadata, calls, hover_row=5, scroll_offsets={'agent-1': 10})
```

---

## click_handler.py

**Purpose:** Handles keyboard and SGR mouse input for expand/collapse UI in subagent and workers panes. Reads digit keypresses (1-9), mouse click/motion/scroll events. All stdin reads via `os.read(fd, 1)` (unbuffered, bypasses Python IO layer).

**Input:** Single character keypresses and multi-byte SGR mouse sequences from stdin in raw mode.

**Output:** Agent/worker ID to toggle. Mouse functions: `enable_mouse()` / `disable_mouse()` activate SGR mode 1003+1006 (Any Event Tracking incl. motion). `read_mouse_event(first_char)` parses `\033[<b;col;rowM` sequences, returns `(button, col, row)` tuple for press/motion events (button 0=click, 32+=motion, 64/65=scroll).

**Usage:**
```python
from src.click_handler import setup_keyboard_input, read_keypress, get_agent_by_index, enable_mouse, disable_mouse, read_mouse_event
setup_keyboard_input()
enable_mouse()
key = read_keypress()
if key == '\033':
    event = read_mouse_event(key)  # (button, col, row) or None
```

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
