# src/input/

Keyboard and mouse input handling, and interactive UI state management.

## click_handler.py

**Purpose:** Low-level stdin handling for keyboard and SGR mouse input. Sets terminal to raw mode, reads unbuffered keypresses and multi-byte mouse sequences, and provides enable/disable helpers for SGR mouse tracking modes 1003+1006 (Any Event Tracking incl. motion).

**Input:** Stdin file descriptor in raw mode. Single-byte keypresses and `\033[<b;col;rowM/m` SGR mouse sequences.

**Output:** Parsed results: digit keypresses as `int` via `parse_digit_key()`; mouse events as `(button, col, row)` tuple via `read_mouse_event()`; agent IDs via `get_agent_by_index()`. Side effects: terminal mode changes via `setup_keyboard_input()` / `restore_terminal()`.

**Called by:** All interactive pane loops — `panes/token_pane.py`, `panes/rules_pane.py`, `panes/warnings_pane.py`, `panes/waste_pane.py`, `hooks/hooks_pane.py`, `workers/worker_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`, `subagents/subagent_pane.py`.

---

## ui_mode.py

**Purpose:** UI state tracking and shared rendering helpers used across multiple panes. Tracks subagent metadata (agent-to-task/type mapping) from tool call events. Renders the active rules block with expand/collapse, hover highlight, and scroll.

**Input:** Tool call dicts, subagent metadata dicts, agent maps, active rules dicts, expand/line-map/hover/scroll state.

**Output:** Side effects on shared state dicts (subagent metadata, agent maps). Returns formatted ANSI rules block string + updated line map via `format_rules_block()`.

**Called by:** `core/monitor_session.py` via `track_subagent_metadata()`; `panes/rules_pane.py` via `format_rules_block()` (lazy import).
