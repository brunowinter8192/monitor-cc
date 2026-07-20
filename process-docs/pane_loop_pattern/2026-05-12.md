# Pane-Loop Split Pattern — Established 2026-05-12

## Problem

Five pane event-loop functions exceed the 100 LOC heuristic (target: ~30-60 LOC per loop function + 3-5 small helpers):

| File | Function | LOC (pre-refactor) |
|---|---|---|
| `src/proxy_display/worker_proxy_pane.py` | `run_worker_proxy_loop` | 223 → **46** (done) |
| `src/panes/warnings_pane.py` | `run_warnings_loop` | 205 → **51** (done) |
| `src/workers/worker_pane.py` | `run_workers_loop` | 182 → **55** (done) |
| `src/proxy_display/pane.py` | `run_proxy_loop` | 160 → **47** (done) |
| `src/panes/token_pane.py` | `run_tokens_loop` | 118 → **45** (done) |

`run_workers_loop` was refactored as proof-of-concept (commit `f1b8186` on branch `refactor-pane-loop-pattern`, 2026-05-12). The remaining 4 loops are follow-up work for subsequent workers.

## Established Pattern: drain → refresh → render

Every pane loop follows this structural skeleton:

```
INIT:
    register_ram_dump(pane_name, _<pane>_ram_state)
    last_output = None
    last_data_refresh = 0.0
    [pane-specific vars]
    setup_keyboard_input()
    enable_mouse()

try:
    while True:
        [try/except only in workers — error log guard]
        input_changed = False

        # DRAIN: read all pending stdin events
        while True:
            char = read_keypress()
            if char is None:
                break
            if char == '\033':
                event = read_mouse_event(char)
                if event is not None:
                    if _handle_<pane>_mouse(*event[, ctx]):
                        input_changed = True
            else:
                changed[, state] = _handle_<pane>_key(char[, ctx])
                if changed:
                    input_changed = True

        # REFRESH: tick-boundary data refresh
        now = time.time()
        data[, input_changed, last_data_refresh] = _refresh_<pane>_data(
            [data,] now, [frozen,] input_changed, last_data_refresh, [ctx]
        )

        # EXTRA STATE (only proxy, worker_proxy): copy-flash expiry
        # _copy_feedback_until = {k: v for k, v in _copy_feedback_until.items() if v > now}
        # if _copy_feedback_until:
        #     input_changed = True

        # RENDER
        if input_changed:
            output = _build_<pane>_output(data[, ctx])
            if output != last_output:
                print("\033[2J\033[3J\033[H", end='', flush=True)
                if output:
                    print(output)
                last_output = output

        wait_for_input(INPUT_POLL_INTERVAL)
finally:
    disable_mouse()
    restore_terminal()
```

## Helper Shapes (universal)

| Helper | Signature | Returns | Mutates (globals) |
|---|---|---|---|
| `_<pane>_ram_state()` | `() -> list` | state snapshot | — |
| `_handle_<pane>_mouse(button, col, row[, ctx])` | positional ints + optional context | `bool` input_changed | hover_row, expand_states, scroll_offsets |
| `_handle_<pane>_key(char[, ctx])` | char + optional context | `(bool, [state_out])` | expand_states, scroll_offsets, selected_name |
| `_refresh_<pane>_data([data,] now, [frozen,] input_changed, last_data_refresh[, ctx])` | see sig | `([data,] bool, float)` | turns/entries, selected_name |
| `_build_<pane>_output([data,] [ctx])` | data + optional context | `str` ANSI output | `*_line_map`, scroll_offset clamp |

**Key rules:**
- Helpers write module-level globals but do NOT mutate their arguments (new data object returned, not argument mutated in place)
- `_<pane>_ram_state` is module-level (not a nested closure) — reads globals directly, no closure variables needed
- Section structure in each file: INFRASTRUCTURE → ORCHESTRATOR (`run_<pane>_loop`) → FUNCTIONS (callees first: low-level utilities, then `_ram_state`, then `_handle_mouse`, `_handle_key`, `_refresh_data`, `_build_output`)

## workers (DONE — reference implementation)

File: `src/workers/worker_pane.py` — commit `f1b8186`

| Helper | LOC |
|---|---|
| `_workers_ram_state()` | 11 |
| `_handle_workers_mouse(button, col, row)` | 40 |
| `_handle_workers_key(char, workers, frozen, project_filter)` | 24 |
| `_refresh_workers_data(workers, now, frozen, input_changed, last_data_refresh, project_filter)` | 32 |
| `_build_workers_output(workers, frozen)` | 49 |
| `run_workers_loop()` (slim skeleton) | 55 |

**workers-specific variants:**
- Inner `try/except` wrapping the full loop body → stays in `run_workers_loop` (error log at `/tmp/monitor_cc_error.log`)
- `frozen` flag: owned by loop, flows through `_handle_workers_key` (return) and `_refresh_workers_data` (gate)
- `_handle_workers_key` takes `workers: list` for digit-key index lookup
- Mouse handler does NOT need `workers` (no digit-key in mouse path) — `col` unused but kept for signature consistency with other pane mouse handlers
- `_refresh_workers_data` returns new `workers` list on tick-boundary (from `list_workers()`); argument `workers` only used in the `input_changed` partial-expand branch (read-only)
- `worker_scroll_offset` (dormant int) clamped in `_build_workers_output` — still kept per Gotchas (anchors viewport slice cap)

## Remaining loops — fit check and per-loop variants

### `run_tokens_loop` (118 LOC) — DONE (commit `d4d2345`, 2026-05-12)

**Fit:** Clean. No keyboard handler. Simplest of the 5.

**Helpers to extract:**
- `_tokens_ram_state()` — 9 entries
- `_handle_tokens_mouse(button, col, row)` — click expand/collapse, wheel scroll, hover; NO copy-button (tokens pane uses `y` not copy-button)
- `_handle_tokens_key(char)` — `y` copy only; no freeze, no digit keys
- `_refresh_tokens_data(now, input_changed, last_data_refresh)` — JSONL incremental read + session-change detection (filepath != `_cache_current_filepath` reset block)
- `_build_tokens_output()` — `format_cache_tracker` + zebra/hover/truncation loop + sticky-header

**Variant:** `_handle_tokens_mouse` does NOT need `col` (no copy-button). Keep for consistency.

---

### `run_proxy_loop` (160 LOC) — DONE (commit `fe100b2`, 2026-05-12)

**Fit:** Mostly clean. Two cross-phase complications.

**Helpers to extract:**
- `_proxy_ram_state()`
- `_handle_proxy_mouse(button, col, row)` — includes copy-button click (col ≥ pane_width-2), lazy-load on expand, sets `_just_expanded` module-level sentinel
- `_handle_proxy_key(char)` — `y` only (hover+y, no freeze or digit keys); can keep as inline in loop since it's 5 lines
- `_refresh_proxy_data(now, input_changed, last_data_refresh)` — session-change reset, periodic full reparse (`_last_full_parse_ts`), `parse_proxy_log_isolated`, `build_cache_turns`
- `_build_proxy_output()` — `format_proxy_block` + auto-scroll second pass if `_just_expanded` is set

**Variant — `just_expanded`:** In proxy loop, `just_expanded` is a local var shared between input handling and render. Two options, both clean:
- (A) Module-level sentinel `_proxy_just_expanded: Optional = None` — mouse handler sets it, render reads + clears it
- (B) `_handle_proxy_mouse` returns `(input_changed, just_expanded_key)` — caller passes it to `_build_proxy_output`
- Recommendation: (A) is simpler for the render function signature; avoids threading the value through the call chain.

**Variant — copy-flash:** 3-line cleanup block between refresh and render. Keep inline in loop body (no helper needed — too small).

---

### `run_warnings_loop` (205 LOC) — DONE (commit `d4d2345`, 2026-05-12)

**Fit:** Clean. Refresh is the complex part (6 merged sources).

**Helpers to extract:**
- `_warnings_ram_state()`
- `_handle_warnings_mouse(button, col, row)` — clicks two line maps (`error_line_map`, `zero_result_line_map`); wheel direction inverted vs other panes (top-to-bottom viewport: wheel-up DECREASES offset)
- `_handle_warnings_key(char)` — `y` (copy from two maps), `r`/`R` (sets `_force_refresh = True`)
- `_refresh_warnings_data(now, input_changed, last_data_refresh)` — `_force_refresh` flag, project-change reset (6 state clears), truncation detection, `parse_proxy_log` + `scan_worker_logs` + error/zero-result scanning + schema-warning inline processing
- `_build_warnings_output()` — `_format_warnings_pane` (returns tuple including new line maps), header overdraw

**Variant — `_force_refresh`:** module-level bool, written by `_handle_warnings_key`, read+reset by `_refresh_warnings_data`. Stays module-level — no threading needed.

**Variant — render returns new line maps:** `_format_warnings_pane` returns `(output, error_line_map, zero_result_line_map)`. Assign back to module-level globals in `_build_warnings_output`.

**Variant — header overdraw:** after the standard `print(output)`, warnings pane overdraws the header with `print(f"\033[H{_format_warnings_header(...)}\033[K", ...)`. Keep inside `_build_warnings_output` or inline in the render guard block in the loop.

---

### `run_worker_proxy_loop` (223 LOC) — DONE (commit `fe100b2`, 2026-05-12)

**Fit:** Mostly clean. Most complex render of the 5 due to header+body split.

**Helpers to extract:**
- `_worker_proxy_ram_state()`
- `_handle_worker_proxy_mouse(button, col, row)` — copy-button (same as proxy), lazy-load, sets `_wp_just_expanded` module-level sentinel
- `_handle_worker_proxy_key(char)` — digit keys (worker switch → IPC write + `_worker_proxy_force_reload = True`); no `y` or `f`
- `_refresh_worker_proxy_data(now, input_changed, last_data_refresh)` — reads IPC selection file, `list_workers`, worker-name change detection + full reset, periodic reparse (`_worker_proxy_last_full_parse_ts`), `_parse_log_file_isolated`, `build_cache_turns`
- `_build_worker_proxy_output()` — header + `visual_line_count` + `body_hover` adjustment + `format_proxy_block` + line_map shift by `header_lines` + auto-scroll second pass if `_wp_just_expanded`

**Variant — header+body split:** `_build_worker_proxy_output` reads current worker from IPC file (same read as refresh), computes `header_lines = visual_line_count(header, pane_width)`, offsets `body_hover` and `content_height`, calls `format_proxy_block` for body, then shifts `worker_proxy_line_map` and `_worker_proxy_copy_rows` by `header_lines`. Second `format_proxy_block` call for auto-scroll if `_wp_just_expanded`. Most complex render helper of the batch.

**Variant — copy-flash, force-reload:** identical to proxy pane patterns.

## Ordering constraint (all loops)

Input handler reads `*_line_map` and `*_cache_line_map` that were populated by the PREVIOUS iteration's `_build_*_output`. Ordering drain → refresh → render must be preserved. No issue — it's the natural sequence.

## Implementation note for next workers

Each remaining loop should be a standalone worker task. The pattern is fully established — no need to re-derive. Steps per loop:
1. Read the loop file in full
2. Annotate line ranges for each phase (input/refresh/render/wait)
3. Extract helpers per the shapes above, respecting the per-loop variants documented here
4. Move `_ram_state` closure to module level
5. Restructure file: INFRASTRUCTURE → ORCHESTRATOR → FUNCTIONS (callees before callers)
6. AST check + smoke test `_build_*_output(empty_data, ctx)` + caller grep
7. Update DOCS.md LOC + Purpose

## Notes from Worker A implementation (tokens + warnings, 2026-05-12)

**click_handler lazy → module-level:** `warnings_pane.py` previously imported `input.click_handler` lazily inside `run_warnings_loop`. Moved to module-level INFRASTRUCTURE (matching `token_pane.py`). No circular import risk. Worker B should apply the same move to `proxy_display/pane.py` and `worker_proxy_pane.py` if they also have lazy click_handler imports.

**`_handle_*_key` always-False case:** `_handle_tokens_key` returns `False` for every key (`'y'` does not trigger a redraw). This is correct — the helper is still extracted for pattern consistency and extensibility. `else: if _handle_tokens_key(char): input_changed = True` is fine even when the helper always returns False.

**`_refresh_*_data` LOC reality:** `_refresh_warnings_data` came out at ~103 LOC (estimate was ~80). The two reset blocks (project-change + file-truncation) account for the extra lines. Single-responsibility still applies — no split warranted. Worker B should expect similar overruns for `_refresh_worker_proxy_data` given its comparable complexity (IPC file read, `list_workers`, name-change reset, full-parse timer, `build_cache_turns`).

**`format_cache_tracker` empty-turns footgun:** returns 4-tuple on empty turns (`[line], [None], None, 0`) but 5-tuple on the normal path. The 5-value unpack in `_build_tokens_output` will raise `ValueError` if called before the first JSONL data arrives. Pre-existing bug, not introduced by this refactor. Documented in `src/panes/DOCS.md` Gotchas. Worker B's `format_proxy_block` should be checked for similar edge-case return-value mismatches before committing.

**Smoke test strategy:** `_build_*_output()` with completely empty module state works for warnings (renders an empty pane). For tokens, the `format_cache_tracker` empty-turns bug means you need at least one minimal turn in `_cache_turns` to avoid the ValueError. Use `tp._cache_turns = [{'prompt': 'test', 'timestamp': '', 'api_calls': []}]` before calling.

## Notes from Worker B implementation (proxy + worker_proxy, 2026-05-12)

**`just_expanded` module-level sentinel confirmed:** Both `pane.py` (`_proxy_just_expanded`) and `worker_proxy_pane.py` (`_wp_just_expanded`) use Approach A from the Phase A spec. Mouse handler sets the sentinel on expand-click; `_build_*_output` reads it, runs auto-scroll second pass if needed, then clears it unconditionally at function end. No threading through call chain. The expand-click path always sets `input_changed = True` in the same handler invocation, guaranteeing render fires and the sentinel is cleared in the same iteration.

**`_handle_proxy_key` absent:** No `else:` branch in `run_proxy_loop`'s drain loop. hover+y was removed prior to this refactor (copy-button is the sole copy mechanism per DOCS.md). Drain loops with zero keyboard handlers need no `_handle_*_key` helper — pattern spec's `else:` branch is optional.

**`_build_worker_proxy_output` returns `(output, header)` tuple:** Worker-proxy pane has a header-overdraw step after the main `print(output)`: `print(f"\033[H{header}\033[K", ...)`. Returning `(output, header)` from the build helper keeps print logic in the loop (pattern-consistent) while making `header` available for the overdraw without re-computing it. Future reusers: any pane with a post-render overdraw step should use the same tuple-return pattern rather than storing header in a module global.

**`monitor` as context parameter:** Proxy and worker-proxy refresh/build helpers accept `monitor` as a positional `ctx` parameter (pattern spec's `[, ctx]`). Reason: helpers need `monitor._get_newest_main_session()`, `monitor._get_session_start_ts()`, `monitor.get_main_session_files()`, `monitor.active_project_filter` — the full module reference, not a single extracted value. Workers_pane used `project_filter: str` as ctx; proxy panes use the whole module. Both are valid — pass the narrowest ctx that covers all helper needs.

**`_refresh_worker_proxy_data` force-reload-OR-tick gate:** `if not _worker_proxy_force_reload and now - last_data_refresh < POLL_INTERVAL: return input_changed, last_data_refresh` — the gate checks force_reload first, bypassing the tick when digit-key selection changed. `_worker_proxy_force_reload = False` is the first action inside the gate body. Other refresh helpers use tick-only gates; this is the only one with a bypass flag.

**`get_selection_file_path` + `write_selection` moved to INFRASTRUCTURE:** Previously imported inside `run_worker_proxy_loop`. Safe to move to module-level (source is `workers.worker_pane` / `workers.__init__`, no circular import risk). Applied same principle as Worker A's `click_handler` migration. `click_handler` was already at module level in both proxy pane files — no migration needed there.

**`format_proxy_block` clears `line_map` internally:** `format.py` line 204: `line_map.clear()` before populating. This means passing an already-shifted map to the second-pass call in `_build_worker_proxy_output` is safe — it gets cleared and repopulated with unshifted body-row values, then the shift is re-applied. Verified via source read before implementing.
