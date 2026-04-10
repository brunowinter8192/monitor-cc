# src/proxy/

mitmproxy addon package. Loaded by mitmproxy via `-s proxy_addon.py` (the thin wrapper in `src/`).

## addon.py

**Purpose:** Core mitmproxy addon class and low-level HTTP helpers.
**Input:** mitmproxy `http.HTTPFlow` objects via mitmproxy hooks.
**Output:** Modifies `flow.request.content` in place; writes JSONL log entries; writes error payload JSON on 4xx responses.

Contains:
- `ProxyAddon` class with `request()` and `response()` hooks
- `_resolve_log_file()` — resolves log path from MONITOR_CC_ROOT / PROXY_LOG_ID env vars
- `_is_messages_request()` — checks flow is POST /v1/messages on api.anthropic.com
- `_decode_body()` — decodes request body, decompresses gzip if needed
- `_parse_payload()` — parses JSON payload bytes
- `_write_entry()` — appends JSONL log entry to file
- `addons = [ProxyAddon()]` — mitmproxy addon registration

## logging.py

**Purpose:** Build structured log entries from flow + payload data.
**Input:** Raw payload dicts, message lists.
**Output:** Structured dicts for JSONL logging.

Contains:
- `_build_entry()` — builds full log entry from flow + payload + previous state
- `_count_system_chars()` — counts chars in system field (string or list)
- `_compute_diff()` — computes diff between previous and current message summaries
- `_summarize_content_for_log()` — truncates raw content for log storage

## message_summary.py

**Purpose:** Summarize and classify message content for log entries.
**Input:** Raw message dicts from API payload.
**Output:** Compact summary dicts (role, type, chars, preview, blocks, has_cache_control).

Contains:
- `_summarize_message()` — summarizes a single message into a compact dict
- `_has_cache_control()` — checks if message or any block has cache_control set
- `_classify_content()` — classifies message content into (type, chars, preview)
- `_classify_text()` — classifies plain text by special tag prefixes
- `_classify_blocks()` — classifies a list of content blocks

## rules.py

**Purpose:** Apply proxy modification rules to API payloads before forwarding.
**Input:** Raw `payload` dict from Claude Code's API request.
**Output:** `(modified_payload, modifications, original_system2_text, stripped_msg_indices, stripped_msg_originals)` tuple.

Contains:
- `apply_modification_rules()` — orchestrates all rules, returns 5-tuple
- `_strip_blocked_tool_references()` — removes tool_reference blocks for TOOL_BLOCKLIST tools
- `_content_contains()` — checks if message content contains a substring
- `_strip_task_notification_tags()` — removes output-file and tool-use-id tags

## content_strip.py

**Purpose:** Strip or extract specific content blocks from API message payloads.
**Input:** Message content (string or list of blocks), marker strings.
**Output:** Modified content (string or list), or extracted text.

Contains:
- `_strip_plan_mode_blocks()` — removes plan-mode system-reminder blocks
- `_strip_system_reminder()` — strips system-reminder blocks containing a marker string
- `_message_has_rejection()` — detects tool rejection marker in user message
- `_strip_rejection_message()` — replaces rejection tool_result content with "."
- `_extract_session_start_block()` — extracts SessionStart rules block from MSG[0]
- `_strip_session_guidance()` — removes "Session-specific guidance" section from text

## cache.py

**Purpose:** Manage cache_control markers in API payloads.
**Input:** Payload dicts; previous request's message summaries for BP3 placement.
**Output:** Modified payload dicts with cache_control added or stripped.

Contains:
- `_strip_all_cache_control()` — removes all cache_control markers from system, tools, messages
- `_set_cache_breakpoints()` — sets BP1 (rules/last system), BP2 (last tool), BP3 (last unchanged msg), BP4 (last msg)
- `_add_cache_control_to_message()` — adds cache_control to the last content block of a message

## tools.py

**Purpose:** Strip blocklisted tools from API payloads.
**Input:** Payload dict with `tools` list.
**Output:** `(modified_payload, count_removed)` tuple.

Contains:
- `_strip_unused_tools()` — removes tools whose name is in TOOL_BLOCKLIST
