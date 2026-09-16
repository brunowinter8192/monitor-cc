# dev/click_ui/

## Role

Regression coverage proving every tmux-pane control is reachable by mouse, not just keyboard:
worker selection, copy-by-click, pane-chrome buttons (refresh), and per-server digit-key
parity in the gpu pane. Touch this area when adding or changing a click region, a chrome button,
or a `_handle_*_mouse` dispatcher in `src/proxy_display/`, `src/workers/`, `src/panes/`,
`src/gpu_pane/`, or `src/news_pane/`. `md/` holds every run's report.

## Modules

### p1_worker_selection_click_probe.py (313 LOC)

**Purpose:** Proves, after one real render pass, that BOTH worker panes' header click-region
tables (`_worker_proxy_header_regions`, `_worker_tokens_header_regions` — built by the shared
`workers.worker_switch_header.format_worker_switch_header`) each contain one entry per worker at
plausible coordinates, and that a synthetic click at those coordinates produces the same state
change (IPC selection file) as the corresponding digit key — including at pane widths that force
a marker to straddle a wrap boundary, swept down to worker_tokens_pane's real 34%-of-window share.
**Reads:** nothing external — seeds `src.proxy_display.worker_proxy_pane._worker_proxy_workers`
and `src.workers.worker_tokens_pane._worker_tokens_workers` directly with synthetic worker lists.
**Writes:** `md/p1_worker_selection_click_probe_<timestamp>.md`; throwaway IPC selection files
under `/tmp/monitor_cc_selected_worker_<hash>.txt`, removed after each check.
**Called by:** none — run manually; re-run after any change to `workers.worker_switch_header`,
`_handle_worker_proxy_mouse`/`_handle_worker_proxy_key`, or
`_handle_worker_tokens_mouse`/`_handle_worker_tokens_key`.
**Calls out:** `src.proxy_display.worker_proxy_pane`, `src.workers.worker_tokens_pane` — loaded
via `importlib.import_module`.

---

### p2_copy_click_probe.py (269 LOC)

**Purpose:** Proves, per pane (tokens, warnings, worker-tokens), that after one real render pass the
copy-row registry contains an entry for every copyable row, and a synthetic click on the symbol
column copies exactly the same string the `y` key produces — both paths run through the real
serializer, compared against each other. Also a pure-function width-guard regression
(`utils.append_copy_symbol`) and a render-integration width-guard check per pane.
**Reads:** nothing external — seeds `_cache_turns`/`tool_errors`/`_worker_tokens_turns` with
synthetic data; `copy_to_clipboard` is monkeypatched to a capturing stub.
**Writes:** `md/p2_copy_click_probe_<timestamp>.md`; one throwaway IPC selection file under
`/tmp/monitor_cc_selected_worker_<hash>.txt`, removed after the check.
**Called by:** none — run manually; re-run after any change to `append_copy_symbol`,
`format_cache_tracker`, `_format_warnings_pane`, `_serialize_warnings`, or any pane's
`_handle_*_mouse`/`_handle_*_key`.
**Calls out:** `src.panes.token_pane`, `src.format.token_format`, `src.panes.warnings_pane`,
`src.panes.warnings_render`, `src.workers.worker_tokens_pane`, `src.utils` — loaded via
`importlib.import_module`.

---

### p3_button_click_probe.py (286 LOC)

**Purpose:** Proves, per pane (warnings refresh), that after one real render pass the
chrome-button region is registered at a plausible coordinate, a synthetic click produces the
same state change as the corresponding key (`r`), a too-narrow pane registers no region, and each
pane's pre-existing click handling (expand/copy) still works with the header-check ahead of it.
Also covers the proxy pane's permanent search-bar header: `_build_proxy_output` returns row 1
with the search bar baked in, row 1 is not a body key, and
expand/collapse/copy/scroll/`_undo_proxy_expand` all still work at the shifted rows. (2026-09) The
workers-pane freeze-badge test is DELETED, not retargeted — the 'f' freeze feature was tied to the
all-workers list pane, which is gone; see the module docstring for why it has no successor here.
**Reads:** nothing external — seeds `tool_errors`/`proxy_entries` directly.
**Writes:** `md/p3_button_click_probe_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to `_format_warnings_header`,
`_handle_warnings_mouse`/`_handle_warnings_key`, or
`_build_proxy_output`/`_handle_proxy_mouse`/`_undo_proxy_expand`.
**Calls out:** `src.panes.warnings_pane`, `src.panes.warnings_render`, `src.proxy_display.pane`,
`src.proxy_display.format` — loaded via `importlib.import_module`.

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

### p5_proxy_message_copy_click_probe.py (158 LOC)

**Purpose:** Entry script — orchestrates all three copy-granularity suites (message/thinking/
block) from their own modules and writes the combined report; carries the full milestone
docstring.
**Reads:** nothing external.
**Writes:** `md/p5_proxy_message_copy_click_probe_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to `render_messages.py`'s message-row,
thinking-block, or generic-block build sites, `proxy_pane_shared._serialize_proxy_message`/
`_serialize_proxy_block`/`_prepare_copy_text`/`_copy_feedback_key`,
`format._apply_row_backgrounds`, or either pane's `_handle_*_mouse`/`_handle_*_copy_click`.
**Calls out:** `proxy_copy_probe_shared.py`, `proxy_copy_message_probe.py`,
`proxy_copy_thinking_probe.py`, `proxy_copy_block_probe.py`.

---

### proxy_copy_probe_shared.py (60 LOC)

**Purpose:** Shared fixtures for the P5 suite — module handles (`mod_proxy`, `mod_worker_proxy`,
`mod_format`, `mod_shared`), `check()`/`_RESULTS`, `_patch_clipboard`, `_make_entry`,
`_render_expanded`.
**Reads:** nothing external.
**Writes:** nothing (mutates the shared `_RESULTS` list the entry script reads).
**Called by:** `p5_proxy_message_copy_click_probe.py`, `proxy_copy_message_probe.py`,
`proxy_copy_thinking_probe.py`, `proxy_copy_block_probe.py`.
**Calls out:** `src.proxy_display.pane`, `src.proxy_display.worker_proxy_pane`,
`src.proxy_display.format`, `src.proxy_display.proxy_pane_shared` — loaded via
`importlib.import_module`.

---

### proxy_copy_message_probe.py (118 LOC)

**Purpose:** Message-row copy granularity (P5.1-5.5) — `('msg', entry_idx, msg_idx)` key
registration, click/serializer parity, click/copy dispatch, width guard.
**Reads:** nothing external — seeds a synthetic multi-block assistant message plus a blockless
user message via the shared `_make_entry`.
**Writes:** nothing.
**Called by:** `p5_proxy_message_copy_click_probe.py`.
**Calls out:** `proxy_copy_probe_shared.py`.

---

### proxy_copy_thinking_probe.py (131 LOC)

**Purpose:** Thinking-block copy granularity (P5.6-5.10) — `('think', entry_idx, msg_idx, bidx)`
key registration, click/serializer parity, the non-copy-click-still-toggles-expand regression
(the one behavior this granularity must NOT disturb), width guard.
**Reads:** nothing external — seeds a synthetic entry with an assistant thinking block followed by
a text block.
**Writes:** nothing.
**Called by:** `p5_proxy_message_copy_click_probe.py`.
**Calls out:** `proxy_copy_probe_shared.py`.

---

### proxy_copy_block_probe.py (132 LOC)

**Purpose:** Generic-block copy granularity (P5.11-5.15) — `('block', entry_idx, msg_idx, bidx)`
key registration, click/serializer parity nested in both message and REQ copies, the
non-copy-click-is-a-no-op regression (opposite of the thinking-block shape), width guard.
**Reads:** nothing external — reuses the shared `_make_entry` (multi-block assistant message).
**Writes:** nothing.
**Called by:** `p5_proxy_message_copy_click_probe.py`.
**Calls out:** `proxy_copy_probe_shared.py`.

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

**The proxy panes' own body row-1 slot is ALSO reserved for the search bar, one level below the
header-marker case above** — `_handle_proxy_mouse`/`_handle_worker_proxy_mouse` special-case
`row == 1` as "focus the search bar" BEFORE ever looking at `line_map`. A probe calling
`format_proxy_block` directly (the same unshifted-row style `dev/display/test_hover_map.py` and
this suite's other probes already use) gets body rows starting at 1 — dispatching a synthetic
click at a raw `format_proxy_block` row number can silently land on the search-bar branch instead
of the real copy/expand dispatch, `_handle_proxy_mouse`/`_handle_worker_proxy_mouse` still returns
truthy, and the click quietly does nothing to the thing you meant to test. Shift both `line_map`
and `copy_rows` by 1 with `proxy_pane_shared._shift_line_map_and_copy_rows` (the same shift
`_render_and_scroll_body` applies in the real event loop) before dispatching any synthetic click
through `_handle_proxy_mouse`/`_handle_worker_proxy_mouse`.
