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

### token_format.py (307 LOC)

**Purpose:** `format_cache_tracker(turns, ...)` builds logical lines for the tokens/cache-tracker pane — groups API calls into turns with CR/CC/D counts, handles expand/collapse, embeds search-match markers, and computes the scroll viewport. Returns a 5-tuple `(visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count)`. Does NOT render zebra/hover/truncation — that is the caller's own row loop (`token_pane.py`, `worker_format.py`). Also provides `_format_k` (compact token counts) and `shorten_tool_name` (`mcp__plugin__tool` → `tool`).
**Reads:** cache-turn lists, expand-state dicts, pane dimensions, scroll offset, optional `response_rid_map`/`copy_feedback`/`search_match_set`/`search_current_key`/`search_query`/`nav_out` — all passed as arguments.
**Writes:** returns the 5-tuple; mutates `nav_out` in place when given (cleared then rewritten with `{key: absolute_line_idx, ..., 'total_lines': N}`). No stdout, no file writes.
**Called by:** `panes/token_pane.py`, `panes/token_search.py` (reuses `_format_turn_header_line`, `_format_cache_call`, `_call_thinking_meta`, `_render_expanded_call_lines` directly, so a search match can never diverge from what this module actually renders), `workers/worker_format.py`, `workers/worker_render.py`, `proxy_display/format.py` (`_format_k`).
**Calls out:** none.

---

## Gotchas

- `highlight_stripped` wraps each **line** of a chunk individually rather than the whole chunk as one unit — a downstream renderer that splits the result on `\n` and applies a per-line zebra background needs every line marked, not just the first.
- `_format_k`/`_format_cache_call` use a leading underscore but are imported by 4+ external callers — treat them as public despite the naming convention.
- `format_cache_tracker` returns a **5-tuple**, not a string — `initial_parent_count` counts collapsed parent rows before the viewport start; callers that don't need it unpack with `_, _, _, _, _`.
- Line content uses `SOFT_RESET` (`\033[39m`) instead of `RESET` (`\033[0m`) for inline foreground-color endings, so a caller can inject a row-level background without it being killed mid-line. Exception: `_format_cache_call` keeps `RESET` for `cc_broken` rows, since that background must end at the line terminator, not mid-content.
- `_compute_cache_viewport`'s sticky-header truncation path (`len(raw) > pane_width + 20`) rebuilds `sticky_header` from only `re.search(r'Turn \d+ \[[^\]]+\]', raw).group(0)`, discarding everything before/after — including a prepended search marker if the matching turn line was long enough to truncate. A matching turn's highlight can silently disappear specifically when it is both a search match, long enough to truncate, and currently the sticky header; match data and jump-to-match still work, only that one visual cue is lost.
