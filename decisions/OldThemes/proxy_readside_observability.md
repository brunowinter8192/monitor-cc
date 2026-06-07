# Proxy Read-Side Observability

## Origin

Emerged from the `anthropic-beta` flag research (see `proxy_header_mods.md`). Conclusion there: no flag is worth stripping — the proxy's value is observation, not mutation. The constructive inverse of stripping: surface the request/response data on the wire in the monitor pane.

## Status

- **Write-side header capture: DONE** (this session, merged on dev). `_forwarded` now carries `anthropic_beta` (full flag list per request); a new `_response` dual-log captures the response HTTP-header rate-limit family + `request-id` in the `responseheaders()` hook for all status codes. See `decisions/logging.md`, `decisions/pipe05_proxy_cache.md`, `src/proxy/DOCS.md`, smoke `dev/hook_smoke/test_header_capture.py`.
- **Read-side + pane redesign: PENDING** (next session). Surface the captured + already-logged-but-unshown fields; restructure the proxy pane along Request/Response. Tracked in the umbrella issue.
- **Live-verify: PENDING** a proxy restart (frozen live-copy) — grep fresh `_forwarded` for 6/13/9 beta subsets, grep `_response` for real `anthropic-ratelimit-*` (confirms the headers survive on our OAuth traffic).

## Data anatomy — four quadrants (Request/Response × Header/Body)

The monitor confuses two axes. An API exchange splits into direction (Request out / Response back) × layer (HTTP header / body). Today's pane covers ~one quadrant.

| Quadrant | Content | Captured where (WRITE) | Shown (READ) |
|---|---|---|---|
| ① Request-Header | `anthropic-beta` flags (6/13/9 subsets), auth | NOW `_forwarded.anthropic_beta` (was: nowhere) | ❌ not yet |
| ② Request-Body | model, max_tokens, output_config, thinking, system, tools, messages, context_management, diagnostics | `_original` (full), `_forwarded` (delta) | mostly ✅ (sys/tools/messages/fields); context_management + diagnostics ❌ |
| ③ Response-Header | rate-limit family, request-id, retry-after, org-id | NOW `_response` (was: nowhere) | ❌ not yet |
| ④ Response-Body | usage object + content blocks | Session-JSONL (CC writes; proxy stream-passes, captures none) | content ✅, CR/CC/D/Out ✅; rest ❌ |

The screenshot-era pane header row already mixes axes: `eff:`/`think:` are ② (request budget we ask for), `CR:`/`CC:` are ④ (response, joined from Session-JSONL).

## Two log systems (do not confuse)

- **Proxy dual-logs** (`src/logs/dual_log/`, proxy-written): request side (`_original`/`_forwarded`/`_stripped`/`_injected`), `_errors` (4xx), and now `_response` (resp headers). Proxy does NOT capture the response BODY — 2xx is `stream = True` pass-through.
- **Session-JSONL** (`~/.claude/projects/**/*.jsonl`, CC-written): the response `usage` object. Sole source of CR/CC/D/Out and all other usage sub-fields.

## Candidate data — corrected by this session's evidence

### Response-Body usage fields (Session-JSONL) — the real low-hanging fruit
Full `usage` object observed (633 assistant msgs / 8 sessions, consistent): `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens` (shown) + **not shown:** `cache_creation` (`ephemeral_5m`/`ephemeral_1h` split — ties to `extended-cache-ttl`), `server_tool_use` (`web_search`/`web_fetch` counts), `service_tier`, `speed`, `iterations` (per-iteration breakdown; multi-element on compaction), `inference_geo`. These are already in the object `extract_usage_data` (jsonl_extractors.py) parses → trivial read-side extension. **Highest value-per-effort.**

### thinking_tokens — SUPERSEDED ("sure win" was wrong)
Earlier claim: `usage.output_tokens_details.thinking_tokens` sits in the same usage object → trivial. **Falsified:** `output_tokens_details` is present **0 / 633** assistant msgs across 8 recent sessions (appeared once in one old session). CC does NOT persist it to Session-JSONL. The consumed-reasoning value lives only in the raw SSE response stream, which the proxy stream-passes without buffering. → NOT trivial; the **hardest** candidate (needs proxy SSE buffering, breaks the stream-pass design). Today's `think:Nk` = requested budget (max_tokens), not consumed.

### cache_miss_reason — companion param VERIFIED (was "UNVERIFIED")
`diagnostics.cache_miss_reason` (from `cache-diagnosis` flag) needs CC to send `diagnostics.previous_message_id`. **Verified CC sends it on ~every request** (117/119, 108/110, 40/41 in clean `_original` logs). Response-side `diagnostics` key is present but `null` normally — `cache_miss_reason` populates only on actual cache-miss events (conditional/rare-firing), readable from Session-JSONL.

### applied_edits — feature ACTIVE (was "enabled:false")
`context_management.applied_edits` (from `context-management` flag). **Verified CC sends `context_management: {edits:[{type:clear_thinking_20251015, keep:all}]}` on ~every request** (same logs). Response-side `context_management` key present but `null` normally; `applied_edits` populates only when an edit fires (conditional). Readable from Session-JSONL.

### Request-Body directives (②, already logged, not shown)
`context_management` + `diagnostics.previous_message_id` sit in `_original`/`_forwarded` today — pure read-side gap.

## Response-Header rate-limit family (③, NEW candidate)

Anthropic returns on every response (reference: `monitor-cc-reference: platform_claude_com_docs_en_api_rate_limits.md`, `api_overview.md`): `request-id`, `anthropic-organization-id`, and the rate-limit family `anthropic-ratelimit-{requests,tokens,input-tokens,output-tokens}-{limit,remaining,reset}` (reset = RFC-3339), `retry-after` (on throttle), `anthropic-priority-*` (Priority Tier), `anthropic-fast-*` (fast mode). This is "how close to the throttle / when it resets" — observability the monitor has zero of, complementing the consumption view (CR/CC/Out).

**Key mechanic:** response HEADERS arrive with the status line *before* the body streams → readable in `responseheaders()` for free, no body buffering, no stream-pass break. This is why ③ is an EASY win and thinking_tokens (response BODY) is hard.

## Beta-header provenance (why we "knew" about 14 flags)

The 14-flag catalog (`proxy_header_mods.md`) was extracted from an **old top-level `api_requests_*.jsonl`** that had a `request_headers` field. That format was replaced by the dual-log system (bodies only), the header-reading code was removed with the beta-manipulation block, and the source files rotated away (cited file is gone). → the catalog was a frozen snapshot from a deleted log; no live capture existed until this session's `_forwarded.anthropic_beta`.

## Prioritization (post-correction)

1. **Read-side, Session-JSONL extras** (cache_creation split, server_tool_use, service_tier/speed, iterations, inference_geo) — data already parsed-adjacent, highest value-per-effort.
2. **Read-side, response headers** (`_response` now written) — surface rate-limit family in the new pane RESPONSE block.
3. **Read-side, request beta-flags** (`_forwarded.anthropic_beta` now written) + request directives — pane REQUEST block.
4. **Conditional** cache_miss_reason / applied_edits — wire up, rare-firing.
5. **Hard** thinking_tokens consumed — only via proxy SSE buffering; defer.

## Pane redesign direction

Proxy pane = visual single-source-of-truth (logs are for Opus). Restructure per Request/Response: a REQUEST block (sys/tools/messages/fields + beta-flag subset indicator) and a RESPONSE block (usage extras + rate-limit headers). Two-block cut preferred over bolting a response section onto the request-centric layout — "request solid, response absent" is the imbalance to fix, not cement.

## Open

- Live-verify (proxy restart) of `_forwarded.anthropic_beta` subsets + `_response` rate-limit headers on OAuth traffic.
- Read-side extraction shapes + pane-redesign layout (next session).

## Scope note

`src/` changes (capture done; read-side + pane rendering pending) are worker tasks. This file is the chat-derived concept + evidence trail.

## Sources

- `monitor-cc-reference`: `platform_claude_com_docs_en_api_rate_limits.md`, `platform_claude_com_docs_en_api_overview.md`, `platform_claude_com_docs_en_api_service_tiers.md` (response headers).
- Empirical: clean `_original` dual-logs (context_management/previous_message_id presence), 8 Session-JSONLs / 633 assistant msgs (usage object shape, output_tokens_details absence).
- `decisions/OldThemes/proxy_header_mods.md` (14-flag catalogue + provenance).
