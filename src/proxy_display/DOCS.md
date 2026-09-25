# src/proxy_display/

## Role

Proxy pane TUI package. Reads the forwarded, stripped, injected, original and response dual-logs, rebuilds per-request system/tools/messages by delta accumulation and renders an interactive expand/collapse view with a strip/inject overlay. Two event loops: main session and selected worker. Do not touch for the strip/inject rules in `src/proxy/`.

## Public Interface

- main proxy pane loop and worker proxy pane loop, entry points from `core/monitor.py`
- worker proxy log lookup (from `parser.py`)
- proxy block renderer (from `format.py`)

Other modules are imported directly by `src/panes/token_pane.py`, `src/panes/warnings_pane.py` and `src/dual_log_cli/`.

## Flow

Forwarded dual-log → `forwarded_parser.py` (incremental parse, delta accumulation) → `pane.py` / `worker_proxy_pane.py` with overlay accumulation from `dual_log_accumulator.py`.
→ `format.py` and `frozen_turns.py` (turn groups, viewport, row backgrounds) → `render_turn.py` → section renderers → ANSI to stdout.
Entries outside the keep-last window are replayed lazily from the log on expand or search.

## Modules

### pane.py (373 LOC)

**Purpose:** Event loop for the main proxy pane: incremental log read, mouse and keyboard input, search, and render on change.
**Reads:** module state; active project filter from `core/monitor.py`; stdin.
**Writes:** frames to stdout; clipboard; pane error log; its own module state.
**Called by:** `__init__.py`, `src/core/monitor.py`.
**Calls out:** `input.click_handler`, `panes.cache_turns`, `ram_audit`, `pane_error_log`, `search_bar`

---

### worker_proxy_pane.py (374 LOC)

**Purpose:** Event loop for the worker proxy pane with worker switching, own header row and the same input handling as the main pane.
**Reads:** module state; live worker list and selection file from `workers`; stdin.
**Writes:** frames to stdout; clipboard; worker selection file; pane error log; its own module state.
**Called by:** `__init__.py`, `src/core/monitor.py`.
**Calls out:** `input.click_handler`, `workers`, `panes.cache_turns`, `utils`, `ram_audit`, `pane_error_log`, `search_bar`

---

### proxy_pane_shared.py (271 LOC)

**Purpose:** Mechanics shared by both proxy panes: key resolution, copy text, response-log joins, expand and lazy load, overlay attachment, search and scroll dispatch.
**Reads:** parameters only.
**Writes:** mutates argument collections in place; returns values otherwise.
**Called by:** `pane.py`, `worker_proxy_pane.py`.
**Calls out:** `side_logs.py`, `search_bar`

---

### format.py (146 LOC)

**Purpose:** Orchestrates turn grouping and frozen-turn rendering, applies viewport windowing and the row-background priority chain, and identifies standalone entries.
**Reads:** entries, expand states, line map, hover row, dimensions, scroll offset, turns.
**Writes:** returns the ANSI string and total line count; fills position outputs when given.
**Called by:** `pane.py`, `worker_proxy_pane.py`, `render_turn.py`, `search.py`, `proxy_pane_shared.py`, `render_sections.py`, `render_sections_system.py`, `__init__.py`.
**Calls out:** `format/token_format.py`, `search_bar`

---

### frozen_turns.py (185 LOC)

**Purpose:** Renders turn groups with per-group fingerprints so only changed groups are re-rendered.
**Reads:** entries, expand states, turns, request-id map, copy feedback, search state, overlay epoch, the turn cache.
**Writes:** the turn cache; a pane-error-log note when the assignment path changes.
**Called by:** `format.py`.
**Calls out:** `format/token_format.py`, `pane_error_log`, `dual_log_accumulator.py`, `format.py`, `proxy_badge.py`, `render_turn.py`

---

### turn_cache.py (14 LOC)

**Purpose:** Holder for the frozen-turn state of one pane.
**Reads:** none.
**Writes:** its own fields.
**Called by:** `format.py`, `pane.py`, `worker_proxy_pane.py`.
**Calls out:** none

---

### forwarded_parser.py (291 LOC)

**Purpose:** Parses the forwarded dual-log and rebuilds per-request entries by delta application; owns proxy session id and log id resolution shared with `parser.py`.
**Reads:** forwarded dual-log files (incremental); session marker files; repo root via `monitor_root`.
**Writes:** returns entries and positions; pane error log on read failures.
**Called by:** `pane.py`, `worker_proxy_pane.py`, `parser.py`, `proxy_pane_shared.py`, `dual_log_accumulator.py`, `src/dual_log_cli/project_map.py`.
**Calls out:** `proxy.message_summary`, `proxy.logging`, `pane_error_log`, `monitor_root`

---

### parser.py (81 LOC)

**Purpose:** Resolves the proxy log paths of the current session from marker files and discovers worker logs.
**Reads:** session marker files in the runtime log directory.
**Writes:** none (returns paths, ids or None).
**Called by:** `pane.py`, `worker_proxy_pane.py`, `proxy_pane_shared.py`, `__init__.py`, `src/panes/warnings_pane.py`, `src/panes/token_pane.py`.
**Calls out:** `forwarded_parser.py`

---

### proxy_badge.py (77 LOC)

**Purpose:** Decides which strip/inject badges a REQ header shows, including the total-tokens nuke text detection.
**Reads:** entry dicts or raw delta values; parameters only.
**Writes:** none.
**Called by:** `dual_log_accumulator.py`, `render_turn.py`, `format.py`.
**Calls out:** stdlib only

---

### dual_log_accumulator.py (112 LOC)

**Purpose:** Tails the stripped, injected and original dual-logs and builds the per-family overlay state that pane entries reference.
**Reads:** stripped, injected and original dual-log files (incremental).
**Writes:** the accumulator argument in place; returns the new file position; pane error log on read failure.
**Called by:** `pane.py`, `proxy_pane_shared.py`, `frozen_turns.py`, `src/dual_log_cli/overlay.py`.
**Calls out:** `pane_error_log`, `forwarded_parser.py`

---

### side_logs.py (56 LOC)

**Purpose:** Incremental readers for the response and errors side-logs.
**Reads:** response and errors dual-log files.
**Writes:** none (returns tuples); pane error log on failures.
**Called by:** `src/panes/token_pane.py`, `src/panes/warnings_pane.py`, `proxy_pane_shared.py`.
**Calls out:** `pane_error_log`, `forwarded_parser.py`

---

### render_turn.py (170 LOC)

**Purpose:** Renders the per-request rows of an expanded turn group: header line, request labels, status markers and dispatch to the section renderers.
**Reads:** group, entries, expand states, pane width, request number map.
**Writes:** returns lines and keys; mutates a label counter in place.
**Called by:** `frozen_turns.py`, `search.py`.
**Calls out:** `render_messages.py`, `render_sections.py`, `render_sections_system.py`, `format.py`, `utils`

---

### render_sections.py (255 LOC)

**Purpose:** Renders the tools, fields-delta, beta-flags and directives sections of an expanded request, including expandable whole-stripped tools.
**Reads:** entry, previous entry, expand states, pane width, modifications.
**Writes:** returns lines and keys.
**Called by:** `render_turn.py`; `dev/proxy_tool_stripping/tests/test_whole_stripped_tool_expand.py`.
**Calls out:** `render_line_helpers.py`

---

### render_sections_system.py (88 LOC)

**Purpose:** Renders the system-blocks section of an expanded request with per-block delta visibility and strip/inject coloring.
**Reads:** entry, previous entry, expand states.
**Writes:** returns lines and keys.
**Called by:** `render_turn.py`.
**Calls out:** `format.py`, `render_line_helpers.py`

---

### render_line_helpers.py (33 LOC)

**Purpose:** Shared line-emission primitives for the section renderers.
**Reads:** parameters only.
**Writes:** returns lines and keys.
**Called by:** `render_sections.py`, `render_sections_system.py`.
**Calls out:** `colors`

---

### render_messages.py (238 LOC)

**Purpose:** Renders new, modified and removed messages of an expanded request with span overlay, thinking drill-down and copy affordances.
**Reads:** entry, previous entry, all entries, expand states, pane width.
**Writes:** returns lines and keys.
**Called by:** `render_turn.py`.
**Calls out:** `proxy.strip_vocab`, `utils`

---

### search.py (24 LOC)

**Purpose:** Finds the entries whose force-expanded render matches a query, using the real render path.
**Reads:** entries with messages populated, expand states, pane width.
**Writes:** none (returns entry indices).
**Called by:** `proxy_pane_shared.py`.
**Calls out:** `utils`

---

## State

`pane.py` and `worker_proxy_pane.py` each own independent module-level state: entries, expand and search state, scroll and hover, overlay accumulators, and the frozen-turn cache held via `turn_cache.py`. The main pane alone owns the original-tools accumulator and an undo stack. Entries hold references into the accumulators. All other modules are stateless. Invariants and gotchas are in `process-docs/refactoring/` (phase 4 proxy/panes restructure file).
