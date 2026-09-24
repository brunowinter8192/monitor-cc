# src/jsonl/

## Role

Session JSONL parsing pipeline. Reads `~/.claude/projects/**/*.jsonl` files incrementally by byte
offset and extracts per-turn cache-tracking data for the tokens and workers panes. This is the
single source of truth for session content — every pane that displays session data reads through
this package. Touch it when adding new message types or changing cache-turn grouping. Do NOT
touch it for display logic — that lives in the pane packages.

## Public Interface

- `JsonlReader(path, start_pos)` — iterate complete JSON lines from a byte offset; `.position` is the offset after the last complete line
- `read_json_records(path, start_pos)` — list of records plus new byte offset
- `JsonlCorruptError` — raised for an unparseable terminated line
- `get_message_content(message)` — extract content blocks from a message dict
- `is_tool_use(block)` — check if a content block is a `tool_use` block
- `extract_cache_turns(messages)` — extract per-turn cache-tracking data grouped by user prompts

## Flow

`~/.claude/projects/**/*.jsonl` → `jsonl_reader` (incremental read by byte offset, stops before an unterminated last line) →
`jsonl_cache_turns.extract_cache_turns` (group into turns, dedup streaming-snapshot duplicates) →
callers: `panes/cache_turns.py`, `workers/worker_pane.py`, `workers/worker_format.py`. The same reader serves the dual-log, response and errors readers in `proxy_display`, `panes/warnings_pane.py`, `gpu_pane/errors.py` and `dual_log_cli/reader.py`.

## Modules

### jsonl_reader.py (38 LOC)

**Purpose:** Shared incremental JSON-lines reader that never consumes an unterminated last line and raises on interior corruption.
**Reads:** Any JSONL file (by path plus byte offset).
**Writes:** nothing — yields records and exposes the new byte offset.
**Called by:** `core/monitor.py`, `panes/cache_turns.py`, `panes/warnings_pane.py`, `workers/worker_format.py`, `proxy_display/forwarded_parser.py`, `proxy_display/dual_log_accumulator.py`, `proxy_display/side_logs.py`, `gpu_pane/errors.py`, `dual_log_cli/reader.py`.
**Calls out:** none.

---

### jsonl_parser.py (13 LOC)

**Purpose:** Content-block helpers for a session message dict (`get_message_content`, `is_tool_use`).
**Reads:** Message dicts (parameter only).
**Writes:** nothing.
**Called by:** `workers/worker_format.py`.
**Calls out:** none.

---

### jsonl_cache_turns.py (156 LOC)

**Purpose:** `extract_cache_turns(messages)` groups messages into turns (one per external user prompt) and merges each turn's assistant responses into `api_calls`, each carrying CR/CC/D/output token counts, the `timestamp` of the request's LAST assistant entry (response end), plus rate-limit/service-tier usage extras. Implements streaming-snapshot dedup: CC sometimes writes multiple assistant messages for the same request as incremental snapshots (partial thinking + final output) sharing one `requestId`; `_absorb_assistant_call`/`_merge_duplicate_call` use a `seen_types` set of `(type, identifier)` tuples to skip content blocks already counted in an earlier snapshot of the same response.
**Reads:** List of message dicts (parameter only).
**Writes:** nothing — returns a list of cache-turn dicts.
**Called by:** `panes/cache_turns.py`, `workers/worker_pane.py`.
**Calls out:** none.

---

## Gotchas

- CC's current JSONL format splits one logical API response into multiple top-level `assistant` lines — one per content block (thinking/text/tool_use each get their own line) — all sharing the identical `requestId` and `usage` object. `extract_cache_turns`'s per-`requestId` dedup (`_input_key`, `_merge_duplicate_call`) already handles this; do not assume one JSONL line == one API response when reading this package's code.
- `_start_turn_from_user` treats a message starting with `<command-message>`/`<command-name>` as a skill invocation and always opens a new turn for it, even if the previous turn's timestamp matches — this is the one exception to the "same-timestamp messages merge into the current turn" rule.
