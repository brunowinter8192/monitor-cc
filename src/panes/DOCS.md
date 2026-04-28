# src/panes/

## Role

Dedicated tmux pane event loops — each module owns one pane's poll cycle, stdin input handling, and ANSI screen output. These modules are spawned by `core/monitor.py` when `--mode` targets a specific pane (tokens, warnings, waste). They run as the process main loop and never return. Touch this package to change what a pane displays, how it handles mouse/keyboard input, or its scroll/expand state. Do NOT add general formatting logic here — that belongs in `format/`.

## Public Interface

```python
from src.panes import run_tokens_loop      # token/cache tracker pane
from src.panes import run_warnings_loop    # tool errors / unknown types pane
from src.panes import run_waste_loop       # proxy forensics / waste pane
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

### token_pane.py (216 LOC)

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
**Called by:** `warnings_pane.py`; `panes.__init__` (re-exports `track_unknown_type`); `core/monitor_session.py` (via package import).
**Calls out:** stdlib only (`json`, `datetime`), `constants`.

---

### warnings_pane.py (445 LOC)

**Purpose:** Warnings pane event loop — two sections: (1) unknown JSONL types, (2) tool errors + zero-result calls from proxy JSONL. Scrollable expand/collapse. Expanded error view shows pre-strip content with DIM_YELLOW_BG highlights for proxy-stripped chunks (via `format.strip_marker`). Remainder LOC is cohesive by shared event-state globals — further split would require refactoring.
**Reads:** Proxy JSONL (incremental via `_proxy_log_position`); worker log files; shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); mutates `tool_errors`, `error_expand_states`, `error_line_map`, `zero_results`, `schema_warnings`.
**Called by:** `core/monitor.py` (mode dispatch).
**Calls out:** `core.monitor` (lazy), `proxy_display.parser` (lazy), `input.click_handler` (lazy), `panes.warnings_parse`, `format.strip_marker`.

---

### waste_forensics.py (115 LOC)

**Purpose:** Data model for proxy forensics — `ToolUse`, `ToolResult`, `Pair` dataclasses plus `tool_use_blocks()`, `tool_result_blocks()`, `pairs()`, `format_timestamp_local()`. No UI concerns.
**Reads:** Raw proxy event dicts (passed in as lists).
**Writes:** Nothing (pure functions + frozen dataclasses).
**Called by:** `waste_pane.py`.
**Calls out:** stdlib only (`json`, `datetime`).

---

### waste_pane.py (439 LOC)

**Purpose:** Proxy forensics / waste pane — reads proxy JSONL, extracts tool_use/tool_result pairs via `waste_forensics`, filters by `input_chars/output_chars >= threshold`, displays sorted descending. Digit keys 1–9 set threshold. Expanded OUTPUT section shows pre-strip content with DIM_YELLOW_BG highlights when the tool_result's message was proxy-stripped. Remainder LOC is cohesive by shared globals — further split would require refactoring.
**Reads:** Proxy JSONL (via marker file discovery in `proxy_display.parser`); shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); mutates `_waste_above`, `waste_expand_states`, `waste_line_map`, `waste_threshold`, `_strip_by_tool_result_id`.
**Called by:** `core/monitor.py` (mode dispatch).
**Calls out:** `input.click_handler`, `proxy_display.parser`, `core.monitor` (lazy), `panes.waste_forensics`, `format.strip_marker`.

---

## State

Each pane module owns its own module-level scroll/expand/hover state. State is NOT shared between panes. All panes read `monitor.active_project_filter` via `from ..core import monitor as _monitor`.

| Module | Key state vars |
|---|---|
| `token_pane` | `cache_expand_states`, `cache_line_map`, `cache_scroll_offset`, `_cache_turns`, `_cache_jsonl_position` |
| `warnings_parse` | `unknown_type_counts`, `warned_unknown_types` |
| `warnings_pane` | `tool_errors`, `error_expand_states`, `error_scroll_offset`, `_proxy_log_position` |
| `waste_pane` | `_waste_above`, `waste_expand_states`, `waste_threshold`, `_strip_by_tool_result_id` |

## Gotchas

- All 3 pane loops call `from ..core import monitor as _monitor` lazily (inside the run function) to avoid circular imports at module level.
- `build_cache_turns()` in `token_pane.py` is also called by `proxy_display` — it is a shared utility even though it lives in a pane module.
- Zebra/hover/truncation render loop lives in `token_pane.py`, NOT in `token_format.py`. `format_cache_tracker` returns a 4-tuple of logical lines — `token_pane.py` applies visual treatment.
- `line_map` is built 1:1 in the render loop (one physical row per logical line). `visual_line_count` span-loops are gone — long lines are truncated at render time, not wrapped.
- **Header + Body pane contract:** panes that render a fixed header above a scrolling body MUST overdraw the header after printing the body, using `print(f"\033[H{header}\033[K", end='', flush=True)`. Without the overdraw, long body lines that wrap visually push the header off the top of the pane. Empty-body test cases pass trivially — always verify with real (non-empty) data. Applies to warnings_pane and waste_pane.
