# src/panes/

## Role

Dedicated tmux pane event loops — each module owns one pane's poll cycle, stdin input handling,
and ANSI screen output. These modules are spawned by `core/monitor.py` when `--mode` targets
`tokens` or `warnings`. They run as the process main loop and never return. Touch this package to
change what a pane displays, how it handles mouse/keyboard input, or its scroll/expand state. Do
NOT add general formatting logic here — that belongs in `format/`.

## Public Interface

```python
from src.panes import run_tokens_loop      # token/cache tracker pane
from src.panes import run_warnings_loop    # tool errors pane
```

`token_search.py`, `cache_turns.py`, and `log_janitor.py` have no `__init__.py` export — each is
imported directly by its own caller (see their Modules entries below).

## Flow

```
core/monitor.run_monitor(mode=X)
  → lazy import from panes → run_X_loop()
      loop: poll data source
            handle stdin (keyboard/mouse via input.click_handler)
            render to stdout (ANSI escape sequences, full screen redraw)
```

## Modules

### token_pane.py (326 LOC)

**Purpose:** Token/cache-tracker pane event loop — incrementally reads session JSONL (via `cache_turns.build_cache_turns`), renders an interactive expand/collapse/scroll view with CR/CC/D per request, and owns the zebra/hover/truncation render loop over `format.token_format`'s logical lines. Also polls the `_response` dual-log incrementally for rate-limit headers (accumulated into `_response_rid_map`), and runs the 24h `log_janitor` sweep from its own tick — this pane is the always-active, main-checkout-resident process, which is why it hosts that sweep.
**Reads:** session JSONL (incremental via `_cache_jsonl_position`); the `_response` dual-log (incremental via `_response_log_pos`); shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`); mutates `cache_expand_states`, `cache_line_map`, `cache_hover_row`, `cache_scroll_offset`, `cache_copy_rows`, `_cache_copy_feedback_until`, `_cache_pane_width`, `_cache_turns`, `_cache_jsonl_position`, `_response_log_pos`, `_response_rid_map`, `_tokens_search`, `_tokens_nav`.
**Called by:** `core/monitor.py` (mode dispatch).
**Calls out:** none.

---

### cache_turns.py (57 LOC)

**Purpose:** `build_cache_turns(filepath, last_position, existing_turns) -> (turns, new_position)` — incrementally reads new lines from a session JSONL since `last_position`, parses them, and merges the resulting cache turns into `existing_turns` (including the case where the last existing turn was left incomplete by a previous poll).
**Reads:** session JSONL file at `filepath` (via `jsonl.read_new_lines`/`jsonl.get_current_position`) — parameters only.
**Writes:** nothing — returns `(turns, new_position)`; does not mutate `existing_turns`.
**Called by:** `panes/token_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`.
**Calls out:** none.

---

### token_search.py (35 LOC)

**Purpose:** `build_token_search_matches(query, turns, pane_width, response_rid_map=None)` — the ordered list of match keys whose content matches `query` (case-insensitive), reusing the real render functions from `format.token_format` so a match can never diverge from what the pane actually renders.
**Reads:** turns list, pane width, optional response_rid_map — parameters only.
**Writes:** nothing — returns `List[key]`.
**Called by:** `panes/token_pane.py`, `workers/worker_search.py`.
**Calls out:** none.

---

### warnings_pane.py (329 LOC)

**Purpose:** Warnings pane event loop and module-level state owner. Reads tool errors from the current session's `_errors` dual-log plus every worker's own `_errors` dual-log, converts raw records to display dicts, and drives the same drain-refresh-render loop shape as every other pane. On project/session change, resets all state and read positions.
**Reads:** `_errors` dual-log (incremental via `_errors_log_pos`); worker `_errors` dual-logs (incremental via `_worker_errors_positions`); shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`); rebinds `error_line_map` from the render return; extends `tool_errors`; mutates `error_copy_rows`, `_error_copy_feedback_until`, `_error_pane_width`, `_warnings_header_regions`, `_warnings_search`.
**Called by:** `core/monitor.py` (mode dispatch).
**Calls out:** none.

---

### warnings_render.py (192 LOC)

**Purpose:** Pure rendering helpers for the warnings pane — `_format_warnings_pane` returns `(rendered_str, new_error_line_map)` from caller-supplied state with no globals touched; `_format_warnings_header` builds the header line (including the `[refresh]` button and its clickable region); `_serialize_warnings` formats clipboard text for one error entry; `build_warnings_search_matches` matches directly against the underlying error dicts.
**Reads:** all pane state passed as function arguments.
**Writes:** nothing — returns the rendered string and a new line-map dict; `copy_rows_out`/`regions_out`, if given, are mutated in place (cleared then repopulated).
**Called by:** `panes/warnings_pane.py`.
**Calls out:** none.

---

### log_janitor.py (167 LOC)

**Purpose:** `LogSpec` registry (12 entries, the authoritative log inventory) + `sweep_eligible_specs()` + `cleanup_old_jsonl(path)` — the 7-day JSONL sweep triggered from `token_pane.py::run_tokens_loop` every 24h.
**Reads:** JSONL log files passed in as `path` arguments — no shared/module state.
**Writes:** rewrites the passed JSONL file in place (drops records older than 7 days by their `ts` field); exception-safe, never raises.
**Called by:** `panes/token_pane.py` (lazy import inside `_refresh_tokens_data`, gated every 24h); `dev/hook_smoke/test_log_janitor.py` (via `sys.path.insert`, bare `from log_janitor import`).
**Calls out:** none.

---

## State

Each pane module owns its own module-level scroll/expand/hover state. State is NOT shared between
panes. All panes read `monitor.active_project_filter` via `from ..core import monitor as _monitor`.

| Module | Key state vars |
|---|---|
| `token_pane` | `cache_expand_states`, `cache_line_map`, `cache_scroll_offset`, `cache_copy_rows`, `_cache_copy_feedback_until`, `_cache_turns`, `_cache_jsonl_position`, `_response_log_pos`, `_response_rid_map`, `_tokens_search` (`search_bar.SearchState`), `_tokens_nav` (key → line-idx cache for jump-to-match, refreshed every render) |
| `warnings_pane` | `tool_errors`, `error_expand_states`, `error_line_map`, `error_hover_row`, `error_scroll_offset`, `error_copy_rows`, `_error_copy_feedback_until`, `_warnings_header_regions`, `_errors_log_pos`, `_errors_log_path`, `_worker_errors_positions`, `_last_project_filter`, `_monitor_start_ts`, `_warnings_search` (`search_bar.SearchState`) |
| `warnings_render` / `token_search` / `cache_turns` | none — stateless, receive state as arguments and return new values |

## Gotchas

- `from ..core import monitor as _monitor` is lazy, inside `_refresh_tokens_data`/`_refresh_warnings_data`, to avoid circular imports; `input.click_handler` imports stay module-level (no circular-import risk there).
- The zebra/hover/truncation render loop lives in `_render_tokens_rows()` (`token_pane.py`) / `_render_warnings_rows()` (`warnings_render.py`), not in `format/token_format.py` — `format_cache_tracker` only returns logical lines and a uniform 5-tuple.
- `token_pane._render_tokens_rows`, `warnings_render._render_warnings_rows`, and `workers/worker_render._render_workers_rows` are three separate, near-identical zebra/hover/copy-row render loops — not folded into one shared helper. They differ in the search-match-substring-bg constant checked (`LIGHT_RED_BG` in the first two, `DIM_YELLOW_BG` in warnings) and in key handling (tuple keys vs. bare int/str keys).
- `line_map` is built 1:1 in each render loop (one physical row per logical line) — long lines are truncated at render time, not wrapped.
- **Header + Body pane contract:** a pane that renders a fixed header above a scrolling body must overdraw the header after printing the body (`print(f"\033[H{header}\033[K", end='', flush=True)`), or long body lines that wrap visually push the header off the top. Applies to `warnings_pane`. Does NOT apply to `token_pane` — it truncates every line (`truncate_visible`) instead of wrapping, so the precondition never occurs.
- `token_pane.py`'s `_handle_tokens_mouse` checks `row == 1` (search bar) before the `cache_line_map` body lookup — no collision is possible since `cache_line_map` never gets a row-1 entry.
- Wheel direction is inverted between the two panes: `warnings_pane` renders top-to-bottom, so wheel-up (button 64) decreases `error_scroll_offset` and wheel-down (65) increases it; `token_pane` renders bottom-to-top and adds on wheel-up (64).
- `colors.ZEBRA_BG_A == ''` is the `chosen_bg` for every non-hovered, non-error row in both render loops — `search_bar.resolve_bg_restore(line, chosen_bg)` must run unconditionally there, or an embedded search-highlight sentinel leaks into the terminal.
