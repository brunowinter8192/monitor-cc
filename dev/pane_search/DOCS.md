# dev/pane_search/

## Role
Feasibility measurement and regression coverage for the search-bar rollout across all 8 tmux panes
(`src/search_bar.py`, shared by every pane). `p1_` measured message-reconstruction cost before any
feature code existed; `p2_`/`p3_` are the regression suite for the proxy pane (the rollout's
reference implementation); `p5_`-`p8_` are per-pane parity suites proving each remaining pane reaches
the same search-bar behavior as the proxy pane. Touch when changing a pane's search/mouse handlers,
`search_bar.py` itself, or a pane's header/row-background rendering that search highlighting touches.

## Public Interface
No `__init__.py` in this directory. Each `pN_..._test.py` (and `p1_full_sweep_cost_probe.py`) is
invoked directly as a script: `./venv/bin/python dev/pane_search/pN_..._test.py`.

## Flow
Each parity script seeds a pane module's state (synthetic entries/turns, or a real dual-log/JSONL
fixture) directly, drives the pane's real search/mouse handler functions, and asserts on the
resulting query/match state and rendered output — no live tmux session involved. Output is
one verdict line per strand to stdout plus a fixed-name report in `md/`.

Each `pN_*_test.py` runs its `test_*` functions as parallel strands: one subprocess per function (`--strand <name>`), launched by `dev/refactoring/strand_runner.py`, each fail-fast (`check()` raises on the first failing check), siblings run to completion and the parent names the aborted strands. The fixtures assign `MONITOR_CC_ROOT` to the worktree (never `setdefault`) and pin `os.get_terminal_size` to 220x50, so no suite needs a tty. `p7_` derives its project filter from the process id so parallel strands do not share the worker-selection file.

Each `pN_*` suite splits into an entry script (kept runnable at its original path/name) plus sibling
`_fixtures.py` (module loads, state resets, `check()`) and `_cases*.py` (the `test_*` functions)
helper modules in the same directory, following the split convention already used in
`dev/proxy_dual_log/`. `dev/` scripts may not `import src.` at module level; the entry/fixtures
modules load `src` via `importlib.import_module` (see `src/hooks/block_dev_imports_src.py`), and
sibling `pN_*` modules import each other with plain `from pN_... import name`.

## Modules

### p1_full_sweep_cost_probe.py (50 LOC)

**Purpose:** Orchestrates the M1 cost probe end to end and writes the markdown report.
**Reads:** a forwarded dual-log JSONL (positional arg, or the newest one found under src/logs/dual_log
on the dev machine — gitignored runtime data, absent from a fresh worktree).
**Writes:** `md/p1_full_sweep_cost_report.md`; a one-line stdout summary.
**Called by:** none — manual, one-off feasibility measurement.
**Calls out:** `p1_full_sweep_reconstruct.py`, `p1_full_sweep_report.py`.

---

### p1_full_sweep_reconstruct.py (161 LOC)

**Purpose:** Local reimplementation of the forwarded-delta reconstruction algorithm (both the
per-entry lazy-load and one-sweep strategies) plus their wall-time/RAM measurement wrappers.
**Reads:** nothing at import time; its functions read a forwarded-delta JSONL passed as an argument.
**Writes:** nothing — pure functions returning entries/timings.
**Called by:** `p1_full_sweep_cost_probe.py`.
**Calls out:** stdlib only (`json`, `gc`, `tracemalloc`, `collections.deque`) — mirrors
`src/proxy_display/forwarded_parser.py` structurally rather than importing it.

---

### p1_full_sweep_report.py (171 LOC)

**Purpose:** Computes derived report metrics and formats the markdown report body section by section.
**Reads:** the entries/timing/RAM values `p1_full_sweep_cost_probe.py` measured.
**Writes:** nothing — returns the report string; the caller writes the file.
**Called by:** `p1_full_sweep_cost_probe.py`.
**Calls out:** `p1_full_sweep_reconstruct.py` (`_infer_model_family`, for the per-family stats).

---

### p2_search_feature_regression_test.py (46 LOC)

**Purpose:** Runs the M2 proxy-pane search-bar regression suite and writes the PASS/FAIL report.
**Reads:** nothing external.
**Writes:** `md/p2_search_feature_regression_test.md` (fixed name, overwritten each run); exits 1 if any strand aborts.
**Called by:** none — manual regression guard, re-run after changing `pane.py`'s search
state/handlers, `format.py`'s row-background/render functions, `render_turn.py`'s search-marker
embedding, `search.py`, `forwarded_parser.py`'s reconstruction functions, or
`input.click_handler.read_keypress`.
**Calls out:** `p2_search_feature_regression_fixtures.py`, `p2_search_feature_regression_cases.py`.

---

### p2_search_feature_regression_fixtures.py (103 LOC)

**Purpose:** Loads the `src` modules under test, imports the shared fail-fast `check()`, and
builds synthetic proxy entries and pane-state resets for the M2 suite's test cases.
**Reads:** nothing external.
**Writes:** nothing — mutates in-process `src.proxy_display.pane` module state on demand.
**Called by:** `p2_search_feature_regression_test.py`, `p2_search_feature_regression_cases.py`.
**Calls out:** `src.proxy_display.pane`, `src.proxy_display.format`, `src.proxy_display.search`,
`src.proxy_display.forwarded_parser`, `src.input.click_handler`, `src.colors` — loaded via
`importlib.import_module`.

---

### p2_search_feature_regression_cases.py (273 LOC)

**Purpose:** The M2 suite's `test_*` functions covering search-bar render/highlight/nav/UTF-8
input behavior.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p2_search_feature_regression_test.py`.
**Calls out:** `p2_search_feature_regression_fixtures.py`.

---

### p3_drag_select_regression_test.py (56 LOC)

**Purpose:** Runs the proxy pane's drag-to-select regression suite and writes the PASS/FAIL report.
**Reads:** nothing external.
**Writes:** `md/p3_drag_select_regression_test.md` (fixed name, overwritten each run); exits 1 if any strand aborts.
**Called by:** none — manual regression guard, re-run after changing `pane.py`'s
`_search_col_to_query_index`, `_handle_proxy_mouse`, `_handle_proxy_search_release`,
`_clear_proxy_search_selection`, or `_render_proxy_search_bar`.
**Calls out:** `p3_drag_select_regression_fixtures.py`, `p3_drag_select_regression_cases.py`.

---

### p3_drag_select_regression_fixtures.py (42 LOC)

**Purpose:** Loads `src.proxy_display.pane`, holds `check()`/results, and resets pane/search state
between drag-select test cases.
**Reads:** nothing external.
**Writes:** nothing — mutates in-process `src.proxy_display.pane` module state on demand.
**Called by:** `p3_drag_select_regression_test.py`, `p3_drag_select_regression_cases.py`.
**Calls out:** `src.proxy_display.pane` — loaded via `importlib.import_module`.

---

### p3_drag_select_regression_cases.py (276 LOC)

**Purpose:** The drag-select suite's `test_*` functions covering column mapping, drag/click/editing
mechanics, and selection-clearing.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p3_drag_select_regression_test.py`.
**Calls out:** `p3_drag_select_regression_fixtures.py`.

---

### p5_worker_proxy_pane_parity_test.py (66 LOC)

**Purpose:** Runs the worker-proxy pane's search-bar parity suite and writes the PASS/FAIL report.
**Reads:** nothing external.
**Writes:** `md/p5_worker_proxy_pane_parity_test.md` (fixed name, overwritten each run); exits 1 if any strand aborts.
**Called by:** none — manual regression guard, re-run after changing `worker_proxy_pane.py`'s
search/mouse handlers, `_build_worker_proxy_output`'s header composition,
`workers/worker_switch_header.py` (imported here under the alias `_format_worker_proxy_header`),
or `src/search_bar.py`.
**Calls out:** `p5_worker_proxy_pane_parity_fixtures.py`, `p5_worker_proxy_pane_parity_cases_mechanics.py`,
`p5_worker_proxy_pane_parity_cases_search.py`.

---

### p5_worker_proxy_pane_parity_fixtures.py (112 LOC)

**Purpose:** Loads `src.proxy_display.worker_proxy_pane`/`src.search_bar`, holds `check()`/results,
and builds synthetic worker-proxy entries, state resets, and clipboard/output-building helpers.
**Reads:** nothing external.
**Writes:** nothing — mutates in-process `worker_proxy_pane` module state on demand.
**Called by:** `p5_worker_proxy_pane_parity_test.py`, both `p5_..._cases_*.py` modules.
**Calls out:** `src.proxy_display.worker_proxy_pane`, `src.search_bar` — loaded via
`importlib.import_module`.

---

### p5_worker_proxy_pane_parity_cases_mechanics.py (207 LOC)

**Purpose:** `test_*` functions for the 2-row header, drag-select, and editor-style-deletion
mechanics half of the p5 suite.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p5_worker_proxy_pane_parity_test.py`.
**Calls out:** `p5_worker_proxy_pane_parity_fixtures.py`.

---

### p5_worker_proxy_pane_parity_cases_search.py (139 LOC)

**Purpose:** `test_*` functions for Enter-triggered search, the reconstruction merge, n/N nav, and
the worker-switch reset half of the p5 suite.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p5_worker_proxy_pane_parity_test.py`.
**Calls out:** `p5_worker_proxy_pane_parity_fixtures.py`.

---

### p6_tokens_pane_parity_test.py (70 LOC)

**Purpose:** Runs the tokens pane's search-bar parity suite and writes the PASS/FAIL report.
**Reads:** nothing external.
**Writes:** `md/p6_tokens_pane_parity_test.md` (fixed name, overwritten each run); exits 1 if any strand aborts.
**Called by:** none — manual regression guard, re-run after changing `token_pane.py`'s search/mouse
handlers, `token_format.py`'s `format_cache_tracker`/`_compute_cache_viewport`, `token_search.py`,
or `src/search_bar.py`.
**Calls out:** `p6_tokens_pane_parity_fixtures.py`, `p6_tokens_pane_parity_cases_mechanics.py`,
`p6_tokens_pane_parity_cases_matching.py`.

---

### p6_tokens_pane_parity_fixtures.py (65 LOC)

**Purpose:** Loads the `src` token-pane modules, holds `check()`/results, and builds synthetic
turns and pane-state resets for the p6 suite's test cases.
**Reads:** nothing external.
**Writes:** nothing — mutates in-process `token_pane` module state on demand.
**Called by:** `p6_tokens_pane_parity_test.py`, both `p6_..._cases_*.py` modules.
**Calls out:** `src.panes.token_pane`, `src.panes.token_search`, `src.format.token_format`,
`src.search_bar`, `src.colors`, `src.core.monitor`, `src.proxy_display.parser`,
`src.proxy_display.side_logs` — loaded via `importlib.import_module`.

---

### p6_tokens_pane_parity_cases_mechanics.py (194 LOC)

**Purpose:** `test_*` functions for state shape, render, drag-select, and editor-style-deletion
mechanics half of the p6 suite.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p6_tokens_pane_parity_test.py`.
**Calls out:** `p6_tokens_pane_parity_fixtures.py`.

---

### p6_tokens_pane_parity_cases_matching.py (152 LOC)

**Purpose:** `test_*` functions for two-key match semantics, the sentinel/LIGHT_RED_BG regressions,
nav, jump-to-match, and session-change-reset half of the p6 suite.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p6_tokens_pane_parity_test.py`.
**Calls out:** `p6_tokens_pane_parity_fixtures.py`.

---

### p7_workers_pane_parity_test.py (70 LOC)

**Purpose:** Runs the worker-tokens pane's search-bar + worker-switch-header parity suite and
writes the PASS/FAIL report.
**Reads:** nothing external.
**Writes:** `md/p7_workers_pane_parity_test.md` (fixed name, overwritten each run); exits 1 if any strand aborts.
**Called by:** none — manual regression guard, re-run after changing `worker_tokens_pane.py`'s
search/mouse/header handlers, `worker_switch_header.py`, `panes/token_search.py`, or
`src/search_bar.py`.
**Calls out:** `p7_workers_pane_parity_fixtures.py`, `p7_workers_pane_parity_cases_mechanics.py`,
`p7_workers_pane_parity_cases_matching.py`.

---

### p7_workers_pane_parity_fixtures.py (116 LOC)

**Purpose:** Loads `src.workers.worker_tokens_pane`/`src.search_bar`/`src.colors`, holds
`check()`/results, and builds real throwaway worker-JSONL fixtures plus state resets.
**Reads:** nothing at import time; `_setup_one_worker_jsonl` writes and later reads a throwaway
JSONL fixture under a temp directory with `find_worker_jsonl` monkeypatched to resolve to it.
**Writes:** a throwaway JSONL fixture file per test that requests one (cleaned up by
`_cleanup_worker_jsonl`).
**Called by:** `p7_workers_pane_parity_test.py`, both `p7_..._cases_*.py` modules.
**Calls out:** `src.workers.worker_tokens_pane`, `src.search_bar`, `src.colors` — loaded via
`importlib.import_module`.

---

### p7_workers_pane_parity_cases_mechanics.py (208 LOC)

**Purpose:** `test_*` functions for the 2-row header, drag-select, and editor-style-deletion
mechanics half of the p7 suite.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p7_workers_pane_parity_test.py`.
**Calls out:** `p7_workers_pane_parity_fixtures.py`.

---

### p7_workers_pane_parity_cases_matching.py (189 LOC)

**Purpose:** `test_*` functions for two-key match semantics, the sentinel/LIGHT_RED_BG regressions,
nav, jump-to-match, and the worker-switch reset half of the p7 suite.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p7_workers_pane_parity_test.py`.
**Calls out:** `p7_workers_pane_parity_fixtures.py`.

---

### p8_warnings_gpu_news_parity_test.py (72 LOC)

**Purpose:** Runs the warnings/gpu/news panes' bundled search-bar parity suite and writes the
PASS/FAIL report.
**Reads:** nothing external.
**Writes:** `md/p8_warnings_gpu_news_parity_test.md` (fixed name, overwritten each run); exits 1 if any strand aborts.
**Called by:** none — manual regression guard, re-run after changing `warnings_pane.py`/
`warnings_render.py`'s search handling, `gpu_pane/pane.py`'s or `news_pane/pane.py`'s
`_render_pane`/inline mouse dispatch, or `src/search_bar.py`.
**Calls out:** `p8_warnings_gpu_news_parity_fixtures.py`, `p8_warnings_gpu_news_parity_cases_warnings.py`,
`p8_warnings_gpu_news_parity_cases_gpu.py`, `p8_warnings_gpu_news_parity_cases_news.py`.

---

### p8_warnings_gpu_news_parity_fixtures.py (104 LOC)

**Purpose:** Loads the warnings/gpu/news `src` modules, holds `check()`/results, and builds
synthetic tool-errors/presets plus per-pane state resets and the inline gpu-click dispatcher.
**Reads:** nothing external.
**Writes:** nothing — mutates in-process pane module state on demand.
**Called by:** `p8_warnings_gpu_news_parity_test.py`, all three `p8_..._cases_*.py` modules.
**Calls out:** `src.panes.warnings_pane`, `src.panes.warnings_render`, `src.gpu_pane.pane`,
`src.news_pane.pane`, `src.search_bar`, `src.colors` — loaded via `importlib.import_module`.

---

### p8_warnings_gpu_news_parity_cases_warnings.py (197 LOC)

**Purpose:** `test_*` functions for the warnings pane's 2-row header, two-stage match marking,
sentinel fix, and drag/editing mechanics.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p8_warnings_gpu_news_parity_test.py`.
**Calls out:** `p8_warnings_gpu_news_parity_fixtures.py`.

---

### p8_warnings_gpu_news_parity_cases_gpu.py (107 LOC)

**Purpose:** `test_*` functions for the gpu pane's highlight-only match/nav and unshifted-render
button-region behavior.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p8_warnings_gpu_news_parity_test.py`.
**Calls out:** `p8_warnings_gpu_news_parity_fixtures.py`.

---

### p8_warnings_gpu_news_parity_cases_news.py (80 LOC)

**Purpose:** `test_*` functions for the news pane's highlight-only match/nav and unshifted-render
button-region behavior.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p8_warnings_gpu_news_parity_test.py`.
**Calls out:** `p8_warnings_gpu_news_parity_fixtures.py`.

---

## State
Every `pN_*_fixtures.py` module imports `check()` from `dev/refactoring/strand_runner.py`;
`pN_*_cases*.py` modules mutate the imported real `src` pane module's globals (e.g.
`src.proxy_display.pane.proxy_entries`, `src.panes.token_pane._tokens_search`) directly on each
test call, and the matching `_reset_state`/`_reset_*_state` fixture function clears them between
tests. No state persists across separate `python` invocations — each entry script runs in its own
process.
