# src/core/

Core monitoring loop — session discovery, JSONL processing, tool call routing, and terminal output.

## monitor.py

**Purpose:** Entry point and orchestrator for the monitoring loop. Discovers active Claude Code sessions, dispatches to pane-specific event loops (tokens, rules, warnings, hooks, workers, proxy, metadata, waste), or runs the streaming main loop.

**Input:** `project_filter` (optional path), `mode` (all/main/subagent/rules/warnings/hooks/tokens/workers/proxy/metadata/waste), `ui` (bool). Shared module-level state: `file_positions`, `tool_use_caches`, `call_counter`, `agent_to_task`, `agent_to_type`, `buffered_subagent_calls`, `task_requests_seen`, `active_project_filter`, `active_mode`, `hook_log_position`.

**Output:** Dispatches to pane loops (no return value) or runs `run_streaming_loop()` which continuously polls sessions and writes formatted tool calls to stdout.

**Called by:** `workflow.py` via `run_monitor()`. All pane modules read shared state via `from ..core import monitor as _monitor`.

---

## monitor_session.py

**Purpose:** Per-session JSONL processing. Reads new lines from a session file, extracts tool calls, classifies them (task request/response, subagent call, regular tool), and dispatches to display functions. Also handles historical loading of past sessions on startup.

**Input:** Session JSONL file paths. Shared state from `monitor.py` (file positions, agent maps, call counter, buffered calls). Tool call dicts from `jsonl.parse_new_tool_calls`.

**Output:** Side effects: increments `call_counter`, populates `agent_to_task` / `agent_to_type`, buffers subagent calls. Delegates display output to `monitor_display.py`.

**Called by:** `monitor.py` via `process_all_sessions()` → `process_session_file()`. Also `load_historical_main()` / `load_historical_subagents()` on startup.

---

## monitor_display.py

**Purpose:** Terminal output functions for the main streaming pane. Formats and prints tool calls, user prompts, thinking blocks, skill activations, system messages, warnings, and session status lines to stdout.

**Input:** Tool call dicts, prompt items, media items, thinking items, warning dicts, session count and filter strings.

**Output:** ANSI-colored strings written to stdout via `print()`.

**Called by:** `monitor_session.py` for per-tool-call output; `monitor.py` via `print_session_status()` on startup of the main streaming loop.
