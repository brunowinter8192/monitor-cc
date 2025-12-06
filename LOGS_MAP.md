# Logging Architecture - Workflow-Oriented

## Overview
Monitor_CC uses 9 workflow-oriented log files that follow the execution sequence from startup through continuous monitoring. Each log file tracks events for a specific workflow phase.

## Log Files by Workflow Phase

### 01_startup.log (12 events)

| # | Event | Module | Function | Tag | Color |
|---|-------|--------|----------|-----|-------|
| 1 | Main function entry with args | workflow.py | main() | MAIN_ENTRY | Magenta |
| 2 | Arguments parsed | workflow.py | parse_arguments() | ARGPARSE | Magenta |
| 3 | launch_split_screen entry | workflow.py | launch_split_screen() | SPLIT_LAUNCH | Cyan |
| 4 | tmux installation check | workflow.py | is_tmux_installed() | TMUX_CHECK | Cyan |
| 5 | Inside tmux check | workflow.py | is_inside_tmux() | TMUX_INSIDE | Cyan |
| 6 | Session name generated | workflow.py | generate_session_name() | SESS_NAME | Cyan |
| 7 | Script path resolved | workflow.py | launch_split_screen() | SCRIPT_PATH | Cyan |
| 8 | Session existence check | workflow.py | check_session_exists() | SESS_EXISTS | Cyan |
| 9 | Session killed (stale) | workflow.py | kill_session() | SESS_KILL | Yellow |
| 10 | Signal handlers registered | workflow.py | setup_signal_handlers() | SIGNAL_REG | Magenta |
| 11 | Shutdown signal received | workflow.py | handle_shutdown() | SHUTDOWN | Red |
| 12 | Monitor startup message | workflow.py | print_startup_message() | MONITOR_START | Green |

---

### 02_initialization.log (5 events)

| # | Event | Module | Function | Tag | Color |
|---|-------|--------|----------|-----|-------|
| 1 | run_monitor entry | monitor.py | run_monitor() | RUN_MONITOR | Magenta |
| 2 | Starting UI mode | monitor.py | run_monitor() | UI_MODE | Cyan |
| 3 | Starting streaming mode | monitor.py | run_monitor() | STREAM_MODE | Cyan |
| 4 | Initializing N sessions | monitor.py | initialize_file_positions() | INIT_SESS | Blue |
| 5 | File position initialized | monitor.py | initialize_file_positions() | FILE_POS_INIT | Blue |

---

### 03_session_discovery.log (11 events)

| # | Event | Module | Function | Tag | Color |
|---|-------|--------|----------|-----|-------|
| 1 | find_active_sessions called | session_finder.py | find_active_sessions() | FIND_SESS | Blue |
| 2 | Projects directory not found | session_finder.py | get_project_directories() | NO_PROJ_DIR | Red |
| 3 | Found N project directories | session_finder.py | get_project_directories() | PROJ_DIRS | Blue |
| 4 | Collecting JSONL files | session_finder.py | collect_jsonl_files() | COLLECT_JSONL | Blue |
| 5 | Skipping project (filter) | session_finder.py | collect_jsonl_files() | FILTER_SKIP | Yellow |
| 6 | Found N JSONL files in project | session_finder.py | collect_jsonl_files() | JSONL_FOUND | Blue |
| 7 | Collected N total files | session_finder.py | collect_jsonl_files() | TOTAL_JSONL | Green |
| 8 | Filter match check | session_finder.py | matches_project_filter() | FILTER_MATCH | Blue |
| 9 | Encoded project path | session_finder.py | encode_project_path() | PATH_ENCODE | Blue |
| 10 | Sorted files by mtime | session_finder.py | sort_by_modification_time() | SORT_FILES | Blue |
| 11 | Found N active sessions | session_finder.py | find_active_sessions() | ACTIVE_SESS | Green |

---

### 04_file_reading.log (5 events)

| # | Event | Module | Function | Tag | Color |
|---|-------|--------|----------|-----|-------|
| 1 | File not found | jsonl_parser.py | read_new_lines() | FILE_404 | Red |
| 2 | Read N bytes, M lines | jsonl_parser.py | read_new_lines() | FILE_READ | Blue |
| 3 | Processing session file | monitor.py | process_session_file() | PROCESS_FILE | Blue |
| 4 | New session discovered | monitor.py | update_session_tracking() | NEW_SESS | Green |
| 5 | Session removed | monitor.py | update_session_tracking() | SESS_REMOVED | Yellow |

---

### 05_jsonl_parsing.log (6 events)

| # | Event | Module | Function | Tag | Color |
|---|-------|--------|----------|-----|-------|
| 1 | parse_new_tool_calls entry | jsonl_parser.py | parse_new_tool_calls() | PARSE_START | Green |
| 2 | Read N new lines | jsonl_parser.py | parse_new_tool_calls() | LINES_READ | Blue |
| 3 | JSON decode error | jsonl_parser.py | parse_jsonl_lines() | JSON_ERROR | Red |
| 4 | Valid vs malformed stats | jsonl_parser.py | parse_jsonl_lines() | PARSE_STATS | White |
| 5 | Parsed N tool calls | jsonl_parser.py | parse_new_tool_calls() | PARSE_DONE | Green |
| 6 | Malformed JSONL warning | monitor.py | display_warning() | MALFORMED | Yellow |

---

### 06_tool_extraction.log (8 events)

| # | Event | Module | Function | Tag | Color |
|---|-------|--------|----------|-----|-------|
| 1 | extract_tool_calls entry | jsonl_parser.py | extract_tool_calls() | EXTRACT_START | Green |
| 2 | Cached tool_use | jsonl_parser.py | extract_tool_calls() | TOOL_CACHED | White |
| 3 | Matched tool_result | jsonl_parser.py | extract_tool_calls() | TOOL_MATCH | Green |
| 4 | Orphaned tool_result | jsonl_parser.py | extract_tool_calls() | TOOL_ORPHAN | Yellow |
| 5 | Extraction statistics | jsonl_parser.py | extract_tool_calls() | EXTRACT_STATS | White |
| 6 | After filtering count | jsonl_parser.py | extract_tool_calls() | FILTER_COUNT | White |
| 7 | Agent metadata discovered | monitor.py | track_subagent_metadata() | AGENT_DISC | Cyan |
| 8 | Updated agent call count | monitor.py | track_subagent_metadata() | AGENT_COUNT | White |

---

### 07_display_routing.log (9 events)

| # | Event | Module | Function | Tag | Color |
|---|-------|--------|----------|-----|-------|
| 1 | monitor_sessions called | monitor.py | monitor_sessions() | MON_SESS | Blue |
| 2 | After mode filter | monitor.py | monitor_sessions() | MODE_FILTER | Blue |
| 3 | filter_sessions_by_mode | monitor.py | filter_sessions_by_mode() | FILTER_MODE | Blue |
| 4 | Task request displayed | monitor.py | process_session_file() | TASK_REQ | Purple |
| 5 | Task response displayed | monitor.py | process_session_file() | TASK_RESP | Purple |
| 6 | Subagent UI tracked | monitor.py | process_session_file() | SUB_UI_TRACK | Orange |
| 7 | Subagent displayed | monitor.py | process_session_file() | SUB_DISPLAY | Orange |
| 8 | Subagent buffered | monitor.py | process_session_file() | SUB_BUFFER | Yellow |
| 9 | Processing summary stats | monitor.py | process_session_file() | PROC_STATS | White |

---

### 08_ui_rendering.log (10 events)

| # | Event | Module | Function | Tag | Color |
|---|-------|--------|----------|-----|-------|
| 1 | UI loop iteration (debug) | monitor.py | run_ui_loop() | UI_ITER | White |
| 2 | sync_ui_to_screen entry | monitor.py | sync_ui_to_screen() | UI_SYNC | Purple |
| 3 | Re-rendering UI | monitor.py | sync_ui_to_screen() | UI_RENDER | Purple |
| 4 | No change, skip render | monitor.py | sync_ui_to_screen() | UI_SKIP | White |
| 5 | render_subagent_list entry | subagent_ui.py | render_subagent_list() | RENDER_LIST | Purple |
| 6 | No subagents to render | subagent_ui.py | build_all_entries() | NO_AGENTS | Yellow |
| 7 | Built N entries | subagent_ui.py | build_all_entries() | ENTRIES_BUILT | Purple |
| 8 | Agent has no tool calls | subagent_ui.py | build_expanded_entry() | NO_CALLS | Yellow |
| 9 | Building expanded entry | subagent_ui.py | build_expanded_entry() | EXPAND_BUILD | Purple |
| 10 | Rendered output stats | subagent_ui.py | render_subagent_list() | RENDER_STATS | White |

---

### 09_input_handling.log (6 events)

| # | Event | Module | Function | Tag | Color |
|---|-------|--------|----------|-----|-------|
| 1 | Keyboard input setup | click_handler.py | setup_keyboard_input() | SETUP | Green |
| 2 | Raw stdin mode set | click_handler.py | set_raw_stdin() | RAW_STDIN | Blue |
| 3 | Terminal restored | click_handler.py | restore_terminal() | RESTORE | Blue |
| 4 | Keypress received | click_handler.py | read_keypress() | KEYPRESS | Cyan |
| 5 | Digit key parsed | click_handler.py | parse_digit_key() | DIGIT_KEY | Green |
| 6 | Agent lookup by index | click_handler.py | get_agent_by_index() | AGENT_LOOKUP | Blue |

---

### 10_long_outputs.log (4 events)

| # | Event | Module | Function | Tag | Color |
|---|-------|--------|----------|-----|-------|
| 1 | Long output detected | formatter.py | log_long_output() | LONG_OUTPUT | Red |
| 2 | Content preview logged | formatter.py | log_long_output() | PREVIEW | White |
| 3 | Full content logged | formatter.py | log_long_output() | FULL_CONTENT | White |
| 4 | Separator logged | formatter.py | log_long_output() | SEPARATOR | White |

---

## Quick Reference Table

| Log File | Events | Primary Module | Frequency | Key Tags |
|----------|--------|----------------|-----------|----------|
| 01_startup.log | 12 | workflow.py | Startup-only | MAIN_ENTRY, TMUX_CREATE, SESS_NAME |
| 02_initialization.log | 5 | monitor.py | Startup-only | RUN_MONITOR, INIT_SESS, UI_MODE |
| 03_session_discovery.log | 11 | session_finder.py | On changes only | PROJ_DIRS, ACTIVE_SESS, TOTAL_JSONL |
| 04_file_reading.log | 5 | jsonl_parser.py, monitor.py | On new data only | FILE_READ, NEW_SESS, SESS_REMOVED |
| 05_jsonl_parsing.log | 6 | jsonl_parser.py, monitor.py | On new data only | LINES_READ, JSON_ERROR, PARSE_DONE |
| 06_tool_extraction.log | 8 | jsonl_parser.py, monitor.py | On tool calls only | TOOL_CACHED, TOOL_MATCH, TOOL_ORPHAN |
| 07_display_routing.log | 9 | monitor.py | On changes only | MON_SESS, TASK_REQ, SUB_DISPLAY |
| 08_ui_rendering.log | 10 | monitor.py, subagent_ui.py | On changes only (UI mode) | UI_RENDER, RENDER_LIST, ENTRIES_BUILT |
| 09_input_handling.log | 6 | click_handler.py | On keypresses (UI mode) | KEYPRESS, DIGIT_KEY, AGENT_LOOKUP |
| 10_long_outputs.log | 4 | formatter.py | On long outputs only | LONG_OUTPUT, PREVIEW, FULL_CONTENT |

**Total: 76 events across 10 workflow phases**
