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

## Pending — research each flag before touching headers again

Before any future header manipulation is introduced, look up each flag in the Anthropic
beta-features documentation and document what it does:

- `claude-code-20250219`
- `oauth-2025-04-20`
- `context-1m-2025-08-07`
- `interleaved-thinking-2025-05-14`
- `redact-thinking-2026-02-12`
- `thinking-token-count-2026-05-13`
- `context-management-2025-06-27`
- `prompt-caching-scope-2026-01-05`
- `advisor-tool-2026-03-01`
- `advanced-tool-use-2025-11-20`
- `effort-2025-11-24`
- `extended-cache-ttl-2025-04-11`
- `cache-diagnosis-2026-04-07`

Only after each flag is documented may it be considered for proxy-side manipulation.
