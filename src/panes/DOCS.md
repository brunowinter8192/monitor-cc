# src/panes/

Tmux pane event loops — each module owns one pane's poll cycle, input handling, and ANSI output.

## token_pane.py

**Purpose:** Event loop for the Token / Cache Tracker pane. Incrementally reads session JSONL, builds cache-turn dicts, and renders the interactive expand/collapse/scroll view.

**Input:** Shared monitor state (`_cache_jsonl_position`, project session path). Mouse and keyboard events via stdin.

**Output:** ANSI screen output written to stdout (direct tmux pane write).

**Called by:** `monitor.py` via `run_monitor()` (spawned in dedicated thread).

---

## rules_pane.py

**Purpose:** Event loop for the Rules pane. Polls the hook log for active rule invocations, groups them by source label, and renders an interactive expand/collapse view. Also exposes `process_hook_log()` for one-shot rule-state refresh from the monitor loop.

**Input:** Shared monitor state (project filter, session timestamp, hook log position). Mouse and keyboard events via stdin.

**Output:** ANSI screen output written to stdout (direct tmux pane write).

**Called by:** `monitor.py` via `run_monitor()` (spawned in dedicated thread); `process_hook_log()` called directly from the monitor loop.

---

## warnings_pane.py

**Purpose:** Event loop for the Warnings pane. Tails proxy JSONL for tool errors, groups them into expand/collapse entries, and renders a scrollable error list. Also exposes `track_unknown_type()` so the monitor session can log unknown message types into the warnings state.

**Input:** Shared monitor state (project filter, proxy log path, worker log positions). Mouse events via stdin.

**Output:** ANSI screen output written to stdout (direct tmux pane write).

**Called by:** `monitor.py` via `run_monitor()` (spawned in dedicated thread); `track_unknown_type()` called from `monitor_session.py`.

---

## waste_pane.py

**Purpose:** Event loop for the Waste / Proxy Forensics pane. Reads proxy JSONL and session JSONL to correlate tool-use calls with cache misses, and renders a scrollable cost-analysis view.

**Input:** Shared monitor state (project filter, proxy session start timestamp). Mouse and keyboard events via stdin.

**Output:** ANSI screen output written to stdout (direct tmux pane write).

**Called by:** `monitor.py` via `run_monitor()` (spawned in dedicated thread).
