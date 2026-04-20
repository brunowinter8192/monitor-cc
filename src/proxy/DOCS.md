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

**Request pipeline order** (inside `ProxyAddon.request()`):
1. `_check_payload_schema()` (→ `schema_check.py`) — schema-drift detection on first opus request per session; writes `schema_warning` log entry if drift detected
2. `apply_modification_rules()` — strip/replace system2, inject project rules, strip system-reminders, normalize worktree paths in sys[3]
3. Fixation capture/apply via `_capture_fixation()` / `_apply_fixation()` (→ `fixation.py`)
4. `_strip_unused_tools()` — remove TOOL_BLOCKLIST entries from payload.tools
5. `inject_mcp_tools()` — append MCP schemas from schema store
6. `_strip_blocked_tool_references()` — remove blocklisted tool_reference blocks from tool_results
7. `_inject_context_management()` (→ `inject_helpers.py`) — inject `context_management` payload block if enabled in config
8. `_inject_model_override()` (→ `inject_helpers.py`) — override model/thinking/effort/max_tokens from `proxy_rules.json` config (opus only)
9. `_build_entry()` + `_write_entry(entry)` — **log entry captures post-injection state**, so the Proxy Pane sees all injected MCP tools (not just CC's 10 built-ins); includes `context_management_injected: bool`
10. `_strip_all_cache_control()` + `_set_cache_breakpoints()` — cache marker placement
11. `_build_sent_meta()` (→ `hash_meta.py`) + `_write_entry(sent_meta)` — per-request hash snapshot
12. `flow.request.content = modified_payload`
13. Beta header management — strips deprecated `interleaved-thinking-2025-05-14`, appends `context-management-2025-06-27`

## fixation.py

**Purpose:** Capture and apply per-model-family fixation state — freezes sys[2] content and msg[0] project-rules block after the first request.
**Input:** Modified payload dict, modifications list, fixated state dict.
**Output:** Updated fixated dict (capture) or modified payload with frozen content applied (apply).

Contains:
- `_capture_fixation()` — snapshots sys[2] text, msg[0] rules block, active_plugins on first request per model_family
- `_apply_fixation()` — applies frozen content to subsequent requests; refreshes active_plugins if changed

## hash_meta.py

**Purpose:** Compute per-request hash snapshots for cache-stability forensics and drift detection.
**Input:** Final modified payload (tools, system, messages lists).
**Output:** `sent_meta` JSONL entry dict with hashes, breakpoint indices, and drift report.

Contains:
- `_compute_sys_block_hashes()` — MD5[:10] per system block
- `_compute_tool_hashes()` — MD5[:10] per tool
- `_compute_msg_hashes()` — first 10 + rolling middle chunks + last 5 message hashes
- `_compute_msg0_block_hashes()` — per-block hashes for messages[0].content
- `_compute_drift_report()` — compares current vs previous hash snapshot, reports changed indices
- `_build_sent_meta()` — orchestrates hash computation + drift report into the `sent_meta` JSONL entry

## schema_check.py

**Purpose:** Validate API payload structure against known-good invariants (system block count, messages[0] shape, tools presence).
**Input:** Raw payload dict before proxy modifications.
**Output:** List of warning strings (empty if no drift detected).

Contains:
- `_check_payload_schema()` — checks top-level keys, system block count, messages[0] content shape, tools presence and definition key shape

## inject_helpers.py

**Purpose:** Inject model override and context management fields into payloads based on `proxy_rules.json` config.
**Input:** Payload dict, model_family string.
**Output:** `(modified_payload, injected_bool)` tuple.

Contains:
- `_inject_model_override()` — overrides model/thinking/effort/max_tokens from config; opus only
- `_inject_context_management()` — injects `context_management.edits` block with clear_thinking + clear_tool_uses directives

## payload_helpers.py

**Purpose:** Low-level payload content inspection and manipulation helpers used by rules.py.
**Input:** Message content (str or list), payload dicts.
**Output:** Modified content or filtered payload dicts.

Contains:
- `_find_system_reminder_blocks()` — extracts `<system-reminder>` blocks containing a marker from str or list content
- `_strip_blocked_tool_references()` — removes tool_reference blocks for TOOL_BLOCKLIST tools from tool_result content
- `_content_contains()` — checks if message content (str or list) contains a substring
- `_strip_task_notification_tags()` — replaces `<task-notification>...</task-notification>` XML blocks with the plain `<summary>` text only (all other XML tags incl. task-id, status, tool-use-id, output-file stripped)

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
- `_strip_task_notification_tags()` — replaces `<task-notification>` XML blocks with just the summary text
- `_inject_context_management(payload)` — reads `context_management` config from `proxy_rules.json`; if `enabled: true`, injects `context_management.edits` block with `clear_tool_uses_20250919` (trigger: 100k input tokens, keep: 5 tool_uses, clear_at_least: 10k) and `clear_thinking_20251015` (keep: 2 thinking_turns) into the payload. Returns `(modified_payload, injected_bool)`.

**Cumulative second-pass strip (after the per-message elif-chain):** iterates over `new_messages` and strips `<system-reminder>` blocks containing `"The following skills are available for use with the Skill tool"` (marker: `stripped_skills_sr`) and `"# claudeMd"` (marker: `stripped_claudemd_sr`) from any user message. Runs additionally to the existing elif-branch strips so a single msg[0] that already had e.g. `stripped_deferred_tools_sr` applied still gets Skills and claudeMd sr removed.

## content_strip.py

**Purpose:** Strip or extract specific content blocks from API message payloads.
**Input:** Message content (string or list of blocks), marker strings.
**Output:** Modified content (string or list), or extracted text.

Contains:
- `_strip_plan_mode_blocks()` — removes plan-mode system-reminder blocks
- `_strip_system_reminder()` — strips system-reminder blocks containing a marker string
- `_strip_user_interrupt_sr()` — for user-interrupt SRs (`"user sent a new message while you were working"`): preserves the whole SR block + user body, strips ONLY the `IMPORTANT:` notification line. Position-independent (works whether IMPORTANT is at top or bottom of the SR).
- `_message_has_rejection()` — detects tool rejection marker in user message
- `_strip_rejection_message()` — replaces rejection tool_result content with "."
- `_extract_session_start_block()` — extracts SessionStart rules block from MSG[0] (dead code — no longer called from rules.py since proxy reads files directly)
- `_strip_session_guidance()` — removes "Session-specific guidance" section from text
- `_strip_git_status(text)` — strips the gitStatus section from sys[3] (the CC-injected environment block); called from `apply_modification_rules()` on system[3] before forwarding

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
- `inject_mcp_tools()` — orchestrator: appends missing schemas for all active plugins. Short-circuits to no-op when `_is_project_excluded()` matches.
- `_load_schema_store()` — reads all `<plugin>/*.json` files; one-time load per process
- `_load_active_plugins()` — reads `active_plugins.json` with mtime check; default `[iterative-dev]`
- `_resolve_schema_store_path()` — resolves path via `MONITOR_CC_ROOT` env or module-relative fallback
- `_is_project_excluded()` — substring-matches `project_path` against `config["tool_injection"]["exclude_projects"]` in `~/.claude/shared-rules/proxy_rules.json` (same pattern as `system2_rules.exclude_projects` opt-out in `rules.py`). Used to fully disable MCP schema injection for specific projects.


---

# Proxy Investigation & Debugging Notes

## Cross-Pane Data Correlation (CRITICAL)

When two panes display the same data grouped differently (e.g., both show API requests grouped by turn), they MUST use the **same source** for grouping. Never derive grouping from different sources — the counts and boundaries will diverge.

**Rule:** Correlated panes → same data source for the shared dimension (turns, requests, timestamps).

Concrete failure (2026-04-09): Proxy Pane detected turns from proxy entry messages (`_get_last_user_prompt()`), Token Pane detected turns from session JSONL (`extract_cache_turns()`). Different sources → different turn boundaries → turns didn't match. 3 iterations to fix. Solution: Proxy Pane now reads session JSONL for turn detection (same source as Token Pane).

**Corollary:** When request numbering must match across panes, both must count from the same source. Session JSONL api_calls (deduplicated streaming chunks) ≠ Proxy log entries (actual HTTP requests). Positional mapping between different sources is unreliable.

## Proxy Edit Safety

mitmproxy **hot-reloads** addon scripts when the file changes on disk. This resets `ProxyAddon` state (`prev_messages_by_model`) → BP3 can't find unchanged prefix → cache invalidation.

**Live-Copy protection (implemented):** `claude_proxy_start.sh` copies `proxy_addon.py` to `.proxy_addon_live_<session_id>.py` AND copies the entire `src/proxy/` package to `src/logs/.proxy_live_<session_id>/proxy/`. The live-copy script detects `_live_` in its filename, extracts the session_id, and imports from the frozen package copy instead of `src/proxy/` on disk. Worker proxies also use live-copy (`.proxy_addon_worker_{name}.py`) since iterative-dev commit b8930f3.

**Why the full package copy is needed:** The live-copy of `proxy_addon.py` alone is NOT sufficient. The addon imports from `src/proxy/` (addon.py, rules.py, cache.py, message_summary.py, etc.). When worker merges change ANY file in `src/proxy/`, Python can pick up the changed module — causing state reset and cache invalidation. Freezing the entire package at proxy-start time prevents this.

**Rules:**
- NEVER edit files in `src/proxy/` during a live session and expect the running proxy to be unaffected — the frozen copy isolates it, but only from git merges, not from direct file edits to the live copy
- When multiple proxy changes are needed: batch them in one worker, merge once. The running proxy is isolated, but verify after next proxy restart
- Hot-reload cannot be disabled in mitmproxy (hardcoded `reload=True` in script.py)
- Cleanup on exit: trap removes both `.proxy_addon_live_<id>.py` and `.proxy_live_<id>/` directory

Concrete failure (2026-04-08): Worker merged proxy_addon.py changes → mitmproxy hot-reloaded → state reset → 145k CC cache rebuild. Three separate merges in one session = three rebuilds.
Concrete failure (2026-04-09): Worker proxy (spawned before live-copy fix) loaded proxy_addon.py directly → git merge triggered hot-reload → 41k CC rebuild. Fixed: worker proxies now use live-copy.
Concrete failure (2026-04-10): Worker merged `src/proxy/message_summary.py` changes (full_text field). Live-copy of proxy_addon.py was NOT affected, but the running proxy still imported message_summary.py from disk → cache rebuild (82k CC + 87k CC, two rebuilds). Fixed: full package copy isolates ALL proxy imports.

## Cache-Rebuild Investigation Pattern

When a cache rebuild is observed (high CC, low CR in Token Pane):
0. **ZEROTH:** Verify proxy was in path during the rebuild. (a) `ps aux | grep mitmdump` — is any proxy process running? (b) Does `src/logs/api_requests_*_<session>.jsonl` have an entry at the rebuild timestamp? If NO → proxy died / was bypassed. Infrastructure fix, not payload analysis.
1. **FIRST:** `git log --since='2h' -- src/proxy/` — check for recent merges on proxy files
2. **SECOND:** Check proxy log timestamps — correlate rebuild time with merge time
3. **THIRD:** Only if no merge correlation AND proxy was alive → investigate payload causes (byte diff per msg, TTL, API-side).
   - **READ `cache.py:_set_cache_breakpoints` FIRST** before theorizing about upstream causes (schema reload, strip/inject mutation, tool_injection logic, rule loader). The BP-setter is the last function to touch the payload before it hits the wire — most marker-related symptoms originate there. Chasing upstream hypotheses (tool_injection, rules.py) without first verifying what the BP setter actually placed on which tool wastes tool calls.
   - Only after ruling out the BP setter: inspect the upstream modification path (rules, strip, inject, cache_control placement history).
   - Concrete failure (2026-04-13): Investigated a rebuild triggered by `activate_plugin` MCP tool. Spent ~5 tool calls on upstream hypotheses (schema cache reload, file mtime drift, inject-order bug) before reading `_set_cache_breakpoints`. The root cause was visible in 10 lines of that function (BP2 marker placement on last tool every request → byte-diff on tool at the old position because `cache_control` attribute was removed).

## System Block Content Investigation

When investigating "what lands in sys[2] or msg[0]" (cross-session cacheability, byte-stability, worker vs opus differences): READ the proxy modification path FIRST before theorizing about content origin.

- **`rules.py:_load_system2_rules(model_family, project_path)`** — returns the raw text that gets written into `system[2]` via `replaced_system_prompt` modification. Opus gets `global + opus` rule files; Sonnet/Haiku workers get `global + worker` rule files; Haiku bypass returns `""`. Per-project `exclude_projects` short-circuits to `""`.
- **`rules.py:_load_project_rules(project_path)`** — returns the raw text injected into `messages[0]` as `injected_project_rules` modification. Substring-match against `message_rules.projects[].path_contains` in `~/.claude/shared-rules/proxy_rules.json`.
- **`rules.py:apply_modification_rules`** — the orchestrator. It sets `new_system[2] = {**block, "text": system_rules if system_rules else "."}`. If `system_rules == ""`, sys[2] becomes `"."` (1 char).

**Rule:** Before claiming "sys[2] differs across workers" or "msg[0] bytes change every request" — read `_load_system2_rules`, `_load_project_rules`, and `apply_modification_rules`. All worker sessions of the same model family get IDENTICAL sys[2] bytes (same rule files → same concatenated text). Any byte-difference claim must be grounded in what these functions actually return.

Concrete failure (2026-04-14): Claimed "each worker has its own sys[2]" based on assumption that `replaced_system_prompt` meant spawn-prompt content. Actually it means rules.py output, which is byte-identical cross-worker. Wasted exchanges on a wrong cache-model hypothesis. Reading `_load_system2_rules` first would have prevented the detour entirely.

See `decisions/cache_rebuild_cases.md` for the case catalog.

When investigating: present each family as hypothesis, rule in/out with evidence. Do not claim root cause from a single case — see `verify-before-execution.md` "Correlation Check Before Root-Cause Claim".

## Proxy Log Field Selection (CRITICAL)

Proxy log entries have two independent fact surfaces. NEVER confuse them.

| Surface | Where | Contains | Use for |
|---|---|---|---|
| **Pre-modification** | `entry.raw_payload.*`, `entry.tools`, `entry.tools_count`, `entry.tools_names` | What Claude Code **sent**. BEFORE proxy modifications (strip, inject, fixate, cache markers). | "What did CC hand us?" |
| **Post-modification** | `sent_meta.sent_tools_count`, `sent_meta.sent_tools_bytes_hash`, `sent_meta.sent_cache_breakpoints`, `sent_meta.prefix_hash_bp2_tools` | What the proxy **forwarded to Anthropic**. Includes injected MCP tools, final cache markers, final byte hashes. | "What actually went on the wire? Why did cache rebuild?" |

**Rule:** When investigating cache behavior, rebuilds, tool count, or marker placement — ALWAYS read `sent_meta.*` first. `raw_payload.tools` is a stale snapshot and will mislead you about what Anthropic actually received.

Concrete failure (2026-04-14): Observed `raw_payload.tools` length = 10, concluded "tool_injection Stage 2 not merged, BP-Layout v2 never triggered". Reality: `sent_meta.sent_tools_count: 51`, tool_injection IS merged, BP-Layout v2 fired correctly on the activate_plugin grow step (`tools=[30,50]` anchor+end markers, anchor hash hit confirmed). The entire hypothesis chain (TTL eviction, cumulative idle gaps, stage 2 not merged) came from reading the wrong field. Cost: 4+ exchanges of wrong conclusions before user stopped the rabbit hole.

**Query template** for rebuild forensics:
```
jq -c 'select(.type == "sent_meta") | {ts: .timestamp, tc: .sent_tools_count, tbh: .sent_tools_bytes_hash, bps: .sent_cache_breakpoints, bp2t: .prefix_hash_bp2_tools}' src/logs/api_requests_*.jsonl
```

## Worker-Send Proxy Staleness (CRITICAL)

Long-lived workers have their own frozen proxy live-copy (`.proxy_live_worker_<name>/`). Each worker's proxy package is snapshot at spawn time and NEVER updates during the worker's lifetime. When Opus merges proxy-touching changes to `dev` AFTER a worker has spawned, the worker's proxy is behind main. The WORKER HIMSELF cannot test code he cannot reach through his stale proxy — his next API call returns `API Error: Unable to connect to API (ECONNREFUSED)` OR forwards through old code that lacks the new behavior.

**Rule:** BEFORE `worker_send` to an idle worker for a proxy-touching task:
1. Check when the worker was spawned (`worker_list` shows spawn time)
2. `git log --since='<spawn-time>' -- src/proxy/ src/proxy_addon.py` — any merges on proxy files since spawn?
3. If YES → one of:
   - Kill worker + spawn new one from current `dev`
   - Opus edits directly (with user approval — the `Opus NEVER edits source code` rule has an explicit override path)
   - NEVER `worker_send` proxy code changes into a stale worker

Concrete failure (2026-04-14): `bp-layout-v2` worker spawned 23:31, idle at 58% context. Dispatched `worker_send` with addon.py log-order fix task. Worker attempted edit → `API Error: Unable to connect to API (ECONNREFUSED)` because worker's frozen proxy package was pre-merge and the merged dev branch had imports the old proxy couldn't resolve. User had to override: "du kannst selber alle edits alleine machen". 2 exchanges + 1 failed dispatch.

**The reuse-worker rule does NOT override this staleness check.** Worker reuse is only valid when the worker's proxy is AT or AFTER the merge state of the task being sent.

## Proxy Log Investigation

When searching for a specific message format in proxy logs (e.g., rejection messages, error patterns):
- **Trigger it yourself first.** Running `sleep 10` + ESC is 10x faster than grepping through 800MB JSONL with wrong patterns.
- Only grep logs when you need historical data or pattern frequency analysis.
- The monitor's Proxy Pane shows live requests — use it to see the current format.

Concrete failure (2026-04-09): 3 failed grep attempts searching for ESC-rejection message format in proxy logs. User triggered it themselves in 5 seconds.

## UI Feature Scoping (Pane Display Changes)

Before dispatching a worker for display changes that depend on stored data fields:
1. **Investigate the data pipeline FIRST** — what fields exist on each entry? How are they populated? What are the size limits (e.g., content_preview truncation)?
2. **Verify data availability** — if the display needs data from position X in a message, confirm that the stored field actually CONTAINS position X. Truncated previews, deleted raw_payloads, computed vs stored fields — all can cause "shows nothing" bugs.
3. **Write ONE comprehensive spec** covering data storage + display logic. Do NOT send piecemeal corrections.

Concrete failure (2026-04-09): Modified messages feature required 6+ correction messages to the worker. Root cause: didn't investigate that `content_preview` only stores the first ~400 chars of a message. New content appended at the END wasn't in the preview. Had to add `content_tail` field to `_extract_raw_payload_fields()` — but only discovered this after 4 failed display attempts. One upfront investigation of the data pipeline would have revealed the limitation immediately.

## API Error Payload Logging

When the API returns a 4xx error, the proxy's `response()` hook saves the full request payload to `src/logs/api_error_payload_{timestamp}.json`. This enables debugging of malformed requests (e.g., extra fields on tool_result blocks).

**Investigation workflow:**
1. Error occurs → check `src/logs/api_error_payload_*.json`
2. Read the error_response field for the API's error message
3. Navigate to the exact message index mentioned in the error
4. Compare the message structure against API spec

Concrete failure (2026-04-10): `messages.202.content.0.tool_result.text: Extra inputs are not permitted` — proxy's `_strip_system_reminder()` potentially adds `text` field to non-text blocks via `{**block, "text": new_text}`. Error-payload logging implemented to capture the exact malformed request next time it occurs.


---

## Post-Merge Proxy Load Test (MANDATORY)

After ANY merge that touches `src/proxy/`, `src/proxy_addon.py`, or any file imported by the proxy addon:

```bash
cd src/logs && mitmdump -s ../.proxy_addon_live_*.py --set flow_detail=0 -q -p 0 2>&1 &
PID=$!; sleep 3; kill $PID 2>/dev/null; wait $PID 2>/dev/null
```

If this outputs ANY import error or traceback → the merge broke the proxy. Fix BEFORE proceeding.

**Why:** mitmproxy runs in its own Python environment. Import errors that Python catches at module level (missing symbols, wrong module paths) crash mitmproxy silently. Worker proxies crash too — workers get "unable to connect to API". A 3-second load test catches this immediately.

Concrete failure (2026-04-10): `proxy/logging.py` split moved `_has_cache_control` to `message_summary.py`. `cache.py` still imported from `logging.py`. Neither worker nor Opus caught it in review. Next worker's proxy crashed on startup.
