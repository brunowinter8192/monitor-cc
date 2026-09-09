# src/workers/

## Role

Workers pane package. Discovers active Claude Code worker sessions via tmux, extracts token and
tool-call data from their JSONL files, renders an interactive TUI pane with expand/collapse and
per-worker cache-tracker, and publishes the selected worker name via an IPC file for cross-pane
coordination with `proxy_display`. Touch this package when changing worker
discovery, worker status detection, or the workers pane display. Do NOT touch for proxy
rendering — that pane only reads the IPC selection file.

## Public Interface

- `run_workers_loop` — Workers pane event loop (entry point from `core.monitor`)
- `write_selection(worker_name)` — write selected worker name to IPC file (used by `proxy_display`)

## Flow

tmux session list → `worker_tmux` (discover workers, detect status, find JSONL path)
→ `worker_format` (extract tokens + tool calls from JSONL, render block)
→ `worker_pane` (event loop, IPC selection file write → stdout)

**(2026-09, helper-extraction milestone)** `worker_pane.py` split by concern into four sibling
modules to stay under the 400-LOC file limit and the 50-LOC helper-extraction threshold:
`worker_selection.py` (selection IPC path + write), `worker_clipboard.py` (clipboard
serialization), `worker_render.py` (pure viewport/row-render + jump-scroll computation),
`worker_search.py` (search on_commit reconstruction). Module-level STATE stays in `worker_pane.py`
exclusively (dev probes read/mutate it by attribute); every function that rebinds a scalar
global (`worker_selected_name`, `worker_hover_row`, `_worker_pane_width`) or performs a
monkeypatch-sensitive bare-name call (`find_worker_jsonl`, `copy_to_clipboard`, `read_keypress`)
also stays in `worker_pane.py` — see that module's own entry and `process-docs/proxy_display/`
(the prior milestone's proxy-display split, whose constraints this one mirrors) for the reasoning.

## Modules

### worker_tmux.py (94 LOC)

**Purpose:** Discover active Claude Code worker sessions via `tmux list-sessions`, detect per-worker status, and locate each worker's most recent session JSONL file.
**Reads:** tmux session list (via subprocess); tmux pane/window state for status detection; worker CWD from tmux env.
**Writes:** Nothing — returns worker dicts and JSONL paths.
**Called by:** `src/workers/worker_pane.py`, `src/proxy_display/worker_proxy_pane.py`
**Calls out:** `session_finder` (encode_project_path)

---

### worker_format.py (266 LOC)

**Purpose:** Extract token sums, context-% and tool call lists from worker JSONL files; render the full workers pane block with per-worker rows, status, context-%, model, token counts, and expanded cache tracker. `extract_worker_context_pct(jsonl_path)` scans assistant messages for the latest `cache_read_input_tokens` value and returns `(100 * (_WORKER_CONTEXT_WINDOW - cr)) // _WORKER_CONTEXT_WINDOW` as remaining context percentage (None if no JSONL data yet). `_WORKER_CONTEXT_WINDOW = 1000000` — flat 1M window, no per-model lookup; the worker fleet runs exclusively on 1M-context models (opus-4-8, sonnet-5, fable-5), haiku-4-5 (200k) is never a worker. **(2026-07-30) Copy symbol on both row kinds:** `format_workers_block` takes `copy_feedback: Optional[dict] = None` — a flat dict mixing `str` name keys (worker header row) and `(name,turn_idx,call_idx)` tuple keys (expanded cache-call rows). Header row: `append_copy_symbol(header_line, ..., pane_width)` when `copy_feedback` given. Cache rows: `_worker_cache_copy_feedback(copy_feedback, name)` filters the flat dict down to a `(turn_idx,call_idx)→expiry` sub-dict scoped to THIS worker (avoids cross-worker key collision — `format_cache_tracker`'s own key format is the 2-tuple, and multiple workers can be expanded simultaneously, each with independent turn/call indices) before passing it to `format_cache_tracker(..., copy_feedback=...)`. **(2026-07-30) `[LIVE]`/`[FROZEN]` badge as the freeze button:** `regions_out: Optional[dict] = None` param — when given, registers `regions_out['freeze'] = (start_col, end_col)` (COLUMN SPAN ONLY, no row — `format_workers_block` doesn't know the final phys_row, that's resolved by the caller after viewport clipping, see `worker_pane.py`), width-guarded (`pane_width` computed BEFORE the `if not workers:` early return, so both branches can use it): the badge text itself is pre-existing, ALWAYS rendered regardless; only the region registration is gated on whether it fits.

**(2026-08-18, rollout sub-milestone 5) Search-highlight embedding + composition with `format_cache_tracker`.** `format_workers_block` gains `search_match_set`/`search_current_key`/`search_query` — keys are worker-TAGGED (same shape `worker_pane.py`'s `_worker_search.matches` holds): bare `str` name (worker-level match — text is `name + purpose`), `(name, 'turn', turn_idx)`, or `(name, turn_idx, call_idx)` (REUSES the exact 3-tuple shape this module already built for cache rows — zero new shape). A worker-level match container-marks the `header_line` UNCONDITIONALLY (`marker+line+search_bar._BG_RESTORE_SENTINEL`, mirrors `token_format`'s turn-header treatment) — BEFORE `append_copy_symbol`, so the copy button stays outside the marked span. For the nested per-worker view, `_scope_matches_to_worker(matches, name)` / `_scope_current_key_to_worker(current_key, name)` strip the leading worker name and convert to `token_format`'s own shape (`('turn', idx)` / `(turn_idx, call_idx)`), filtered to keys belonging to THIS worker only — critical: a match belonging to a DIFFERENT worker must never highlight in this worker's own view — then thread straight into the EXISTING `format_cache_tracker(...)` call, which does 100% of the collapsed-container-mark / expanded-substring-highlight work internally. Zero new highlighting logic needed for the nested view itself.

**(2026-09, helper-extraction milestone) `format_workers_block` (was 121 LOC) split into helpers,
same output byte-for-byte:** `_register_freeze_region(regions_out, frozen, pane_width)` (the
freeze-badge column-span registration); `_build_worker_header_line(...)` (status/context-%/
spawned/model/tokens suffixes + search-mark + copy symbol — reads the new module constant
`_STATUS_COLORS`, hoisted out of the per-call dict literal the old body rebuilt every worker);
`_build_worker_purpose_line(purpose, is_expanded)`; `_render_worker_expanded_view(...)` (the
nested cache-tracker call + key re-tagging); `_render_worker_row(...)` (wires the previous three
together for one worker, including the trailing blank-line separator). `format_workers_block`
itself is now the top-level loop over `_render_worker_row` plus the empty-workers/freeze-region
setup. Byte-identical — verified via `dev/workers/format_byte_identity.py`.
**Reads:** Worker JSONL file (full read for token/tool extraction); worker list + expand/scroll state dicts (for rendering).
**Writes:** Nothing — returns token summary dict, tool call list, or formatted TUI string.
**Called by:** `src/workers/worker_pane.py`
**Calls out:** `jsonl`, `format` (token_format), `utils` (`append_copy_symbol`), `search_bar` (`_BG_RESTORE_SENTINEL`)
New private helpers (same module): `_register_freeze_region`, `_build_worker_header_line`,
`_build_worker_purpose_line`, `_render_worker_expanded_view`, `_render_worker_row` (2026-09).

---

### worker_selection.py (27 LOC, new 2026-09, split out of `worker_pane.py` — see `process-docs/proxy_display/` for the split-methodology precedent)

**Purpose:** Selection IPC — `get_selection_file_path(project_filter)` builds the
`/tmp/monitor_cc_selected_worker_<hash>.txt` path (md5 of the normalized project path, or
`'global'` when absent); `_write_selection(project_filter, name)` writes the selected worker name
to that path, or removes it when `name` is falsy. Both pure/self-contained — no module state.
Moved out of `worker_pane.py` verbatim; never referenced by exact name in any dev probe (only
called through it), so free to relocate. `worker_pane.py` imports both names (genuinely used
internally, not a re-export shim) so `..workers.worker_pane.get_selection_file_path` — the fixed
import path `proxy_display/worker_proxy_pane.py` uses — still resolves unchanged; `src/workers/__init__.py`'s own `from .worker_pane import ..., _write_selection as write_selection` line also needed no change for the same reason.
**Reads:** Nothing.
**Writes:** `/tmp/monitor_cc_selected_worker_<hash>.txt`.
**Called by:** `src/workers/worker_pane.py`; `src/proxy_display/worker_proxy_pane.py` (`get_selection_file_path`, via `worker_pane`)
**Calls out:** stdlib only (`hashlib`, `os`)

---

### worker_clipboard.py (40 LOC, new 2026-09, split out of `worker_pane.py`)

**Purpose:** `_serialize_workers(key, worker_turns)` — full untruncated clipboard text for a
worker-header row (`key: str`, identity + turn/call counts) or an expanded cache-call row
(`key: (name, turn_idx, call_idx)`, the call's cache stats + content blocks). Gained an explicit
`worker_turns: dict` parameter in the split (was a bare module-global read in `worker_pane.py`
before) — mirrors `proxy_pane_shared._serialize_proxy_entry(key, entries)`'s own explicit-argument
shape; both call sites in `worker_pane.py` (`_handle_workers_body_click`, `_handle_workers_key`)
now pass `worker_turns` explicitly. Never referenced by exact name in any dev probe (only its
effect, via `copy_to_clipboard`'s captured output).
**Reads:** Parameters only.
**Writes:** Nothing — returns a string.
**Called by:** `src/workers/worker_pane.py`
**Calls out:** stdlib only (`json`)

---

### worker_render.py (126 LOC, new 2026-09, split out of `worker_pane.py`)

**Purpose:** Pure viewport/row-rendering + jump-scroll helpers with no module state — every
function takes the caller's own dicts/scalars as explicit parameters and either returns a value
or mutates a passed-in dict/set in place (never a bare global). `_workers_terminal_size()` — raw
`(term.lines, term.columns)` (no `-1` adjustment, unlike `proxy_pane_shared._terminal_size`),
falling back to `(50, 80)` on `OSError`. `_compute_viewport(total_lines, content_height,
scroll_offset)` — clamp + `vp_start`, returning `(clamped_offset, vp_start)` for the caller to
write back to its own `worker_scroll_offset` global. `_render_workers_rows(...)` — the zebra/hover
background loop, mirrors `proxy_display.format._apply_row_backgrounds`'s shape; populates
`line_map_out`/`cache_line_map_out`/`copy_rows_out` in place, returns the rendered lines (search
bar NOT included — the caller prepends it). `_resolve_workers_hover_key(hover_row,
worker_cache_line_map, worker_line_map)` — moved from `worker_pane.py`, gained the two map
params instead of reading module globals. `apply_scroll(button, row, worker_cache_line_map,
worker_line_map, selected_name, worker_scroll_offsets)` — moved out of
`_handle_workers_mouse`'s wheel branch; safe to relocate since it has no scalar-global rebind
(only a `worker_scroll_offsets` item mutation). `compute_jump_scroll_offset(key, turns,
per_worker_expand, pane_width)` — moved out of `_jump_to_workers_match`'s tail (the
`format_cache_tracker(...,nav_out=...)` call + scroll-math), pure given its four inputs; returns
`None` when the nav target can't be resolved (caller only writes `worker_scroll_offsets[name]`
when non-`None`). None of these five are referenced by exact name in any dev probe.
**Reads:** Parameters only.
**Writes:** Nothing directly — mutates `line_map_out`/`cache_line_map_out`/`copy_rows_out`/`worker_scroll_offsets` arguments in place where documented above.
**Called by:** `src/workers/worker_pane.py`
**Calls out:** `constants`, `utils` (`truncate_visible`), `search_bar` (`resolve_bg_restore`), `format.token_format` (`format_cache_tracker`)

---

### worker_search.py (48 LOC, new 2026-09, split out of `worker_pane.py`)

**Purpose:** `workers_search_on_commit(state, workers, project_filter, pane_width, worker_turns,
load_turns_fn, jump_fn)` — the search bar's on_commit body (fires on Enter), moved out of
`worker_pane._workers_search_on_commit`. `worker_turns` is only populated for currently-EXPANDED
workers (see `worker_pane._refresh_workers_data`), so finding matches across ALL workers requires
force-parsing every listed worker's own JSONL — `load_turns_fn` and `jump_fn` are INJECTED
callables (same established pattern as `search_bar.handle_search_mouse_release`'s
`copy_to_clipboard` parameter) rather than direct imports: `load_turns_fn` must stay
`worker_pane._load_worker_turns`, whose own bare `find_worker_jsonl(...)` lookup resolves against
`worker_pane.py`'s module globals (`dev/pane_search/p7`'s monkeypatch target) — passing it by
reference here preserves that patchability without this module importing `find_worker_jsonl`
itself (which would NOT be patchable via `worker_pane.find_worker_jsonl = ...`, since it'd be a
separate, independently-bound name). Three match-key shapes: bare `name` (worker-level — text is
`name + purpose`), `(name,'turn',turn_idx)`, `(name,turn_idx,call_idx)` — the latter two wrap
`panes.token_search.build_token_search_matches`'s own (reused unmodified)
`('turn',idx)`/`(turn_idx,call_idx)` shapes with the worker name.
**Reads:** Parameters only.
**Writes:** Nothing directly — mutates `state`/`worker_turns` in place; calls `jump_fn()`.
**Called by:** `src/workers/worker_pane.py` (`_handle_workers_search_input`'s on_commit closure)
**Calls out:** `panes.token_search` (`build_token_search_matches`)

---

### worker_pane.py (398 LOC, split by concern 2026-09 — see `worker_selection.py`/`worker_clipboard.py`/`worker_render.py`/`worker_search.py` entries above and `process-docs/proxy_display/` for the split-methodology precedent)

**Purpose:** Workers pane event loop — keyboard/mouse input, periodic data refresh, viewport-clipped screen rendering, and IPC selection file write for cross-pane coordination. Structured as drain-refresh-render: `run_workers_loop` (ORCHESTRATOR) delegates to private helpers: `_poll_workers_input` (the per-tick input-drain loop, extracted 2026-09 — kept local since `read_keypress`/`read_mouse_event` are `dev/pane_error_log`'s monkeypatch targets on this module), `_handle_workers_mouse` (dispatches to `_handle_workers_body_click` for `button==0` body clicks and to `worker_render.apply_scroll` for the wheel), `_handle_workers_key` (drain keyboard: y-copy via `worker_render._resolve_workers_hover_key`, f-freeze, digit-select), `_refresh_workers_data` (tick-boundary `list_workers` + `worker_turns` build via `_parse_worker_turns`; partial-expand branch on input_changed), `_build_workers_output` (calls `format_workers_block` then `worker_render._workers_terminal_size`/`_compute_viewport`/`_render_workers_rows` for the viewport-clip + zebra/hover render, updates `worker_line_map`/`worker_cache_line_map`). `_workers_ram_state` is a module-level function (was a closure) registered with `register_ram_dump`. `_load_worker_turns(session)` / `_parse_worker_turns(jsonl_path)` (2026-09) consolidate the `find_worker_jsonl` → `read_new_lines` → `parse_jsonl_lines` → `extract_cache_turns` chain that `_workers_search_on_commit`, `_jump_to_workers_match`, and `_refresh_workers_data` used to repeat inline — `_load_worker_turns` is the ONE place doing the `find_worker_jsonl(...)` call (`dev/pane_search/p7`'s monkeypatch target), so it stays in this module and is passed BY REFERENCE into `worker_search.workers_search_on_commit` as an injected callable (mirrors `copy_to_clipboard`'s own injected-parameter pattern into `search_bar.handle_search_mouse_release`) — `worker_search.py` itself never imports `find_worker_jsonl`. **The `while True:` body has always been wrapped in its own `try/except Exception:`** — the reference pattern the other 7 pane loops were retrofitted to match (2026-07-31). **(2026-07-31 fix)** the except clause previously wrote the traceback with an inline `open('/tmp/monitor_cc_error.log', 'a')` — a failing write (disk full, permissions) would have propagated out of the except block itself and killed the loop, since nothing wrapped it; now delegates to `pane_error_log.log_pane_error('workers')`, which is exception-safe end to end and shared by all 8 pane loops. **(2026-07-30) Row click now selects, not just expands:** `_handle_workers_mouse` takes `project_filter` and, on a `worker_line_map` row hit (the pre-existing whole-row hit area — header line + purpose line, both mapped to the worker name in `format_workers_block`), now also sets `worker_selected_name = name` and calls `_write_selection(project_filter, name)` — matching `_handle_workers_key`'s digit-key branch exactly (toggle expand/collapse AND select, unconditionally, even when collapsing). Call site (`run_workers_loop`) passes `_monitor.active_project_filter`. No column check — the entire row width is the hit area; does not touch the `worker_cache_line_map` branch (cache-call toggle only, no selection) or the scroll/hover branches (different SGR button codes, no collision). Visual affordance unchanged — the row already renders `[idx] name` (CYAN) with a `>>` selected-prefix and `[+]`/`[-]` toggle, the same bracket-button convention used elsewhere; the click wiring makes that existing look-clickable marker actually clickable. **(2026-07-30) Copy-by-click on the ⎘ symbol, both row kinds:** `_handle_workers_body_click` (the `button==0` body of `_handle_workers_mouse` since the 2026-09 split) checks `col >= _worker_pane_width - 2 and row in worker_copy_rows` FIRST on BOTH the `worker_cache_line_map` branch and the `worker_line_map` branch (ahead of the milestone-1 select/expand logic) — a hit calls `copy_to_clipboard(_serialize_workers(key, worker_turns))`, never touches selection state. `worker_copy_rows` is one flat `Set[int]`, populated by `_build_workers_output` (via `worker_render._render_workers_rows`) by substring-detecting `⎘`/`✓` in the rendered line (same pattern as `proxy_display.format._apply_row_backgrounds`), so it naturally covers both row kinds with no type dispatch needed. **Bug found + fixed in the same pass:** `_handle_workers_key`'s `y`-branch used to try `resolve_parent_key(worker_line_map, hover_row)` first, falling back to `worker_cache_line_map` only on `None` — but `resolve_parent_key` walks backward to row 1, so it ALWAYS finds the owning worker's header/purpose row above any cache-call row, making the cache-map fallback dead code (`y` while hovering an expanded cache row silently copied the parent worker's identity summary, never the specific call). Replaced with `worker_render._resolve_workers_hover_key` (moved out of this module 2026-09, see that module's entry), which compares which map's nearest ancestor row is CLOSER to `hover_row` and prefers that one — correctly resolves a cache-row hover to the specific `(name,turn_idx,call_idx)` while still resolving a subsequent worker's own header/purpose hover to that worker's name (not a prior worker's trailing cache row). **(2026-07-30) Freeze badge as a clickable button:** `_handle_workers_mouse`'s SIGNATURE CHANGED — now takes `frozen: bool` and returns `(input_changed, updated_frozen)` instead of a bare bool (mirrors `_handle_workers_key`'s existing `(changed, frozen)` contract); `run_workers_loop`'s call site unpacks the tuple the same way it already did for the key path. On `button == 0`, checks `_worker_header_regions` (populated by `_build_workers_output` from `format_workers_block`'s `regions_out['freeze']` column span, resolved to a phys_row) FIRST, ahead of the cache/copy/select checks — a hit returns `(True, not frozen)`, exactly what pressing `f` does. The freeze line is always `all_lines[0]` in `format_workers_block`'s output, but this pane has NO separate fixed header (unlike `proxy_display`/`worker_proxy_pane`) — it's part of the same scrollable content everything else is, so `_build_workers_output` only registers the region when that first line actually survived viewport clipping (`vp_start == 0`); with many workers and default (bottom-anchored) scroll, the badge can scroll out of view like any other early row — a pre-existing characteristic of this pane's layout, not fixed here (deliverable was "don't redesign layout").

**(2026-08-18, rollout sub-milestone 5) Permanent row-1 search bar, mirroring `proxy_display/pane.py`'s reference implementation — the FIRST pane needing a genuine NEW reconstruction strategy.** `worker_turns` is only populated for currently-EXPANDED workers (see `_refresh_workers_data`), so the Enter callback force-parses EVERY listed worker's own JSONL — measured ~200ms for 9 real, multi-MB session files (`process-docs/pane_search/`), comfortably under budget. Three match-key shapes: bare `name` (worker-level), `(name,'turn',turn_idx)`, `(name,turn_idx,call_idx)` — the latter two wrap `panes.token_search.build_token_search_matches`' own (reused UNMODIFIED) `('turn',idx)`/`(turn_idx,call_idx)` shapes with the worker name; `format_workers_block` derives the per-worker SCOPED sub-set before threading into its own `format_cache_tracker` call (see `worker_format.py`'s entry). **(2026-09)** the reconstruction body itself moved to `worker_search.workers_search_on_commit` (see that module's entry) — `_handle_workers_search_input`'s `on_commit = lambda state: ...` closure captures THIS tick's `workers` list and `project_filter`, plus injects `_load_worker_turns` and a `_jump_to_workers_match` closure as callables — `search_bar.handle_search_input`'s generic `on_commit(state)` signature only ever passes `state`, so the extra context is captured at the closure site, not threaded through `search_bar.py` itself.

**Jump-to-match (`_jump_to_workers_match`) respects the dormant pane-level scroll — deliberately.** Every jump (Enter and every `n`/`N` step) auto-expands (`worker_expand_states[name] = True`) and auto-selects (`worker_selected_name` + `_write_selection`) the match's worker, uniformly across all 3 match levels (mirrors proxy's own jump-auto-expand). It NEVER touches `worker_scroll_offset` (the dormant pane-level bottom-anchor fail-safe — see this file's own pre-existing Gotcha below); if the matched worker is scrolled off the top of a long list, that's the same pre-existing limitation that already prevents any other means of reaching it (no wheel-scroll-up exists for the outer list either) — not something jump-to-match can or should work around. For a turn/call-level match, it computes `worker_scroll_offsets[name]` (the per-worker scroll the pane already fully supports) via `worker_render.compute_jump_scroll_offset` (2026-09, moved out of this function's own tail — see that module's entry), which runs a FRESH, self-contained `format_cache_tracker(turns, ..., nav_out=nav)` call at jump time (not through `format_workers_block`, and not from a cached last-render position) — deliberately never trusts `worker_turns`, which `_refresh_workers_data` clears EVERY POLL TICK for any worker not yet expand-gated: a match found at Enter-time for a worker not jumped to yet would otherwise have its cached turns evicted before a later `n`/`N` reaches it. `_jump_to_workers_match` always re-parses the target worker's JSONL fresh (via `_load_worker_turns`) and merges into `worker_turns[name]` immediately, so the very first render after the jump already shows correct content. Self-healing: if the matched worker vanished from the current `workers` list (or its JSONL can't be found), the jump is an inert no-op, not a crash.

**No worker-switch reset analog — considered, declined, documented as a design choice, not an oversight.** Every prior search-enabled pane (proxy/worker-proxy/tokens) tracks exactly ONE current session/worker, giving a single clean reset trigger (mirrored across 3 milestones: `pane.py`, `worker_proxy_pane.py`, `token_pane.py`). This pane shows ALL workers simultaneously — there is no equivalent single-item switch to reset on. The self-healing jump design above makes this safe: a stale match referencing a since-vanished worker becomes an inert no-op rather than showing wrong data.

**Collateral fix, same shape as the tokens pane:** `_build_workers_output`'s `LIGHT_RED_BG` (cc_broken row) detection changed from `line.startswith(LIGHT_RED_BG)` to `LIGHT_RED_BG in line` — a container-marked search match now prepends `marker` before it. **Found during this same pass, NOT fixed (pre-existing, unrelated to search):** the check was ALREADY dead for nested cache-call rows before this milestone — `format_workers_block` prepends a literal `"  "` (2 spaces) before every line `format_cache_tracker` returns (`all_lines.append(f"  {cl}")`), so a cc_broken row's `LIGHT_RED_BG` prefix was never actually at position 0 to begin with. Left as-is (out of scope — would need restructuring the indent, not a search-bar concern).
**Reads:** `_monitor.active_project_filter` (shared global state); stdin (keyboard/mouse); worker JSONL files via `worker_format` AND directly via `_load_worker_turns`/`_parse_worker_turns` (search reconstruction + jump-time re-parse), bypassing `worker_format.py`.
**Writes:** ANSI output to stdout; selected worker name to `/tmp/monitor_cc_selected_worker_<hash>.txt` (via `worker_selection._write_selection`); `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`); mutates `worker_copy_rows`, `_worker_copy_feedback_until`, `_worker_pane_width`, `_worker_header_regions`, `_worker_search` (query/focused/matches/match_set/current_idx/drag-select fields), `worker_expand_states`/`worker_turns`/`worker_scroll_offsets`/`worker_selected_name` (via jump-to-match, same targets `_handle_workers_mouse`/`_handle_workers_key` already mutate).
**Called by:** `src/core/monitor.py` (via `..workers.run_workers_loop`); `src/proxy_display/worker_proxy_pane.py` (imports `get_selection_file_path` — re-exported via this module's own `worker_selection` import, `write_selection` — re-exported via `src/workers/__init__.py`)
**Calls out:** `jsonl`, `input` (click_handler), `worker_selection`, `worker_clipboard`, `worker_render`, `worker_search`, `pane_error_log` (`log_pane_error`), `search_bar` (shared search-bar mechanics)

---

## State

`worker_pane.py` owns:
- `worker_expand_states: Dict[str, bool]` — expand/collapse state keyed by worker name
- `worker_scroll_offsets: Dict[str, int]` — intra-worker scroll position (for expanded cache-tracker, 15-line view); reset to 0 on expand
- `worker_scroll_offset: int` — dormant pane-level scroll int; always 0 after wheel routing moved to `worker_scroll_offsets`; kept as bottom-anchor for viewport fail-safe slice cap
- `worker_copy_rows: Set[int]` — phys_rows where ⎘/✓ is rendered (both worker-header and cache-call rows); cleared+rebuilt each `_build_workers_output` call
- `_worker_copy_feedback_until: Dict` — mixed-key (`str` name OR `(name,turn_idx,call_idx)` tuple) → expiry float for the ✓ flash
- `_worker_header_regions: Dict[Tuple[int,int,int], str]` — `(start_col,end_col,phys_row) → 'freeze'`; empty when the freeze badge (`all_lines[0]`) has scrolled out of the viewport; row is now `1 + _WORKERS_SEARCH_BAR_LINES` (was `1`) since 2026-08-18
- `_worker_search: search_bar.SearchState` (2026-08-18) — `.matches` holds worker-tagged keys (`str` name / `(name,'turn',turn_idx)` / `(name,turn_idx,call_idx)`); no session/worker-switch reset trigger exists for this pane, see the module entry above

Mutated by `run_workers_loop`'s private helpers (`_handle_workers_mouse`/`_handle_workers_body_click`, `_handle_workers_key`, `_refresh_workers_data`, `_build_workers_output`, `_handle_workers_search_input` via `worker_search.workers_search_on_commit`, `_jump_to_workers_match`) — all still defined in `worker_pane.py` itself (2026-09 split moved only the STATE-FREE computation out; every scalar-global rebind and monkeypatch-sensitive call stayed local, see that module's own entry) — no external mutators. `worker_scroll_offsets` read by `format_workers_block` in the same process.

## Gotchas

**`worker_scroll_offset` (pane-level int) is dormant.** Wheel 64/65 events write to `worker_scroll_offsets[name]` (per-worker dict), which `format_cache_tracker` reads to scroll the expanded REQ view. `worker_scroll_offset` stays permanently 0 — `vp_start = max(0, total_lines - content_height - worker_scroll_offset)` (was `pane_height`, now `content_height = pane_height - _WORKERS_SEARCH_BAR_LINES` since 2026-08-18) reduces to a bottom-anchor. The int is not removed because it anchors the `all_lines[vp_start:vp_start + content_height]` slice-cap that prevents terminal overflow with many workers. **(2026-08-18) Jump-to-match deliberately never touches it either** — see `worker_pane.py`'s own module entry for the reasoning.

**Safety-net error log:** `worker_pane.py` appends unhandled exceptions in its render loop to `/tmp/monitor_cc_error.log` — silent crash guard so the pane stays alive. Check this file when the workers pane appears frozen or blank without an obvious error on screen.
