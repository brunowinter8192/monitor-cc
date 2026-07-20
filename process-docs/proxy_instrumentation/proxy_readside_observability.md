# Proxy Read-Side Observability

## Origin

Emerged from the `anthropic-beta` flag research documented in the proxy-header-mods process history. Conclusion there: no flag is worth stripping — the proxy's value is observation, not mutation. The constructive inverse of stripping: surface the request/response data on the wire in the monitor pane.

## Status

- **Write-side header capture: DONE + LIVE-VERIFIED** (2026-06-08). `_forwarded` carries `anthropic_beta`; `_response` dual-log captures response rate-limit headers + `request-id` in `responseheaders()` for all status codes. Verified live on disk: real `_response` entries (status 200, `anthropic-ratelimit-unified-*` family present) and `anthropic_beta` subsets in `_forwarded`. The earlier "frozen live-copy, live-verify PENDING" note is obsolete.
- **Architecture refined (2026-06-08): proxy pane = REQUEST only, token pane = RESPONSE.** Supersedes the "two-block REQUEST/RESPONSE inside the proxy pane" direction (see `## Pane redesign direction`, now marked superseded). Full reasoning in `## 2026-06-08 — Architecture refinement` below.
- **Proxy-pane (request) cluster: DONE + merged on dev** (2026-06-08, worker `proxy-req-pane`): `beta:` drill-down section (`anthropic_beta` from `_forwarded`); CR/CC removed from the proxy header (response data → token pane); write-side carry of `context_management` + `diagnostics` into `_forwarded` (read deferred — no real entries until a proxy restart + traffic). See `src/proxy/DOCS.md`, `src/proxy_display/DOCS.md`.
- **Token-pane (response) cluster: DONE + merged on dev + LIVE-VERIFIED** (2026-06-08, worker `proxy-req-pane` reused): usage extras (`extract_cache_turns` api_call + `format_cache_tracker`) and unified rate-limit headers (`_response` reader `find_response_log_path`/`read_response_log`, joined by `request_id` — verified 67/67 + 73 live) rendered above the thinking block, per request N. User-verified live. See `src/jsonl/DOCS.md`, `src/format/DOCS.md`, `src/panes/DOCS.md`, `src/proxy_display/DOCS.md`.
- **Token-pane nits — both REJECTED (2026-06-09):** (a) `overage:rejected(org_level_disabled)` is NOT suppressed — it is a server-returned response field, and the pane shows server-returned data for completeness even when it carries no per-request signal (the completeness principle, consistent with other no-signal-but-shown fields). (b) The `float(utilization)` parse in `format_cache_tracker` is NOT guarded — the header is reliably a float string, so a guard would be a fallback without a real need.
- **Directives read-side: DONE** — `parser._extract_forwarded_fields` extracts `context_management` + `diagnostics` verbatim from `_forwarded`; `render_sections.render_directives` renders collapsible `ctx: N edits` (expanded: one line per edit `type`) + non-collapsible `diag: <pmid[:14]>` in the expanded REQUEST view of `render_turn_expanded`, immediately after `render_beta`. Live-verified on real `_forwarded` entries: `▶ ctx: 1 edits` / `diag: msg_01CTk7dYN4` rendered correctly (entries with `clear_thinking_20251015` + `previous_message_id`).

## 2026-06-08 — Architecture refinement (the request/response boundary)

The earlier "two-block REQUEST/RESPONSE inside the proxy pane" plan was rejected. Two principles replace it.

**1. Pane assignment by request/response semantics.** Each pane is indexed per request N, but each shows a different direction of that exchange:
- **Proxy pane = REQUEST** — what the proxy sends TO the API for req N (request body + request headers). The response of req N feeds into req N+1; the design counts in requests, not separate blocks. We do NOT restructure into REQUEST/RESPONSE blocks — we enrich the request-centric rows with request-side fields only.
- **Token pane = RESPONSE** — what the server returns for req N. Since req N's response is not re-sent to the API in req N+1, it belongs to the token pane, not the proxy pane.

**2. Two orthogonal questions — do not conflate:**
- *What may the proxy LOG?* → **wire-Lesart**: only data the proxy captures on the wire. Request body/headers (`_original`/`_forwarded`) ✅; response HEADERS (`_response`, read in `responseheaders()` before the body streams) ✅; response BODY/usage object ❌ (2xx `stream=True` pass-through — never touches the proxy; CC writes it to Session-JSONL). `_response` capture stays as-is, it is legitimate.
- *Which pane DISPLAYS a datum?* → request/response semantics, independent of which file logged it. The rate-limit headers are wire-captured by the proxy (so the `_response` log is correct) but are RESPONSE data → displayed in the **token pane**. The token pane therefore reads TWO sources for req N's response: the Session-JSONL usage object + the proxy `_response` rate-limit headers.

**Consequences:**
- Proxy pane loses CR/CC from the header (response data; token pane owns it) — restores the boundary (CR/CC were a long-standing leak of Session-JSONL response data into the request pane).
- Proxy pane gains only request-side enrichment: `beta:` (request header) and — once read-side lands — `context_management`/`diagnostics` (request body directives, write-carried into `_forwarded` this session).
- The `usage:`-section-in-the-proxy-pane idea is DEAD — usage extras are Session-JSONL response data → token pane.
- Rate-limit `ratelimit:` rendering moves from proxy pane → token pane.

## 2026-06-08 — Response-header family CORRECTION (unified, not classic)

The rate-limit family on our OAuth/subscription traffic is NOT the classic API `anthropic-ratelimit-{requests,tokens,input-tokens,output-tokens}-{limit,remaining,reset}` the reference docs (and `## Response-Header rate-limit family` below) describe. Real captured `_response` headers (status 200, verified on disk 2026-06-08) are the **`anthropic-ratelimit-unified-*` subscription family**: `unified-status`, `unified-5h-{status,reset,utilization}`, `unified-7d-{status,reset,utilization}`, `unified-representative-claim`, `unified-fallback-percentage`, `unified-reset`, `unified-overage-{status,disabled-reason}`, plus `request-id`, `anthropic-organization-id`. (`anthropic-priority-*`/`anthropic-fast-*` absent on OAuth traffic.) The write-side filter `_filter_response_headers` already captures these via the `anthropic-ratelimit-` prefix match. Token-pane RESPONSE rendering targets the unified 5h/7d utilization + reset — NOT requests/tokens-remaining. This is exactly the "what really happens vs. what the API docs say" gap the header capture was built to close.

## 2026-06-08 — Usage extras re-measured + directives correction

- **Usage extras present 932/932** assistant msgs (6 recent sessions): `cache_creation` (`ephemeral_5m`/`ephemeral_1h`), `server_tool_use` (`web_search_requests`/`web_fetch_requests`), `service_tier` (str, e.g. `"standard"`), `speed` (str), `inference_geo` (str, often `""`), `iterations` (list of per-iteration breakdown dicts). `output_tokens_details` 0/932 → thinking-tokens deferral reconfirmed.
- **Join path corrected:** the panes get per-request usage via `extract_cache_turns` (`jsonl_cache_turns.py`) building `api_calls`, NOT via `extract_usage_data` (a different consumer). Usage extras land on the token pane by extending the `api_call` dict in `extract_cache_turns` + rendering in `format_cache_tracker` (`token_format.py`) above the thinking block.
- **Directives correction:** the claim "`context_management` + `diagnostics` sit in `_original`/`_forwarded` today — pure read-side gap" (see `### Request-Body directives` below) was WRONG. They sit only in `_original`; the `_forwarded` delta carried only `anthropic_beta` (header, added in addon.py). Surfacing them needed a write-side carry into `_build_forwarded_delta` (logging.py) — landed 2026-06-08. Read-side deferred until real entries exist.

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

> **CORRECTED 2026-06-08** — the classic `anthropic-ratelimit-{requests,tokens}-*` family below is NOT what our OAuth traffic returns. Real family is `anthropic-ratelimit-unified-*` (5h/7d windows). See `## 2026-06-08 — Response-header family CORRECTION`.

Anthropic returns on every response (reference: `monitor-cc-reference: platform_claude_com_docs_en_api_rate_limits.md`, `api_overview.md`): `request-id`, `anthropic-organization-id`, and the rate-limit family `anthropic-ratelimit-{requests,tokens,input-tokens,output-tokens}-{limit,remaining,reset}` (reset = RFC-3339), `retry-after` (on throttle), `anthropic-priority-*` (Priority Tier), `anthropic-fast-*` (fast mode). This is "how close to the throttle / when it resets" — observability the monitor has zero of, complementing the consumption view (CR/CC/Out).

**Key mechanic:** response HEADERS arrive with the status line *before* the body streams → readable in `responseheaders()` for free, no body buffering, no stream-pass break. This is why ③ is an EASY win and thinking_tokens (response BODY) is hard.

## Beta-header provenance (why we "knew" about 14 flags)

The 14-flag catalog (documented in the proxy-header-mods process history) was extracted from an **old top-level `api_requests_*.jsonl`** that had a `request_headers` field. That format was replaced by the dual-log system (bodies only), the header-reading code was removed with the beta-manipulation block, and the source files rotated away (cited file is gone). → the catalog was a frozen snapshot from a deleted log; no live capture existed until this session's `_forwarded.anthropic_beta`.

## Prioritization (post-correction)

1. **Read-side, Session-JSONL extras** (cache_creation split, server_tool_use, service_tier/speed, iterations, inference_geo) — data already parsed-adjacent, highest value-per-effort.
2. **Read-side, response headers** (`_response` now written) — surface rate-limit family in the new pane RESPONSE block.
3. **Read-side, request beta-flags** (`_forwarded.anthropic_beta` now written) + request directives — pane REQUEST block.
4. **Conditional** cache_miss_reason / applied_edits — wire up, rare-firing.
5. **Hard** thinking_tokens consumed — only via proxy SSE buffering; defer.

## Pane redesign direction

> **SUPERSEDED 2026-06-08** — the two-block cut was rejected. See `## 2026-06-08 — Architecture refinement`. Replaced by: proxy pane = REQUEST only (request-centric rows enriched, no response block), token pane = RESPONSE (usage extras + rate-limit headers).

Proxy pane = visual single-source-of-truth (logs are for Opus). Restructure per Request/Response: a REQUEST block (sys/tools/messages/fields + beta-flag subset indicator) and a RESPONSE block (usage extras + rate-limit headers). Two-block cut preferred over bolting a response section onto the request-centric layout — "request solid, response absent" is the imbalance to fix, not cement.

## Open

- Live-verify (proxy restart) of `_forwarded.anthropic_beta` subsets + `_response` rate-limit headers on OAuth traffic.
- Read-side extraction shapes + pane-redesign layout (next session).

## Scope note

`src/` changes (capture done; read-side + pane rendering pending) are worker tasks. This file is the chat-derived concept + evidence trail.

## Sources

- `monitor-cc-reference`: `platform_claude_com_docs_en_api_rate_limits.md`, `platform_claude_com_docs_en_api_overview.md`, `platform_claude_com_docs_en_api_service_tiers.md` (response headers).
- Empirical: clean `_original` dual-logs (context_management/previous_message_id presence), 8 Session-JSONLs / 633 assistant msgs (usage object shape, output_tokens_details absence).
- The proxy-header-mods process history (14-flag catalogue + provenance).
