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

**Purpose:** Apply proxy modification rules to API payloads before forwarding. Reads rule files from `~/.claude/shared-rules/` and writes system2 rules into system[2], project rules into messages[0].
**Input:** Raw `payload` dict from Claude Code's API request, `model_family` ("opus"/"sonnet"/"haiku"), `project_path` string.
**Output:** `(modified_payload, modifications, original_system2_text, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed)` tuple.

Contains:
- `apply_modification_rules(payload, model_family, project_path)` — orchestrates all rules, returns 6-tuple. Loads system2 rules via `_load_system2_rules(model_family, project_path)`, project rules via `_load_project_rules(project_path)`, replaces `system[2]` content with system2 rules (or `"."` if empty), injects project rules as `<system-reminder>` block in `messages[0]`.
- `_load_config()` — reads `~/.claude/shared-rules/proxy_rules.json`, caches by mtime
- `_read_rule_file()` — reads a rule file relative to shared-rules dir, caches by mtime
- `_load_system2_rules(model_family, project_path="")` — concatenates `global + opus` (for opus family) or `global + worker` (for sonnet) rule files from config. Haiku returns empty. **Project-level opt-out:** if `project_path` matches any pattern in `config["system2_rules"]["exclude_projects"]` (substring match, identical semantics to `_load_project_rules`), returns empty string immediately → `system[2]` becomes `"."`.
- `_load_project_rules(project_path)` — concatenates rule files for projects whose `path_contains` pattern matches `project_path`. Used to inject project-specific `<system-reminder>` into `messages[0]`.
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
- `_extract_session_start_block()` — extracts SessionStart rules block from MSG[0] (dead code — no longer called from rules.py since proxy reads files directly)
- `_strip_session_guidance()` — removes "Session-specific guidance" section from text

## cache.py

**Purpose:** Manage cache_control markers in API payloads.
**Input:** Payload dicts; previous request's message summaries for BP3 placement; previous request's tools count for stable-anchor marker on tools growth.
**Output:** Modified payload dicts with cache_control added or stripped.

Contains:
- `_strip_all_cache_control()` — removes all cache_control markers from system, tools, messages; calls `_normalize_user_content_shape()` on user msgs after strip
- `_normalize_user_content_shape()` — collapses `[{"type":"text","text":"X"}]` (single text block, no extra fields) to plain string `"X"` for user messages. Prevents byte-diff with Claude Code's native string form when BPs move across turns (see `decisions/cache_rebuild_cases.md` Case 1)
- `_set_cache_breakpoints(payload, prev_mod_messages, prev_tools_count)` — sets Tools Anchor (at `prev_tools_count - 1`, only on tools growth) + Tools End (last non-defer tool) + BP3 (last unchanged msg) + BP4 (last msg). BP1 (system marker) removed — system is cached implicitly via the tools→system→messages prefix leading to BP3. On stable tools count the anchor collapses onto the end marker (one effective marker). See `decisions/cache_rebuild_cases.md` Case 5 for the tool-growth rationale.
- `_add_cache_control_to_message()` — adds cache_control to the last content block of a message

## tools.py

**Purpose:** Strip blocklisted tools from API payloads.
**Input:** Payload dict with `tools` list.
**Output:** `(modified_payload, count_removed)` tuple.

Contains:
- `_strip_unused_tools()` — removes tools whose name is in TOOL_BLOCKLIST

## tool_injection.py

**Purpose:** Deterministic append-only injection of MCP tool schemas into `payload["tools"]`. Replaces Claude Code's lazy ToolSearch mechanism with proxy-side schema loading. Prevents `tools[]` mutation that causes cache rebuilds via alphabetical INSERT before BP2.
**Input:** Payload dict, project_path string.
**Output:** Modified payload with injected tools (iterative-dev always first, active plugins in activation order, stable alphabetical within each plugin block).

Reads schema store at `src/proxy/schemas/<plugin>/*.json` (populated by `dev/tool_injection/01_extract_schemas.py`) and active plugin list at `<project>/.claude/active_plugins.json` (managed by iterative-dev MCP tools `activate_plugin` / `deactivate_plugin` / `list_active_plugins`). Schema store is loaded once per proxy process (module-level cache). Active plugins use mtime-based reload. If schema store is missing or empty, injection is a no-op with a stderr warning.

Contains:
- `inject_mcp_tools()` — orchestrator: appends missing schemas for all active plugins
- `_load_schema_store()` — reads all `<plugin>/*.json` files; one-time load per process
- `_load_active_plugins()` — reads `active_plugins.json` with mtime check; default `[iterative-dev]`
- `_resolve_schema_store_path()` — resolves path via `MONITOR_CC_ROOT` env or module-relative fallback
