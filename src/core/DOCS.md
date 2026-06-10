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
  → [mode dispatch] → pane loop OR run_main_loop()
  → run_main_loop():
      loop: monitor_sessions() → process_all_sessions(sessions)
              → process_session_file(path) → parse_new_tool_calls()
              → classify (task/subagent/tool) → display_*(...)
              → render_main_buffer()      # flush buffer to stdout
```

Buffer: `monitor_display._buffer_append()` appends each event to `main_event_buffer`; when the buffer exceeds `MAIN_EVENT_BUFFER_CAP` (from `constants.py`), the oldest entries are deleted to keep the buffer bounded.

## Modules

### monitor.py (356 LOC)

**Purpose:** Polling orchestrator — discovers sessions, drives the streaming loop, dispatches to pane event loops by mode, and owns all shared state dicts. `run_main_loop()` runs a 24h log janitor (via `log_janitor.cleanup_old_jsonl`) for sweep-eligible logs (`hook_firing.jsonl`, `api_errors.jsonl`, `polling_state.jsonl`). Mouse-event handler now has three branches for `button == 0` (left-click): row 1 (search-bar text-area focuses, `[←]`/`[→]` arrow regions navigate matches), row ≥ 2 (⎘ copy-button hit on tool_call REQUEST/RESPONSE headers via `_main_copy_rows` lookup). `read_mouse_event` returns `(-1,-1,-1)` sentinel for SGR release events — handled as no-op in a dedicated `event[0] != -1` branch BEFORE the bare-ESC handler so releases don't trigger search-cancel. Keyboard input has search-focus branch (Enter commits matches + calls `ensure_match_visible`; Esc clears query/matches/focus; Backspace edits; printable chars append while focused — y-hotkey only reachable when not focused). `run_main_loop()` decomposed (C2): 6 private helpers `_main_ram_state`, `_handle_main_mouse`, `_handle_main_search_cancel`, `_handle_main_search_input`, `_refresh_main_data`, `_build_main_output`.
**Reads:** `~/.claude/projects/**/*.jsonl` via `session_finder`; lazy reads from `panes`, `workers`, `proxy_display`; module-level `monitor_display._main_copy_rows`, `_main_pane_width`, `_search_focused`, `_search_query`, `_search_matches`.
**Writes:** stdout (via `monitor_display`); mutates shared state (`file_positions`, `tool_use_caches`, `agent_to_task`, `agent_to_type`, `buffered_subagent_calls`, `call_counter`); mutates `monitor_display._search_*` state via Enter/Esc/Backspace/printable handlers; mutates `monitor_display._main_copy_feedback_until` on click.
**Called by:** `workflow.py` (top-level entry).
**Calls out:** `session_finder`, `jsonl`; lazy: `panes`, `workers`, `proxy_display`, `input.click_handler` (copy_to_clipboard, read_mouse_event with sentinel-aware return).

---

### monitor_session.py (146 LOC)

**Purpose:** Per-session JSONL processor — reads new lines, classifies tool calls as task requests/responses, subagent calls, or regular tools, and routes each to the appropriate handler.
**Reads:** Session JSONL files (incremental, via file positions in `monitor.py` state); shared state from `monitor.py`.
**Writes:** Mutates `monitor.call_counter`, `monitor.agent_to_task`, `monitor.agent_to_type`, `monitor.buffered_subagent_calls`; calls `monitor_display` for output.
**Called by:** `monitor.py` via `process_all_sessions()` → `process_session_file()`; also `load_historical_main()` on startup.
**Calls out:** `jsonl`, `monitor_display`.

---

### monitor_display.py (391 LOC)

**Purpose:** Terminal output + event buffer for the main streaming pane. Buffers all events (tool calls, user prompts, system messages, etc.) in `main_event_buffer`. On each render cycle: applies proxy strip highlights (tool_call output replaced with pre-strip content + `highlight_stripped()`; user prompts get `[~]` badge); renders the persistent search bar on row 1; injects ⎘ copy-buttons on REQUEST and RESPONSE header lines of tool_calls with click-region tracking via `_main_copy_rows: dict[phys_row → (event_idx, 'request'|'response')]`; applies per-line substring highlight for search matches via `_highlight_query_in_line` (ANSI-safe split-and-inject pattern from `highlight_stripped`); buffer renders from row 2 (row 1 reserved for search bar). `serialize_main_event(event_idx, part='all'|'request'|'response')` converts a buffer entry to clipboard text for the y-hotkey ('all') or ⎘ click ('request' / 'response').

**Search infrastructure:**
- `_search_query` typed text, `_search_focused` keyboard-input gate, `_search_committed` (matches only displayed after Enter — typing alone doesn't trigger search).
- `_compute_search_matches(query)` case-insensitive substring match on serialized event text (untruncated, including bash output beyond render-truncation).
- `_compute_match_line_offsets(query, matches)` returns event_idx → first rendered-line-offset where query appears (for scroll-to-match-line, not just scroll-to-event-start).
- `ensure_match_visible()` scrolls so current match's line is visible (2 lines context above).
- `_render_search_bar(pane_width)` renders row-1 bar: `Search: <query>_  N/M [←] [→]` with focus-aware cursor, click-region detection via fixed-geometry right-aligned arrows.

**ANSI-safe BG handling:** render loop ends each line with `\033[49m\033[K{RESET}` — the explicit `\033[49m` (BG-reset only) before `\033[K` (erase-to-EOL) ensures the search-match BG can't bleed across the rest of the row even if `truncate_visible` cut the line mid-highlight before reaching the per-chunk `\033[49m` injected by `_highlight_query_in_line`.

**Reads:** Tool call dicts, event dicts passed as arguments; module-level `_strip_by_tool_id`, `_strip_prompt_ts_set`, `main_hover_row`, `_search_*` state, `_main_copy_rows`, `_main_copy_feedback_until`, `_main_pane_width`, `_search_all_line_offsets`, `_search_match_line_offsets`, `_search_total_lines`.
**Writes:** stdout via `print()` (via `render_main_buffer`); mutates `main_event_buffer`, `main_scroll_offset`, `main_hover_row`, `main_line_map`, `_strip_by_tool_id`, `_strip_prompt_ts_set`, `_main_copy_rows`, `_main_copy_feedback_until` (expiry cleanup), `_main_pane_width`, `_search_all_line_offsets`, `_search_total_lines`, `_search_current_idx` (clamp on buffer shrink).
**Called by:** `monitor.py` (`print_session_status`, `ingest_proxy_strip_data`, `render_main_buffer`, `serialize_main_event`, `ensure_match_visible`, `_compute_search_matches`, `_compute_match_line_offsets`, `_count_buffer_lines`); `monitor_session.py` (all display functions).
**Calls out:** `format.formatter`, `format.formatter_events`, `format.strip_marker`, `utils` (`truncate_visible`, `_ANSI_ESCAPE_RE`, `_cell_width`).

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
| `_strip_proxy_position` | `int` | `_refresh_strip_cache()` each poll cycle |

`monitor_display.py` owns main-pane render state:

| Variable | Type | Mutated by |
|---|---|---|
| `main_event_buffer` | `list` | `_buffer_append` (via all `display_*` fns) |
| `main_scroll_offset` | `int` | `run_main_loop` (wheel events), `ensure_match_visible` |
| `main_hover_row` | `int \| None` | `run_main_loop` (mouse motion events) |
| `main_line_map` | `Dict[int, int]` | `render_main_buffer` each render cycle |
| `_main_copy_rows` | `Dict[int, Tuple[int,str]]` | `render_main_buffer` (phys_row → (event_idx, 'request'\|'response')) |
| `_main_copy_feedback_until` | `Dict[Tuple[int,str], float]` | `run_main_loop` click handler (set ✓-flash expiry), cleanup loop (prune expired) |
| `_main_pane_width` | `int` | `render_main_buffer` (start of cycle, snapshot for click handler) |
| `_search_query` | `str` | `run_main_loop` keyboard handler (printable/backspace/Esc) |
| `_search_focused` | `bool` | `run_main_loop` (search-bar text-area click ON, buffer-area click no longer toggles, Enter/Esc OFF) |
| `_search_committed` | `bool` | `run_main_loop` (Enter sets True, edits set False) |
| `_search_matches` | `List[int]` | `run_main_loop` Enter handler (calls `_compute_search_matches`), edits clear to `[]` |
| `_search_match_set` | `set[int]` | `run_main_loop` Enter handler, edits clear |
| `_search_current_idx` | `int` | `run_main_loop` (Enter resets to 0, ←/→ arrows step), `render_main_buffer` (clamp on buffer shrink) |
| `_search_cached_query` | `str` | Enter handler — last committed query, avoids redundant `_compute_search_matches` |
| `_search_match_line_offsets` | `Dict[int, int]` | Enter handler (`_compute_match_line_offsets`) — event_idx → first line within event containing query |
| `_search_all_line_offsets` | `Dict[int, int]` | `render_main_buffer` (event_idx → first line offset in `all_lines`, used by `ensure_match_visible`) |
| `_search_total_lines` | `int` | `render_main_buffer` (len of all_lines, used by `ensure_match_visible`) |

All pane modules read monitor.py state via `from ..core import monitor as _monitor`.

## Gotchas

- `monitor_session.py` lazy-imports `monitor` (`from . import monitor as _monitor`) to avoid circular import at module level — both live in the same package so `.` is correct.
- Session scoping: `_get_session_start_ts()` reads the newest main session JSONL and subtracts 60s as the cutoff. Changing this affects what history gets replayed on startup.
- `is_agent_file()` in `monitor.py` filters out subagent JSONLs by path pattern — logic must stay in sync with `session_finder.py` which indexes them.
