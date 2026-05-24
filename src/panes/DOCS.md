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

### token_pane.py (259 LOC)

**Purpose:** Token/cache tracker pane — incrementally reads session JSONL, builds cache-turn dicts, renders interactive expand/collapse/scroll view with CR/CC/D per request. Owns the zebra/hover/truncation render loop: calls `format_cache_tracker` for logical lines, then applies `ZEBRA_BG_A/B`, `HOVER_BG` priority, and `truncate_visible` per line. Loop follows drain-refresh-render pattern; private helpers `_tokens_ram_state`, `_handle_tokens_mouse`, `_handle_tokens_key`, `_refresh_tokens_data`, `_build_tokens_output` extracted from loop body.
**Reads:** Session JSONL (incremental via `_cache_jsonl_position`); shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); mutates module-level `cache_expand_states`, `cache_line_map`, `cache_hover_row`, `cache_scroll_offset`, `_cache_turns`, `_cache_jsonl_position`.
**Called by:** `core/monitor.py` (mode dispatch); `proxy_display/pane.py` + `proxy_display/worker_proxy_pane.py` (`build_cache_turns` function).
**Calls out:** `jsonl`, `input.click_handler`, `format.token_format`, `core.monitor` (lazy, inside `_refresh_tokens_data`), `utils.truncate_visible`.

---

### warnings_parse.py (110 LOC)

**Purpose:** Pure parsing/classification helpers and unknown-type tracking state for the warnings pane. No UI concerns.
**Reads:** Proxy entry dicts (passed in as lists); reads `unknown_type_counts` module state.
**Writes:** Mutates `unknown_type_counts`, `warned_unknown_types` (module-level state).
**Called by:** `warnings_pane.py` (`_iso_to_float`); `warnings_scan.py` (parse helpers); `warnings_render.py` (`unknown_type_counts`, `format_unknown_type_warning`); `panes.__init__` (re-exports `track_unknown_type`); `core/monitor_session.py` (via package import).
**Calls out:** stdlib only (`json`, `datetime`), `constants`.

---

### warnings_pane.py (298 LOC)

**Purpose:** Warnings pane event loop and module-level state owner. Owns all mutable globals (`tool_errors`, `zero_results`, `schema_warnings`, dedup sets, scroll/hover state). Delegates scanning to `warnings_scan`, rendering to `warnings_render`, persistence to `warnings_persist`. Processes schema-warning entries inline (no scan helper needed — simpler pattern). Loop follows drain-refresh-render pattern; private helpers `_warnings_ram_state`, `_handle_warnings_mouse`, `_handle_warnings_key`, `_refresh_warnings_data`, `_build_warnings_output` extracted from loop body.
**Reads:** Proxy JSONL (incremental via `_proxy_log_position`); worker log files; shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); rebinds `error_line_map`, `zero_result_line_map` from render return tuple; extends `tool_errors`, `zero_results`, `schema_warnings`; appends new tool errors to `src/logs/tool_errors.jsonl` via `warnings_persist.append_tool_errors` (parallel persistent-write, fail-silent, forward-only from monitor start).
**Called by:** `core/monitor.py` (mode dispatch).
**Calls out:** `input.click_handler` (module-level), `core.monitor` (lazy, inside `_refresh_warnings_data`), `proxy_display.parser` (lazy, inside `_refresh_warnings_data`), `panes.warnings_parse` (`_iso_to_float`), `panes.warnings_scan`, `panes.warnings_render`, `panes.warnings_persist`.

---

### warnings_scan.py (107 LOC)

**Purpose:** Pure scanning helpers — reads proxy/worker log entry dicts, classifies tool errors and zero-result blocks, deduplicates via caller-supplied seen-key sets. No UI concerns, no module-level state. Returns `(items_list, new_dedup_keys)` tuples; caller extends its own lists and updates its own seen sets. Tool error dicts include persistence fields `_ts_raw`, `_tool_use_id`, `_proxy_file`, `_request_id` for use by `warnings_persist`.
**Reads:** Entry dicts passed as `entries` list; `seen_error_keys` / `seen_zero_keys` sets read-only for dedup check.
**Writes:** Nothing — returns new lists and sets; no mutation of arguments.
**Called by:** `panes.warnings_pane` (`run_warnings_loop`).
**Calls out:** `panes.warnings_parse` (`_iso_to_float`, `_is_tool_error`, `_is_zero_result_block`, `_build_tool_use_id_map`, `_resolve_tool_call`), `utils.format_timestamp`, `format.strip_marker` (`get_stripped_data`).

---

### warnings_persist.py (38 LOC)

**Purpose:** Persistent-write helper for tool error events — appends each new tool error detected by `warnings_pane` to `src/logs/tool_errors.jsonl` (append-forever, no rotation). Schema per line: `{ts, session_id, worker, tool_name, tool_use_id, error_full, proxy_file, request_id}`. Worker attribution: `_worker_name` from entry → `"main"` (empty) or `"worker:<name>"`. Session_id: proxy session hash (md5 of project_path). Fail-silent on any write exception. Log path overridable via `MONITOR_CC_TOOL_ERROR_LOG` env var. Forward-only: populated from first warnings_pane refresh after monitor start; no historical backfill.
**Reads:** error dicts from `_scan_proxy_entries_for_errors`; `project_filter` from `warnings_pane` module-level state.
**Writes:** `src/logs/tool_errors.jsonl` (appends one line per new error; path resolved from `__file__` relative to project root).
**Called by:** `panes.warnings_pane` (`_refresh_warnings_data`) after `tool_errors.extend(new_errors)`.
**Calls out:** `proxy_display.parser` (`proxy_session_id_for_project`).

---

### warnings_render.py (168 LOC)

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

- `from ..core import monitor as _monitor` is lazy in `_refresh_tokens_data` and `_refresh_warnings_data` (inside the helper, not the loop) to avoid circular imports. `load_historical_warnings` also imports lazily. `input.click_handler` imports are at module level (no circular-import risk).
- `build_cache_turns()` in `token_pane.py` is also called by `proxy_display` — it is a shared utility even though it lives in a pane module.
- Zebra/hover/truncation render loop lives in `_build_tokens_output()` in `token_pane.py`, NOT in `token_format.py`. `format_cache_tracker` returns a uniform 5-tuple `(visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count)` on all paths including empty turns (fixed 2026-05-12, commit `1f887ae`).
- `line_map` is built 1:1 in the render loop (one physical row per logical line). `visual_line_count` span-loops are gone — long lines are truncated at render time, not wrapped.
- **Header + Body pane contract:** panes that render a fixed header above a scrolling body MUST overdraw the header after printing the body, using `print(f"\033[H{header}\033[K", end='', flush=True)`. Without the overdraw, long body lines that wrap visually push the header off the top of the pane. Empty-body test cases pass trivially — always verify with real (non-empty) data. Applies to `warnings_pane`.
