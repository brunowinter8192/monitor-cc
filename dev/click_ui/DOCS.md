# dev/click_ui/

## Role

Regression coverage proving every tmux-pane control is reachable by mouse, not just keyboard:
worker selection, copy-by-click, pane-chrome buttons (freeze/refresh), and per-server digit-key
parity in the gpu pane. Touch this area when adding or changing a click region, a chrome button,
or a `_handle_*_mouse` dispatcher in `src/proxy_display/`, `src/workers/`, `src/panes/`,
`src/gpu_pane/`, or `src/news_pane/`. `md/` holds every run's report.

## Modules

### p1_worker_selection_click_probe.py (279 LOC)

**Purpose:** Proves, after one real render pass, that the worker-proxy header's per-worker click
regions (`_worker_proxy_header_regions`) and the workers pane's per-worker row hit area
(`worker_line_map`) each contain one entry per worker at plausible coordinates, and that a
synthetic click at those coordinates produces the same state change (IPC selection file, expand
state) as the corresponding digit key — including at pane widths that force a marker to straddle
a wrap boundary.
**Reads:** nothing external — seeds `src.proxy_display.worker_proxy_pane._worker_proxy_workers`
and calls `src.workers.worker_pane._build_workers_output` directly with synthetic worker lists.
**Writes:** `md/p1_worker_selection_click_probe_<timestamp>.md`; throwaway IPC selection files
under `/tmp/monitor_cc_selected_worker_<hash>.txt`, removed after each check.
**Called by:** none — run manually; re-run after any change to `_format_worker_proxy_header`,
`_handle_worker_proxy_mouse`, `_handle_worker_proxy_key`, `worker_line_map`/
`format_workers_block`, `_handle_workers_mouse`, or `_handle_workers_key`.
**Calls out:** `src.proxy_display.worker_proxy_pane`, `src.workers.worker_pane` — loaded via
`importlib.import_module`.

---

### p2_copy_click_probe.py (281 LOC)

**Purpose:** Proves, per pane (tokens, warnings, workers), that after one real render pass the
copy-row registry contains an entry for every copyable row, and a synthetic click on the symbol
column copies exactly the same string the `y` key produces — both paths run through the real
serializer, compared against each other. Also a pure-function width-guard regression
(`utils.append_copy_symbol`) and a render-integration width-guard check per pane.
**Reads:** nothing external — seeds `_cache_turns`/`tool_errors`/`worker_turns` with synthetic
data; `copy_to_clipboard` is monkeypatched to a capturing stub.
**Writes:** `md/p2_copy_click_probe_<timestamp>.md`; one throwaway IPC selection file under
`/tmp/monitor_cc_selected_worker_<hash>.txt`, removed after the check.
**Called by:** none — run manually; re-run after any change to `append_copy_symbol`,
`format_cache_tracker`, `_format_warnings_pane`, `_serialize_warnings`, `format_workers_block`,
`_resolve_workers_hover_key`, or any pane's `_handle_*_mouse`/`_handle_*_key`.
**Calls out:** `src.panes.token_pane`, `src.format.token_format`, `src.panes.warnings_pane`,
`src.panes.warnings_render`, `src.workers.worker_pane`, `src.utils` — loaded via
`importlib.import_module`.

---

### p3_button_click_probe.py (330 LOC)

**Purpose:** Proves, per pane (workers freeze, warnings refresh), that after one real render pass
the chrome-button region is registered at a plausible coordinate, a synthetic click produces the
same state change as the corresponding key (`f`/`r`), the freeze badge reflects pre-click state,
a too-narrow pane registers no region, and each pane's pre-existing click handling (row-select,
expand/copy) still works with the header-check ahead of it. Also covers the proxy pane's
permanent search-bar header: `_build_proxy_output` returns row 1 with the search bar baked in, row
1 is not a body key, and expand/collapse/copy/scroll/`_undo_proxy_expand` all still work at the
shifted rows.
**Reads:** nothing external — seeds `tool_errors`/synthetic `workers` list/`proxy_entries`
directly.
**Writes:** `md/p3_button_click_probe_<timestamp>.md`; one throwaway IPC selection file under
`/tmp/monitor_cc_selected_worker_<hash>.txt`, removed after the check.
**Called by:** none — run manually; re-run after any change to `_format_warnings_header`,
`_handle_warnings_mouse`/`_handle_warnings_key`, `format_workers_block`, `_handle_workers_mouse`/
`_handle_workers_key`, or `_build_proxy_output`/`_handle_proxy_mouse`/`_undo_proxy_expand`.
**Calls out:** `src.panes.warnings_pane`, `src.panes.warnings_render`, `src.workers.worker_pane`,
`src.workers.worker_format`, `src.proxy_display.pane`, `src.proxy_display.format` — loaded via
`importlib.import_module`.

---

### p4_gpu_news_button_probe.py (333 LOC)

**Purpose:** Proves gpu's digit keys 1-9 need no dedicated button — the pre-existing per-server
button fires the identical `rag-cli` subprocess call as `_toggle_server(idx, presets)` (what the
digit key calls), for both a stopped and a running+healthy preset. Also proves the gpu/news
`[refresh]` header buttons: region registered on row 1, disjoint from every pre-existing button
region, dispatched before the pre-existing `_fire_button`/`_fire_pipeline` branch; narrow panes
get no `[refresh]` text/region; news's pre-existing `[run pipeline]` click still fires. Sweeps
pane widths across each pane's button-visibility crossover (gpu 27, news 38) to prove the
decorative rule shrinks before `[refresh]` is dropped.
**Reads:** nothing external — seeds synthetic gpu preset dicts and news status dicts;
`gpu_pane.status.PRESET_NAMES` is monkeypatched to a fixed list; `subprocess.Popen` is
monkeypatched to a capturing stub (no real `rag-cli`/news-pipeline process ever launched).
**Writes:** `md/p4_gpu_news_button_probe_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to `_render_pane` (either pane),
`_toggle_server`, `_fire_button`, `_fire_pipeline`, `utils.compute_header_rule_len`, or either
loop's inline mouse-dispatch snippet.
**Calls out:** `src.gpu_pane.pane`, `src.news_pane.pane` — loaded via `importlib.import_module`.

---

## Gotchas

**Both gpu and news panes keep `_render_pane`'s own row numbering unshifted** (relative to its
own top); the search-bar row is prepended and `_button_regions` shifted externally, in each pane's
loop, after `_render_pane` returns. A probe calling `_render_pane` directly (as this suite does)
sees the unshifted numbering — dispatch-loop-level assertions must account for the external
shift separately.

**The worker-proxy header's row-1 slot is reserved for the search bar** — a header-marker click
probe must apply `_WP_SEARCH_BAR_LINES`'s shift itself when calling `_format_worker_proxy_header`
directly (bypassing `_build_worker_proxy_output`, which performs the shift internally).
