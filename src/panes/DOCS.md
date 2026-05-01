# src/panes/

## Role

Dedicated tmux pane event loops — each module owns one pane's poll cycle, stdin input handling, and ANSI screen output. These modules are spawned by `core/monitor.py` when `--mode` targets a specific pane (tokens, warnings). They run as the process main loop and never return. Touch this package to change what a pane displays, how it handles mouse/keyboard input, or its scroll/expand state. Do NOT add general formatting logic here — that belongs in `format/`.

## Public Interface

```python
from src.panes import run_tokens_loop      # token/cache tracker pane
from src.panes import run_warnings_loop    # tool errors / unknown types pane
from src.panes import track_unknown_type   # called by monitor_session for unknown JSONL types
```

## Flow

```
core/monitor.run_monitor(mode=X)
  → lazy import from panes → run_X_loop()
      loop: poll data source
            handle stdin (keyboard/mouse via input.click_handler)
            render to stdout (ANSI escape sequences, full screen redraw)
```

## Modules

### token_pane.py (229 LOC)

**Purpose:** Token/cache tracker pane — incrementally reads session JSONL, builds cache-turn dicts, renders interactive expand/collapse/scroll view with CR/CC/D per request. Owns the zebra/hover/truncation render loop: calls `format_cache_tracker` for logical lines, then applies `ZEBRA_BG_A/B`, `HOVER_BG` priority, and `truncate_visible` per line.
**Reads:** Session JSONL (incremental via `_cache_jsonl_position`); shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); mutates module-level `cache_expand_states`, `cache_line_map`, `cache_hover_row`, `cache_scroll_offset`, `_cache_turns`, `_cache_jsonl_position`.
**Called by:** `core/monitor.py` (mode dispatch); `proxy_display/pane.py` + `proxy_display/worker_proxy_pane.py` (`build_cache_turns` function).
**Calls out:** `jsonl`, `input.click_handler`, `format.token_format`, `core.monitor` (lazy state read), `utils.truncate_visible`.

---

### warnings_parse.py (110 LOC)

**Purpose:** Pure parsing/classification helpers and unknown-type tracking state for the warnings pane. No UI concerns.
**Reads:** Proxy entry dicts (passed in as lists); reads `unknown_type_counts` module state.
**Writes:** Mutates `unknown_type_counts`, `warned_unknown_types` (module-level state).
**Called by:** `warnings_pane.py` (`_iso_to_float`); `warnings_scan.py` (parse helpers); `warnings_render.py` (`unknown_type_counts`, `format_unknown_type_warning`); `panes.__init__` (re-exports `track_unknown_type`); `core/monitor_session.py` (via package import).
**Calls out:** stdlib only (`json`, `datetime`), `constants`.

---

### warnings_pane.py (258 LOC)

**Purpose:** Warnings pane event loop and module-level state owner. Owns all mutable globals (`tool_errors`, `zero_results`, `schema_warnings`, dedup sets, scroll/hover state). Delegates scanning to `warnings_scan`, rendering to `warnings_render`. Processes schema-warning entries inline (no scan helper needed — simpler pattern).
**Reads:** Proxy JSONL (incremental via `_proxy_log_position`); worker log files; shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); rebinds `error_line_map`, `zero_result_line_map` from render return tuple; extends `tool_errors`, `zero_results`, `schema_warnings`.
**Called by:** `core/monitor.py` (mode dispatch).
**Calls out:** `core.monitor` (lazy), `proxy_display.parser` (lazy), `input.click_handler` (lazy), `panes.warnings_parse` (`_iso_to_float`), `panes.warnings_scan`, `panes.warnings_render`.

---

### warnings_scan.py (103 LOC)

**Purpose:** Pure scanning helpers — reads proxy/worker log entry dicts, classifies tool errors and zero-result blocks, deduplicates via caller-supplied seen-key sets. No UI concerns, no module-level state. Returns `(items_list, new_dedup_keys)` tuples; caller extends its own lists and updates its own seen sets.
**Reads:** Entry dicts passed as `entries` list; `seen_error_keys` / `seen_zero_keys` sets read-only for dedup check.
**Writes:** Nothing — returns new lists and sets; no mutation of arguments.
**Called by:** `panes.warnings_pane` (`run_warnings_loop`).
**Calls out:** `panes.warnings_parse` (`_iso_to_float`, `_is_tool_error`, `_is_zero_result_block`, `_build_tool_use_id_map`, `_resolve_tool_call`), `utils.format_timestamp`, `format.strip_marker` (`get_stripped_data`).

---

### warnings_render.py (167 LOC)

**Purpose:** Pure rendering helpers — formats the warnings pane from caller-supplied state. `_format_warnings_pane` returns `(rendered_str, new_error_line_map, new_zero_result_line_map)` as a tuple; no globals written. Reads `unknown_type_counts` from `warnings_parse` (its owner module). `_serialize_warnings` formats clipboard output given explicit tool_errors/zero_results lists.
**Reads:** All pane state passed as function arguments; `unknown_type_counts` imported from `warnings_parse` (read-only).
**Writes:** Nothing — returns rendered strings and new line-map dicts; no mutation of arguments.
**Called by:** `panes.warnings_pane` (`run_warnings_loop`).
**Calls out:** `panes.warnings_parse` (`unknown_type_counts`, `format_unknown_type_warning`), `format.strip_marker` (`highlight_stripped`), `utils` (`truncate_visible`, `first_word_of_call`, `format_worker_prefix`), `constants`.

---

## State

Each pane module owns its own module-level scroll/expand/hover state. State is NOT shared between panes. All panes read `monitor.active_project_filter` via `from ..core import monitor as _monitor`.

| Module | Key state vars |
|---|---|
| `token_pane` | `cache_expand_states`, `cache_line_map`, `cache_scroll_offset`, `_cache_turns`, `_cache_jsonl_position` |
| `warnings_parse` | `unknown_type_counts`, `warned_unknown_types` |
| `warnings_pane` | `tool_errors`, `error_expand_states`, `error_line_map`, `zero_results`, `zero_result_line_map`, `schema_warnings`, `_seen_error_keys`, `_seen_zero_keys`, `error_scroll_offset`, `_proxy_log_position` |
| `warnings_scan` | none (stateless — receives state as args, returns new values) |
| `warnings_render` | none (stateless — receives state as args, returns new values) |

## Gotchas

- All 3 pane loops call `from ..core import monitor as _monitor` lazily (inside the run function) to avoid circular imports at module level.
- `build_cache_turns()` in `token_pane.py` is also called by `proxy_display` — it is a shared utility even though it lives in a pane module.
- Zebra/hover/truncation render loop lives in `token_pane.py`, NOT in `token_format.py`. `format_cache_tracker` returns a 4-tuple of logical lines — `token_pane.py` applies visual treatment.
- `line_map` is built 1:1 in the render loop (one physical row per logical line). `visual_line_count` span-loops are gone — long lines are truncated at render time, not wrapped.
- **Header + Body pane contract:** panes that render a fixed header above a scrolling body MUST overdraw the header after printing the body, using `print(f"\033[H{header}\033[K", end='', flush=True)`. Without the overdraw, long body lines that wrap visually push the header off the top of the pane. Empty-body test cases pass trivially — always verify with real (non-empty) data. Applies to `warnings_pane`.
