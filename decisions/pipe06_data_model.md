# Monitor Data Pipeline

## Two Data Sources

The monitor has two independent data sources — never confuse them:

| Source | File | Contains | Used by |
|--------|------|----------|---------|
| Session JSONL | `~/.claude/projects/<project>/<session>.jsonl` | API **responses** — usage tokens (CR, CC, D, Out), message content, tool calls | Token Pane, Main Pane |
| Proxy JSONL | `src/logs/api_requests_<session_id>.jsonl` | API **requests** — full payload (system, tools, messages), cache breakpoints, modifications | Proxy Pane |

**Session JSONL** tells you what the API **returned** (token counts, cache behavior).
**Proxy JSONL** tells you what Claude Code **sent** (message structure, tool definitions, system prompt).

To understand cache behavior: you need BOTH. Proxy shows WHY (what changed in the request), Session JSONL shows WHAT HAPPENED (how many tokens were cached/created).

## Streaming Chunks (Session JSONL)

The Session JSONL contains **multiple `assistant` events per API call** — these are streaming chunks. Each chunk repeats the same input usage but has incrementally growing output tokens.

**Deduplication rule:** Group by input signature `(cache_read, cache_creation, input_tokens)`. The final chunk (highest `output_tokens`) is the complete response.

```
# Same API call, 3 streaming chunks:
CR:0  CC:36389  D:9  Out:26    ← partial
CR:0  CC:36389  D:9  Out:26    ← partial  
CR:0  CC:36389  D:9  Out:159   ← final (highest Out)
```

**The Token Pane already deduplicates** — it shows per-request values from `accumulate_tokens()`. But when analyzing raw JSONL manually (dev scripts, debugging), always deduplicate first.

## Proxy Fields: Logged vs Computed

Some fields exist in the Proxy JSONL directly, others are computed by `monitor.py` at display time:

| Field | Source | Notes |
|-------|--------|-------|
| `tools_count`, `tools_chars`, `tools_names`, `tools` | proxy_addon.py `_build_entry()` | From raw payload |
| `cache_breakpoints` | proxy_addon.py | Message indices with `cache_control` set |
| `has_cache_control` (per message) | proxy_addon.py `_has_cache_control()` | Whether message has `cache_control` attribute |
| `tools_hash` | monitor.py `_extract_raw_payload_fields()` | MD5 of sorted tool names, computed from `raw_payload` |
| `system_total_chars` | monitor.py | Computed from `raw_payload.system` blocks |
| `schema_warnings` | monitor.py | Computed by checking against `KNOWN_*` sets in constants.py |

## Cache-Control vs Cache Behavior

**`CC ●` in Proxy Pane** = the message has `cache_control` set in the API request. This is a **cache breakpoint marker** — it tells the API "cache everything up to here".

**This does NOT mean the content was actually cache-read or cache-created.** Cache behavior depends on:
1. Whether the prefix matches a previous cached prefix
2. Whether system/tools/earlier messages changed (invalidates cache from that point)

**Actual cache behavior** is only visible in the Session JSONL usage fields:
- `cache_read_input_tokens` (CR) — tokens served from cache
- `cache_creation_input_tokens` (CC) — tokens written to cache (new or rewritten)
- `input_tokens` (D) — tokens not cached at all

## Cache Invalidation Patterns

When the Token Pane shows high CC (cache_creation) despite similar total_in:

| Pattern | Cause | How to identify |
|---------|-------|-----------------|
| High CC after TOOLS CHANGED | Tool definitions changed → prefix mismatch from tools section onward | Proxy shows `⚠ TOOLS CHANGED`, CC roughly = tools + messages size |
| High CC after SYSTEM CHANGED | System prompt block changed → prefix mismatch from system onward | Proxy shows `⚠ SYSTEM CHANGED` |
| High CC on first request | No cache exists yet | CR = 0, expected behavior |
| Small CC (~200-500) after TOOLS CHANGED | Only new tools appended, prefix mostly intact | Normal incremental growth |

**Key insight from 2026-04-08 investigation:** The FIRST tool load via ToolSearch (e.g., loading `bead_list` schema) can cause a massive cache rewrite (~27k CC) because it changes the tool definitions in the prefix. Subsequent tool loads cause only small CC (~200-500) because the prefix is already established and tools are appended.

## Known Cache Invalidation Triggers

Beyond content changes, these events cause cache invalidation:

| Trigger | Impact | Why |
|---------|--------|-----|
| ToolSearch loading new tool schema | ~27k CC on first load, ~200-500 CC on subsequent | Tool definitions are part of the API prefix. First load changes the tool set significantly. |
| MCP server reconnect (`/mcp`) | Full cache rewrite (= current session size) | Reconnect reloads tool schemas → system-reminder with deferred tools list changes → prefix mismatch |
| First request of session | Full CC (expected) | No cached prefix exists yet |

**MCP reconnect is extremely expensive.** Avoid `/mcp` unless the server actually crashed. Each reconnect rewrites the ENTIRE cached prefix — cost scales linearly with session length. At 500k tokens into a session, that's 500k CC. At 1M tokens, it's 1M CC.

## Verify API Behavior (CRITICAL)

When investigating cache behavior, TTL, or any API-side mechanism:
1. **Check the raw_payload in the Proxy JSONL FIRST** — it shows exactly what was sent
2. **NEVER derive API behavior from training data** — the API evolves, training data is stale
3. **Look for explicit fields** — `cache_control.ttl`, `cache_control.scope`, `thinking.type` etc. are in the payload

Concrete failure (2026-04-08): Opus claimed "Cache TTL is ~5 minutes" from training data. Raw payload showed `ttl: "1h"` explicitly. The actual bug was the proxy stripping TTL from markers.

## Dev Scripts for Analysis

Manual `python3 -c` analysis in Bash is an anti-pattern. Reusable analysis belongs in `dev/session_analysis/`:

- `01_extract.py` — Session JSONL extraction
- `02_cache_timeline.py` — Cache behavior over time
- `03_cache_rebuild_context.py` — Cache rebuild root cause analysis
- `04_cache_validation.py` — Cache validation checks
- `05_req_breakdown.py` — Forensic per-segment token attribution (tiktoken cl100k_base); writes MD reports to `04_reports/`. Supports cross-session byte-diff for prefix attribution (`--prev-proxy-log`).

When adding new analysis: follow existing script patterns in `dev/session_analysis/`.
