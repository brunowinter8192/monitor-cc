# Proxy Header Manipulations — Decision Trail

## Decision

All `anthropic-beta` header manipulation removed from `addon.py` `request()` hook. CC's
`anthropic-beta` header now passes through to api.anthropic.com unmodified.

The `content-encoding` pop (`flow.request.headers.pop("content-encoding", None)`) is
**retained** — it is mechanically required by the body rewrite and is NOT a beta-flag
manipulation (see below).

## What the proxy was doing

Two header operations existed in `request()`, after line 197 (`flow.request.content = json.dumps(...)`):

1. **`content-encoding` pop (line 198):** Dropped the `content-encoding: gzip` header.
   Required: CC sends requests gzip-compressed; `_decode_body()` decompresses before parsing;
   the proxy re-serializes the modified payload as plain UTF-8 JSON. The gzip header must be
   removed or api.anthropic.com fails to decode the plain-JSON body. This is a body-rewrite
   housekeeping step, not a beta-flag operation.

2. **`anthropic-beta` block (lines 199–212, removed):**
   - **Stripped:** `interleaved-thinking-2025-05-14` from the header value on every request.
   - **"Added" `context-management-2025-06-27`:** Dead no-op — CC already includes this flag
     (confirmed from real logs below), so the branch `if beta_value not in existing_beta`
     evaluated False and the header was written back unchanged (minus `interleaved-thinking`).

## The 13 flags CC sends in every full-session request

Source: `request_headers["anthropic-beta"]` in `src/logs/api_requests_opus_wise2627_1780512121.jsonl`
(full-session set, appears from REQ#3 onward once all CC subsystems are active):

```
claude-code-20250219
oauth-2025-04-20
context-1m-2025-08-07
interleaved-thinking-2025-05-14
redact-thinking-2026-02-12
thinking-token-count-2026-05-13
context-management-2025-06-27
prompt-caching-scope-2026-01-05
advisor-tool-2026-03-01
advanced-tool-use-2025-11-20
effort-2025-11-24
extended-cache-ttl-2025-04-11
cache-diagnosis-2026-04-07
```

Early requests in the same session carry fewer flags (CC progressively activates subsystems;
6 flags at REQ#1, 9 at REQ#2, 13 from REQ#3 onward).

## Rationale for removal

We do not know what any of these flags do. Stripping `interleaved-thinking` and "adding"
`context-management` were both done without documented understanding of the effects. The
`context-management` add was already a no-op because CC sends it natively. The
`interleaved-thinking` strip was a live behavioral mutation with unknown consequences.

Rule: **no proxy-side header manipulation until each flag has been researched from the
Anthropic docs** and the effect is understood and intentional.

## Research Result (resolved)

### Catalogue correction — 14 flags, not 13

Empirical source: `src/logs/api_requests_opus_trading_1780512209.jsonl`-class proxy logs (latest full session, 392 reqs). `anthropic-beta` is NOT a fixed set — CC sends different subsets by request type. Three distinct combinations observed; union = 14 flags. Earlier "13" was a single full-main-request snapshot; `structured-outputs-2025-12-15` appears only in structured-output (subagent/tool) requests.

| Request type | Count | Flags |
|---|---|---|
| Universal core — every request | 6 | `oauth-2025-04-20`, `interleaved-thinking-2025-05-14`, `redact-thinking-2026-02-12`, `thinking-token-count-2026-05-13`, `context-management-2025-06-27`, `prompt-caching-scope-2026-01-05` |
| Full main request | 13 | core + `claude-code-20250219`, `context-1m-2025-08-07`, `advisor-tool-2026-03-01`, `advanced-tool-use-2025-11-20`, `effort-2025-11-24`, `extended-cache-ttl-2025-04-11`, `cache-diagnosis-2026-04-07` |
| Structured-output request | 9 | core + `advisor-tool-2026-03-01`, `cache-diagnosis-2026-04-07`, `structured-outputs-2025-12-15` |

### Per-flag verdict

| Flag | What it does | Our setup (Opus 4.8 + Sonnet 4.6, adaptive thinking) | Strip? |
|---|---|---|---|
| `claude-code-20250219` | CC client identity | tied to CC auth/billing/tier | NO — breaks auth/billing; CC-internal, not in public docs |
| `oauth-2025-04-20` | OAuth authentication | authentication | NO — breaks auth; not in public docs |
| `context-1m-2025-08-07` | 1M context window | Opus 4.8 / Sonnet 4.6 have 1M GA at standard pricing — header not required → no-op | NO — no-op |
| `interleaved-thinking-2025-05-14` | think between tool calls | adaptive thinking auto-enabled; header deprecated + "safely ignored" on Opus 4.8/4.7/4.6 → no-op | NO — no-op |
| `redact-thinking-2026-02-12` | flag not in public docs; likely governs `redacted_thinking` blocks (safety-redacted encrypted thinking, must round-trip unchanged) | unknown exact effect | NO — undocumented + correctness-sensitive roundtrip |
| `thinking-token-count-2026-05-13` | gates `usage.output_tokens_details.thinking_tokens` | GA "no beta header required" (release note 2026-05-27) → no-op | NO — no-op; monitor wants this field |
| `context-management-2025-06-27` | enables server-side context editing (`clear_tool_uses` / `clear_thinking`) | header required to enable; ENABLER for proxy `context_management` injection | NO — strip breaks our `context_management` feature |
| `prompt-caching-scope-2026-01-05` | flag not in public docs (base `prompt-caching-2024-07-31` is); prompt cache scoping | caching = cost savings | NO — degrades caching |
| `advisor-tool-2026-03-01` | model-as-advisor tool type | active if CC uses advisor tool | NO — breaks the tool |
| `advanced-tool-use-2025-11-20` | flag not in public docs; advanced tool use: programmatic calling, tool search | active if CC uses it | NO — breaks tools |
| `effort-2025-11-24` | effort beta gate | effort param "available on all supported models with no beta header required" → no-op; proxy effort override injects param directly | NO — no-op; proxy override does not depend on this header |
| `extended-cache-ttl-2025-04-11` | 1-hour cache TTL | longer cache = cost savings | NO — degrades caching |
| `cache-diagnosis-2026-04-07` | cache-miss diagnostics (`cache_miss_reason`) | necessary-but-not-sufficient (also needs `diagnostics.previous_message_id` body param) | NO — monitor wants this data |
| `structured-outputs-2025-12-15` | structured outputs (JSON-schema conformance) | active in structured-output requests; corpus has different version `-2025-11-13`, page culled from capture | NO — breaks structured-output requests |

### Conclusion

No flag is worth stripping. Keep ALL pass-through, no manipulation. Each flag either (a) breaks auth/billing, (b) breaks or degrades a CC feature, (c) is a no-op on our models, or (d) is correctness-sensitive.

**No-op set on our config (4):** `context-1m`, `interleaved-thinking`, `thinking-token-count`, `effort` — all GA-headerless or adaptive-auto on Opus 4.8 / Sonnet 4.6.

**Read-side opportunity:** Monitor could surface response-side data these flags produce: `usage.output_tokens_details.thinking_tokens` (always present, GA), `diagnostics.cache_miss_reason` (only if CC sends `diagnostics.previous_message_id` in request body), context_management `applied_edits` (only if feature active). UNVERIFIED: whether CC sends the companion body params for cache-diagnosis and context-management — checkable in request bodies, not yet done.

**Literal-corpus presence:** 8 of 14 flags appear by exact name in captured Anthropic docs (`context-1m`, `interleaved-thinking`, `thinking-token-count`, `context-management`, `advisor-tool`, `effort`, `extended-cache-ttl`, `cache-diagnosis`); 6 do not (`claude-code`, `oauth`, `redact-thinking`, `prompt-caching-scope`, `advanced-tool-use`, `structured-outputs` — last three have their feature documented under a different flag-date or feature page; first two are CC-internal).

### Sources

`monitor-cc-reference`: `api_beta_headers.md`, `extended_thinking.md`, `effort.md`, `context_editing.md`, `cache_diagnostics.md`, `prompt_caching.md`, `context_windows.md`, `release_notes_overview.md`, `tool_use/advisor_tool.md`, `about_claude_models_overview.md`. Empirical 14-flag catalogue: `src/logs/api_requests_opus_trading_1780512209.jsonl`-class proxy logs (392 reqs).
