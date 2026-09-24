# src/panes/

## Role

Dedicated tmux pane event loops for the token/cache tracker and the warnings pane. Each module owns one pane's poll cycle, stdin handling and ANSI output, spawned by `core/monitor.py` and never returning. Touch to change what a pane shows or how it reacts to input. General formatting belongs in `format/`.

## Public Interface

`__init__.py` exports the tokens loop and the warnings loop. `token_search.py`, `cache_turns.py` and `log_janitor.py` are not exported; their callers import them directly.

## Flow

`core/monitor.py` selects a mode → lazy import from this package → the pane loop polls its data source.
→ stdin is handled through `input.click_handler` → the frame is written via `frame_writer` (in-place, synchronized output).

## Modules

### token_pane.py (329 LOC)

**Purpose:** Token/cache-tracker pane loop with incremental transcript read, interactive view, response-log polling, and the periodic log sweep.
**Reads:** session JSONL and response dual-log (incremental); active project filter from `core/monitor.py`.
**Writes:** stdout frames; pane error log; its own module state.
**Called by:** `src/core/monitor.py`.
**Calls out:** none

---

### cache_turns.py (70 LOC)

**Purpose:** Incrementally reads new session JSONL lines and merges the resulting cache turns into the existing list.
**Reads:** the session JSONL from a given position (parameters only).
**Writes:** none (returns turns and the new position).
**Called by:** `token_pane.py`, `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py`.
**Calls out:** none

---

### token_search.py (34 LOC)

**Purpose:** Finds the token-pane match keys for a query by reusing the real render functions.
**Reads:** turns, pane width, optional response map (parameters only).
**Writes:** none (returns keys).
**Called by:** `token_pane.py`, `workers/worker_search.py`.
**Calls out:** none

---

### warnings_pane.py (315 LOC)

**Purpose:** Warnings pane loop and state owner: reads tool errors from session and worker errors dual-logs and renders them.
**Reads:** errors dual-log and worker errors dual-logs (incremental); active project filter.
**Writes:** stdout frames; pane error log; its own module state.
**Called by:** `src/core/monitor.py`.
**Calls out:** none

---

### warnings_render.py (193 LOC)

**Purpose:** Pure rendering helpers for the warnings pane: pane body, header, clipboard text and search matching.
**Reads:** all state passed as arguments.
**Writes:** none (returns strings and a line map); fills region outputs when given.
**Called by:** `warnings_pane.py`.
**Calls out:** none

---

### log_janitor.py (190 LOC)

**Purpose:** Registry of the project's log files and the age-based JSONL cleanup triggered from the token pane.
**Reads:** JSONL files passed in as paths.
**Writes:** rewrites the given JSONL file atomically; pane error log and notes.
**Called by:** `token_pane.py`; `dev/hook_smoke/test_log_janitor.py`.
**Calls out:** none

---

## State

Each pane module owns its own module-level scroll, expand, hover, copy and search state; nothing is shared between panes. All read the active project filter from `core/monitor.py`. `warnings_render.py`, `token_search.py` and `cache_turns.py` are stateless. Gotchas about render loops and input are in `process-docs/refactoring/` (phase 4 proxy/panes restructure file).
