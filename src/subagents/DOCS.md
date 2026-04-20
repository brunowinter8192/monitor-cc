# src/subagents/

## Role

Subagents pane package. Tracks active Claude Code subagent sessions, renders per-agent tool call
lists and per-turn cache-tracker views in an interactive TUI pane with expand/collapse. The
`subagent_states` dict in `subagent_ui` is the shared expand/collapse state — imported directly
(not copied) by the render and pane modules and by `input.ui_mode` for the main pane subagent
overlay. Touch this package when changing subagent display, expand/collapse behavior, or
cache-tracker rendering per agent. Do NOT touch for subagent tracking in the MAIN pane — that
runs via `input.ui_mode.track_subagent_metadata()` called from `monitor_session.py`.

## Public Interface

- `run_subagents_loop` — Subagents pane event loop (defined but not currently wired to `--mode` in `workflow.py` — see Gotchas)

## Flow

`_monitor.subagent_metadata` + `_monitor.tool_calls_by_agent` (shared global state)
→ `subagent_pane` (event loop, per-agent JSONL reads for cache turns)
→ `subagent_render` (render list with token view for expanded agents)
→ `subagent_ui` (build entries, apply hover/scroll viewport)
→ `subagent_ui_format` (format collapsed/expanded rows, tool call summaries)
→ stdout

## Modules

### subagent_pane.py (143 LOC)

**Purpose:** Subagents pane event loop — keyboard/mouse input, periodic JSONL data refresh for cache turns, session change detection, and screen rendering.
**Reads:** `_monitor.subagent_metadata`, `_monitor.tool_calls_by_agent` (shared global state); session JSONL files for `extract_cache_turns`; stdin.
**Writes:** ANSI output to stdout (direct tmux pane write).
**Called by:** `src/core/monitor.py` (via `..subagents.run_subagents_loop`)
**Calls out:** `jsonl`, `session_finder`, `input` (click_handler)

---

### subagent_render.py (83 LOC)

**Purpose:** Render the full subagent list with per-agent cache-tracker turns for expanded agents; populates `pane_line_map` and `cache_line_map` for click handling.
**Reads:** `subagent_metadata_map`, `turns_by_agent`, pane dimensions, scroll/expand state dicts; imports `subagent_states` from `subagent_ui`.
**Writes:** Nothing — returns formatted ANSI string; mutates caller-supplied `pane_line_map` and `cache_line_map`.
**Called by:** `src/subagents/subagent_pane.py`
**Calls out:** `format` (token_format)

---

### subagent_ui.py (127 LOC)

**Purpose:** Subagent list state owner and rendering orchestrator — builds all entries, applies hover highlight and scroll viewport, manages `subagent_states` expand/collapse dict.
**Reads:** `subagent_metadata` dict (agent_id → metadata), `tool_calls_by_agent` dict from monitor global state.
**Writes:** Mutates `subagent_states` via `toggle_subagent_state`; returns formatted ANSI string.
**Called by:** `src/subagents/subagent_render.py`, `src/subagents/subagent_pane.py`, `src/input/ui_mode.py`
**Calls out:** —

---

### subagent_ui_format.py (95 LOC)

**Purpose:** Low-level entry formatting helpers — collapsed/expanded agent headers, tool call summary lines, display name derivation, char count formatting.
**Reads:** Agent metadata dicts, tool call dicts.
**Writes:** Nothing — returns formatted terminal strings.
**Called by:** `src/subagents/subagent_ui.py`, `src/subagents/subagent_render.py`, `src/input/ui_mode.py`
**Calls out:** —

---

## State

`subagent_ui.py` owns `subagent_states: Dict[str, bool]` — the expand/collapse state keyed by
`agent_id`. This object is imported by reference (not copied) in `subagent_render.py`,
`subagent_pane.py`, and `input.ui_mode`, so mutations in any of those modules are immediately
visible to all others within the same process.

Also owns: `line_to_agent_map`, `_last_agent_count`, `_last_expanded_count`, `_last_entry_count`,
`_last_expanded_entries` — render-delta tracking to avoid redundant redraws.

## Gotchas

`run_subagents_loop` is exported via `__init__.py` but is NOT wired to any `--mode` flag in
`workflow.py`. The subagent tracking visible in the MAIN pane runs via a different path:
`input.ui_mode.track_subagent_metadata()` called from `monitor_session.py`. The two paths share
`subagent_states` but operate in separate processes and have separate event loops.
