# src/jsonl/

## Role

Session JSONL parsing pipeline: reads session files incrementally by byte offset and extracts per-turn cache-tracking data for the tokens and workers panes. Single source of truth for session content. Touch for new message types or cache-turn grouping; not for display logic, which lives in the pane packages.

## Public Interface

`__init__.py` re-exports the following:
- the incremental line reader class and its list-returning helper
- the corrupt-line error type
- content-block helpers for a message dict
- the cache-turn extractor

## Flow

Session JSONL files -> `jsonl_reader.py` (incremental read by byte offset, stops before an unterminated last line) -> `jsonl_cache_turns.py` (group into turns, dedup streaming snapshots) -> callers `panes/cache_turns.py`, `workers/worker_format.py`. The same reader serves the dual-log, response and error readers in `proxy_display`, `panes/warnings_pane.py`, `gpu_pane/errors.py` and `dual_log_cli/reader.py`.

## Modules

### jsonl_reader.py (38 LOC)

**Purpose:** shared incremental JSON-lines reader that never consumes an unterminated last line and raises on interior corruption.
**Reads:** any JSONL file (by path plus byte offset).
**Writes:** nothing; yields records and exposes the new byte offset.
**Called by:** `core/monitor.py`, `panes/cache_turns.py`, `panes/warnings_pane.py`, `workers/worker_format.py`, `proxy_display/forwarded_parser.py`, `proxy_display/dual_log_accumulator.py`, `proxy_display/side_logs.py`, `gpu_pane/errors.py`, `dual_log_cli/reader.py`.
**Calls out:** none.

---

### jsonl_parser.py (13 LOC)

**Purpose:** content-block helpers for a session message dict.
**Reads:** message dicts (parameter only).
**Writes:** nothing.
**Called by:** `workers/worker_format.py`.
**Calls out:** none.

---

### jsonl_cache_turns.py (156 LOC)

**Purpose:** groups messages into turns per external user prompt and merges each turn's assistant responses into per-request API calls with token counts and timing.
**Reads:** list of message dicts (parameter only).
**Writes:** nothing; returns a list of cache-turn dicts.
**Called by:** `panes/cache_turns.py`.
**Calls out:** none.

---
