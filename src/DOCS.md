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
├── utils.py          # Shared utilities (logging, timestamps, colors)
├── constants.py      # Shared constants (tool names, modes, patterns)
├── startup.py        # CLI argument parsing, signal handlers, startup messages
├── tmux_launcher.py  # tmux split-screen session launch and configuration
├── monitor.py
├── ui_mode.py
├── session_finder.py
├── jsonl_parser.py
├── hook_parser.py
├── formatter.py
├── subagent_ui.py
├── click_handler.py
├── DOCS.md
├── debug/
└── logs/
```

**Note:** Entry point workflow.py resides at project root and imports from this src/ package.

## Module Documentation

## utils.py

**Purpose:** Shared utilities for logging and timestamp formatting used across all modules.

**Functions:**
- `log_tagged(logger, tag, color, message)` - Tagged logging with colored prefix
- `format_timestamp(iso_timestamp)` - Convert ISO timestamp to HH:MM:SS local time

**Constants:**
- ANSI color codes: `RESET`, `RED`, `GREEN`, `YELLOW`, `BLUE`, `MAGENTA`, `CYAN`, `WHITE`, `PURPLE`, `ORANGE`

**Usage:**
```python
from src.utils import log_tagged, format_timestamp, GREEN
log_tagged(logger, "TAG", GREEN, "Message")
time_str = format_timestamp("2025-01-01T12:00:00Z")
```

---

## constants.py

**Purpose:** Shared constants for tool names, modes, hook events, and patterns.

**Constants:**
- `TOOL_TASK` - Task tool name
- `MODE_ALL`, `MODE_MAIN`, `MODE_SUBAGENT` - Monitoring modes
- `HOOK_USER_PROMPT`, `HOOK_PRE_TOOL` - Hook event names
- `EXCLUDED_TOOLS` - Set of tools excluded from display
- `SYSTEM_REMINDER_PATTERN` - Regex for system-reminder tags

**Usage:**
```python
from src.constants import TOOL_TASK, MODE_ALL, EXCLUDED_TOOLS
if mode == MODE_ALL:
    ...
```

---

## startup.py

**Purpose:** CLI argument parsing, signal handling, and startup/shutdown messages for the monitor entry point.

**Outputs:**
- Parsed command-line arguments (argparse.Namespace)
- Signal handler registration for graceful shutdown
- Formatted startup/shutdown console messages

**Functions:**
- `parse_arguments()` - orchestrator, parses --project, --mode, --ui flags
- `setup_signal_handlers()` - Register SIGINT/SIGTERM handlers
- `handle_shutdown()` - Handle shutdown signals gracefully
- `print_startup_message()` - Print colored startup banner
- `print_shutdown_message()` - Print colored shutdown banner

**Usage:**
```python
from src.startup import parse_arguments, setup_signal_handlers, print_startup_message
args = parse_arguments()
setup_signal_handlers()
print_startup_message(args.project, args.mode)
```

---

## tmux_launcher.py

**Purpose:** Launches tmux split-screen session with separate panes for main agent and subagent monitoring.

**Inputs:**
- `project_filter`: Optional project path to filter sessions
- `ui`: Enable collapsible UI mode for subagent pane
- `script_path`: Absolute path to workflow.py for subprocess commands

**Outputs:**
- Creates and attaches to tmux session with configured panes

**Functions:**
- `launch_split_screen()` - orchestrator
- `is_tmux_installed()` - Check tmux availability
- `is_inside_tmux()` - Detect nested tmux
- `generate_session_name()` - Hash-based unique session name
- `check_session_exists()` - Check for existing session
- `kill_session()` - Kill stale session
- `get_global_history_limit()` - Save current history limit
- `restore_global_history_limit()` - Restore saved limit
- `configure_tmux_session()` - Set keybindings, mouse, status bar

**Usage:**
```python
from src.tmux_launcher import launch_split_screen
launch_split_screen(project_filter="/path/to/project", ui=True, script_path="/path/to/workflow.py")
```

---

## monitor.py

**Purpose:** Core polling orchestrator. Continuously monitors session files and displays new tool calls with color-coded output.

**Inputs:**
- `project_filter`: Optional project path to filter sessions
- `mode`: Filter for main/subagent/all files (default: all)
- `ui_mode`: Enable collapsible subagent UI (default: False)

**Outputs:**
- Formatted tool calls to console (streaming mode)
- Collapsible UI list (if ui_mode enabled)

**Usage:**
```python
from src.monitor import run_monitor
run_monitor(project_filter="/path/to/project", mode="main", ui_mode=False)
```

**Variables:**
- `POLL_INTERVAL`: Seconds between session polls (default: 0.5)

**Key Functions:**
- `run_monitor()` - orchestrator
- `process_session_file()` - Process single JSONL file
- `handle_task_request()` - Handle Task tool REQUEST
- `handle_task_response()` - Handle Task tool RESPONSE (maps agent IDs, displays full result)
- `handle_subagent_call()` - Handle tool calls from subagents
- `accumulate_usage()` - Accumulate token usage for turn total
- `display_user_prompt_from_jsonl()` - Display USER PROMPT detected from session JSONL, with pending hook output

---

## ui_mode.py

**Purpose:** UI mode loop with keyboard input and subagent tracking for interactive monitoring.

**Inputs:**
- `subagent_metadata`: Dict tracking discovered agents
- `tool_calls_by_agent`: Dict of agent tool calls
- `agent_to_task`: Dict mapping agent IDs to parent task IDs
- `agent_to_type`: Dict mapping agent IDs to subagent types
- `monitor_sessions_fn`: Callback to monitor.monitor_sessions

**Outputs:**
- Renders collapsible UI to terminal (clears screen on each update)

**Functions:**
- `run_ui_loop()` - orchestrator
- `handle_pending_keypresses()`
- `sync_ui_to_screen()` - Renders only subagent list (no main agent tasks)
- `track_subagent_metadata()`

**Usage:**
```python
from src.ui_mode import run_ui_loop
run_ui_loop(metadata, calls, agent_to_task, agent_to_type, monitor_fn)
```

---

## session_finder.py

**Purpose:** Discovers active Claude Code session files in ~/.claude/projects with optional project filtering. Includes subagent files from `*/subagents/agent-*.jsonl` subdirectories.

**Inputs:**
- `project_filter`: Optional project path to match against encoded directory names

**Outputs:**
- List of JSONL file paths sorted by modification time (most recent first)

**Usage:**
```python
from src.session_finder import find_active_sessions
sessions = find_active_sessions(project_filter="/path/to/project")
```

---

## jsonl_parser.py

**Purpose:** Parses JSONL conversation files and extracts correlated tool_use/tool_result pairs with metadata.

**Inputs:**
- `file_path`: Path to JSONL session file
- `last_position`: Byte offset to start reading from

**Outputs:**
- List of tool call dictionaries with name, input, output, timestamp, agent metadata, usage, is_error
- New file position for next read
- List of malformed line warnings
- List of user media items (images, documents)
- List of thinking blocks

**Key Functions:**
- `parse_new_tool_calls()` - orchestrator
- `parse_jsonl_lines()` - Parse raw lines into message objects
- `extract_tool_calls()` - Extract tool_use/tool_result pairs (includes usage stats, is_error flag)
- `extract_user_media()` - Extract non-text content from user messages (images, documents)
- `extract_user_prompts()` - Extract user prompts from external user messages (filters command-messages and skill injections)
- `extract_thinking_blocks()` - Extract extended thinking from assistant messages

**Usage:**
```python
from src.jsonl_parser import parse_new_tool_calls
tool_calls, new_position, warnings, user_media, thinking, user_prompts = parse_new_tool_calls(file_path, last_position, cache)
```

---

## hook_parser.py

**Purpose:** Parses hook log file (hook_outputs.jsonl) written by Claude Code hooks for display in monitor.

**Inputs:**
- `file_path`: Path to hook log file
- `last_position`: Byte offset to start reading from

**Outputs:**
- List of hook entry dictionaries with timestamp, cwd, hook_event, hook_script, output, tool_name
- New file position for next read

**Usage:**
```python
from src.hook_parser import parse_new_hook_entries
entries, new_position = parse_new_hook_entries(file_path, last_position)
```

---

## formatter.py

**Purpose:** Formats tool calls with color-coded headers (green for main agent, blue for subagents) and proper indentation.

**Inputs:**
- Tool call data: name, input dict, output string, timestamp, tool_use_id, agent metadata

**Outputs:**
- Formatted string with ANSI color codes for terminal display

**Key Functions:**
- `format_tool_call()` - orchestrator for tool call formatting
- `format_user_prompt()` - Format USER PROMPT stamp with optional hook outputs
- `format_user_media()` - Format user media item as `[IMAGE: mime/type]` or `[DOC: mime/type]`
- `format_hook_annotation()` - Format hook annotation for PreToolUse hooks
- `format_usage()` - Format token usage stats as `[in:X cache_r:Y cache_w:Z out:W]` (pastel yellow)
- `format_turn_total()` - Format turn total usage with separator line (signal pink)
- `format_thinking()` - Format thinking block with timestamp (pastel orange)
- `format_error_output()` - Format error output in red

**Usage:**
```python
from src.formatter import format_tool_call, format_user_media, format_thinking
output = format_tool_call(name, input_params, output, timestamp, tool_id, is_subagent, usage=usage, is_error=False)
media_output = format_user_media({'type': 'image', 'media_type': 'image/png', 'timestamp': '...'})
thinking_output = format_thinking({'thinking': 'Der User...', 'timestamp': '...'})
```

---

## subagent_ui.py

**Purpose:** Renders collapsible subagent list UI for interactive monitoring of subagent activity.

**Inputs:**
- `subagent_metadata`: Dict of agent_id -> metadata (name, timestamp, call_count)
- `tool_calls_by_agent`: Dict of agent_id -> list of tool calls
- `subagent_states`: Dict of agent_id -> expanded (boolean)

**Outputs:**
- Formatted terminal UI string with collapsible entries (subagent tool calls only)

**Usage:**
```python
from src.subagent_ui import render_subagent_list
ui_output = render_subagent_list(metadata, calls)
```

---

## click_handler.py

**Purpose:** Handles keyboard input for the collapsible subagent UI. Reads digit keypresses (1-9) to toggle subagent expanded/collapsed state.

**Inputs:**
- Single character keypresses from stdin in raw mode

**Outputs:**
- Agent ID to toggle when digit key pressed

**Usage:**
```python
from src.click_handler import setup_keyboard_input, read_keypress, get_agent_by_index
setup_keyboard_input()
key = read_keypress()
agent_id = get_agent_by_index(int(key), sorted_agents)
```
