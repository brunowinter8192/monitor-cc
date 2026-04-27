# src/hooks/

## Role

Hook log pipeline for the dedicated Hooks tmux pane. Parses `src/logs/hook_outputs.jsonl`
incrementally, enriches entries with persisted additionalContext files, formats them into
interactive ANSI display items with expand/collapse and hover, and drives the pane event loop.
Touch this package when adding new hook event types, changing hooks pane display logic, or
modifying how persisted context files are discovered. Do NOT touch for rules pane routing —
that lives in `src/panes/rules_pane.py`.

## Public Interface

- `run_hooks_loop` — Hooks pane event loop (entry point from `core.monitor`)
- `parse_new_hook_entries(last_position)` — parse new log lines, returns `(entries, new_position)`
- `filter_by_project(entries, project_filter)` — filter entries by project path substring
- `filter_by_timestamp(entries, min_ts)` — filter entries to current session window
- `get_current_position()` — return current byte offset of hook log file

## Flow

`src/logs/hook_outputs.jsonl` → `hook_parser` (incremental JSONL parse by byte offset)
→ `hooks_format` (build display items, expand/collapse, hover)
→ `hooks_persist` (enrich with persisted additionalContext from session tool-results/)
→ `hooks_pane` (render + stdin event loop → stdout)

## Modules

### hook_parser.py (62 LOC)

**Purpose:** Parse `src/logs/hook_outputs.jsonl` into hook entry dicts with incremental byte-offset reads and optional project/timestamp filtering.
**Reads:** `src/logs/hook_outputs.jsonl` (by last byte position).
**Writes:** Nothing — returns `(entries_list, new_position)`.
**Called by:** `src/hooks/hooks_pane.py`, `src/panes/rules_pane.py`, `src/core/monitor.py`
**Calls out:** —

---

### hooks_format.py (150 LOC)

**Purpose:** Convert raw hook entry dicts into display item dicts and render the full hooks pane block with expand/collapse, scroll viewport, and hover highlight.
**Reads:** Raw hook entry dicts; in-memory display item list; scroll offset and hover state.
**Writes:** ANSI-escaped string for pane output.
**Called by:** `src/hooks/hooks_pane.py`, `src/hooks/hooks_persist.py`
**Calls out:** —

---

### hooks_pane.py (206 LOC)

**Purpose:** Event loop for the Hooks tmux pane — polls hook log, processes mouse/keyboard input, renders on change.
**Reads:** Shared monitor state (`active_project_filter`, session timestamp); stdin (keyboard/mouse via `input.click_handler`).
**Writes:** ANSI output to stdout (direct tmux pane write).
**Called by:** `src/core/monitor.py` (via `..hooks.run_hooks_loop`)
**Calls out:** `input` (click_handler)

---

### hooks_persist.py (79 LOC)

**Purpose:** Scan active session `tool-results/` directories for persisted `additionalContext` files (written when hook output exceeds ~10 KB); enrich in-memory display items with full content.
**Reads:** `<session>/tool-results/hook-*-additionalContext.txt` files; active session list via `session_finder`.
**Writes:** Mutates existing display items in place; returns new standalone items for `toolu_*` files.
**Called by:** `src/hooks/hooks_pane.py`
**Calls out:** `session_finder`

---

## State

`hooks_pane.py` owns three module-level mutable variables:
- `hooks_display_items: List[dict]` — accumulated display items across polls
- `hooks_hover_row: Optional[int]` — currently hovered row index
- `hooks_line_map: Dict[int, int]` — maps screen line → display item index for click handling

All three are mutated exclusively by `run_hooks_loop` and read by the format/render pipeline in the same pane process.
