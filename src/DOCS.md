# Monitor_CC Source Modules

Live monitoring tool for Claude Code CLI conversations - captures all tool calls with full input/output.

## Working Directory

**CRITICAL:** All commands assume CWD = `Monitor_CC/` (project root, not src/)

```bash
cd ./Monitor_CC
```

## Directory Structure

```
src/
├── __init__.py
├── monitor.py
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

---

## session_finder.py

**Purpose:** Discovers active Claude Code session files in ~/.claude/projects with optional project filtering.

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
- List of tool call dictionaries with name, input, output, timestamp, agent metadata
- List of malformed line warnings
- New file position for next read

**Usage:**
```python
from src.jsonl_parser import parse_new_tool_calls
tool_calls, warnings, new_position = parse_new_tool_calls(file_path, last_position)
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

**Usage:**
```python
from src.formatter import format_tool_call
output = format_tool_call(name, input_params, output, timestamp, tool_id, is_subagent)
```

---

## subagent_ui.py

**Purpose:** Renders collapsible subagent list UI for interactive monitoring of subagent activity.

**Inputs:**
- `subagent_metadata`: Dict of agent_id -> metadata (name, timestamp, call_count)
- `tool_calls_by_agent`: Dict of agent_id -> list of tool calls
- `subagent_states`: Dict of agent_id -> expanded (boolean)

**Outputs:**
- Formatted terminal UI string with collapsible entries

**Usage:**
```python
from src.subagent_ui import render_subagent_list
ui_output = render_subagent_list(metadata, calls, states)
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
