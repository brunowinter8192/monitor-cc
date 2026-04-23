# src/core/

## Role

Session discovery, polling loop, and terminal output for the main monitoring pane. This is the heartbeat of the monitor: `monitor.py` discovers JSONL files, drives the streaming loop, and dispatches each tool call through `monitor_session.py` for classification and routing to `monitor_display.py` for output. Touch this package when changing polling behaviour, session scoping, tool call classification, or main-pane display logic. Do NOT touch it to change pane-specific rendering — that lives in `panes/`, `format/`, or the dedicated pane packages.

## Public Interface

```python
from src.core import run_monitor                  # main entry — called by workflow.py
from src.core import process_session_file         # per-session JSONL processing
from src.core import get_file_end_position        # init file position at EOF
from src.core import get_initial_position         # position for new session
from src.core import load_historical_main         # replay main session on startup
from src.core import display_tool_call            # print formatted tool call to stdout
from src.core import display_warning              # print malformed-JSON warning
from src.core import display_user_media           # print media items
from src.core import display_skill_activation     # print skill activation event
from src.core import display_thinking             # print thinking block
from src.core import display_user_prompt_from_jsonl
from src.core import display_system_message
from src.core import print_session_status         # startup session-count line
```

## Flow

```
workflow.py → run_monitor(project_filter, mode)
  → initialize_file_positions()           # scan ~/.claude/projects, set EOF positions
  → [mode dispatch] → pane loop OR run_streaming_loop()
  → run_streaming_loop():
      loop: monitor_sessions() → process_all_sessions(sessions)
              → process_session_file(path) → parse_new_tool_calls()
              → classify (task/subagent/tool) → display_*(...)
```

## Modules

### monitor.py (263 LOC)

**Purpose:** Polling orchestrator — discovers sessions, drives the streaming loop, dispatches to pane event loops by mode, and owns all shared state dicts. In `run_main_loop()`, also scans proxy JSONL each poll cycle via `_refresh_strip_cache()` to feed strip data into `monitor_display`.
**Reads:** `~/.claude/projects/**/*.jsonl` via `session_finder`; hook log position via `hooks`; proxy JSONL via `proxy_display.parser` (for strip cache); lazy reads from `panes`, `workers`, `hooks`, `proxy_display`, `metadata`.
**Writes:** stdout (via `monitor_display`); mutates shared state (`file_positions`, `tool_use_caches`, `agent_to_task`, `agent_to_type`, `buffered_subagent_calls`, `call_counter`, `_strip_proxy_position`).
**Called by:** `workflow.py` (top-level entry).
**Calls out:** `session_finder`, `jsonl`, `hooks` (top-level); lazy: `panes`, `workers`, `proxy_display`, `metadata`.

---

### monitor_session.py (146 LOC)

**Purpose:** Per-session JSONL processor — reads new lines, classifies tool calls as task requests/responses, subagent calls, or regular tools, and routes each to the appropriate handler.
**Reads:** Session JSONL files (incremental, via file positions in `monitor.py` state); shared state from `monitor.py`.
**Writes:** Mutates `monitor.call_counter`, `monitor.agent_to_task`, `monitor.agent_to_type`, `monitor.buffered_subagent_calls`; calls `monitor_display` for output.
**Called by:** `monitor.py` via `process_all_sessions()` → `process_session_file()`; also `load_historical_main()` on startup.
**Calls out:** `jsonl`, `panes` (track_unknown_type).

---

### monitor_display.py (202 LOC)

**Purpose:** Terminal output + event buffer for the main streaming pane. Buffers all events (tool calls, user prompts, system messages, etc.) in `main_event_buffer`. On each render cycle, applies proxy strip highlights: tool_call output is replaced with pre-strip content and `highlight_stripped()` is applied; user prompts get a `[~]` badge when the corresponding proxy request had stripped content. `ingest_proxy_strip_data(entries)` updates the strip caches; called from `monitor._refresh_strip_cache()`. `render_main_buffer` fills `main_line_map` (phys_row→event_idx) and reads `main_hover_row` for highlight; `serialize_main_event(event_idx)` converts a buffer entry to clipboard text for the `y`-hotkey.
**Reads:** Tool call dicts, event dicts passed as arguments; module-level `_strip_by_tool_id`, `_strip_prompt_ts_set`, `main_hover_row`.
**Writes:** stdout via `print()` (via `render_main_buffer`); mutates `main_event_buffer`, `main_scroll_offset`, `main_hover_row`, `main_line_map`, `_strip_by_tool_id`, `_strip_prompt_ts_set`.
**Called by:** `monitor.py` (`print_session_status`, `ingest_proxy_strip_data`, `render_main_buffer`, `serialize_main_event`); `monitor_session.py` (all display functions).
**Calls out:** `format.formatter`, `format.formatter_events`, `format.strip_marker`.

---

## State

`monitor.py` owns all module-level state. Key variables:

| Variable | Type | Mutated by |
|---|---|---|
| `file_positions` | `Dict[Path, int]` | `monitor_session` via `update_session_tracking` |
| `call_counter` | `int` | `monitor_session.process_session_file` |
| `agent_to_task` / `agent_to_type` | `Dict[str, str]` | `monitor_session.handle_task_request` |
| `buffered_subagent_calls` | `Dict[str, List]` | `monitor_session.handle_subagent_call` |
| `active_project_filter` | `str \| None` | `run_monitor()` on startup |
| `hook_log_position` | `int` | `initialize_hook_log_position()` + `panes.process_hook_log` |
| `_strip_proxy_position` | `int` | `_refresh_strip_cache()` each poll cycle |

`monitor_display.py` owns main-pane render state:

| Variable | Type | Mutated by |
|---|---|---|
| `main_event_buffer` | `list` | `_buffer_append` (via all `display_*` fns) |
| `main_scroll_offset` | `int` | `run_main_loop` (wheel events) |
| `main_hover_row` | `int \| None` | `run_main_loop` (mouse motion events) |
| `main_line_map` | `Dict[int, int]` | `render_main_buffer` each render cycle |

All pane modules read monitor.py state via `from ..core import monitor as _monitor`.

## Gotchas

- `monitor_session.py` lazy-imports `monitor` (`from . import monitor as _monitor`) to avoid circular import at module level — both live in the same package so `.` is correct.
- Session scoping: `_get_session_start_ts()` reads the newest main session JSONL and subtracts 60s as the cutoff. Changing this affects what history gets replayed on startup.
- `is_agent_file()` in `monitor.py` filters out subagent JSONLs by path pattern — logic must stay in sync with `session_finder.py` which indexes them.
