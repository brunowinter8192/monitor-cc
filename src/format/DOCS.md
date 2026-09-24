# src/format/

## Role

ANSI-colored string rendering for the tokens/cache-tracker pane, plus a shared proxy-strip
highlight helper reused by the warnings pane. This package has no side effects: every function
takes data in and returns a formatted string. Touch this package to change how the cache tracker
renders. Do NOT add I/O, shared state, or pane loop logic here.

## Public Interface

```python
from src.format.strip_marker import highlight_stripped   # inline DIM_YELLOW_BG chunk highlight

from src.format import format_cache_tracker
from src.format import _format_k          # compact "Xk" token count — used by workers/proxy_display
from src.format import shorten_tool_name  # mcp__plugin__tool → tool
```

## Modules

### strip_marker.py (20 LOC)

**Purpose:** `highlight_stripped(text, stripped_chunks, outer_bg='')` wraps each found chunk (line by line) in `DIM_YELLOW_BG`/`SOFT_RESET`.
**Reads:** chunk strings passed as arguments. No I/O, no shared state.
**Writes:** returns strings. No stdout, no file writes.
**Called by:** `panes/warnings_render.py`.
**Calls out:** none.

---

### token_format.py (359 LOC)

**Purpose:** `format_cache_tracker(turns, ...)` builds logical lines for the tokens/cache-tracker pane — groups API calls into turns with CR/CC/D counts, handles expand/collapse, embeds search-match markers, and computes the scroll viewport. Returns a 5-tuple `(visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count)`. `expand_states` and the keyword-only `turn_cache` (owned by the calling pane, created by `turn_cache.new_turn_cache`) are required; each turn's rendered lines are computed once and reused. Does NOT render zebra/hover/truncation — that is the caller's own row loop (`token_pane.py`, `worker_format.py`). Also provides `_format_k` (compact token counts), `shorten_tool_name` (`mcp__plugin__tool` → `tool`), and the one REQ counter: `call_numbers(turns)` (per-turn lists of running numbers, used by the renderer and by `panes/token_search.py`) with `request_numbers_by_id(turns)` (request_id -> number) built on it for `proxy_display`. Every turn header and REQ row carries its time of day right-aligned via `utils.right_align_time` (turn: turn timestamp; REQ: `call['timestamp']`); `request_times_by_id(turns)` (request_id -> `HH:MM:SS`) serves `proxy_display`.
**Reads:** cache-turn lists, expand-state dicts, pane dimensions, scroll offset, optional `response_rid_map`/`copy_feedback`/`search_match_set`/`search_current_key`/`search_query`/`nav_out` — all passed as arguments. `response_rid_map` values are full `_response` dual-log entries (`{headers, cc_requested_model, proxy_forwarded_model, answering_model, ...}`), keyed by `request_id` — `_render_rate_limit_lines` reads `entry['headers']`, `_render_answering_model_line` reads `entry['proxy_forwarded_model']`/`entry['answering_model']` and colors the expanded `model:` line RED when they differ (DIM otherwise; nothing rendered when `answering_model` is empty).
**Writes:** returns the 5-tuple; mutates `nav_out` in place when given (cleared then rewritten with `{key: absolute_line_idx, ..., 'total_lines': N}`). No stdout, no file writes.
**Called by:** `panes/token_pane.py`, `workers/worker_tokens_pane.py`, `panes/token_search.py` (reuses `_format_turn_header_line`, `_format_cache_call`, `_call_thinking_meta`, `_render_expanded_call_lines` directly, so a search match can never diverge from what this module actually renders), `workers/worker_format.py`, `workers/worker_render.py`, `proxy_display/format.py` (`_format_k`, `_format_turn_header_line`, `request_numbers_by_id`, `request_times_by_id`), `panes/token_search.py` (`call_numbers`).
**Calls out:** none.

---

## Gotchas

- `highlight_stripped` wraps each **line** of a chunk individually rather than the whole chunk as one unit — a downstream renderer that splits the result on `\n` and applies a per-line zebra background needs every line marked, not just the first.
- `_format_k`/`_format_cache_call` use a leading underscore but are imported by 4+ external callers — treat them as public despite the naming convention.
- `format_cache_tracker` returns a **5-tuple**, not a string — `initial_parent_count` counts collapsed parent rows before the viewport start; callers that don't need it unpack with `_, _, _, _, _`.
- Line content uses `SOFT_RESET` (`\033[39m`) instead of `RESET` (`\033[0m`) for inline foreground-color endings, so a caller can inject a row-level background without it being killed mid-line. Exception: `_format_cache_call` keeps `RESET` for `cc_broken` rows, since that background must end at the line terminator, not mid-content.
- `_compute_cache_viewport`'s sticky-header truncation path (`len(raw) > pane_width + 20`) rebuilds `sticky_header` from only `re.search(r'Turn \d+', raw).group(0)`, discarding everything before/after — including a prepended search marker if the matching turn line was long enough to truncate. A matching turn's highlight can silently disappear specifically when it is both a search match, long enough to truncate, and currently the sticky header; match data and jump-to-match still work, only that one visual cue is lost.

### turn_cache.py (160 LOC)

**Purpose:** Frozen-turn cache for `format_cache_tracker` — `sync_document` re-renders only the turns whose render inputs changed and reuses the assembled document otherwise; `publish_nav` refills the caller's nav dict.
**Reads:** the cache dict, turns and the render-input bundle passed by `token_format` — all arguments.
**Writes:** mutates the passed cache dict in place; `publish_nav` clears and refills the passed nav dict.
**Called by:** `format/token_format.py`; the cache dict is owned by `panes/token_pane.py` and `workers/worker_tokens_pane.py`.
**Calls out:** none.

---
