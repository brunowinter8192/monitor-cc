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
├── utils.py
├── constants.py
├── startup.py
├── tmux_launcher.py
├── monitor.py
├── ui_mode.py
├── session_finder.py
├── jsonl_parser.py
├── hook_parser.py
├── formatter.py
├── subagent_ui.py
├── click_handler.py
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
- Tool names, mode strings (MODE_ALL, MODE_MAIN, MODE_SUBAGENT, MODE_RULES, MODE_WARNINGS, MODE_HOOKS, MODE_TOKENS, MODE_WORKERS), hook event names
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

**Output:** Creates and attaches to a tmux session with 4-window layout (main+tokens | rules+hooks | workers | warnings+subagents).

**Usage:**
```python
from src.tmux_launcher import launch_split_screen
launch_split_screen(project_filter="/path/to/project", ui=True, script_path="/path/to/workflow.py")
```

---

## monitor.py

**Purpose:** Core polling orchestrator. Continuously monitors session files and displays new tool calls with color-coded output.

**Input:** `project_filter` (optional path), `mode` (main/subagent/all/rules/warnings/hooks/tokens/workers), `ui_mode` (bool).

**Output:** Formatted tool calls to console; collapsible UI list; rules display with screen-clear refresh; warnings display with screen-clear refresh; hooks display as scrolling stream; token profiling display (input tokens: direct/cache create/cache read with color legend + output tokens per tool flat list, session browser for cumulative N sessions with granular output breakdown) with screen-clear refresh; workers display (real-time worker status via window_activity timestamp, expand/collapse with scrollable viewport + compact tool call display, hover-highlight, keyboard + SGR mouse input with dual poll intervals 50ms/500ms). Headers rendered as sticky tmux pane-border labels (PASTEL_ORANGE).

**Workers-Pane functions:** `find_worker_jsonl(session)` discovers worker JSONL via tmux `pane_current_path` → `encode_project_path()`. `extract_worker_tool_calls(jsonl_path)` parses tool_use entries. State: `worker_expand_states`, `worker_scroll_offsets`, `worker_line_map`, `hover_row`.

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

**Purpose:** Discovers active Claude Code session files in `~/.claude/projects` with optional project filtering. Includes subagent files from `*/subagents/agent-*.jsonl` subdirectories.

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

**Purpose:** Parses hook log file (`src/logs/hook_outputs.jsonl`) written by Claude Code hooks for display in the monitor.

**Input:** `file_path` (hook log file path), `last_position` (byte offset for incremental reads).

**Output:** List of hook entry dicts (timestamp, cwd, hook_event, hook_script, output, tool_name); new file position.

**Usage:**
```python
from src.hook_parser import parse_new_hook_entries
entries, new_position = parse_new_hook_entries(file_path, last_position)
```

---

## formatter.py

**Purpose:** Formats tool calls, user prompts, hook annotations, thinking blocks, skill activations, token profiles (input + output sections with bar charts), cumulative token profiles, worker status blocks, and pane headers as color-coded terminal strings.

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
