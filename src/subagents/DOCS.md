# src/subagents/

Subagents pane subpackage. Tracks active Claude Code subagent sessions, renders per-agent tool call
lists and cache-tracker views in an interactive TUI pane.

## subagent_ui_format.py

**Purpose:** Entry formatting helpers for individual subagent entries.
**Input:** Agent metadata dicts, tool call dicts, input data dicts.
**Output:** Formatted terminal strings for collapsed/expanded entries, tool call summary lines,
display names.

Contains:
- `build_collapsed_entry(index, metadata, is_expanded)` — renders the one-line agent header with
  toggle symbol, index, name, agent_id, timestamp
- `build_expanded_entry(index, metadata, tool_calls)` — renders header + tool call summary lines
- `format_tool_call_summary(tool_call)` — MCP tools: short name + input preview; non-MCP: name +
  char count
- `get_agent_display_name(subagent_type, agent_id)` — converts subagent_type to Title Case or falls
  back to agent_id
- `count_calls_for_agent(tool_calls)` — returns len(tool_calls)
- `format_char_count`, `get_input_preview`, `format_subagent_name` — formatting utilities

## subagent_ui.py

**Purpose:** Subagent list state and rendering.
**Input:** `subagent_metadata` dict (agent_id → metadata) + `tool_calls_by_agent` dict from
monitor.py global state.
**Output:** Formatted terminal string for the full subagent list; mutable `subagent_states` dict
(expanded/collapsed per agent).

Contains:
- `subagent_states` — module-level dict: `{agent_id: bool}`. Shared with `subagent_render.py`,
  `subagent_pane.py`, and `ui_mode.py` via direct import.
- `render_subagent_list(...)` — orchestrator: builds header + all entries, applies hover highlight
  and scroll viewport
- `toggle_subagent_state(agent_id)` — flips `subagent_states[agent_id]`
- `build_all_entries`, `build_list_header`, `combine_sections` — rendering helpers

## subagent_render.py

**Purpose:** Renders subagent list with per-agent cache-tracker turns (token view for expanded
agents).
**Input:** `subagent_metadata_map`, `turns_by_agent` (from `extract_cache_turns`), pane dimensions,
scroll/expand state dicts.
**Output:** Formatted terminal string with ANSI escape codes; populates `pane_line_map` and
`cache_line_map` for click handling.

Contains:
- `render_subagents_with_tokens(...)` — main rendering function used by `subagent_pane.py`;
  delegates cache-tracker output to `token_format.format_cache_tracker()`

## subagent_pane.py

**Purpose:** Subagents pane event loop — keyboard/mouse input, JSONL data refresh, screen rendering.
**Input:** `_monitor.subagent_metadata` + `_monitor.subagent_metadata` global state; active session
JSONL files for cache turn extraction.
**Output:** Writes formatted subagents pane to stdout in a continuous loop.

**Event loop** (`run_subagents_loop()`):
1. Read keyboard/mouse input: click to expand/collapse agent, scroll within expanded agent, digit
   keys 1-9, 'f' to freeze
2. Data refresh every `POLL_INTERVAL` seconds: `_monitor.monitor_sessions()` (suppressed stdout) →
   per-agent `extract_cache_turns()` from JSONL
3. Session change detection: clears all state, reloads historical subagents via
   `_monitor.load_historical_subagents()`
4. Re-render via `render_subagents_with_tokens()` only when output changed

**Note:** `run_subagents_loop` is defined here but not currently wired to a `--mode` flag in
`workflow.py`. The subagent tracking visible in the main pane runs via `ui_mode.track_subagent_metadata()`
which is called from `monitor_session.py`.
