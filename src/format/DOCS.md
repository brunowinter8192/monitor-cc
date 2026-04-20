# src/format/

Formatting functions — ANSI-colored terminal strings for tool calls, events, and token/cache display.

## formatter.py

**Purpose:** Format tool call request/response pairs as ANSI-colored terminal strings for the main streaming pane. Handles output truncation, todo list rendering, parameter formatting, and status icons/colors.

**Input:** Tool call dicts (name, input params, output string, tool_use_id, timestamp, call number, subagent flag, error flag, system_reminders list).

**Output:** Formatted ANSI-colored strings for stdout.

**Called by:** `core/monitor_display.py` via `format_tool_call()`.

---

## formatter_events.py

**Purpose:** Format non-tool-call events — user prompts, hook annotations, system messages, media items, skill activations, and thinking blocks — as ANSI-colored terminal strings.

**Input:** Timestamps, text content, hook output/script strings, media item lists, skill item dicts, thinking item dicts.

**Output:** Formatted ANSI-colored strings for stdout.

**Called by:** `core/monitor_display.py` via `format_user_prompt()`, `format_user_media()`, `format_thinking()`, `format_skill_activation()`, `format_system_message()`.

---

## token_format.py

**Purpose:** Render the token/cache tracker pane — groups API calls into turns with CR/CC/D counts and formats an interactive expand/collapse/scroll/hover view.

**Input:** Cache turn lists, expand state dicts, line map dicts, hover row, pane dimensions, scroll offset.

**Output:** ANSI-colored screen string for the token pane (written directly to stdout by `panes/token_pane.py`).

**Called by:** `panes/token_pane.py` via `format_cache_tracker()`; `workers/worker_format.py`, `metadata/metadata_format.py`, `proxy_display/format.py` via `_format_k()`; `subagents/subagent_render.py` via `format_cache_tracker()`.
