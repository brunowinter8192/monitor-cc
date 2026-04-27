# src/format/

## Role

ANSI-colored string rendering — tool call pairs, user events, and the token/cache tracker pane. This package has no side effects: every function takes data in and returns a formatted string. Touch this package to change how tool calls look, how events are formatted, or how the cache tracker renders. Do NOT add I/O, state, or pane loop logic here.

## Public Interface

```python
# Strip highlighting (strip_marker.py)
from src.format.strip_marker import highlight_stripped        # inline DIM_YELLOW_BG chunk highlight
from src.format.strip_marker import get_stripped_data         # (pre_strip_text, chunks) from proxy entry
from src.format.strip_marker import build_tool_result_strip_lookup  # for waste_pane (raw events)
from src.format.strip_marker import build_tool_id_strip_lookup      # for main-pane (parsed entries)

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

### strip_marker.py (85 LOC)

**Purpose:** Proxy-strip content highlighting helper — `highlight_stripped` wraps found chunks in `DIM_YELLOW_BG`/`SOFT_RESET` inline; `get_stripped_data` extracts pre-strip text + removed chunks from a proxy entry for a given message index; `build_tool_result_strip_lookup` / `build_tool_id_strip_lookup` build `tool_use_id → (pre_strip_text, chunks)` maps for waste_pane and main-pane respectively.
**Reads:** Proxy entry dicts passed as arguments. No I/O, no shared state.
**Writes:** Returns strings / dicts. No stdout, no file writes.
**Called by:** `panes.warnings_pane`, `panes.waste_pane`, `core.monitor_display`.
**Calls out:** `constants` only.

---

### formatter.py (176 LOC)

**Purpose:** Format tool call request/response pairs as ANSI-colored terminal strings. Handles output truncation, todo list rendering, parameter formatting, and status icons/colors.
**Reads:** Tool call dicts passed as arguments. No shared state, no file I/O.
**Writes:** Returns formatted strings. No stdout, no file writes.
**Called by:** `core/monitor_display.py` (`format_tool_call`).
**Calls out:** nothing (only `utils`, `constants`).

---

### formatter_events.py (73 LOC)

**Purpose:** Format non-tool-call events — user prompts, hook annotations, system messages, media items, skill activations, thinking blocks — as ANSI-colored strings. `format_user_prompt` accepts `strip_badge=True` to append a `DIM_YELLOW_BG [~]` marker when the corresponding proxy request had stripped content.
**Reads:** Timestamps, text, hook output/script strings, item dicts passed as arguments.
**Writes:** Returns formatted strings. No stdout, no file writes.
**Called by:** `core/monitor_display.py` (`format_user_prompt`, `format_user_media`, `format_thinking`, `format_skill_activation`, `format_system_message`).
**Calls out:** nothing (only `utils`, `constants`).

---

### token_format.py (156 LOC)

**Purpose:** Build logical lines for the token/cache tracker — groups API calls into turns with CR/CC/D counts, handles expand/collapse and viewport clipping. Returns a 5-tuple `(visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count)`. The fifth element `initial_parent_count` is the number of collapsed parent rows before the current viewport — used by `token_pane.py` to keep expand/collapse key assignments stable across scrolls. Does NOT render (no zebra, no hover, no truncation) — that is `token_pane.py`'s job. Also provides `_format_k` for compact token counts.
**Reads:** Cache turn lists, expand state dicts, pane dimensions, scroll offset — all passed as arguments.
**Writes:** Returns 5-tuple. No stdout, no file writes.
**Called by:** `panes/token_pane.py` (`format_cache_tracker`); `workers/worker_format.py` (`format_cache_tracker`, `_format_k`); `metadata/metadata_format.py`, `proxy_display/format.py` (`_format_k`).
**Calls out:** `format.formatter` (lazy, `shorten_tool_name` for tool name abbreviation in cache rows).

## Gotchas

- `highlight_stripped` wraps each **line** of a chunk individually (`DIM_YELLOW_BG{line}SOFT_RESET` per `\n`-separated segment) rather than wrapping the whole chunk as a single unit. Downstream renderers (`warnings_pane`, `waste_pane`) split the result on `\n` and apply a per-line zebra BG; a single wrap around the whole chunk would leave lines 2..N without `DIM_YELLOW_BG`, causing the zebra selector to miss them. `outer_bg` is appended once after the final highlighted line to restore the caller's row background.
- `token_format.py` lazy-imports `formatter.shorten_tool_name` inside `format_cache_tracker()` — both are in the same package so the import is `from .formatter import shorten_tool_name`. Do NOT change to `..formatter`.
- `_format_k` and `_format_cache_call` use leading underscores but are exported and used by 4 external callers — they are effectively public despite the naming convention.
- `format_cache_tracker` returns a **5-tuple** `(visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count)` — NOT a string. The render loop (zebra/hover/truncation) lives in `token_pane.py`. `initial_parent_count` counts collapsed parent rows before the viewport start; callers that don't need it unpack with `_, _, _, _, _`.
- Line content uses `SOFT_RESET` (`\033[39m`) instead of `RESET` (`\033[0m`) for inline FG-color endings. This lets the render loop inject a row-level BG without it being killed mid-line. Exception: `_format_cache_call` keeps `RESET` for `cc_broken` rows (error-BG ends at the line terminator, not mid-content).
