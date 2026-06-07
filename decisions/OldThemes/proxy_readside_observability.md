# Proxy Read-Side Observability

## Origin

Emerged from the `anthropic-beta` flag research (see `proxy_header_mods.md`). Conclusion there: no flag is worth stripping — the proxy's value is observation, not mutation. The constructive inverse of stripping: surface the response-side / header data these flags produce in the monitor pane.

## Concept

The proxy already reads response usage — the pane's `CR` / `CC` values are `cache_read_input_tokens` / `cache_creation_input_tokens` from the response `usage` object. Read-side observability = extend that existing capture to surface MORE of what is already on the wire, instead of mutating requests.

## Candidate data

### 1. thinking_tokens — sure win

`usage.output_tokens_details.thinking_tokens` — billed output tokens spent on internal reasoning.

```json
"usage": { "output_tokens": 348, "output_tokens_details": { "thinking_tokens": 312 } }
```

Always present (GA, no header — historically gated by `thinking-token-count-2026-05-13`, now headerless). Sits in the SAME `usage` object the pane already reads for CR/CC → trivial extension. Pane today shows `think:Nk` = the BUDGET we set (`max_tokens`/effort), not the CONSUMED reasoning; `thinking_tokens` is the consumed value.

### 2. cache_miss_reason — conditional

From `cache-diagnosis-2026-04-07`. On a cache miss, `diagnostics.cache_miss_reason` reports WHERE the prompt prefix diverged (model / system / tools / messages). Turns the pane's "CC dropped to 0" into "WHY it dropped". CONDITION: appears only if CC also sends the body param `diagnostics.previous_message_id` — the header is necessary-but-not-sufficient. UNVERIFIED whether CC sends it.

### 3. applied_edits — conditional

From `context-management-2025-06-27`. Response `context_management.applied_edits` reports what server-side context-editing cleared (tool_uses, tokens). CONDITION: only when the feature is active — the proxy's own `context_management` is currently `enabled: false`.

## Header visibility gap

The `anthropic-beta` flags CC sends live ONLY in the `request_headers` field of the top-level `api_requests_*.jsonl`. They are NOT surfaced in the pane and NOT in `dual_log/` (body-deltas only). Right now there is no live readable view of which flags go out. A pane element showing the per-request flag set would make subset-shifts visible — e.g. a request carrying only the 6-flag universal core vs the full 13 (subsets documented in `proxy_header_mods.md`).

## Open

- Verify in the request bodies whether CC sends the companion params `diagnostics.previous_message_id` (cache-diagnosis) and `context_management` (decides whether #2 / #3 are achievable at all).
- Locate the current response-usage capture path: the top-level `api_requests_*.jsonl` rotates and was absent when this was written; `dual_log/` carries request-body deltas only. Confirm where the pane reads CR/CC from so `thinking_tokens` can hook the same path.

## Scope note

`src/` changes (pane rendering + response-usage extension) are a worker task. This file is the chat-derived concept trail.
