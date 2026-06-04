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

### warnings_parse.py (31 LOC)

**Purpose:** Unknown-type tracking state and format helpers for the warnings pane. Gutted in Stage 2D — old parse/classify helpers (_iso_to_float, _is_tool_error, _is_zero_result_block, _build_tool_use_id_map, _resolve_tool_call) removed. Retains: `unknown_type_counts` / `warned_unknown_types` module-level state; `track_unknown_type(entry)` called by `monitor_session`; `format_unknown_type_warning(msg_type, count)` and `format_warnings_block()` used by `warnings_render`.
**Reads:** `unknown_type_counts` module state.
**Writes:** Mutates `unknown_type_counts`, `warned_unknown_types` (module-level state).
**Called by:** `warnings_render.py` (`unknown_type_counts`, `format_unknown_type_warning`); `panes.__init__` (re-exports `track_unknown_type`); `core/monitor_session.py` (via package import).
**Calls out:** `constants` (YELLOW, RESET).

---

### warnings_pane.py (247 LOC)

**Purpose:** Warnings pane event loop and module-level state owner. Reads tool errors directly from the `_errors` dual-log (current proxy session, via `find_errors_log_path`) and from worker `_errors` dual-logs (via `scan_worker_errors_logs`); no proxy-log scanning. `_errors_record_to_display(rec)` converts raw `_errors` records to display dicts; `_read_errors_log(path, last_pos)` does incremental line-by-line reads. On project/session change, all state is reset and positions cleared. Loop follows drain-refresh-render pattern; private helpers `_warnings_ram_state`, `_handle_warnings_mouse`, `_handle_warnings_key`, `_refresh_warnings_data`, `_build_warnings_output` extracted from loop body. No zero_results, schema_warnings, or dedup sets.
**Reads:** `_errors` dual-log (incremental via `_errors_log_pos`); worker `_errors` dual-logs (incremental via `_worker_errors_positions`); shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); rebinds `error_line_map` from render return; extends `tool_errors`.
**Called by:** `core/monitor.py` (mode dispatch).
**Calls out:** `input.click_handler` (module-level), `core.monitor` (lazy, inside `_refresh_warnings_data`), `proxy_display.parser` (lazy: `find_errors_log_path`, `scan_worker_errors_logs`, `proxy_session_id_for_project`, `get_proxy_session_start_ts`), `panes.warnings_render`.

---

### warnings_scan.py (12 LOC)

**Purpose:** No-op stub — scan functions removed in Stage 2D; errors are now sourced from `_errors` dual-log by `warnings_pane` directly. Two stub functions retained for import compatibility; both return empty results immediately.
**Reads:** Nothing.
**Writes:** Nothing.
**Called by:** Nothing (stub, not called).
**Calls out:** Nothing.

---

### warnings_persist.py (8 LOC)

**Purpose:** No-op stub — `append_tool_errors` removed in Stage 2D; tool errors are now written to the `_errors` dual-log by the proxy write-side, not by monitor. Single stub function retained for import compatibility; returns immediately without writing.
**Reads:** Nothing.
**Writes:** Nothing.
**Called by:** Nothing (stub, not called).
**Calls out:** Nothing.

---

### warnings_render.py (124 LOC)

**Purpose:** Pure rendering helpers — formats the warnings pane from caller-supplied state. `_format_warnings_pane(tool_errors, error_expand_states, error_hover_row, error_scroll_offset, pane_height, pane_width, last_refresh_ts)` returns `(rendered_str, new_error_line_map)` 2-tuple; no globals written. `_format_warnings_header(last_refresh_ts)` builds the header line. Reads `unknown_type_counts` from `warnings_parse` (its owner module). `_serialize_warnings(key, tool_errors)` formats clipboard output for a single error entry.
**Reads:** All pane state passed as function arguments; `unknown_type_counts` imported from `warnings_parse` (read-only).
**Writes:** Nothing — returns rendered string and new line-map dict; no mutation of arguments.
**Called by:** `panes.warnings_pane` (`run_warnings_loop`).
**Calls out:** `panes.warnings_parse` (`unknown_type_counts`, `format_unknown_type_warning`), `format.strip_marker` (`highlight_stripped`), `utils` (`truncate_visible`, `first_word_of_call`, `format_worker_prefix`), `constants`.

---

## State

Each pane module owns its own module-level scroll/expand/hover state. State is NOT shared between panes. All panes read `monitor.active_project_filter` via `from ..core import monitor as _monitor`.

| Module | Key state vars |
|---|---|
| `token_pane` | `cache_expand_states`, `cache_line_map`, `cache_scroll_offset`, `_cache_turns`, `_cache_jsonl_position` |
| `warnings_parse` | `unknown_type_counts`, `warned_unknown_types` |
| `warnings_pane` | `tool_errors`, `error_expand_states`, `error_line_map`, `error_hover_row`, `error_scroll_offset`, `_errors_log_pos`, `_errors_log_path`, `_worker_errors_positions`, `_last_project_filter`, `_monitor_start_ts` |
| `warnings_scan` | none (stub — no state) |
| `warnings_persist` | none (stub — no state) |
| `warnings_render` | none (stateless — receives state as args, returns new values) |

## Gotchas

- `from ..core import monitor as _monitor` is lazy in `_refresh_tokens_data` and `_refresh_warnings_data` (inside the helper, not the loop) to avoid circular imports. `load_historical_warnings` also imports lazily. `input.click_handler` imports are at module level (no circular-import risk).
- `build_cache_turns()` in `token_pane.py` is also called by `proxy_display` — it is a shared utility even though it lives in a pane module.
- Zebra/hover/truncation render loop lives in `_build_tokens_output()` in `token_pane.py`, NOT in `token_format.py`. `format_cache_tracker` returns a uniform 5-tuple `(visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count)` on all paths including empty turns (fixed 2026-05-12, commit `1f887ae`).
- `line_map` is built 1:1 in the render loop (one physical row per logical line). `visual_line_count` span-loops are gone — long lines are truncated at render time, not wrapped.
- **Header + Body pane contract:** panes that render a fixed header above a scrolling body MUST overdraw the header after printing the body, using `print(f"\033[H{header}\033[K", end='', flush=True)`. Without the overdraw, long body lines that wrap visually push the header off the top of the pane. Empty-body test cases pass trivially — always verify with real (non-empty) data. Applies to `warnings_pane`.
