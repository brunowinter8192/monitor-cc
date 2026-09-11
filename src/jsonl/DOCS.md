# src/jsonl/

## Role

Session JSONL parsing pipeline. Reads `~/.claude/projects/**/*.jsonl` files incrementally by byte
offset and extracts per-turn cache-tracking data for the tokens and workers panes. This is the
single source of truth for session content — every pane that displays session data reads through
this package. Touch it when adding new message types or changing cache-turn grouping. Do NOT
touch it for display logic — that lives in the pane packages.

## Public Interface

- `read_new_lines(filepath, last_position)` — read raw new lines from file
- `parse_jsonl_lines(lines)` — parse raw lines into message dicts (+ malformed-line records)
- `get_current_position(filepath)` — return current byte offset
- `get_message_content(message)` — extract content blocks from a message dict
- `is_tool_use(block)` — check if a content block is a `tool_use` block
- `extract_cache_turns(messages)` — extract per-turn cache-tracking data grouped by user prompts

## Flow

`~/.claude/projects/**/*.jsonl` → `jsonl_parser` (incremental read by byte offset, line parse) →
`jsonl_cache_turns.extract_cache_turns` (group into turns, dedup streaming-snapshot duplicates) →
callers: `panes/cache_turns.py`, `workers/worker_pane.py`, `workers/worker_format.py`.

## Modules

### jsonl_parser.py (51 LOC)

**Purpose:** Core session JSONL reader — reads new lines incrementally by byte offset and parses them into message dicts, flagging malformed lines.
**Reads:** Session JSONL file (by `filepath` + `last_position` byte offset).
**Writes:** nothing — returns parsed messages / malformed-line records / byte positions.
**Called by:** `core/monitor.py`, `panes/cache_turns.py`, `workers/worker_pane.py`, `workers/worker_format.py`.
**Calls out:** none.

---

### jsonl_cache_turns.py (154 LOC)

**Purpose:** `extract_cache_turns(messages)` groups messages into turns (one per external user prompt) and merges each turn's assistant responses into `api_calls`, each carrying CR/CC/D/output token counts plus rate-limit/service-tier usage extras. Implements streaming-snapshot dedup: CC sometimes writes multiple assistant messages for the same request as incremental snapshots (partial thinking + final output) sharing one `requestId`; `_absorb_assistant_call`/`_merge_duplicate_call` use a `seen_types` set of `(type, identifier)` tuples to skip content blocks already counted in an earlier snapshot of the same response.
**Reads:** List of message dicts (parameter only).
**Writes:** nothing — returns a list of cache-turn dicts.
**Called by:** `panes/cache_turns.py`, `workers/worker_pane.py`.
**Calls out:** none.

---

## Gotchas

- CC's current JSONL format splits one logical API response into multiple top-level `assistant` lines — one per content block (thinking/text/tool_use each get their own line) — all sharing the identical `requestId` and `usage` object. `extract_cache_turns`'s per-`requestId` dedup (`_input_key`, `_merge_duplicate_call`) already handles this; do not assume one JSONL line == one API response when reading this package's code.
- `_start_turn_from_user` treats a message starting with `<command-message>`/`<command-name>` as a skill invocation and always opens a new turn for it, even if the previous turn's timestamp matches — this is the one exception to the "same-timestamp messages merge into the current turn" rule.
