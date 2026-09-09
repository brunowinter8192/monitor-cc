# src/panes/

## Role

Dedicated tmux pane event loops — each module owns one pane's poll cycle, stdin input handling, and ANSI screen output. These modules are spawned by `core/monitor.py` when `--mode` targets a specific pane (tokens, warnings). They run as the process main loop and never return. Touch this package to change what a pane displays, how it handles mouse/keyboard input, or its scroll/expand state. Do NOT add general formatting logic here — that belongs in `format/`.

## Public Interface

```python
from src.panes import run_tokens_loop      # token/cache tracker pane
from src.panes import run_warnings_loop    # tool errors pane
```

`panes/token_search.py` has no `__init__.py` export — imported directly by `token_pane.py`
(`from .token_search import build_token_search_matches`).

`panes/log_janitor.py` has no `__init__.py` export — imported directly by `token_pane.py`
(`from .log_janitor import cleanup_old_jsonl, sweep_eligible_specs`) and by
`dev/hook_smoke/test_log_janitor.py` (via `sys.path.insert`, bare `from log_janitor import`).

## Flow

```
core/monitor.run_monitor(mode=X)
  → lazy import from panes → run_X_loop()
      loop: poll data source
            handle stdin (keyboard/mouse via input.click_handler)
            render to stdout (ANSI escape sequences, full screen redraw)
```

## Modules

### token_pane.py (333 LOC)

**Purpose:** Token/cache tracker pane — incrementally reads session JSONL (via `cache_turns.build_cache_turns`), renders interactive expand/collapse/scroll view with CR/CC/D per request. Owns the zebra/hover/truncation render loop: calls `format_cache_tracker` for logical lines, then applies `ZEBRA_BG_A/B`, `HOVER_BG` priority, and `truncate_visible` per line. Loop follows drain-refresh-render pattern; private helpers `_tokens_ram_state`, `_handle_tokens_mouse`, `_handle_tokens_key`, `_refresh_tokens_data`, `_build_tokens_output` extracted from loop body. Also polls `_response` dual-log incrementally via `find_response_log_path` + `read_response_log` (from `proxy_display.parser`), accumulates `_response_rid_map: {request_id → headers}` for rate-limit display; resets on session change alongside other state. **(2026-07-31) The `while True:` body is wrapped in its own `try/except Exception:`** — an uncaught exception is caught, logged via `pane_error_log.log_pane_error('tokens')`, and the loop continues after `wait_for_input(INPUT_POLL_INTERVAL)`; `KeyboardInterrupt`/`SystemExit` still propagate, `finally: disable_mouse(); restore_terminal()` still runs. **(2026-07-30) Copy-by-click on the ⎘ symbol:** `format_cache_tracker` is called with `copy_feedback=_cache_copy_feedback_until` (button-region pattern, mirrors `proxy_display`'s `_proxy_copy_rows`); `_build_tokens_output` detects the rendered `⎘`/`✓` substring per row and populates `cache_copy_rows`. `_handle_tokens_mouse` checks `col >= _cache_pane_width - 2 and row in cache_copy_rows` FIRST (before the pre-existing expand-toggle) — a hit calls `copy_to_clipboard(_serialize_tokens(key))` and sets a 1.5s `✓`-flash entry, identical to the `y` key's `_serialize_tokens` call for the same row.

**(2026-09, panes-split milestone) `build_cache_turns` moved out to `cache_turns.py`** (see that module's own entry) — it was a pure JSONL-turn accumulation function two OTHER real modules (`proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`) import, a data concern rather than a pane concern; `token_pane.py` now imports it back (`from .cache_turns import build_cache_turns`) for its own use in `_refresh_tokens_data`. `run_tokens_loop` (was 67 LOC) and `_build_tokens_output` (was 53 LOC) both dropped under 50: `run_tokens_loop`'s input-drain dispatch (`read_keypress`/`read_mouse_event` bare-name calls) extracted into a same-module top-level `_poll_tokens_input()` — stays physically in this module because `dev/pane_error_log/p1_pane_loop_survives_exception_probe.py` and `dev/pane_search/p6_tokens_pane_parity_test.py` monkeypatch `read_keypress`/`setup_keyboard_input`/`enable_mouse`/`disable_mouse`/`restore_terminal` as attributes of `token_pane` itself, which only works for bare-name lookups made from code physically defined in this module; `_build_tokens_output`'s zebra/hover row-render loop extracted into `_render_tokens_rows(...)`, also same-module (no cross-module reuse case for it — the `Optional` note in the milestone brief explicitly said not to fold this loop with `warnings_render._render_warnings_rows` / `workers/worker_render._render_workers_rows` this round, see Gotchas). `_serialize_tokens`, `_handle_tokens_mouse`, `_handle_tokens_key`, and `_handle_tokens_search_release` all stay in this module for the same monkeypatch/bare-name reason (they call `copy_to_clipboard` bare-name).

**(2026-09) Window 0 is now the tokens pane at full width** (the main pane was removed entirely —
see `process-docs/main_pane/`). `run_tokens_loop`'s `_refresh_tokens_data` gained a `last_janitor_ts`
param/return threaded through the loop exactly like the old main pane's `run_main_loop` did: every
tick, once `now - last_janitor_ts >= 86400`, runs `log_janitor.cleanup_old_jsonl` over
`log_janitor.sweep_eligible_specs(Path(__file__).parent.parent / 'logs')` — the tokens pane is
always-active and runs from the main checkout (unlike the menubar bundle, which resolves the wrong
`logs/` path), the same property that made the main pane the janitor's original host; see
`process-docs/logging/log_janitor.md`.

**(2026-08-18, rollout sub-milestone 4) Permanent row-1 search bar, mirroring `proxy_display/pane.py`'s reference implementation** — `_tokens_search: search_bar.SearchState`, thin wrapper functions (`_handle_tokens_search_cancel`/`_input`/`_release`, `_render_tokens_search_bar`), `_tokens_search_on_commit` (Enter callback — data is ALWAYS fully loaded incrementally here, no windowing/reconstruction step unlike the proxy panes, so it just calls `token_search.build_token_search_matches` directly over `_cache_turns`; always re-runs, no unchanged-query gate), `_jump_tokens_search_match`/`_ensure_tokens_match_visible` (`n`/`N` — mirrors `core/monitor_display.py`'s simpler `ensure_match_visible` pattern, NOT the proxy panes' defer-to-next-render `_proxy_just_expanded` dance, since there's no lazy-load to interleave with a scroll here). `_ensure_tokens_match_visible` reads `_tokens_nav` (key → absolute line index + `'total_lines'`, populated fresh by `format_cache_tracker`'s `nav_out` param on every render — not part of `SearchState`, pane-specific) to compute a scroll offset the same way the main pane's `_search_all_line_offsets`/`_search_total_lines` do; relies on at least one prior render having populated it (same accepted staleness tolerance as the main pane's own design — positions don't depend on scroll/search state, only on `_cache_turns`/`cache_expand_states`).

**The sentinel bug, same class as the proxy pane.** `colors.ZEBRA_BG_A == ''` (2026-09 constants-split milestone — moved from `constants.ZEBRA_BG_A`) is the `chosen_bg` for every non-hovered, non-`LIGHT_RED_BG` row and every expanded-detail line. `format_cache_tracker` embeds search highlights with `search_bar._BG_RESTORE_SENTINEL` (not a hardcoded color) at construction time; `_build_tokens_output`'s own hand-rolled row loop calls `search_bar.resolve_bg_restore(line, chosen_bg)` right after `chosen_bg` is chosen (unconditional, no-ops when the sentinel isn't present) — exact same fix shape as `process-docs/pane_search/2026-08-18_highlight_flood_empty_bg_fix.md`. **Collateral fix in the same loop:** the pre-existing `LIGHT_RED_BG` (cc_broken row) detection changed from `line.startswith(LIGHT_RED_BG)` to `LIGHT_RED_BG in line` — a container-marked search match now prepends `marker` before `_format_cache_call`'s own `LIGHT_RED_BG` prefix, so a literal prefix-check would miss it when both conditions co-occur; a substring check still finds it, and is provably equivalent to the old prefix check whenever no marker is present (i.e. byte-identical for every non-search-match row).

**2-row header:** `format_cache_tracker`'s optional `sticky_header` (row 1 when scrolled, before this milestone) now shifts to row 2 — `_TOKENS_SEARCH_BAR_LINES = 1` (fixed) always wins row 1. `format_cache_tracker`'s own internal viewport reservation (`_compute_cache_viewport`'s `pane_height - 1`, reserved for the sticky-header slot whether used or not) is UNTOUCHED — `_build_tokens_output` computes `content_height = pane_height - _TOKENS_SEARCH_BAR_LINES` and passes THAT as `format_cache_tracker`'s own `pane_height` argument, same "caller subtracts its own header rows, the renderer's internal reservation stays put" convention the proxy panes already established. `phys_row` (this pane's own local row counter, no separate shift-dict-after-the-fact step needed since `cache_line_map`/`cache_copy_rows` are built fresh from the correct starting value every render) starts at `1 + _TOKENS_SEARCH_BAR_LINES + (1 if sticky_header else 0)`.

**Known limitation (documented, not fixed):** `_compute_cache_viewport`'s sticky-header truncation path can silently drop a search highlight in the narrow combination of "matching turn" + "long enough to truncate" + "currently the sticky header" — see `format/DOCS.md`'s `token_format.py` entry for the mechanism.
**Reads:** Session JSONL (incremental via `_cache_jsonl_position`); `_response` dual-log (incremental via `_response_log_pos`); shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`); mutates module-level `cache_expand_states`, `cache_line_map`, `cache_hover_row`, `cache_scroll_offset`, `cache_copy_rows`, `_cache_copy_feedback_until`, `_cache_pane_width`, `_cache_turns`, `_cache_jsonl_position`, `_response_log_pos`, `_response_rid_map`, `_tokens_search` (query/focused/matches/match_set/current_idx/drag-select fields), `_tokens_nav`.
**Called by:** `core/monitor.py` (mode dispatch).
**Calls out:** `panes.cache_turns` (`build_cache_turns`), `input.click_handler`, `format.token_format`, `core.monitor` (lazy, inside `_refresh_tokens_data`), `proxy_display.parser` (lazy: `find_response_log_path`, `read_response_log`), `log_janitor` (lazy, inside `_refresh_tokens_data`: `cleanup_old_jsonl`, `sweep_eligible_specs`), `pane_error_log` (`log_pane_error`), `panes.token_search` (`build_token_search_matches`), `search_bar` (shared search-bar mechanics), `utils.truncate_visible`.

---

### cache_turns.py (57 LOC, new 2026-09, panes-split milestone)

**Purpose:** `build_cache_turns(filepath, last_position, existing_turns) -> (turns, new_position)` — incrementally reads new lines from a session JSONL since `last_position`, parses them, and merges the resulting cache turns into `existing_turns`. Split out of `token_pane.py` (moved, not rewritten) because it is a pure JSONL-turn accumulation/merge function with no pane-loop or module-state coupling — a data concern, shared by `proxy_display/pane.py` and `proxy_display/worker_proxy_pane.py` in addition to `token_pane.py` itself, not a pane concern. `build_cache_turns` (was 53 LOC) dropped under 50 by extracting the duplicate-call merge block (the "last existing turn was incomplete — merge its api_calls with the fresh parse" branch) into `_merge_duplicate_turn(existing_turns, new_turns) -> list`.
**Reads:** Session JSONL file at `filepath` (via `jsonl.read_new_lines`/`jsonl.get_current_position`) — parameters only, no module state.
**Writes:** Nothing — returns `(turns, new_position)`; no mutation of `existing_turns`.
**Called by:** `panes/token_pane.py` (`_refresh_tokens_data`), `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`.
**Calls out:** `jsonl` (`read_new_lines`, `parse_jsonl_lines`, `extract_cache_turns`, `get_current_position`).

---

### token_search.py (35 LOC, new 2026-08-18, rollout sub-milestone 4)

**Purpose:** `build_token_search_matches(query, turns, pane_width, response_rid_map=None)` — the ordered list of match keys whose content matches `query` (case-insensitive). Mirrors `proxy_display/search.py`'s role/shape exactly (parallel structure across the two search-enabled pane families) — uses the REAL render functions (`token_format._format_turn_header_line`, `_format_cache_call`, `_render_expanded_call_lines`), not a duplicated serializer, so a match can never diverge from what `token_format.py` actually renders. For each turn: checks the turn's own header line (`('turn', turn_idx)` on match). For each call within it: FORCE-renders the call's header (fixed `▼` symbol, arbitrary — the glyph itself is never searched) plus its expanded detail content, ignoring the call's own `cache_expand_states` toggle (`(turn_idx, call_idx)` on match — the whole point is to also find matches in currently-collapsed calls). No `expand_states` param (unlike `proxy_display.search.build_search_matches`) — calls have no nested sub-toggles to force-expand as-is.
**Reads:** Turns list, pane width, optional response_rid_map — parameters only, no module state.
**Writes:** Nothing — returns `List[key]`.
**Called by:** `panes/token_pane.py` (`_tokens_search_on_commit`, on search-Enter).
**Calls out:** `utils` (`_ANSI_ESCAPE_RE`), `format.token_format` (`_format_turn_header_line`, `_format_cache_call`, `_call_thinking_meta`, `_render_expanded_call_lines`).

---

### warnings_pane.py (332 LOC)

**Purpose:** Warnings pane event loop and module-level state owner. Reads tool errors directly from the `_errors` dual-log (current proxy session, via `find_errors_log_path`) and from worker `_errors` dual-logs (via `scan_worker_errors_logs`); no proxy-log scanning. `_errors_record_to_display(rec)` converts raw `_errors` records to display dicts; `_read_errors_log(path, last_pos)` does incremental line-by-line reads. On project/session change, all state is reset and positions cleared. Loop follows drain-refresh-render pattern; private helpers `_warnings_ram_state`, `_handle_warnings_mouse`, `_handle_warnings_key`, `_refresh_warnings_data`, `_build_warnings_output` extracted from loop body. No zero_results, schema_warnings, or dedup sets. **(2026-07-31) The `while True:` body is wrapped in its own `try/except Exception:`** — an uncaught exception is caught, logged via `pane_error_log.log_pane_error('warnings')`, and the loop continues after `wait_for_input(INPUT_POLL_INTERVAL)`; `KeyboardInterrupt`/`SystemExit` still propagate, `finally: disable_mouse(); restore_terminal()` still runs. **(2026-07-30) Copy-by-click on the ⎘ symbol:** `_build_warnings_output` passes `copy_feedback=_error_copy_feedback_until, copy_rows_out=error_copy_rows` into `_format_warnings_pane`. `_handle_warnings_mouse` checks `col >= _error_pane_width - 2 and row in error_copy_rows` FIRST (before the pre-existing expand-toggle) — a hit calls `copy_to_clipboard(_serialize_warnings(ekey, tool_errors))` and sets a 1.5s `✓`-flash entry. This surfaced a pre-existing `y`-key bug (see `warnings_render.py`): `error_line_map` stores a bare int, but `_serialize_warnings` expected a `('error', idx)` tuple — `y` silently copied `''` for every row until fixed here. **(2026-07-30) `[refresh]` header button:** `_build_warnings_output` now computes `header = _format_warnings_header(_last_refresh_ts, pane_width, _warnings_header_regions)` ONCE and threads it into `_format_warnings_pane` as a plain `header: str` param (replacing that function's own internal `last_refresh_ts`-based header construction) — `_build_warnings_output` now returns `(output, header)`, and `run_warnings_loop`'s overdraw print reuses that SAME returned header instead of recomputing `_format_warnings_header` a second time with different args (which would have silently dropped the button on the overdraw pass).

**(2026-09, panes-split milestone) `run_warnings_loop` (was 71 LOC) dropped under 50** by extracting the input-drain dispatch (`read_keypress`/`read_mouse_event` bare-name calls) into a same-module top-level `_poll_warnings_input()` — stays physically in this module for the same monkeypatch reason as `token_pane.py`'s `_poll_tokens_input` (see that module's entry).

**(2026-08-18, rollout sub-milestone 6) Permanent row-1 search bar, mirroring `proxy_display/pane.py`'s reference implementation.** `_warnings_search: search_bar.SearchState`, full mechanics via thin wrappers (`_handle_warnings_search_cancel`/`_input`/`_release`, `_render_warnings_search_bar`). `_warnings_search_on_commit` (Enter callback) — data is ALWAYS fully loaded (`tool_errors` accumulates every polled error, no windowing) — calls `warnings_render.build_warnings_search_matches` directly; always re-runs. `_jump_warnings_search_match` (`n`/`N`) cycles `current_idx` only — this pane HAS real scroll infra (`error_scroll_offset`, wheel-driven) but n/N deliberately never touches it, matching the reduced scope also used for gpu/news (a real jump-to-match, auto-scrolling to the match, was judged out of scope for this bundled milestone — flagged, not silently omitted). `_handle_warnings_mouse` now checks `row == 1` (search bar) FIRST, then clears any lingering drag-selection before falling through to the (now row-shifted) `_warnings_header_regions` check, then copy/expand — `_warnings_header_regions`'s `[refresh]` region shifts from row 1 to row `1 + _WARNINGS_SEARCH_BAR_LINES` (rebuild-then-shift, mirrors `worker_proxy_pane.py`'s identical pattern) since `_format_warnings_header` itself still registers at its own row 1. `_build_warnings_output` passes `header_lines=1 + _WARNINGS_SEARCH_BAR_LINES` into `_format_warnings_pane` (generalizes what used to be a hardcoded single-header-row assumption there) and composes the 2-line `header` (`search_bar_line + '\n' + refresh_header`) fed into the PRE-EXISTING overdraw print unchanged.
**Reads:** `_errors` dual-log (incremental via `_errors_log_pos`); worker `_errors` dual-logs (incremental via `_worker_errors_positions`); shared state `monitor.active_project_filter`.
**Writes:** stdout (ANSI screen); `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`); rebinds `error_line_map` from render return; extends `tool_errors`; mutates `error_copy_rows`, `_error_copy_feedback_until`, `_error_pane_width`, `_warnings_header_regions`, `_warnings_search` (query/focused/matches/match_set/current_idx/drag-select fields).
**Called by:** `core/monitor.py` (mode dispatch).
**Calls out:** `input.click_handler` (module-level), `core.monitor` (lazy, inside `_refresh_warnings_data`), `proxy_display.parser` (lazy: `find_errors_log_path`, `scan_worker_errors_logs`, `proxy_session_id_for_project`, `get_proxy_session_start_ts`), `panes.warnings_render` (incl. `build_warnings_search_matches`), `search_bar` (shared search-bar mechanics).

---

### warnings_render.py (192 LOC)

**Purpose:** Pure rendering helpers — formats the warnings pane from caller-supplied state. `_format_warnings_pane(tool_errors, error_expand_states, error_hover_row, error_scroll_offset, pane_height, pane_width, header, copy_feedback=None, copy_rows_out=None, header_lines=1, search_match_set=None, search_current_key=None, search_query='')` returns `(rendered_str, new_error_line_map)` 2-tuple; no globals written. Takes the already-built `header: str` directly (caller-owned, see `warnings_pane.py`) instead of a `last_refresh_ts` float. When `copy_feedback` is given, appends a `⎘`/`✓` symbol to each error row via `utils.append_copy_symbol` and, when `copy_rows_out` is given, registers the row (substring-detected, same pattern as `proxy_display.format._apply_row_backgrounds`). `_format_warnings_header(last_refresh_ts, pane_width=80, regions_out=None)` builds the header line — **(2026-07-30)** now also appends a `[refresh]` button (WHITE, next to the pre-existing `[r]efresh · last: ... · polling: ...` text, unchanged) and, when `regions_out` given, registers its `(start_col,end_col,phys_row=1)` region (relative to its OWN top — shifted externally by `warnings_pane.py` since 2026-08-18) — but ONLY when it fits `pane_width`; when it doesn't, neither the button text nor the region is added. `_serialize_warnings(key, tool_errors)` formats clipboard output for a single error entry — **(2026-07-30 fix)** `key` is the bare `int` `error_line_map` actually stores, NOT the internal `('error', idx)` tuple `_format_warnings_pane`'s own `all_keys` uses.

**(2026-09, panes-split milestone) `_format_warnings_pane` (was 97 LOC) split into 3 helpers, itself now a thin orchestrator (31 LOC) under its own unchanged name:** `_build_one_warning_lines(err_idx, err, is_expanded, ...)` — the header line + optional expanded-detail lines for ONE error; `_build_warnings_lines(tool_errors, error_expand_states, ...)` — loops `_build_one_warning_lines` over the whole `tool_errors` list (or the "No warnings." placeholder), building `all_lines`/`all_keys`; `_render_warnings_rows(visible_lines, visible_keys, ...)` — the viewport-clipped zebra/hover row loop, carrying the `DIM_YELLOW_BG in line` check. The zebra/viewport loop DID move this round (unlike `token_pane.py`'s equivalent, which stayed in-module by default) — `dev/pane_search/p8_warnings_gpu_news_parity_test.py`'s `inspect.getsource` check on that literal substring was re-pointed from `_format_warnings_pane` to `_render_warnings_rows` in the same commit (Main-approved deviation from the milestone's default "don't fold render loops" stance, since this one has an explicit test dependency forcing the move rather than a discretionary reuse case).

**(2026-08-18, rollout sub-milestone 6) Search-highlight embedding — VERIFIED before assuming anything, per the milestone's own explicit requirement: the row-bg loop already used `DIM_YELLOW_BG in line` (substring), NOT `.startswith()` — unlike every prior pane in this rollout, no collateral fix was needed here.** `ZEBRA_BG_A == ''` DOES still apply (same shared constant as every other pane) — `search_bar.resolve_bg_restore(line, chosen_bg)` threaded into this same (already-correct) loop. `header_lines: int = 1` (new param, default preserves every pre-existing caller's exact behavior) generalizes what used to be a hardcoded `header_offset = 2` — `warnings_pane.py` passes `header_lines=2` (search bar + `[refresh]`). `search_match_set`/`search_current_key` hold a bare `int` err_idx (no nesting — one expand level, matches `error_line_map`'s own key shape). A match's header line is container-marked UNCONDITIONALLY (`marker+line+_BG_RESTORE_SENTINEL`, mirrors `token_format`'s turn-header treatment) — BEFORE `append_copy_symbol`. When expanded, the matching detail lines (`tool_call_input` k/v + the `full_text`/`highlight_stripped` body) ADDITIONALLY get browser-find substring-highlighted via `utils.highlight_query_in_line`. New `build_warnings_search_matches(query, tool_errors)` — the match key IS the bare `err_idx` — checks the underlying dict fields (`tool_name`, `worker_name`, `tool_call_input`, `full_text`) directly rather than re-rendering (this pane's render is trivial, no branching to risk diverging from), covering the FULL untruncated `full_text` regardless of collapsed/expanded display state.
**Reads:** All pane state passed as function arguments.
**Writes:** Nothing — returns rendered string and new line-map dict; no mutation of arguments (`copy_rows_out`/`regions_out`, if given, ARE mutated in place — cleared then repopulated, same contract as `proxy_display.format`'s `copy_rows_out`).
**Called by:** `panes.warnings_pane` (`run_warnings_loop`, `_build_warnings_output`, `build_warnings_search_matches`).
**Calls out:** `format.strip_marker` (`highlight_stripped`), `utils` (`truncate_visible`, `first_word_of_call`, `format_worker_prefix`, `append_copy_symbol`, `highlight_query_in_line`, `_ANSI_ESCAPE_RE`), `search_bar` (`_BG_RESTORE_SENTINEL`, `resolve_bg_restore`), `colors` (`YELLOW`, `RED`, `DIM`, `WHITE`, `RESET`, `HOVER_BG`, `ZEBRA_BG_A`, `ZEBRA_BG_B`, `SOFT_RESET`, `DIM_YELLOW_BG`, `SEARCH_MATCH_BG`, `SEARCH_CURRENT_BG` — 2026-09 constants-split milestone, re-pointed from `constants`), `constants` (`WARNINGS_POLL_INTERVAL`).

---

### log_janitor.py (167 LOC)

**Purpose:** `LogSpec` registry (12 entries) + `sweep_eligible_specs()` + `cleanup_old_jsonl(path)` — authoritative log inventory; 7-day JSONL sweep triggered from `token_pane.py::run_tokens_loop` every 24h. Moved here 2026-09 from `src/log_janitor.py` because `token_pane.py` is its only in-tree importer and no external entry point loaded it at root (see `process-docs/main_pane/` and `process-docs/logging/` for why it left the now-removed main pane originally).

**`LogSpec` field table:**

| Field | Meaning |
|---|---|
| `name` | identifier |
| `path_pattern` | relative to `src/logs/` (`gpu_pane` + `ccwrap` use explicit subdir paths) |
| `writer` | `"module.py:symbol"` |
| `purpose` | one-liner |
| `fmt` | `jsonl` / `log` / `bin+ansi` |
| `retention` | `7d-ts-records` / `count-30` / `7d-timed-rotation` / `count-10-pairs` / `unbounded-plain-text-low-volume` |
| `janitor_trigger` | `monitor-24h` / `proxy-start-bash` / `live-handler` / `ccwrap-caller` / `monitor-janitor-self` |
| `sweep_eligible` | `True` = `cleanup_old_jsonl` applies via the monitor-24h tick |

`monitor_sweep.log` is plain text (a few lines/day), so `cleanup_old_jsonl`'s ts-field parse does not apply and it has no rotation.
**Reads:** JSONL log files passed in as `path` arguments — no shared/module state.
**Writes:** Rewrites the passed JSONL file in place (drops records older than 7 days by `ts` field); exception-safe (never raises).
**Called by:** `panes/token_pane.py` (lazy import inside `_refresh_tokens_data`, gated every 24h); `dev/hook_smoke/test_log_janitor.py` (smoke test, direct import via `sys.path.insert`).
**Calls out:** none — stdlib only (`json`, `dataclasses`, `datetime`, `pathlib`).

---

## State

Each pane module owns its own module-level scroll/expand/hover state. State is NOT shared between panes. All panes read `monitor.active_project_filter` via `from ..core import monitor as _monitor`.

| Module | Key state vars |
|---|---|
| `token_pane` | `cache_expand_states`, `cache_line_map`, `cache_scroll_offset`, `cache_copy_rows`, `_cache_copy_feedback_until`, `_cache_turns`, `_cache_jsonl_position`, `_response_log_pos`, `_response_rid_map`, `_tokens_search` (`search_bar.SearchState`), `_tokens_nav` (key → line-idx cache for jump-to-match, refreshed every render) |
| `warnings_pane` | `tool_errors`, `error_expand_states`, `error_line_map`, `error_hover_row`, `error_scroll_offset`, `error_copy_rows`, `_error_copy_feedback_until`, `_warnings_header_regions`, `_errors_log_pos`, `_errors_log_path`, `_worker_errors_positions`, `_last_project_filter`, `_monitor_start_ts`, `_warnings_search` (`search_bar.SearchState`, 2026-08-18 — `.matches` holds bare `int` err_idx) |
| `warnings_render` | none (stateless — receives state as args, returns new values) |
| `token_search` | none (stateless — receives turns/pane_width as args, returns a match list) |

## Gotchas

- `from ..core import monitor as _monitor` is lazy in `_refresh_tokens_data` and `_refresh_warnings_data` (inside the helper, not the loop) to avoid circular imports. `load_historical_warnings` also imports lazily. `input.click_handler` imports are at module level (no circular-import risk).
- `build_cache_turns()` lives in `cache_turns.py` (moved out of `token_pane.py`, 2026-09 panes-split milestone) and is called by `proxy_display/pane.py` + `proxy_display/worker_proxy_pane.py` in addition to `token_pane.py` itself — a shared data-concern utility, not pane-loop code, which is exactly why it moved.
- Zebra/hover/truncation render loop lives in `_render_tokens_rows()` (called from `_build_tokens_output()`) in `token_pane.py`, NOT in `token_format.py`. `format_cache_tracker` returns a uniform 5-tuple `(visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count)` on all paths including empty turns (fixed 2026-05-12, commit `1f887ae`) — this shape is unchanged even after the 2026-08-18 search-highlight params (all optional, `nav_out` is an out-param not a return value).
- **(2026-09, panes-split milestone) `token_pane._render_tokens_rows`, `warnings_render._render_warnings_rows`, and `workers/worker_render._render_workers_rows` are three near-identical zebra/hover/copy-row render loops, NOT folded into one shared helper this round.** They differ in the search-match-substring-bg constant checked (`LIGHT_RED_BG` in the first two, `DIM_YELLOW_BG` in warnings) and in key handling (tuple keys vs bare-int/str keys). A genuine 3-way fold is a real candidate for a future milestone but was explicitly out of scope here — do not assume it already happened.
- `line_map` is built 1:1 in the render loop (one physical row per logical line). `visual_line_count` span-loops are gone — long lines are truncated at render time, not wrapped.
- **Header + Body pane contract:** panes that render a fixed header above a scrolling body MUST overdraw the header after printing the body, using `print(f"\033[H{header}\033[K", end='', flush=True)`. Without the overdraw, long body lines that wrap visually push the header off the top of the pane. Empty-body test cases pass trivially — always verify with real (non-empty) data. Applies to `warnings_pane`. Does NOT apply to `token_pane` (nor `core/monitor.py`) — both deliberately truncate every line (`truncate_visible`) rather than wrap, so the precondition that triggers the header-pushed-off-top symptom never occurs; `token_pane`'s new row-1 search bar was added WITHOUT an overdraw for this reason.
- `token_pane.py`'s `_handle_tokens_mouse` checks `row == 1` (search bar) FIRST, before the `cache_line_map` body lookup — no collision possible since `cache_line_map` never gets a row-1 entry (`phys_row` starts at `1 + _TOKENS_SEARCH_BAR_LINES + ...`, never 1).
- **(2026-08-18)** `warnings_pane.py`'s search-bar migration is the ONLY one in this rollout that needed ZERO sentinel-detection collateral fix — `warnings_render.py`'s `DIM_YELLOW_BG in line` check already used the substring form before this milestone touched it (verified by reading the source directly, per the milestone's own explicit requirement — see `process-docs/pane_search/`). `ZEBRA_BG_A == ''` still required `search_bar.resolve_bg_restore` in that same loop, same as every other pane.
- Wheel direction is inverted relative to `token_pane`: `warnings_pane` renders top-to-bottom (`visible = lines[offset:offset+height]`) so button 64 (wheel-up) DECREASES `error_scroll_offset` and 65 increases it; `token_pane` renders bottom-to-top and adds 3 on 64.
