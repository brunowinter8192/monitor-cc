# src/gpu_pane/

## Role

Standalone tmux pane that monitors RAG GPU servers and indexed collections across projects. Reads the RAG box state files, shows servers, collections and recent errors, and toggles servers via `rag-cli` on key or click. No dependency on `core/monitor.py`. Do not touch for the RAG server lifecycle itself.

## Public Interface

The pane loop in `pane.py` is the entry point, called by `workflow.py` for the gpu mode.

## Flow

Poll tick in `pane.py` → `status.py` reads the state files and anomalies, `errors.py` reads today's errors, collections are fetched on a slower cadence.
→ `gpu_render.py` renders the blocks and rebuilds the button regions.
Key or click → `gpu_actions.py` fires the `rag-cli` action and tracks the transition until confirmed or timed out.

## Modules

### pane.py (244 LOC)

**Purpose:** Event loop with keyboard and mouse dispatch, search bar and preset toggling.
**Reads:** status, anomalies, errors and collections from the sibling modules.
**Writes:** stdout frames; pane error log; the search state and, in place, the toggle and button-region state of sibling modules.
**Called by:** `workflow.py`.
**Calls out:** `rag-cli`

---

### gpu_actions.py (44 LOC)

**Purpose:** Server control actions and the pending-toggle state with its expiry.
**Reads:** preset and arbitrary server lists passed as arguments.
**Writes:** the toggle state; one `rag-cli` subprocess per action.
**Called by:** `pane.py`, `gpu_render.py`.
**Calls out:** `rag-cli`, `pane_error_log`

---

### gpu_render.py (180 LOC)

**Purpose:** Renders the servers, collections and errors blocks with idle countdown and context-dependent buttons.
**Reads:** the toggle state from `gpu_actions.py`; everything else via arguments.
**Writes:** the button regions (rebuilt on every render); returns the rendered string.
**Called by:** `pane.py`; `dev/click_ui/p4_gpu_news_button_probe.py`.
**Calls out:** none

---

### status.py (243 LOC)

**Purpose:** Reads the RAG state-file registry, builds server status lists, detects anomalies and fetches collections.
**Reads:** RAG state files; server health endpoints; process memory via `ps`; `rag-cli` output.
**Writes:** its anomaly list and the pane's own rotating log file.
**Called by:** `pane.py`.
**Calls out:** `rag-cli`, `ps`, `pane_error_log`

---

### errors.py (41 LOC)

**Purpose:** Reads RAG's error log and keeps only today's anomaly events.
**Reads:** RAG's error JSONL.
**Writes:** none.
**Called by:** `pane.py`.
**Calls out:** none

---

## State

`gpu_actions.py` owns the pending-toggle state, `gpu_render.py` the clickable button regions, `status.py` the anomaly list and the preset names, `pane.py` the search state. Modules share the same objects by import and are mutated only by their owners and `pane.py`. Behavior notes are in `process-docs/refactoring/` (phase 4 proxy/panes restructure file).
