# src/jsonl/

## Role

Session JSONL parsing pipeline. Reads `~/.claude/projects/**/*.jsonl` files incrementally by byte
offset and provides cache-turn data for the token and worker panes. This is the single source of
truth for all session content — every pane that displays session data reads through this package.
Touch it when adding new message types or changing cache-turn grouping. Do NOT touch for display
logic — that lives in the pane packages.

**(2026-09) The tool_use/tool_result correlation + classification path removed** — `extract_tool_calls`,
`create_tool_use_entry`, `update_request_numbers`, `parse_new_tool_calls`/`parse_new_tool_calls_isolated`
(and its subprocess worker), `is_tool_result`, `get_progress_content`, `extract_spawned_agent_id`,
`extract_result_content`, `filter_excluded_tools`, `sort_by_timestamp`, `build_malformed_warnings`
all had exactly one real caller, `core/monitor_session.py`, which was deleted along with the main
pane it fed (window 0 is now the tokens pane at full width — see `process-docs/main_pane/`).
`jsonl_extractors.py` (user media/prompts/thinking/skills/usage/system-message extraction) lost
its only caller the same way and was deleted entirely.

## Public Interface

- `read_new_lines(filepath, last_position)` — read raw new lines from file
- `parse_jsonl_lines(lines)` — parse raw lines into message dicts
- `get_current_position(filepath)` — return current byte offset
- `get_message_content(message)` — extract content from a message dict
- `is_tool_use(message)` — check if message is a tool_use block
- `extract_cache_turns(messages)` — extract per-turn cache tracking data grouped by user prompts

## Flow

`~/.claude/projects/**/*.jsonl` → `jsonl_parser` (incremental read by byte offset, line parse) →
callers: `panes.token_pane`, `workers` (`read_new_lines`/`parse_jsonl_lines`/`extract_cache_turns`/
`get_message_content`/`is_tool_use`, read directly).

## Modules

### jsonl_parser.py (51 LOC)

**Purpose:** Core session JSONL reader — reads new lines incrementally by byte offset and parses
them into message dicts, flagging malformed lines.
**Reads:** Session JSONL file (by `filepath` + `last_position` byte offset).
**Writes:** Nothing — returns parsed messages / malformed-line records / byte positions.
**Called by:** `panes/token_pane.py`, `workers/worker_format.py` (`read_new_lines`, `parse_jsonl_lines`,
`get_current_position`, `get_message_content`, `is_tool_use` — all lower-level functions; there is
no higher-level "parse tool calls" entry point anymore, see Role above).
**Calls out:** —

---

### jsonl_cache_turns.py (154 LOC)

**Purpose:** Extract per-turn cache tracking data grouped by user prompts; each turn contains a list of requests with CR/CC/D/Out token metrics. Implements streaming-snapshot dedup: CC sometimes writes multiple assistant messages for the same request as incremental snapshots (partial thinking + final output). The dedup logic uses a `seen_types` set of `(type, identifier)` tuples (`('tool_use', tool_name)`, `('thinking',)`, `('text', preview)`) to skip blocks already counted in an earlier snapshot of the same response — preventing double-counting of thinking_chars across snapshots. Each `api_call` dict carries 6 usage extras from the `usage` object: `cache_creation_ttl` (dict `{ephemeral_5m_input_tokens, ephemeral_1h_input_tokens}`), `server_tool_use` (dict `{web_search_requests, web_fetch_requests}`), `service_tier` (str), `speed` (str), `inference_geo` (str, often `""`), `iterations` (list of per-iteration breakdown dicts).
**(2026-09, tokens-data-render-helpers milestone):** `extract_cache_turns` was 65 LOC — split into `_start_turn_from_user(message, current_turn, turns) -> Optional[dict]` (the external-user-message branch: starts a new turn for a skill-command or a plain prompt, or returns `current_turn` unchanged for a tool-result/empty/skill-preamble/duplicate-timestamp message — every early-exit path in the original just fell through to `continue` without touching `current_turn`, so the helper's "unchanged" return reproduces that exactly) and `_absorb_assistant_call(message, current_turn) -> None` (the assistant branch: dedup-merge into the last call or append a new one — mutates `current_turn` in place, same as before the split). `extract_cache_turns` itself is now a 2-branch dispatch loop calling these, byte-identical (`dev/panes/render_byte_identity.py`'s `build_cache_turns` incremental-chunk check, hash unchanged before/after).
**Reads:** List of message dicts.
**Writes:** Nothing — returns list of cache turn dicts.
**Called by:** `src/panes/token_pane.py`, `src/workers/worker_pane.py`
**Calls out:** —
Private helpers (same module): `_parse_user_message_text`, `_extract_content_blocks`, `_build_api_call`, `_merge_duplicate_call`, `_start_turn_from_user`, `_absorb_assistant_call`.

## Gotchas

- **CC's current JSONL format splits one logical API response into multiple top-level `assistant` lines — one per content block** (thinking/text/tool_use each get their own line), all sharing the identical `requestId` and `usage` object. `extract_cache_turns`'s pre-existing per-`requestId` dedup (`_input_key`, `_merge_duplicate_call`) already handles this correctly without any special-casing for the split — do not assume one JSONL line == one API response when reading this package's code.
