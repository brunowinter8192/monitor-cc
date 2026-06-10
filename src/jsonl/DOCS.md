# src/jsonl/

## Role

Session JSONL parsing pipeline. Reads `~/.claude/projects/**/*.jsonl` files incrementally by byte
offset, correlates tool_use/tool_result pairs, extracts typed metadata (prompts, media, thinking,
skills, usage), and provides cache-turn data for the token and worker panes. This is the
single source of truth for all session content — every pane that displays session data reads
through this package. Touch it when adding new message types, changing extraction logic, or
modifying cache-turn grouping. Do NOT touch for display logic — that lives in the pane packages.

## Public Interface

- `parse_new_tool_calls(filepath, last_position, tool_use_cache)` — incremental parse, returns 9-tuple of lists + new position
- `read_new_lines(filepath, last_position)` — read raw new lines from file
- `parse_jsonl_lines(lines)` — parse raw lines into message dicts
- `get_current_position(filepath)` — return current byte offset
- `get_message_content(message)` — extract content from a message dict
- `is_tool_use(message)` — check if message is a tool_use block
- `extract_cache_turns(messages)` — extract per-turn cache tracking data grouped by user prompts

## Flow

`~/.claude/projects/**/*.jsonl` → `jsonl_parser` (incremental read by byte offset, line parse,
tool_use/tool_result correlation) → `jsonl_extractors` (typed extractions from message list)
→ callers: `core.monitor`, `panes.token_pane`, `workers`

## Modules

### jsonl_parser.py (256 LOC)

**Purpose:** Core session JSONL parser — reads new lines incrementally by byte offset, correlates tool_use/tool_result pairs, and delegates typed extraction to `jsonl_extractors`.
**Reads:** Session JSONL file (by `filepath` + `last_position` byte offset); `tool_use_cache` dict for cross-chunk correlation.
**Writes:** Nothing — returns 9-tuple `(tool_calls, new_position, malformed_warnings, user_media, thinking_blocks, user_prompts, skill_activations, usage_data, system_messages)`.
**Called by:** `src/core/monitor.py`, `src/core/monitor_session.py`, `src/workers/worker_format.py`, `src/workers/worker_pane.py`, `src/panes/token_pane.py`
**Calls out:** —

---

### jsonl_extractors.py (180 LOC)

**Purpose:** Extract typed data from parsed JSONL message lists: user media (images/documents), user prompts, thinking blocks, skill activations, usage data, system messages.
**Reads:** List of message dicts (from `parse_jsonl_lines`).
**Writes:** Nothing — one typed list returned per extractor function.
**Called by:** `src/jsonl/jsonl_parser.py`
**Calls out:** —

---

### jsonl_cache_turns.py (150 LOC)

**Purpose:** Extract per-turn cache tracking data grouped by user prompts; each turn contains a list of requests with CR/CC/D/Out token metrics. Implements streaming-snapshot dedup: CC sometimes writes multiple assistant messages for the same request as incremental snapshots (partial thinking + final output). The dedup logic uses a `seen_types` set of `(type, identifier)` tuples (`('tool_use', tool_name)`, `('thinking',)`, `('text', preview)`) to skip blocks already counted in an earlier snapshot of the same response — preventing double-counting of thinking_chars across snapshots. Each `api_call` dict carries 6 usage extras from the `usage` object: `cache_creation_ttl` (dict `{ephemeral_5m_input_tokens, ephemeral_1h_input_tokens}`), `server_tool_use` (dict `{web_search_requests, web_fetch_requests}`), `service_tier` (str), `speed` (str), `inference_geo` (str, often `""`), `iterations` (list of per-iteration breakdown dicts).
**Reads:** List of message dicts.
**Writes:** Nothing — returns list of cache turn dicts.
**Called by:** `src/panes/token_pane.py`, `src/workers/worker_pane.py`
**Calls out:** —
Private helpers (same module): `_parse_user_message_text`, `_extract_content_blocks`, `_build_api_call`, `_merge_duplicate_call`.
