# src/hooks/

Hook log pipeline — parse → filter → enrich → display in dedicated tmux pane.

## Data Flow

```
src/logs/hook_outputs.jsonl → hook_parser → filter/ts-scope → hooks_format + hooks_persist → hooks_pane TUI
```

## Modules

## hook_parser.py

**Purpose:** Parse `src/logs/hook_outputs.jsonl` into hook entry dicts. Filter by project path and timestamp.

**Input:** File byte positions (for incremental reads), optional project filter string, optional ISO timestamp.

**Output:** List of hook entry dicts; updated file position int.

---

## hooks_format.py

**Purpose:** Build display item dicts from raw hook entries; render the hooks pane block with expand/collapse, hover highlight, and scroll.

**Input:** Raw hook entry dicts; display item lists; scroll/hover state.

**Output:** Formatted ANSI strings for the hooks pane.

---

## hooks_persist.py

**Purpose:** Scan active session `tool-results/` directories for persisted `additionalContext` files (written when hook output exceeds the ~10KB injection limit). Enrich in-memory hook display items with their full content.

**Input:** Optional project filter; list of existing hook display items.

**Output:** Enriched items (mutated in place) + standalone display items for `toolu_*` files.

---

## hooks_pane.py

**Purpose:** Event loop for the Hooks tmux pane. Polls hook log for new entries, handles mouse scroll/click/hover, and renders the formatted block.

**Input:** Shared monitor state (project filter, session timestamp, hook log position).

**Output:** ANSI screen output written to stdout (direct tmux pane write).
