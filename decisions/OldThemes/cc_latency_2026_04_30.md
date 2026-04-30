# CC Latency / TTFT — Research Snapshot 2026-04-30

Investigation into known Claude Code latency and TTFT problems as of CC 2.1.114.x, Opus 4.6/4.7, macOS, OAuth Max-plan. Session context: 31 API requests in ~25 minutes (~48 s/req average), perceived as catastrophically slow.

Our setup specifics relevant to filtering: custom mitmproxy in front of `api.anthropic.com`, 4 cache breakpoints (sys[2], end-of-tools, last-unchanged-msg, last-msg) with 1h TTL, stripped tool descriptions and system-reminders, OAuth Max-plan auth (not direct API key), workers via tmux + Sonnet sharing the same credential file.

---

## GitHub Issues

### #54999 — OAuth token serialization tax (OPEN, 2026-04-30)

URL: https://github.com/anthropics/claude-code/issues/54999  
Labels: `bug, has repro, platform:linux, area:auth`  
Reported: 2026-04-30T13:07Z — today, zero comments yet.

When two or more `claude` processes run in parallel sharing the **same OAuth Bearer token**, one runs at normal latency (~6–8 s) and N-1 others incur a consistent **5–10 s server-side serialization tax**. Confirmed via strace: no local lock contention, both processes connect to `api.anthropic.com` within milliseconds; delay is server-side, keyed on Bearer token identity. Distinct tokens remove the effect.

Applicability: **high**. Our workers are spawned via `claude.exe` and share the main session's `~/.claude/.credentials.json`. Every concurrent main + worker API call pair is subject to this tax. Related historical issues: #54443 (concurrent OAuth refresh race), #27933, #25609 (closed, OAuth refresh variants).

### #33949 — SSE streaming hangs indefinitely, no client-side timeout (OPEN, 2026-03-13)

URL: https://github.com/anthropics/claude-code/issues/33949  
Labels: `bug, has repro, platform:windows, area:core`  
Comments: 34. Last updated: 2026-04-30.

Root cause identified from source analysis of `cli.js` across 12 npm versions (2.0.72–2.1.74): the `messages.stream()` call has **no timeout and no keepalive check**. When the TCP connection silently dies (half-open), the Node.js HTTP client cannot detect it. The process waits indefinitely — no error fires, token count stays at 0, wall clock advances.

Measured hang frequency across 1,571 sessions / 148,444 tool calls:

| Period | Versions | Orphan rate |
|--------|----------|-------------|
| Dec 2025 | 2.0.72–2.1.2 | 6–14% |
| Jan 2026 | 2.1.5–2.1.23 | 5–10% |
| Feb 2026 | 2.1.29–2.1.56 | 3–8% |
| Mar 2026 | 2.1.69–2.1.74 | 2.4–4% |

No evidence the issue was fixed in 2.1.74–2.1.114 range; rate reportedly rising again by April (see #26224).

Applicability: **medium**. Hangs inflate the observed per-request average without being genuine TTFT. A 10% hang rate at 5 min average hang duration would alone account for most of the 48 s/req average. ESC does not fully recover: the queue auto-restart mechanism (queue.length > 0 → `n()`) immediately fires the next queued prompt rather than returning control.

### #46987 — "Stream idle timeout — partial response received" (OPEN, 2026-04-12)

URL: https://github.com/anthropics/claude-code/issues/46987  
Labels: `duplicate, platform:macos, api:anthropic`  
Comments: 164. Last updated: 2026-04-30T13:01Z — active today.

Same root cause as #33949. Widespread breakout starting 2026-04-12, both Opus and Sonnet affected, CC versions from 2.1.90 onward. 164 comments indicate broad user impact, not an edge case. Error string: `API Error: Stream idle timeout - partial response received`.

Applicability: **medium**. Confirms the no-timeout hang is ongoing and unresolved as of today.

### #54443 — OAuth refresh returns 400; concurrent sessions → forced re-login (OPEN, 2026-04-28)

URL: https://github.com/anthropics/claude-code/issues/54443  
Labels: `bug, has repro, platform:linux, area:auth`  
Comments: 2.

Two CC sessions sharing one `~/.claude/.credentials.json` file: when session A receives an early 401 and attempts to refresh, session B may have already written a newer credential. Session A uses its stale in-memory refresh token → server returns HTTP 400 (`invalid_grant`). Both sessions then cascade into repeated `/login` prompts. Happens hours before local `expiresAt`. Timeline in the issue shows 401s firing 5 hours before local expiry.

Our situation: `workflow.py` main session + tmux worker share the same credential file. If both sessions are active around an Anthropic-side early revocation event, this cascade applies directly.

Applicability: **medium**. Not a TTFT issue but contributes to session stalls: forced re-login mid-session can add 30–120 s of dead time.

### #54847 — Tool dispatch stalls silently in 2.1.121–2.1.123 (OPEN, 2026-04-29)

URL: https://github.com/anthropics/claude-code/issues/54847  
Labels: `bug, platform:macos, area:tools, regression`  
Comments: 7.

`tool_use` emitted in session JSONL, no matching `tool_result`, no disk side-effect, no error. 11 incidents in one day on one host with real MCP load. Appears to be a regression introduced in 2.1.121.

Applicability: **low**. We are on 2.1.114. Noted for awareness if we upgrade.

### #46829 — Cache TTL regressed 1h→5min in March 2026 (CLOSED, 2026-04-12)

URL: https://github.com/anthropics/claude-code/issues/46829  
Labels: `bug, has repro, area:cost, api:anthropic`  
Comments: 53. Closed 2026-04-29.

Server-side TTL flip from 1h to 5min around 2026-03-06–08. Analysis of 119,866 API calls across two machines confirmed via `usage.cache_creation.ephemeral_1h_input_tokens` vs `ephemeral_5m_input_tokens`. From 2026-02-01 to 2026-03-05 Anthropic defaulted to 1h; from 2026-03-08 onward 5min became dominant.

Applicability: **none for us**. Our proxy explicitly sets `cache_control` headers forcing 1h TTL on all breakpoints. We are unaffected by server-side default changes.

### #45381 — Disabling telemetry also disables 1h TTL (CLOSED, 2026-04-08)

URL: https://github.com/anthropics/claude-code/issues/45381  
Labels: `bug, has repro, platform:windows, area:core, api:anthropic`  
Comments: 13. Closed 2026-04-26.

Setting `DISABLE_TELEMETRY=1` or `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` causes sessions to fall back to 5min TTL even if the account would otherwise qualify for 1h. Behavior on CC 2.1.96 on Windows, Anthropic API.

Applicability: **low**. Our proxy forces cache_control headers, so even if CC's own TTL selection regresses, our breakpoints get 1h TTL. Worth verifying via proxy log `raw_payload.system[2]` that our `cache_control` override is actually arriving on every request.

---

## Anthropic Status Page — Last 14 Days

Source: `https://status.anthropic.com/api/v2/incidents.json`, queried 2026-04-30.

All incidents affecting Opus models, April 16–30:

| Date | Incident | Impact | Duration (UTC) |
|------|----------|--------|----------------|
| Apr 16 | Opus 4.6 elevated rate of errors | minor | 23:03–00:26 (83 min) |
| Apr 19 | Elevated errors on Opus 4.6 | none | ~22:44–00:00 |
| Apr 23 | Elevated errors on Claude Opus 4.7 | minor | 08:23–08:35 (12 min) |
| Apr 24 | Elevated errors on Claude Opus 4.7 (3 blips) | minor | 09:53, 10:01, 10:34 UTC |
| Apr 25 | Elevated error rates on Claude Opus 4.7 | minor | 01:24–01:59 (35 min) |
| Apr 25 | Elevated errors on Claude Opus 4.7 | minor | 07:48–08:37 (49 min) |
| Apr 25 | Elevated errors on Claude Opus 4.7 | minor | 08:43–11:58 (195 min) |
| Apr 25 | Investigated elevated errors and slower responses on claude.ai | none | 18:42–19:02 (20 min) |
| Apr 28 | Elevated errors on Claude Sonnet 4.5 | minor | 13:22–13:39 (17 min) |
| Apr 28 | Claude.ai unavailable and elevated errors on the API | major | 17:34–18:52 (78 min) |
| Apr 28 | Elevated errors on Claude Opus 4.7 | minor | 23:25–23:33 (8 min) |
| Apr 30 | claude.ai and API unavailable | critical | 01:20–01:51 (31 min) |
| Apr 30 | Elevated errors on Claude Haiku 4.5 | minor | 13:10 — investigating |

Notable: three separate Opus 4.7 incidents on April 25 alone, totaling ~5 hours of degraded service. The April 28 major outage affected auth paths for Claude Code. The session producing the 48 s/req average ran on April 30, the same day as the critical outage (resolved before our session ran, but infrastructure degradation can persist beyond resolution timestamps).

Status page uses "elevated errors" terminology consistently — this covers both error-rate increases and latency spikes; Anthropic does not report latency separately.

---

## Anthropic Docs

### Fast mode (beta)

Source: `https://docs.anthropic.com/en/docs/build-with-claude/fast-mode`

Explicit from docs: "Speed benefits are focused on output tokens per second (OTPS), not time to first token (TTFT)." Fast mode does NOT reduce TTFT. Additional constraints:

- Only supported on Opus 4.6 (not 4.7)
- Switching between `speed: "fast"` and standard **invalidates the prompt cache** — caches are not shared across speed settings
- Not available with Priority Tier
- Costs 6× standard per output token (implicit from pricing page reference)

### Priority Tier

Source: `https://docs.anthropic.com/en/api/rate-limits`

Priority Tier is enterprise-level, requires committed API spend, contact-sales. It is **not the Max subscription plan**. Max plan uses OAuth; Priority Tier uses API key with enterprise contract. No public documentation exists describing TTFT or queue depth differences between Priority Tier and standard API. The fast-mode docs state: "Fast mode is not available with Priority Tier" — the only public mention of Priority Tier in a latency context.

### Reducing latency

Source: `https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-latency`

Three general recommendations: (1) choose a smaller model, (2) reduce prompt and output length, (3) use streaming. No mention of TTFT impact from input context size, number of cache breakpoints, or OAuth vs API key auth. No quantitative guidance.

### CC binary scan

Binary: `~/.npm-global/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe`, 213 MB, Bun-compiled native binary (not inspectable JS). `strings` extraction shows 590+ occurrences of retry/backoff strings — all attributable to embedded MSAL (Microsoft Auth Library, version 15.13.1) handling OAuth refresh flows. No CC-specific `maxRetries` or `retryDelay` constants for API calls found. No streaming timeout constant found in strings — consistent with the #33949 root-cause analysis.

---

## Hypothesis Matrix

| Hypothesis | Evidence found | Sources |
|---|---|---|
| H1: Long input contexts (200k+ tokens) inflate TTFT independent of speed mode | Partial. Official docs: "fewer tokens → faster response" but no quantification at 200k+. Transformer prefill is O(n) in sequence length — physics dictates this is true. No GH issue with measurements. | `https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-latency` |
| H2: 1h-TTL cache reads have higher TTFT than 5min-TTL reads | Not supported. Cache reads reduce TTFT relative to cache misses; TTL affects creation cost not read latency. No evidence 1h segments take longer to restore than 5min segments. | No source |
| H3: Cache breakpoint placement (4 BPs vs fewer) affects TTFT | Unconfirmed. Plausible: more cache segments = more restore operations server-side. Confirmed adjacent risk: switching fast↔standard speed invalidates ALL caches simultaneously. No GH issue addressing BP count vs TTFT. | Fast mode docs |
| H4: OAuth/Max-plan auth has a separate queueing layer that adds latency vs direct API key | Partially confirmed. #54999 confirms server-side serialization for concurrent same-token sessions (~5–10 s tax). Single isolated session: no evidence of systematic queue difference vs API key users. Priority Tier ≠ Max plan. | #54999 |
| H5: Opus 4.6/4.7 known capacity/latency degradation as of late April 2026 | Confirmed. Status page shows 6+ separate Opus 4.7 incidents April 23–28, including 3 incidents on April 25 alone totaling ~5 hours. April 28 major outage affecting all API and auth. April 30 critical outage resolved before our session but infrastructure can remain degraded. "Elevated errors" includes latency spikes per Anthropic's incident terminology. | Anthropic status page |
| H6: CC harness adds client-side delays between user input and API send | Partially confirmed. No streaming timeout (source: #33949 source analysis) means hangs look like TTFT inflation. OAuth refresh mid-session (source: #54443) can stall a turn for 30–120 s. Our mitmproxy adds its own per-request latency (rule eval, logging, payload modification) — setup-specific overhead not a CC bug. | #33949, #54443 |

---

## Top Findings by Applicability to Our Setup

**1. Opus 4.7 server-side capacity incidents (status page)**

Six distinct incidents April 23–28. Session ran April 30 with a critical outage that morning. When Anthropic's Opus 4.7 serving infrastructure is degraded, TTFT and error rates rise for all users. This is the highest-probability explanation for systematic 48 s/req in a session that otherwise looks healthy in terms of cache hits and prefix stability. No actionable mitigation exists on the client side — the incidents resolve on Anthropic's end.

**2. OAuth token serialization tax (#54999)**

Every concurrent main session + worker request pair that shares the same OAuth Bearer token incurs a confirmed 5–10 s server-side serialization delay on one of the two requests. In a 25-minute session with 31 requests and workers active for a significant fraction of those, this could add meaningful latency. Mitigation: serialize worker spawns such that no worker is making API calls concurrently with the main session's active stream.

**3. SSE streaming no-timeout hang (#33949, #46987)**

At a 3–15% hang rate per request, a subset of the 31 requests in the session may have hung for seconds to minutes before recovering (either by Anthropic-side retry, user ESC, or silent TCP reconnect). These hangs inflate the average without being measurable as TTFT. Mitigation: no client-side fix available without CC changes; ESC and re-submit is the only recovery path.

---

## What We Considered and Discarded

**Fast mode** — Eliminated for three reasons. (1) Fast mode targets OTPS not TTFT; the user's pain point is the wait before the first token, not token generation speed. (2) Switching between fast and standard speed invalidates the prompt cache; our 4-BP caching strategy depends on cache hit stability — a cache miss on every-other-request would negate the cache savings. (3) Fast mode is reportedly 6× the standard per-output-token price; at session scales, this is prohibitive. Fast mode is also not available on Opus 4.7, only 4.6.

**Separate OAuth tokens per worker** — Mitigation for #54999 requires each worker to authenticate with a different Max-plan OAuth token, i.e., a separate Anthropic account. That is not a configuration lever available per-session or per-worker from within the existing setup. Serializing worker API calls (ensuring no worker has an active stream while the main session is active) is the practical mitigation, at the cost of reduced parallelism.

---

## Open Questions / Dead Ends

- **Priority Tier TTFT impact**: "Service Tiers" docs page (linked from rate-limits page) returns 404. No public data exists on whether Priority Tier has lower TTFT. Would require enterprise contact.
- **Proxy-added latency baseline**: our mitmproxy processes every request (cert pinning bypass, rule eval, logging). No measurement of the proxy's own per-request overhead exists. A 1–5 ms vs 100–500 ms per-request proxy cost would meaningfully affect the 48 s/req picture. Can be measured by comparing proxy log timestamps to session JSONL timestamps.
- **H3 (4 BPs vs fewer)**: no measurement or GH issue. Would require a controlled experiment: same session, same context, 1 BP vs 4 BPs, compare TTFT distributions. Not investigated.
- **Reddit/forum**: no relevant posts found in last 14 days specifically about CC TTFT or 48 s/req at scale. r/ClaudeAI search returned only noise.

---

## Sources

- GitHub issue search: `anthropics/claude-code`, queries run 2026-04-30 via `github-search` skill
- Anthropic status page: `https://status.anthropic.com/api/v2/incidents.json`, fetched 2026-04-30
- Anthropic fast mode docs: `https://docs.anthropic.com/en/docs/build-with-claude/fast-mode`
- Anthropic rate limits docs: `https://docs.anthropic.com/en/api/rate-limits`
- Anthropic reduce-latency docs: `https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-latency`
- CC binary: `~/.npm-global/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe` (strings scan only)
