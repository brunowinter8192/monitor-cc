# src/panes/

## Role

Dedicated tmux pane event loops — each module owns one pane's poll cycle, stdin input handling, and ANSI screen output. These modules are spawned by `core/monitor.py` when `--mode` targets a specific pane (tokens, rules, warnings, waste). They run as the process main loop and never return. Touch this package to change what a pane displays, how it handles mouse/keyboard input, or its scroll/expand state. Do NOT add general formatting logic here — that belongs in `format/`.

## Public Interface

```python
from src.panes import run_tokens_loop      # token/cache tracker pane
from src.panes import run_rules_loop       # active rules pane
from src.panes import run_warnings_loop    # tool errors / unknown types pane
from src.panes import run_waste_loop       # proxy forensics / waste pane
from src.panes import process_hook_log     # one-shot hook log refresh (called from streaming loop)
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

### token_pane.py (154 LOC)

**Purpose:** Token/cache tracker pane — incrementally reads session JSONL, builds cache-turn dicts, renders interactive expand/collapse/scroll view with CR/CC/D per request.
**Reads:** Session JSONL (incremental via `_cache_jsonl_position`); shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); mutates module-level `cache_expand_states`, `cache_line_map`, `cache_hover_row`, `cache_scroll_offset`, `_cache_turns`, `_cache_jsonl_position`.
**Called by:** `core/monitor.py` (mode dispatch); `proxy_display/pane.py` + `proxy_display/worker_proxy_pane.py` (`build_cache_turns` function).
**Calls out:** `jsonl`, `input.click_handler`, `format.token_format`, `core.monitor` (lazy state read).

---

### rules_pane.py (169 LOC)

**Purpose:** Active rules pane — polls hook log for InstructionsLoaded events, groups rules by [P]roject/[G]lobal source, renders interactive expand/collapse view. Also exposes `process_hook_log()` for the main streaming loop.
**Reads:** Hook log (`src/logs/hook_outputs.jsonl`) via `hooks` package; shared state `monitor.active_project_filter`, `monitor.hook_log_position`.
**Writes:** stdout (ANSI screen); mutates `active_rules`, `rules_invokers`, `rules_expand_states`, `rules_line_map`, `rules_scroll_offset`.
**Called by:** `core/monitor.py` (mode dispatch + `process_hook_log` in streaming loop).
**Calls out:** `hooks`, `input.click_handler`, `core.monitor` (lazy), `input.ui_mode` (lazy, `format_rules_block`).

---

### warnings_pane.py (503 LOC)

**Purpose:** Warnings pane — two sections: (1) unknown JSONL message types from session parsing, (2) tool errors from proxy JSONL. Scrollable expand/collapse list. Also exposes `track_unknown_type()` for `monitor_session`.
**Reads:** Proxy JSONL (incremental via `_proxy_log_position`); worker log files; shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); mutates `tool_errors`, `error_expand_states`, `error_line_map`, `warned_unknown_types`, `unknown_type_counts`.
**Called by:** `core/monitor.py` (mode dispatch); `core/monitor_session.py` (`track_unknown_type`).
**Calls out:** `core.monitor` (lazy), `proxy_display.parser` (lazy), `input.click_handler` (lazy).

---

### waste_pane.py (519 LOC)

**Purpose:** Proxy forensics / waste pane — reads proxy JSONL, extracts tool_use/tool_result pairs, filters by `input_chars/output_chars >= threshold`, displays sorted descending. Digit keys 1–9 set threshold.
**Reads:** Proxy JSONL (via marker file discovery in `proxy_display.parser`); shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); mutates `_waste_above`, `waste_expand_states`, `waste_line_map`, `waste_threshold`.
**Called by:** `core/monitor.py` (mode dispatch).
**Calls out:** `input.click_handler`, `proxy_display.parser`, `core.monitor` (lazy).

---

## State

Each pane module owns its own module-level scroll/expand/hover state. State is NOT shared between panes. All panes read `monitor.active_project_filter` via `from ..core import monitor as _monitor`.

| Module | Key state vars |
|---|---|
| `token_pane` | `cache_expand_states`, `cache_line_map`, `cache_scroll_offset`, `_cache_turns`, `_cache_jsonl_position` |
| `rules_pane` | `active_rules`, `rules_invokers`, `rules_expand_states`, `rules_scroll_offset` |
| `warnings_pane` | `tool_errors`, `error_expand_states`, `error_scroll_offset`, `_proxy_log_position` |
| `waste_pane` | `_waste_above`, `waste_expand_states`, `waste_threshold` |

## Gotchas

- All 4 pane loops call `from ..core import monitor as _monitor` lazily (inside the run function) to avoid circular imports at module level.
- `build_cache_turns()` in `token_pane.py` is also called by `proxy_display` — it is a shared utility even though it lives in a pane module.
