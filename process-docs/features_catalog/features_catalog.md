# Anthropic API Feature Catalog for Monitor_CC

Derived from sources/*.md scan on 2026-07-16. 60 of 69 source files read fully or substantially (ProgToolCalling4-5, Vision2, PDF_support2-3, Search_results3-4, PromptCaching2-6 partially skipped — content of those files is well understood from prior investigations and overlapping topics).

---

## 1. Context Preservation
*(features that help prefix stability, compaction, token efficiency)*

### Server-side Compaction (`compact_20260112`)
- **What it is:** Beta API feature that automatically summarizes the conversation when input tokens exceed a configurable threshold (default 150k, min 50k). Returns a `compaction` content block in the response; subsequent requests ignore all message content before that block. Generates `usage.iterations` array distinguishing compaction vs message iterations. `pause_after_compaction` flag lets you inject additional context between summary and continuation.
- **Source file(s):** `Monitor_reference/Compaction1.md`, `Monitor_reference/Compaction2.md`, `Monitor_reference/Compaction3.md`, `Monitor_reference/Compaction4.md`
- **Current status in Monitor_CC:** not used — `compaction` block type is not in `KNOWN_MESSAGE_TYPES` in `constants.py`; would appear as unknown type warning. `usage.iterations` not parsed.
- **Monitor_CC feature idea:** (a) Add `compaction` to `KNOWN_MESSAGE_TYPES` so it doesn't spam warnings pane. (b) In Token Pane, detect compaction events and display them as a special row: "COMPACTION — before: Nk tokens, after: Nk tokens, summary preview". Parse `usage.iterations` to get per-iteration token breakdown. (c) Show `stop_reason: compaction` distinctly in Token Pane. If CC starts enabling compaction (beta header already stable), Monitor_CC would otherwise silently miss these events.
- **Effort:** M
- **Value:** high — compaction is now GA for Opus 4.6/Sonnet 4.6; if CC enables it, Monitor_CC breaks silently today.

---

### Server-side Context Editing (`context-management-2025-06-27`)
- **What it is:** Beta feature with two strategies: `clear_tool_uses_20250919` (auto-clears oldest tool results when input tokens exceed a threshold) and `clear_thinking_20251015` (clears thinking blocks from history, configurable keep: N turns or "all"). Applied server-side before the prompt reaches Claude. Response includes `context_management.applied_edits` showing cleared counts and tokens. Cache interaction: tool result clearing invalidates cache; thinking block clearing preserves cache if blocks are kept.
- **Source file(s):** `Monitor_reference/ContextEditing1.md` – `Monitor_reference/ContextEditing5.md`
- **Current status in Monitor_CC:** not used. `context_management` response field not parsed. If CC enables this (e.g. for workers), Token Pane would show unexplained token drops without explanation.
- **Monitor_CC feature idea:** Parse `context_management.applied_edits` from session JSONL response. In Token Pane, annotate the affected request with "CONTEXT EDIT: cleared N tool results (Xk tokens)" or "THINKING CLEARED: N turns". Helps explain sudden token count drops.
- **Effort:** S
- **Value:** medium — future-proofing; CC doesn't enable this today but increasingly relevant as sessions grow.

---

### Automatic Prompt Caching (top-level `cache_control`)
- **What it is:** Setting `cache_control` at the top level of the request (rather than on individual blocks) enables automatic caching: the API moves the breakpoint to the last cacheable block as conversations grow, without requiring manual breakpoint management.
- **Source file(s):** `Monitor_reference/PromptCaching1.md`
- **Current status in Monitor_CC:** proxy uses explicit BP-Layout v2 (BP1-sys, BP2-tools, BP3-messages, BP4-tail). Automatic mode not used.
- **Monitor_CC feature idea:** None — proxy already handles this with explicit breakpoints which give more control. BP-Layout v2 is intentionally more granular.
- **Effort:** —
- **Value:** low — already covered by existing proxy logic.

---

### Thinking Block Stripping in Context Window
- **What it is:** The API automatically strips thinking blocks from previous turns before counting input tokens. Effective context = input_tokens − previous_thinking_tokens + current_turn_tokens. Exception: when returning tool results that accompanied a thinking block, the thinking block MUST be included. After the full tool-use cycle, thinking blocks can be dropped again.
- **Source file(s):** `Monitor_reference/ContextWindow.md`
- **Current status in Monitor_CC:** Token Pane shows raw CR/CC/D/Out values from session JSONL. Thinking block stripping effect is not annotated — the token count already reflects the stripped state, so no bug, but no explanation either.
- **Monitor_CC feature idea:** In Metadata Pane or Token Pane, when thinking tokens are present, show "(thinking stripped from context)" annotation to clarify why input_tokens appear lower than the sum of all message content.
- **Effort:** S
- **Value:** low — cosmetic clarification; not causing incorrect data today.

---

### ToolSearch Deferred Loading and Cache Preservation
- **What it is:** Tools marked `defer_loading: true` are NOT included in the system-prompt prefix. When Claude discovers them via tool search, they are appended as `tool_reference` blocks inline in the conversation — the prefix is untouched, so prompt caching is preserved. Deferred tools consume no prefix tokens until actually needed. Up to 10,000 tools in catalog; returns 3–5 results per search.
- **Source file(s):** `Monitor_reference/ToolSearch1.md`, `Monitor_reference/ToolSearch2.md`, `Monitor_reference/ToolSearch3.md`
- **Current status in Monitor_CC:** `tool_search_tool_result`, `tool_reference`, `server_tool_use` (for tool search) block types likely not in `KNOWN_MESSAGE_TYPES`. `tool_search_requests` in `usage.server_tool_use` not extracted. iterative-dev plugin uses ToolSearch — so these blocks appear in live sessions.
- **Monitor_CC feature idea:** (a) Add `tool_search_tool_result`, `tool_reference` to `KNOWN_MESSAGE_TYPES` / `KNOWN_IGNORED_TYPES` as appropriate — stop warnings pane noise. (b) In Proxy Pane, show ToolSearch events: query string, number of tools discovered, names of discovered tools. (c) In Token Pane, show `tool_search_requests` count per request from `usage.server_tool_use.tool_search_requests`. (d) In Metadata Pane, show number of deferred vs loaded tools.
- **Effort:** S (b is S, a is S, c is S, d is M)
- **Value:** high — ToolSearch is already in production use via iterative-dev plugin. Currently pollutes warnings pane.

---

### Skills List Stability and Cache
- **What it is:** Changing the `container.skills` list between requests breaks the prompt cache (Skills5.md explicitly documents this). Skills run via `code_execution` + `skills-2025-10-02` beta. Skills metadata (name, description) is injected into the system prompt prefix — changing the list invalidates the prefix. Max 8 skills per request.
- **Source file(s):** `Monitor_reference/Skills1.md` – `Monitor_reference/Skills6.md`
- **Current status in Monitor_CC:** Proxy already strips `system-reminders` that contain skill content (existing strip logic). But changes to `container.skills` field are not tracked as a cache invalidation trigger.
- **Monitor_CC feature idea:** In Proxy Pane, detect changes to `container.skills` between requests (hash the sorted skill IDs + versions). Show `⚠ SKILLS CHANGED` warning, similar to existing `⚠ TOOLS CHANGED`. Add to cache rebuild cases analysis.
- **Effort:** S
- **Value:** medium — if CC uses Skills (iterative-dev uses them), skills list changes would cause undiagnosed cache rebuilds.

---

### Compaction + Prompt Caching Interaction
- **What it is:** When compaction fires, the summary becomes new content requiring a fresh cache write. Adding `cache_control` on the system prompt (separate from messages) prevents the system prompt cache from being invalidated when a compaction occurs — system stays cached while only the compaction summary block needs to be written.
- **Source file(s):** `Monitor_reference/Compaction3.md`
- **Current status in Monitor_CC:** proxy already places BP1 on system. This interaction is already handled correctly IF the proxy runs when compaction occurs.
- **Monitor_CC feature idea:** Document in `decisions/pipe05_proxy_cache.md` — the existing BP1-sys placement is already optimal for compaction compatibility. No code change needed; knowledge capture only.
- **Effort:** —
- **Value:** low — existing proxy design already optimal.

---

## 2. Instruction Following
*(stop sequences, effort, skills, fine-grained control)*

### Effort Parameter (`output_config.effort`)
- **What it is:** Controls Claude's token spend: `max` / `high` (default) / `medium` / `low`. Affects text output, tool calls, and extended thinking depth. On Opus 4.6 and Sonnet 4.6, `effort` replaces `budget_tokens` (deprecated). Adaptive thinking by default on these models — effort controls thinking depth. Sonnet 4.6 docs explicitly recommend setting effort explicitly to avoid unexpected latency (default is `high`).
- **Source file(s):** `Monitor_reference/Effort.md`
- **Current status in Monitor_CC:** Metadata Pane shows model, max_tokens, thinking type, sampling params — but NOT `effort`. `output_config.effort` exists in `raw_payload` but not extracted.
- **Monitor_CC feature idea:** Add `effort` to Metadata Pane config section alongside existing thinking/sampling display. Extract from `raw_payload.output_config.effort`. Show as `effort: medium` or omit if not set (default `high`). Particularly useful for diagnosing why Sonnet 4.6 is slow (high effort default) vs fast.
- **Effort:** S
- **Value:** medium — directly relevant for diagnosing performance/cost of live CC sessions.

---

### Stop Reasons (complete set)
- **What it is:** All stop reasons: `end_turn`, `max_tokens`, `stop_sequence`, `tool_use`, `pause_turn`, `refusal`, `model_context_window_exceeded`, `compaction`. New additions since Monitor_CC was built: `refusal` (streaming classifier intervention; conversation must be reset), `model_context_window_exceeded` (context window hit, not max_tokens), `compaction` (compaction summary generated with `pause_after_compaction`), `pause_turn` (server-side loop hit iteration limit = 10; re-send to continue).
- **Source file(s):** `Monitor_reference/Stop-Verhalten1.md` – `Monitor_reference/Stop-Verhalten5.md`
- **Current status in Monitor_CC:** Token Pane does NOT currently display `stop_reason` per request. Session JSONL contains it but it's not surfaced in the display.
- **Monitor_CC feature idea:** Show `stop_reason` per request in Token Pane. `end_turn` = neutral (can omit or show faintly). Highlight non-standard ones: `refusal` (red), `compaction` (blue), `pause_turn` (yellow), `model_context_window_exceeded` (orange), `max_tokens` (yellow). This would help diagnose why a session stalled or why there were unexpected token patterns.
- **Effort:** S
- **Value:** medium — important diagnostic signal, currently invisible.

---

### Fine-grained Tool Streaming (`eager_input_streaming`)
- **What it is:** Per-tool opt-in flag. Streams tool input parameters character-by-character without buffering. Reduces latency from 15s to ~3s for large parameters. May produce invalid/partial JSON on `max_tokens` cutoff.
- **Source file(s):** `Monitor_reference/FineGrained1.md`
- **Current status in Monitor_CC:** Not visible. This is an internal CC behavior for its own tools.
- **Monitor_CC feature idea:** None — this is CC's internal optimization, not observable or actionable from Monitor_CC.
- **Effort:** —
- **Value:** low — CC's concern, not Monitor_CC's.

---

### Structured Outputs (`output_config.format`, `strict: true`)
- **What it is:** `output_config.format` = constrained JSON decoding against a JSON Schema. `strict: true` on tool definitions = guaranteed schema-valid tool inputs. Grammar compiled and cached 24h; invalidated if schema changes OR tools list changes. Additional system prompt injected (slightly increases input tokens). Incompatible with citations and message prefilling.
- **Source file(s):** `Monitor_reference/Structured_outputs.md` – `Monitor_reference/Structured_outputs4.md`
- **Current status in Monitor_CC:** `output_config.format` exists in some requests. Metadata Pane doesn't show it.
- **Monitor_CC feature idea:** In Metadata Pane, show `output_config.format.type` when set (e.g. `json_schema`). Flag when `strict: true` tools are in the payload. This would explain why CC sometimes shows unexpected grammar-compilation latency.
- **Effort:** S
- **Value:** low — CC rarely uses structured outputs directly. Nice-to-have.

---

### Context Awareness Token Budget Warnings
- **What it is:** Claude Sonnet 4.6, Sonnet 4.5, Haiku 4.5 receive a `<budget:token_budget>1000000</budget:token_budget>` block at conversation start and `<system_warning>Token usage: X/Y; Z remaining</system_warning>` after each tool call. Injected by the model's training, not by the prompt.
- **Source file(s):** `Monitor_reference/ContextWindow.md`
- **Current status in Monitor_CC:** These are model-injected blocks in user messages. Proxy may or may not strip them. Not specifically tracked.
- **Monitor_CC feature idea:** None — these blocks are invisible in the JSONL (they appear in API requests, not responses). Token Pane already shows actual token counts more precisely.
- **Effort:** —
- **Value:** low — redundant with what Token Pane already shows.

---

## 3. Monitor Display Features
*(things to visualize in the panes — new block types, streaming events, content structures)*

### Compaction Block Type in JSONL Parser
- **What it is:** When compaction fires, session JSONL contains a `type: "compaction"` content block in the assistant turn. `usage.iterations` array contains per-iteration breakdowns. Currently not in `KNOWN_MESSAGE_TYPES` — would show as unknown warning.
- **Source file(s):** `Monitor_reference/Compaction1.md`, `Monitor_reference/Compaction2.md`
- **Current status in Monitor_CC:** `jsonl_parser.py` does not handle compaction block type. Would trigger `warnings_pane.py` unknown type warning.
- **Monitor_CC feature idea:** Add `compaction` to `KNOWN_MESSAGE_TYPES`. In `jsonl_extractors.py`, extract compaction block content (summary text, cleared token count from `usage.iterations`). Display in Token Pane as a special "📦 COMPACTION" event row showing: tokens before, tokens after, summary preview (first 80 chars).
- **Effort:** M
- **Value:** high — CC may enable compaction; Monitor_CC would silently fail to show it today.

---

### ToolSearch Block Types in Parser / Display
- **What it is:** ToolSearch introduces multiple new block types: `server_tool_use` (for tool search calls), `tool_search_tool_result` (containing search results), `tool_reference` (deferred tool reference). `usage.server_tool_use.tool_search_requests` tracks search count. All currently unrecognized in Monitor_CC.
- **Source file(s):** `Monitor_reference/ToolSearch1.md`, `Monitor_reference/ToolSearch2.md`, `Monitor_reference/ToolSearch3.md`
- **Current status in Monitor_CC:** iterative-dev plugin uses ToolSearch in production. These blocks appear in live sessions and cause warnings pane noise. `tool_search_requests` not shown in Token Pane.
- **Monitor_CC feature idea:** (a) Add `tool_search_tool_result`, `tool_reference` to `KNOWN_MESSAGE_TYPES` or `KNOWN_IGNORED_TYPES` to silence warnings pane. (b) In `formatter.py` or `formatter_events.py`, show ToolSearch events in main pane: "🔍 TOOL SEARCH: query='weather' → found: get_weather, search_files". (c) In Token Pane, show `server_tool_use.tool_search_requests` per request. (d) In Metadata Pane tools section, distinguish deferred vs loaded tools.
- **Effort:** S (a alone = S; full b+c+d = M)
- **Value:** high — actively affects live sessions with iterative-dev plugin; current noise is ongoing.

---

### Context Editing Response in Token Pane
- **What it is:** When server-side context editing fires, the response includes `context_management.applied_edits` array with what was cleared (tool uses, thinking turns, tokens cleared per strategy).
- **Source file(s):** `Monitor_reference/ContextEditing3.md`
- **Current status in Monitor_CC:** `context_management` field not parsed from JSONL response.
- **Monitor_CC feature idea:** Parse `context_management.applied_edits` from JSONL. In Token Pane, show as annotated event row: "✂ CONTEXT EDIT: cleared N tool results (Xk tokens)" when it fires. Helps explain unexpected token drops in the middle of a session.
- **Effort:** S
- **Value:** medium — CC doesn't currently use this, but preparation for when it does.

---

### Stop Reason Display in Token Pane
- **What it is:** `stop_reason` field from session JSONL response. New values since Monitor_CC was built: `refusal`, `compaction`, `model_context_window_exceeded`.
- **Source file(s):** `Monitor_reference/Stop-Verhalten1.md` – `Monitor_reference/Stop-Verhalten5.md`
- **Current status in Monitor_CC:** `stop_reason` parsed in JSONL but not displayed in Token Pane (not surfaced per-request).
- **Monitor_CC feature idea:** Add stop_reason column or badge per request in Token Pane. Color-code: `end_turn` = dim/omit, `tool_use` = neutral, `max_tokens` = yellow, `refusal` = red, `pause_turn` = yellow, `compaction` = blue, `model_context_window_exceeded` = orange. Would be visible at a glance without expanding individual requests.
- **Effort:** S
- **Value:** medium — important diagnostic; low implementation cost.

---

### Effort Display in Metadata Pane
- **What it is:** `output_config.effort` field in API request payload. Values: `max`, `high`, `medium`, `low`.
- **Source file(s):** `Monitor_reference/Effort.md`
- **Current status in Monitor_CC:** Metadata Pane shows model, max_tokens, thinking config, sampling — no effort.
- **Monitor_CC feature idea:** Extract `raw_payload.output_config.effort` in `_extract_raw_payload_fields()` (or `metadata_format.py`). Show in Metadata Pane config section. Helps diagnose Sonnet 4.6 latency (high effort = slow by default).
- **Effort:** S
- **Value:** medium — one-line extraction, high diagnostic clarity.

---

### Search Results Block Type
- **What it is:** `search_result` content blocks (type: `search_result`) enable RAG citations. Can appear in user messages (top-level) or as tool_result content. May appear in sessions where iterative-dev plugin or CC itself uses web search or RAG.
- **Source file(s):** `Monitor_reference/Search_results1.md`, `Monitor_reference/Search_results2.md`
- **Current status in Monitor_CC:** `search_result` block type likely not in `KNOWN_MESSAGE_TYPES`. Triggers unknown type warnings.
- **Monitor_CC feature idea:** Add `search_result` to `KNOWN_MESSAGE_TYPES`. In `formatter_events.py`, show search results inline: source URL, title, content preview. Show result count in Token Pane.
- **Effort:** S (just adding to known types = S; full display = M)
- **Value:** medium — if iterative-dev uses web search, these blocks appear in sessions.

---

### Streaming Refusals Display
- **What it is:** `stop_reason: refusal` from streaming classifiers — distinct from model-generated refusals. When this occurs, the conversation history must be reset before continuing. CC itself may receive refusals.
- **Source file(s):** `Monitor_reference/Streaming_Refusals.md`
- **Current status in Monitor_CC:** `stop_reason` not prominently displayed per request. Refusal would be invisible in current Token Pane.
- **Monitor_CC feature idea:** Part of the stop_reason display feature above — flag `refusal` in red in Token Pane. Additional: show in Warnings Pane if `refusal` occurs (it indicates a safety classifier event).
- **Effort:** S
- **Value:** low (edge case for normal CC usage).

---

### Programmatic Tool Calling Block Types
- **What it is:** `caller` field on `tool_use` blocks (`{type: "direct"}` or `{type: "code_execution_20260120", tool_id: ...}`). `container` field in responses with `id` and `expires_at`. New tool version `code_execution_20260120` adds REPL state persistence and allows tools to be called from within code execution.
- **Source file(s):** `Monitor_reference/ProgToolCalling1.md`, `Monitor_reference/ProgToolCalling2.md`, `Monitor_reference/ProgToolCalling3.md`
- **Current status in Monitor_CC:** `caller` field on `tool_use` blocks probably not displayed. `container` field not extracted. CC doesn't currently use programmatic tool calling.
- **Monitor_CC feature idea:** None currently — CC doesn't use programmatic tool calling. If it ever does, add `caller` display to tool call formatter (distinguish "direct" vs "code-executed" tool calls).
- **Effort:** S (when needed)
- **Value:** low — not in use today.

---

### Citations Block Display
- **What it is:** When citations are enabled on documents, response text blocks include a `citations` array with `char_location`, `page_location`, or `content_block_location` objects. `cited_text` doesn't count toward output or input tokens. Incompatible with Structured Outputs.
- **Source file(s):** `Monitor_reference/Citations1.md`, `Monitor_reference/Citations2.md`, `Monitor_reference/Citations3.md`
- **Current status in Monitor_CC:** Citation blocks in text responses not handled. If CC sends requests with citations enabled, the response block structure would be partially mishandled.
- **Monitor_CC feature idea:** Add citation parsing to `formatter_events.py`. Show citation count and document references in main pane. Annotate "cited_text not billed" in Token Pane.
- **Effort:** M
- **Value:** low — CC doesn't use citations API directly. Only relevant if CC starts using RAG with document blocks.

---

### Server Tool Usage Counters in Token Pane
- **What it is:** `usage.server_tool_use` in API responses contains counts for server-side tool usage: `tool_search_requests`, `code_execution_requests`, `web_search_requests`. These are separate from input/output token costs but appear in the response usage field.
- **Source file(s):** `Monitor_reference/ToolSearch3.md`, `Monitor_reference/Tools6.md`, `Monitor_reference/Streaming_Messages5.md`
- **Current status in Monitor_CC:** Token Pane shows CR/CC/D/Out token counts from session JSONL. `server_tool_use` object in usage not extracted or displayed.
- **Monitor_CC feature idea:** Extract `usage.server_tool_use.*` in `jsonl_extractors.py`. Show in Token Pane as additional stats per request: "🔍 2 searches", "⚡ 1 code exec". Helps understand what server-side resources were consumed.
- **Effort:** S
- **Value:** medium — provides cost/usage transparency for server-side tools.

---

### New KNOWN_MESSAGE_TYPES Batch Update
- **What it is:** Multiple new block types introduced since Monitor_CC's `KNOWN_MESSAGE_TYPES` was last audited: `compaction`, `tool_search_tool_result`, `tool_reference`, `search_result`, `web_search_tool_result` (already present?), `bash_code_execution_tool_result`, `text_editor_code_execution_result`, `container_upload`, `citations_delta` (streaming).
- **Source file(s):** `Monitor_reference/Compaction1.md`, `Monitor_reference/ToolSearch2.md`, `Monitor_reference/Search_results1.md`, `Monitor_reference/Tools3.md`, `Monitor_reference/Streaming_Messages5.md`
- **Current status in Monitor_CC:** Unknown block types trigger warnings pane noise, obscuring real warnings.
- **Monitor_CC feature idea:** Audit `KNOWN_MESSAGE_TYPES` and `KNOWN_IGNORED_TYPES` in `constants.py` against the full list above. Add missing types. This is a housekeeping task that reduces warnings pane noise and is prerequisite for all other display features above.
- **Effort:** S
- **Value:** high — constant noise in warnings pane. Quick win, prerequisite for other features.

---

## 4. Not Relevant / Skip
*(scanned but not useful for Monitor_CC — either CC's problem or not applicable to proxy/pane architecture)*

| Feature | Source | Why skip |
|---------|--------|----------|
| Files API (upload/download/manage) | Files1-2.md | CC handles file management; Monitor_CC has no file API interaction |
| Client-side SDK compaction | ContextEditing4-5.md | CC uses server-side compaction; SDK approach not used |
| Custom Skills creation (SKILL.md, upload, versioning) | Skills3-6.md | Monitor_CC is a monitor, not a skills builder |
| Messages API basic usage (prefill, vision examples) | Msgs1-2.md | Standard API patterns; no new Monitor_CC feature |
| Image sizing and cost calculation | Vision1-2.md | CC handles image optimization; Monitor_CC already shows media blocks |
| PDF processing details (Bedrock modes, page handling) | PDF_support1-3.txt/md | CC handles PDF sending; Monitor_CC shows document blocks already |
| JSON Schema limitations for Structured Outputs | Structured_outputs4.md | CC's concern when building prompts, not Monitor_CC's |
| Fine-grained tool streaming internals | FineGrained1.md | Internal CC behavior; not visible/actionable in Monitor_CC |
| Programmatic tool calling container lifecycle | ProgToolCalling2-5.md | CC doesn't use this today |
| Token counting API rate limits | TokenCounting2.md | Not relevant to Monitor_CC monitoring |
| Client-side compaction SDK (Python/TS/Ruby) | ContextEditing4.md | Server-side preferred; CC uses server-side |
| Tool use fundamentals (agentic loop, client vs server) | Tools1-2.md | Background knowledge; already implemented in monitor.py |
| Code execution container specs (RAM, disk, packages) | Tools5-7.md | Container infrastructure; not visible in Monitor_CC |
| Batch API compatibility notes | Various | CC doesn't use batch API |
| MCP connector details | ToolSearch3.md | Monitor_CC monitors MCP but doesn't configure it |
| Strict tool use schema complexity limits | Structured_outputs4.md | CC's concern; not visible in Monitor_CC |
| Context awareness `<budget:>` injection | ContextWindow.md | Model-internal; Token Pane already shows actual counts more precisely |
| PDF citations requirement (Bedrock Converse) | PDF_support1.txt | Platform-specific; CC uses direct API |

---

## Summary: Top 3 Highest-Value / Lowest-Effort Recommendations

**1. KNOWN_MESSAGE_TYPES batch update (Effort S, Value high)**
Add `compaction`, `tool_search_tool_result`, `tool_reference`, `search_result`, `bash_code_execution_tool_result`, `text_editor_code_execution_result`, `container_upload` to `constants.py`. Zero logic required, eliminates ongoing warnings pane noise, and is prerequisite for all other display improvements. Can be done in 30 minutes.

**2. ToolSearch events display in Proxy/Main Pane (Effort S→M, Value high)**
ToolSearch is already live in iterative-dev plugin sessions. Currently: warnings pane noise on every session. Fix: (a) add block types to KNOWN_MESSAGE_TYPES, (b) show ToolSearch query + discovered tools in main pane, (c) show `tool_search_requests` count in Token Pane. Part (a) alone = S; full display = M. Fixes a current annoyance AND adds real value.

**3. Stop reason + effort display in Token Pane + Metadata Pane (Effort S, Value medium)**
`stop_reason` per request in Token Pane (with color-coding for non-standard values) and `effort` in Metadata Pane. Both extracted from existing JSONL/proxy data — no new data sources needed. Combined effort: S. Combined value: medium-high. Provides at-a-glance diagnostic clarity that is currently missing.
