# src/format/

## Role

ANSI-colored string rendering for the token/cache tracker pane, plus the shared proxy-strip highlight helper. This package has no side effects: every function takes data in and returns a formatted string. Touch this package to change how the cache tracker renders. Do NOT add I/O, state, or pane loop logic here.

## Public Interface

```python
# Strip highlighting (strip_marker.py)
from src.format.strip_marker import highlight_stripped        # inline DIM_YELLOW_BG chunk highlight

# Cache tracker rendering (token_format.py)
from src.format import format_cache_tracker
from src.format import _format_k          # compact "Xk" token count — used by workers/proxy_display
from src.format import shorten_tool_name  # mcp__plugin__tool → tool, used by token_format itself
```

**(2026-09) `formatter.py` and `formatter_events.py` removed entirely, main pane deleted** —
`format_tool_call`/`format_request`/`format_response`/`combine_request_response`/`format_todo_list`/
`format_parameters`/`format_task_parameters`/`format_output`/`format_error_output`/`format_value`/
`get_status_icon`/`get_status_color` all had exactly one caller, `core/monitor_display.py`, which
was deleted along with the main pane it rendered (window 0 is now the tokens pane at full width —
see `process-docs/main_pane/`). `shorten_tool_name` had a second real caller (`token_format.py`
itself) and moved there instead of dying with the rest of the module. `formatter_events.py` was
already removed in an earlier pass (2026-09, tool-calls-only redesign) once `core/monitor_session.py`
stopped displaying non-tool-call event types.

## Modules

### strip_marker.py (24 LOC)

**Purpose:** Proxy-strip content highlighting helper — `highlight_stripped` wraps found chunks in `DIM_YELLOW_BG`/`SOFT_RESET` inline. `get_stripped_data`, `build_tool_result_strip_lookup`, and `build_tool_id_strip_lookup` deleted in Stage 3 (main-pane strip overlay removed).
**Reads:** Chunk strings passed as arguments. No I/O, no shared state.
**Writes:** Returns strings. No stdout, no file writes.
**Called by:** `panes.warnings_render`.
**Calls out:** `constants` only.

---

### token_format.py (352 LOC)

**Purpose:** Build logical lines for the token/cache tracker — groups API calls into turns with CR/CC/D counts, handles expand/collapse and viewport clipping. Returns a 5-tuple `(visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count)` — return arity UNCHANGED since 2026-08-18 (see below). The fifth element `initial_parent_count` is the number of collapsed parent rows before the current viewport — used by `token_pane.py` to keep expand/collapse key assignments stable across scrolls. Does NOT render (no zebra, no hover, no truncation) — that is `token_pane.py`'s job. Also provides `_format_k` for compact token counts. `format_cache_tracker` accepts an optional `response_rid_map: dict` (keyed by `request_id`); when a call's `request_id` matches, renders (1) usage-extras lines above the content-blocks loop (5m/1h TTL split, web_search/web_fetch if non-zero, tier/speed/geo, iteration count) and (2) rate-limit header lines (`rl: 5h:X%→HH:MM  7d:X%→…`; status/overage in YELLOW when non-nominal). Graceful when map absent or request_id not matched. **(2026-07-30) Optional `copy_feedback: Optional[dict] = None`** (keyed by `(turn_idx,call_idx)`, same as `line_keys`) — when given, appends a `⎘`/`✓` symbol to the call-summary line via `utils.append_copy_symbol`; `None` (the default, used by every pre-existing caller) skips the branch entirely, byte-identical to before.

**(2026-09, tokens-data-render-helpers milestone) two functions over 50 LOC split into line-group/per-unit helpers, byte-identical behavior (`dev/panes/render_byte_identity.py`'s new `format_cache_tracker` case + the pre-existing `dev/workers/format_byte_identity.py` hash, both unchanged before/after):**
- **`_render_expanded_call_lines`** (was 87 LOC) → 3 line-group helpers, each returning `(lines, keys)`: `_render_usage_extras_lines(call)` (TTL split / web_search-fetch / tier-speed-geo / iteration-count lines), `_render_rate_limit_lines(call, response_rid_map)` (the `rl:` line + YELLOW warn line — empty when the call's `request_id` has no `response_rid_map` entry), `_render_content_block_lines(call)` (the tool_use/thinking/text loop). `_render_expanded_call_lines` itself is now a 3-call sequence extending `lines`/`keys` from each group.
- **`format_cache_tracker`** (was 74 LOC) → `_render_call_line(turn_idx, call_idx, call, is_expanded, request_num, wide, pane_width, search_match_set, search_current_key, copy_feedback) -> (call_line, key, marker)` (the per-call summary-line build — symbol/`_format_cache_call`/search-marker-wrap/copy-symbol; `marker` is `None` unless this call is a search match, telling the caller whether/how to highlight the call's expanded detail lines) and `_render_turn_lines(turn_idx, turn, expand_states, pane_width, wide, request_num, response_rid_map, copy_feedback, search_match_set, search_current_key, search_query, nav_out, all_lines, line_keys) -> int` (renders one turn's header + all its call lines + trailing blank line, appending **directly into the caller's `all_lines`/`line_keys`** rather than returning a sub-list — the in-place-mutation contract `nav_out` already used, needed here too since `nav_out`'s indices are absolute positions in the whole-render line list; returns the updated `request_num`, a running counter across turns). `format_cache_tracker`'s per-turn loop is now `request_num = _render_turn_lines(...)`; the pre-existing dead, never-referenced `prompt_max` computation at the top is untouched (out of this milestone's scope).

**(2026-08-18, rollout sub-milestone 4) Search-highlight embedding — 4 new optional params, ZERO return-arity change.** `search_match_set: Optional[set]`, `search_current_key`, `search_query: str = ''`, `nav_out: Optional[dict] = None`. A match key is either `(turn_idx, call_idx)` [found in that call's own header or force-expanded detail content] or `('turn', turn_idx)` [found in the turn's own prompt/timestamp line]. BOTH get an UNCONDITIONAL whole-line "container mark" (`f"{marker}{line}{search_bar._BG_RESTORE_SENTINEL}"`, `marker` = `SEARCH_CURRENT_BG` or `SEARCH_MATCH_BG`) — not a literal-substring-only wrap, since the actual matching text may be buried in unrendered (collapsed) detail; mirrors `proxy_display`'s REQ-header "text extent" marking. An EXPANDED matching call additionally gets its specific matching detail line(s) browser-find substring-highlighted via `utils.highlight_query_in_line(line, search_query, marker, _BG_RESTORE_SENTINEL)` — header stays marked too (uniform, keeps orientation when scrolling). `('turn', idx)` keys are deliberately NEVER added to `line_keys` — turn headers stay non-interactive for clicks exactly as before this milestone; `nav_out`, when given, is populated (`.clear()`-then-rewritten in place, same contract as `proxy_display.format`'s `copy_rows_out`) with `{key: absolute_line_idx, ..., 'total_lines': N}` for the caller's OWN jump-to-match scroll math — deliberately a SEPARATE out-param from `line_keys`/return value, so `workers/worker_format.py`'s reuse of this function (which assumes every non-None key is a plain 2-int-tuple, `(name, ck[0], ck[1])`) is completely unaffected. All 4 new params default to no-op values — verified byte-identical against all 4 real callers (`token_pane.py`, `workers/worker_format.py`, `dev/click_ui/p2_copy_click_probe.py`, `dev/display/A_format_cache_tracker_proof.py`) via a frozen-turns old-vs-new comparison held constant in one process (the live `A_format_cache_tracker_proof.py` harness reads directly from `~/.claude/projects/.../*.jsonl` — the top-10-most-recently-modified REAL session files — which were actively growing during this milestone's own session, producing a false-positive mismatch on a naive capture-then-verify-later run; see `process-docs/pane_search/` for the full writeup). Two helpers extracted for this: `_format_turn_header_line(turn_idx, turn, pane_width)` (prompt-truncation/timestamp/think_str construction, now shared by the real render loop AND `panes/token_search.py`'s matcher so they can never disagree) and `_call_thinking_meta(call)` (has_thinking/sig_chars extraction, same rationale).

**Known limitation (documented, not fixed this milestone):** `_compute_cache_viewport`'s sticky-header TRUNCATION path (`len(raw) > pane_width+20`) rebuilds `sticky_header` from ONLY `re.search(r'Turn \d+ \[[^\]]+\]', raw).group(0)`, discarding everything before/after — including a prepended search marker/sentinel if the matching turn line was long enough to truncate. Net effect: a matching turn's highlight can silently disappear specifically when that turn is BOTH a search match AND long enough to truncate AND currently the sticky header. Match data and jump-to-match still work correctly in this case; only that one visual cue is lost. Narrow, cosmetic-only, left unfixed — would need restructuring the truncation logic.
**Reads:** Cache turn lists, expand state dicts, pane dimensions, scroll offset, optional response_rid_map/copy_feedback/search_match_set/search_current_key/search_query/nav_out — all passed as arguments.
**Writes:** Returns 5-tuple (unchanged shape); mutates `nav_out` in place when given (`.clear()`-then-rewrite). No stdout, no file writes.
**Called by:** `panes/token_pane.py` (`format_cache_tracker`); `panes/token_search.py` (`_format_turn_header_line`, `_call_thinking_meta`, `_format_cache_call`, `_render_expanded_call_lines`); `workers/worker_format.py` (`format_cache_tracker`, `_format_k`); `proxy_display/format.py` (`_format_k`); `dev/click_ui/p2_copy_click_probe.py`, `dev/display/A_format_cache_tracker_proof.py` (test/proof callers).
**Calls out:** `utils` (`append_copy_symbol`, `highlight_query_in_line`), `search_bar` (`_BG_RESTORE_SENTINEL`).
Private helpers (same module): `_fmt_rl_reset_time`, `_render_expanded_call_lines` (+ `_render_usage_extras_lines`, `_render_rate_limit_lines`, `_render_content_block_lines`), `_compute_cache_viewport`, `_call_thinking_meta`, `_format_turn_header_line`, `_render_call_line`, `_render_turn_lines`.

## Gotchas

- `highlight_stripped` wraps each **line** of a chunk individually (`DIM_YELLOW_BG{line}SOFT_RESET` per `\n`-separated segment) rather than wrapping the whole chunk as a single unit. Downstream renderers (`warnings_pane`) split the result on `\n` and apply a per-line zebra BG; a single wrap around the whole chunk would leave lines 2..N without `DIM_YELLOW_BG`, causing the zebra selector to miss them. `outer_bg` is appended once after the final highlighted line to restore the caller's row background.
- **(2026-09)** `shorten_tool_name` used to live in the now-deleted `formatter.py` (`from .formatter import shorten_tool_name`) — moved into `token_format.py` itself since this was its only remaining caller once the main pane (`formatter.py`'s other consumer) was removed. No import needed anymore; it's a plain module-level function here.
- `_format_k` and `_format_cache_call` use leading underscores but are exported and used by 4 external callers — they are effectively public despite the naming convention.
- `format_cache_tracker` returns a **5-tuple** `(visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count)` — NOT a string, and this shape is preserved even after the 2026-08-18 search-highlight additions (4 new params, all optional out-params/kwargs, zero new return values — `nav_out` is populated in place, not returned). The render loop (zebra/hover/truncation, plus `search_bar.resolve_bg_restore` per row) lives in `token_pane.py`. `initial_parent_count` counts collapsed parent rows before the viewport start; callers that don't need it unpack with `_, _, _, _, _`.
- Line content uses `SOFT_RESET` (`\033[39m`) instead of `RESET` (`\033[0m`) for inline FG-color endings. This lets the render loop inject a row-level BG without it being killed mid-line. Exception: `_format_cache_call` keeps `RESET` for `cc_broken` rows (error-BG ends at the line terminator, not mid-content).
