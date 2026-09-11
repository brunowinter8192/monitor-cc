# dev/pane_search/

## Role
Feasibility measurement and regression coverage for the search-bar rollout across all 8 tmux panes
(`src/search_bar.py`, shared by every pane). `p1_` measured message-reconstruction cost before any
feature code existed; `p2_`/`p3_` are the regression suite for the proxy pane (the rollout's
reference implementation); `p5_`-`p8_` are per-pane parity suites proving each remaining pane reaches
the same search-bar behavior as the proxy pane. Touch when changing a pane's search/mouse handlers,
`search_bar.py` itself, or a pane's header/row-background rendering that search highlighting touches.

## Flow
Each parity script seeds a pane module's state (synthetic entries/turns, or a real dual-log/JSONL
fixture) directly, drives the pane's real search/mouse handler functions, and asserts on the
resulting query/match state and rendered output — no live tmux session involved. Output is
PASS/FAIL to stdout plus a timestamped report in `md/`.

## Modules

### p1_full_sweep_cost_probe.py (403 LOC)

**Purpose:** Compares two message-reconstruction strategies on a real `_forwarded.jsonl` log:
per-entry lazy-load (O(N) replays) vs. one-sweep reconstruction (single pass, keeps messages for
every entry). Measures wall time and peak/current traced RAM for both.
**Reads:** a forwarded dual-log JSONL (positional arg, or the newest one found under src/logs/dual_log
on the dev machine — gitignored runtime data, absent from a fresh worktree).
**Writes:** `md/p1_full_sweep_cost_report.md`; a one-line stdout summary.
**Called by:** none — manual, one-off feasibility measurement.
**Calls out:** stdlib only (`json`, `tracemalloc`, `gc`, `collections.deque`) — the delta-accumulation
algorithm is reimplemented locally rather than importing `src.proxy_display.forwarded_parser`.

---

### p2_search_feature_regression_test.py (471 LOC)

**Purpose:** Regression guard for the proxy pane's search feature: search-bar rendering at row 1,
line_map/copy_rows shift correctness, collapsed-vs-expanded hit marking, `n`/`N` jump ordering, Esc
clearing query+matches without hiding the bar, the `flow_id`-based `_lazy_load_messages_forwarded`
fix, the `ZEBRA_BG_A == ''` sentinel-resolution bug, UTF-8 multi-byte keypress decoding in
`read_keypress`, and kill-line-after-a-real-search-run behavior.
**Reads:** nothing external — seeds `src.proxy_display.pane` module state with synthetic entries
directly; one test writes a throwaway forwarded-delta JSONL fixture under a temp directory.
**Writes:** `md/p2_search_feature_regression_test_<timestamp>.md`; exits 1 if any check fails.
**Called by:** none — manual regression guard, re-run after changing `pane.py`'s search
state/handlers, `format.py`'s row-background/render functions, `render_turn.py`'s search-marker
embedding, `search.py`, `forwarded_parser.py`'s reconstruction functions, or
`input.click_handler.read_keypress`.
**Calls out:** `src.proxy_display.pane`, `src.proxy_display.format`, `src.proxy_display.search`,
`src.proxy_display.forwarded_parser`, `src.input.click_handler`, `src.constants` — loaded via
`importlib.import_module`.

---

### p3_drag_select_regression_test.py (406 LOC)

**Purpose:** Regression guard for drag-to-select on the search bar: column-to-query-index boundary
mapping (ASCII and wide-char/emoji), the full press-motion-release drag flow producing an exact
clipboard copy, plain-click producing zero clipboard calls, editor-style Backspace-deletes-selection
vs. plain Backspace, and kill-line (`pane._KILL_LINE_CHAR`) clearing the whole query.
**Reads:** nothing external — seeds `src.proxy_display.pane` module state directly and drives its
mouse/search handlers with direct `(button, col, row)` calls.
**Writes:** `md/p3_drag_select_regression_test_<timestamp>.md`; exits 1 if any check fails.
**Called by:** none — manual regression guard, re-run after changing `pane.py`'s
`_search_col_to_query_index`, `_handle_proxy_mouse`, `_handle_proxy_search_release`,
`_clear_proxy_search_selection`, or `_render_proxy_search_bar`.
**Calls out:** `src.proxy_display.pane` — loaded via `importlib.import_module`.

---

### p5_worker_proxy_pane_parity_test.py (543 LOC)

**Purpose:** Regression guard for the worker-proxy pane reaching search-bar parity with the proxy
pane: the same drag-select/editing/jump mechanics suite as `p2_`/`p3_`, retargeted at this pane's own
wrappers, plus the 2-row header composition (search bar row 1, worker-switcher header shifted to
row 2+), Enter always re-running the search, the one-sweep reconstruction merge wired for this pane,
and a worker-switch search-state reset.
**Reads:** nothing external — seeds `src.proxy_display.worker_proxy_pane` module state directly; one
test writes a throwaway 2-line forwarded-delta JSONL fixture, another a throwaway IPC selection file.
**Writes:** `md/p5_worker_proxy_pane_parity_test_<timestamp>.md`; exits 1 if any check fails.
**Called by:** none — manual regression guard, re-run after changing `worker_proxy_pane.py`'s
search/mouse handlers, `_build_worker_proxy_output`'s header composition,
`_format_worker_proxy_header`/`worker_proxy_helpers.py`, or `src/search_bar.py`.
**Calls out:** `src.proxy_display.worker_proxy_pane`, `src.search_bar` — loaded via
`importlib.import_module`.

---

### p6_tokens_pane_parity_test.py (515 LOC)

**Purpose:** Regression guard for the tokens pane reaching search-bar parity: the same mechanics
suite as `p3_`-`p5_`, plus two-key match semantics (`(turn_idx, call_idx)` container-marks a call
header unconditionally; `('turn', turn_idx)` marks the turn's prompt line), the same
`ZEBRA_BG_A == ''` sentinel bug, a `LIGHT_RED_BG` detection regression fix (`.startswith()` → `in`),
jump-to-match scroll positioning via `format_cache_tracker`'s `nav_out`, and a session-change search
state reset.
**Reads:** nothing external — seeds `src.panes.token_pane._cache_turns` with synthetic turns
directly; the session-change test monkeypatches session-lookup functions to nonexistent paths.
**Writes:** `md/p6_tokens_pane_parity_test_<timestamp>.md`; exits 1 if any check fails.
**Called by:** none — manual regression guard, re-run after changing `token_pane.py`'s search/mouse
handlers, `token_format.py`'s `format_cache_tracker`/`_compute_cache_viewport`, `token_search.py`,
or `src/search_bar.py`.
**Calls out:** `src.panes.token_pane`, `src.panes.token_search`, `src.format.token_format`,
`src.search_bar`, `src.constants`, `src.core.monitor`, `src.proxy_display.parser` — loaded via
`importlib.import_module`.

---

### p7_workers_pane_parity_test.py (535 LOC)

**Purpose:** Regression guard for the workers pane reaching search-bar parity — the first pane
needing a genuine reconstruction step, since `worker_turns` only holds data for currently-expanded
workers. Covers the same mechanics suite as `p3_`-`p6_`, plus a three-tier match key (worker / turn /
call) with per-worker scoping (a match in one worker must not leak highlighting into another
worker's independently-expanded output), the 2-row header + freeze-badge shift, the same
`LIGHT_RED_BG` collateral fix, and jump-to-match self-healing when `worker_turns` has gone stale or
the matched worker has vanished from the current list.
**Reads:** nothing external — seeds `src.workers.worker_pane` module state directly; some tests write
throwaway JSONL fixture files under a temp directory with `find_worker_jsonl` monkeypatched to
resolve to them.
**Writes:** `md/p7_workers_pane_parity_test_<timestamp>.md`; exits 1 if any check fails.
**Called by:** none — manual regression guard, re-run after changing `worker_pane.py`'s search/mouse
handlers or jump-to-match, `worker_format.py`'s `format_workers_block`/scoping helpers,
`panes/token_search.py`, or `src/search_bar.py`.
**Calls out:** `src.workers.worker_pane`, `src.workers.worker_format`, `src.search_bar`,
`src.constants` — loaded via `importlib.import_module`.

---

### p8_warnings_gpu_news_parity_test.py (584 LOC)

**Purpose:** Regression guard for the final three panes (warnings, gpu, news) reaching search-bar
parity, bundled in one suite. Covers the same drag-select/editing/Esc/render mechanics as `p3_`-`p7_`
retargeted at each pane's wrappers, a literal-source-introspection check pinning that the warnings
row-background loop uses substring matching (not `.startswith()`), the same `ZEBRA_BG_A == ''`
sentinel-resolution fix, and — for gpu/news, which have no scroll infrastructure at all —
highlight-only matching where `n`/`N` cycles `current_idx` with zero scroll calls.
**Reads:** nothing external — seeds `src.panes.warnings_pane.tool_errors` and synthetic
`presets`/`status` dicts directly for gpu/news.
**Writes:** `md/p8_warnings_gpu_news_parity_test_<timestamp>.md`; exits 1 if any check fails.
**Called by:** none — manual regression guard, re-run after changing `warnings_pane.py`/
`warnings_render.py`'s search handling, `gpu_pane/pane.py`'s or `news_pane/pane.py`'s
`_render_pane`/inline mouse dispatch, or `src/search_bar.py`.
**Calls out:** `src.panes.warnings_pane`, `src.panes.warnings_render`, `src.gpu_pane.pane`,
`src.news_pane.pane`, `src.search_bar`, `src.constants` — loaded via `importlib.import_module`.

---

## Gotchas
- `ZEBRA_BG_A` is the empty string (`''`) — substituting a background sentinel with it (instead of
  the SGR reset `\033[49m`) silently deletes the sentinel rather than clearing the background,
  flooding a highlight color to end-of-line. Every pane's parity suite (`p2_`, `p6_`, `p7_`, `p8_`)
  re-checks this because each pane's row-background loop is a separate hand-rolled implementation.
- `format_cache_tracker`'s `nav_out` dict mixes tuple keys (`(turn_idx, call_idx)`, `('turn',
  turn_idx)`) with a string key (`'total_lines'`) — anything hashing or JSON-serializing it with
  `sort_keys=True` needs every key stringified first.
- Synthetic fixture entries must build a CUMULATIVE `messages` list (length == `message_count`, one
  filler message per earlier index) — `render_messages._render_new_messages` finds "new" messages via
  `range(prev_msg_count, len(messages))`, so a non-cumulative per-entry-only list silently renders an
  empty new-message range and a placed marker never appears.
