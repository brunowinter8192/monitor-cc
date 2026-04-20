# src/format/

## Role

ANSI-colored string rendering — tool call pairs, user events, and the token/cache tracker pane. This package has no side effects: every function takes data in and returns a formatted string. Touch this package to change how tool calls look, how events are formatted, or how the cache tracker renders. Do NOT add I/O, state, or pane loop logic here.

## Public Interface

```python
# Tool call formatting (formatter.py)
from src.format import format_tool_call
from src.format import format_request, format_response, combine_request_response
from src.format import format_todo_list, format_parameters, format_task_parameters
from src.format import format_output, format_error_output, format_system_reminders
from src.format import format_value, get_status_icon, get_status_color, shorten_tool_name

# Event formatting (formatter_events.py)
from src.format import format_user_prompt, format_hook_annotation, format_system_message
from src.format import format_user_media, format_skill_activation, format_thinking

# Cache tracker rendering (token_format.py)
from src.format import format_cache_tracker
from src.format import _format_k          # compact "Xk" token count — used by workers/metadata/proxy_display
```

## Modules

### formatter.py (174 LOC)

**Purpose:** Format tool call request/response pairs as ANSI-colored terminal strings. Handles output truncation, todo list rendering, parameter formatting, and status icons/colors.
**Reads:** Tool call dicts passed as arguments. No shared state, no file I/O.
**Writes:** Returns formatted strings. No stdout, no file writes.
**Called by:** `core/monitor_display.py` (`format_tool_call`).
**Calls out:** nothing (only `utils`, `constants`).

---

### formatter_events.py (72 LOC)

**Purpose:** Format non-tool-call events — user prompts, hook annotations, system messages, media items, skill activations, thinking blocks — as ANSI-colored strings.
**Reads:** Timestamps, text, hook output/script strings, item dicts passed as arguments.
**Writes:** Returns formatted strings. No stdout, no file writes.
**Called by:** `core/monitor_display.py` (`format_user_prompt`, `format_user_media`, `format_thinking`, `format_skill_activation`, `format_system_message`).
**Calls out:** nothing (only `utils`, `constants`).

---

### token_format.py (204 LOC)

**Purpose:** Render the token/cache tracker view — groups API calls into turns with CR/CC/D counts, handles expand/collapse, hover highlight, scroll, and viewport clipping. Also provides `_format_k` for compact token counts.
**Reads:** Cache turn lists, expand state dicts, pane dimensions, scroll offset — all passed as arguments.
**Writes:** Returns ANSI screen string. No stdout, no file writes.
**Called by:** `panes/token_pane.py` (`format_cache_tracker`); `workers/worker_format.py`, `metadata/metadata_format.py`, `proxy_display/format.py` (`_format_k`).
**Calls out:** `format.formatter` (lazy, `shorten_tool_name` for tool name abbreviation in cache rows).

## Gotchas

- `token_format.py` lazy-imports `formatter.shorten_tool_name` inside `_format_cache_call()` — both are in the same package so the import is `from .formatter import shorten_tool_name`. Do NOT change to `..formatter`.
- `_format_k` and `_format_cache_call` use leading underscores but are exported and used by 4 external callers — they are effectively public despite the naming convention.
