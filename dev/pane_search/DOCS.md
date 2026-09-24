# dev/pane_search/

## Role
Feasibility measurement and regression coverage for the search-bar rollout across all eight tmux panes (`src/search_bar.py`). p1 measured reconstruction cost; p2 and p3 are the proxy pane regression suite; p5 to p8 are per-pane parity suites. Touch when changing pane search or mouse handlers or the shared search bar.

## Public Interface
No `__init__.py`. Each `pN_..._test.py` and `p1_full_sweep_cost_probe.py` is run directly: `./venv/bin/python dev/pane_search/pN_..._test.py`.

## Flow
Each parity script seeds a pane module's state (synthetic entries or a real fixture), drives the pane's real search and mouse handlers and asserts on query, match state and rendered output; no tmux session. Test functions run as parallel fail-fast strands via the strand runner in `dev/refactoring/`, output is one verdict per strand plus a fixed-name report in `md/`.
Each suite splits into an entry script, a fixtures module and one or more case modules; entry and fixtures load `src` via `importlib`, sibling modules import each other plainly. Details on isolation from the environment are in process-docs.

## Modules

### p1_full_sweep_cost_probe.py (50 LOC)

**Purpose:** Orchestrates the reconstruction cost probe end to end and writes the report.
**Reads:** a forwarded dual-log JSONL (argument, or the newest one on the dev machine; gitignored runtime data).
**Writes:** `md/p1_full_sweep_cost_report.md`; a one-line stdout summary.
**Called by:** none; one-off feasibility measurement.
**Calls out:** `p1_full_sweep_reconstruct.py`, `p1_full_sweep_report.py`.

---

### p1_full_sweep_reconstruct.py (161 LOC)

**Purpose:** Local reimplementation of the forwarded-delta reconstruction (lazy per-entry and one-sweep) plus wall-time and RAM wrappers.
**Reads:** a forwarded-delta JSONL passed as argument.
**Writes:** nothing; returns entries and timings.
**Called by:** `p1_full_sweep_cost_probe.py`.
**Calls out:** stdlib only; mirrors the production parser structurally.

---

### p1_full_sweep_report.py (171 LOC)

**Purpose:** Computes derived report metrics and formats the Markdown body section by section.
**Reads:** the measured entries, timings and RAM values.
**Writes:** nothing; returns the report string.
**Called by:** `p1_full_sweep_cost_probe.py`.
**Calls out:** `p1_full_sweep_reconstruct.py`.

---

### p2_search_feature_regression_test.py (46 LOC)

**Purpose:** Runs the proxy-pane search-bar regression suite and writes the pass/fail report.
**Reads:** nothing external.
**Writes:** `md/p2_search_feature_regression_test.md`, overwritten each run; exits 1 if any strand aborts.
**Called by:** none; manual regression guard, re-run after changing the proxy pane search state or handlers, row-background rendering, search markers or reconstruction.
**Calls out:** `p2_search_feature_regression_fixtures.py`, `p2_search_feature_regression_cases.py`.

---

### p2_search_feature_regression_fixtures.py (104 LOC)

**Purpose:** Loads the modules under test, imports the shared fail-fast check, builds synthetic proxy entries and pane-state resets.
**Reads:** nothing external.
**Writes:** nothing; mutates in-process pane module state.
**Called by:** the entry and cases modules.
**Calls out:** `src.proxy_display.pane`, `.format`, `.search`, `.forwarded_parser`, `src.input.click_handler`, `src.colors`.

---

### p2_search_feature_regression_cases.py (273 LOC)

**Purpose:** Test functions covering search-bar render, highlight, navigation and UTF-8 input.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p2_search_feature_regression_test.py`.
**Calls out:** `p2_search_feature_regression_fixtures.py`.

---

### p3_drag_select_regression_test.py (56 LOC)

**Purpose:** Runs the proxy-pane drag-to-select regression suite and writes the pass/fail report.
**Reads:** nothing external.
**Writes:** `md/p3_drag_select_regression_test.md`, overwritten each run; exits 1 if any strand aborts.
**Called by:** none; manual regression guard, re-run after changing the pane's drag, click or search-bar rendering handlers.
**Calls out:** `p3_drag_select_regression_fixtures.py`, `p3_drag_select_regression_cases.py`.

---

### p3_drag_select_regression_fixtures.py (42 LOC)

**Purpose:** Loads the proxy pane module, holds check results and resets pane and search state between cases.
**Reads:** nothing external.
**Writes:** nothing; mutates in-process pane module state.
**Called by:** the entry and cases modules.
**Calls out:** `src.proxy_display.pane` via `importlib`.

---

### p3_drag_select_regression_cases.py (276 LOC)

**Purpose:** Test functions covering column mapping, drag, click and editing mechanics and selection clearing.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p3_drag_select_regression_test.py`.
**Calls out:** `p3_drag_select_regression_fixtures.py`.

---

### p5_worker_proxy_pane_parity_test.py (66 LOC)

**Purpose:** Runs the worker-proxy pane search-bar parity suite and writes the pass/fail report.
**Reads:** nothing external.
**Writes:** `md/p5_worker_proxy_pane_parity_test.md`, overwritten each run; exits 1 if any strand aborts.
**Called by:** none; manual regression guard, re-run after changing that pane's handlers or header, the worker switch header or the shared search bar.
**Calls out:** `p5_worker_proxy_pane_parity_fixtures.py`, `p5_worker_proxy_pane_parity_cases_mechanics.py`, `p5_worker_proxy_pane_parity_cases_search.py`.

---

### p5_worker_proxy_pane_parity_fixtures.py (112 LOC)

**Purpose:** Loads the pane and search bar modules, holds check results, builds synthetic entries, state resets and clipboard helpers.
**Reads:** nothing external.
**Writes:** nothing; mutates in-process pane module state.
**Called by:** the entry and both case modules.
**Calls out:** `src.proxy_display.worker_proxy_pane`, `src.search_bar`.

---

### p5_worker_proxy_pane_parity_cases_mechanics.py (207 LOC)

**Purpose:** Test functions for the two-row header, drag-select and editor-style deletion mechanics.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p5_worker_proxy_pane_parity_test.py`.
**Calls out:** `p5_worker_proxy_pane_parity_fixtures.py`.

---

### p5_worker_proxy_pane_parity_cases_search.py (139 LOC)

**Purpose:** Test functions for Enter-triggered search, the reconstruction merge, n/N navigation and the worker-switch reset.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p5_worker_proxy_pane_parity_test.py`.
**Calls out:** `p5_worker_proxy_pane_parity_fixtures.py`.

---

### p6_tokens_pane_parity_test.py (70 LOC)

**Purpose:** Runs the tokens pane search-bar parity suite and writes the pass/fail report.
**Reads:** nothing external.
**Writes:** `md/p6_tokens_pane_parity_test.md`, overwritten each run; exits 1 if any strand aborts.
**Called by:** none; manual regression guard, re-run after changing token pane handlers, the cache tracker viewport, token search or the shared search bar.
**Calls out:** `p6_tokens_pane_parity_fixtures.py`, `p6_tokens_pane_parity_cases_mechanics.py`, `p6_tokens_pane_parity_cases_matching.py`.

---

### p6_tokens_pane_parity_fixtures.py (65 LOC)

**Purpose:** Loads the token pane modules, holds check results, builds synthetic turns and pane-state resets.
**Reads:** nothing external.
**Writes:** nothing; mutates in-process token pane state.
**Called by:** the entry and both case modules.
**Calls out:** `src.panes.token_pane`, `.token_search`, `src.format.token_format`, `src.search_bar`, `src.colors`, `src.core.monitor`, `src.proxy_display.parser`, `.side_logs`.

---

### p6_tokens_pane_parity_cases_mechanics.py (194 LOC)

**Purpose:** Test functions for state shape, render, drag-select and editor-style deletion.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p6_tokens_pane_parity_test.py`.
**Calls out:** `p6_tokens_pane_parity_fixtures.py`.

---

### p6_tokens_pane_parity_cases_matching.py (152 LOC)

**Purpose:** Test functions for two-key match semantics, sentinel and background regressions, navigation, jump-to-match and session-change reset.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p6_tokens_pane_parity_test.py`.
**Calls out:** `p6_tokens_pane_parity_fixtures.py`.

---

### p7_workers_pane_parity_test.py (70 LOC)

**Purpose:** Runs the worker-tokens pane search-bar and switch-header parity suite and writes the pass/fail report.
**Reads:** nothing external.
**Writes:** `md/p7_workers_pane_parity_test.md`, overwritten each run; exits 1 if any strand aborts.
**Called by:** none; manual regression guard, re-run after changing that pane, the switch header, token search or the shared search bar.
**Calls out:** `p7_workers_pane_parity_fixtures.py`, `p7_workers_pane_parity_cases_mechanics.py`, `p7_workers_pane_parity_cases_matching.py`.

---

### p7_workers_pane_parity_fixtures.py (116 LOC)

**Purpose:** Loads the worker-tokens pane, search bar and colors modules, holds check results, builds throwaway worker-JSONL fixtures and state resets.
**Reads:** nothing at import time; one throwaway JSONL fixture under a temp dir per requesting test.
**Writes:** that throwaway fixture, cleaned up per test.
**Called by:** the entry and both case modules.
**Calls out:** `src.workers.worker_tokens_pane`, `src.search_bar`, `src.colors`.

---

### p7_workers_pane_parity_cases_mechanics.py (208 LOC)

**Purpose:** Test functions for the two-row header, drag-select and editor-style deletion mechanics.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p7_workers_pane_parity_test.py`.
**Calls out:** `p7_workers_pane_parity_fixtures.py`.

---

### p7_workers_pane_parity_cases_matching.py (189 LOC)

**Purpose:** Test functions for two-key match semantics, sentinel and background regressions, navigation, jump-to-match and the worker-switch reset.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p7_workers_pane_parity_test.py`.
**Calls out:** `p7_workers_pane_parity_fixtures.py`.

---

### p8_warnings_gpu_news_parity_test.py (72 LOC)

**Purpose:** Runs the bundled warnings, gpu and news pane search-bar parity suite and writes the pass/fail report.
**Reads:** nothing external.
**Writes:** `md/p8_warnings_gpu_news_parity_test.md`, overwritten each run; exits 1 if any strand aborts.
**Called by:** none; manual regression guard, re-run after changing those panes' search handling, render or mouse dispatch, or the shared search bar.
**Calls out:** `p8_warnings_gpu_news_parity_fixtures.py` and the three `p8_..._cases_*.py` modules.

---

### p8_warnings_gpu_news_parity_fixtures.py (104 LOC)

**Purpose:** Loads the warnings, gpu and news modules, holds check results, builds synthetic errors and presets, per-pane resets and the inline gpu click dispatcher.
**Reads:** nothing external.
**Writes:** nothing; mutates in-process pane module state.
**Called by:** the entry and all three case modules.
**Calls out:** `src.panes.warnings_pane`, `.warnings_render`, `src.gpu_pane.pane`, `src.news_pane.pane`, `src.search_bar`, `src.colors`.

---

### p8_warnings_gpu_news_parity_cases_warnings.py (197 LOC)

**Purpose:** Test functions for the warnings pane header, two-stage match marking, sentinel fix and drag and editing mechanics.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p8_warnings_gpu_news_parity_test.py`.
**Calls out:** `p8_warnings_gpu_news_parity_fixtures.py`.

---

### p8_warnings_gpu_news_parity_cases_gpu.py (107 LOC)

**Purpose:** Test functions for the gpu pane highlight-only match and navigation and unshifted button regions.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p8_warnings_gpu_news_parity_test.py`.
**Calls out:** `p8_warnings_gpu_news_parity_fixtures.py`.

---

### p8_warnings_gpu_news_parity_cases_news.py (80 LOC)

**Purpose:** Test functions for the news pane highlight-only match and navigation and unshifted button regions.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `p8_warnings_gpu_news_parity_test.py`.
**Calls out:** `p8_warnings_gpu_news_parity_fixtures.py`.

---

## State
Each fixtures module takes its check helper from the strand runner. Case modules mutate the real pane modules' globals on each test call and the fixtures' reset function clears them between tests. No state persists across invocations; each entry script runs in its own process.
