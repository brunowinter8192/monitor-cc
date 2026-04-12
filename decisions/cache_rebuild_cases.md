# Cache Rebuild Cases — Log

Observed cache-rebuild events with as much forensic detail as we can capture. Goal: accumulate enough cases to recognize patterns. Each case needs root cause hypothesis + evidence + gaps.

## Terminology

- **Rebuild** = CR drops significantly while CC jumps, indicating Anthropic cache miss on a substantial prefix portion
- **Partial rebuild** = BP1 still hits (CR ≈ 30k from cross-session rules) but BP2/BP3/BP4 miss
- **Full rebuild** = CR=0 or near-zero, nothing cached

## Status Quo (IST)

- Proxy strips all CC cache_control markers via `_strip_all_cache_control()` in `src/proxy/cache.py`
- Proxy sets its own BPs with `ttl:"1h"` (`cc_marker = {"type":"ephemeral","ttl":"1h"}`)
- BP layout: BP1=sys[2], BP2=last tool without defer_loading, BP3+BP4=messages (rolling, move forward each turn)
- Prefix-hash instrumentation in sent_meta: `prefix_hash_bp1_sys`, `prefix_hash_bp2_tools`, `prefix_hash_bp3_msg`, `prefix_hash_bp4_msg`

## Case 1 — monitor_cc REQ#33 (2026-04-12)

**Symptom:** CR=103,327 → 36,211 (drop to BP1-only level). CC=212 → 68,648.

**Context:**
- Session: `b0f70ffe-5ab3-49a6-b9ef-58f616f18a8a` (Monitor_CC)
- Proxy log: `src/logs/api_requests_opus_monitor_cc_1776017395.jsonl`
- Gap REQ#32 → REQ#33: 9.4 minutes
- Proxy was in path the whole time

**Byte-level diff REQ#32 vs REQ#33:**
- sys_hash, tools_bytes_hash, bp1_sys, bp2_tools: **byte-identical**
- All top-level payload fields except `messages`: byte-identical
- Messages: ONLY `MSG[56]` differed (msgs[0..55] byte-identical)

**MSG[56] shape change:**
- REQ#32: `{"role":"user","content":[{"type":"text","text":"...","cache_control":{"type":"ephemeral","ttl":"1h"}}]}`
- REQ#33: `{"role":"user","content":"..."}` (plain string)

Claude Code had placed BP4 on MSG[56] in REQ#32 (→ list form with cache_control). In REQ#33 CC moved BP4 forward to MSG[58] → demoted MSG[56] from list-with-block to plain string. Our proxy strips cache_control but doesn't collapse the remaining list shape → different bytes.

**But the shape change alone doesn't fully explain the rebuild:**
- 11 other list1[text+cc]→str demotions occurred in the same session (REQ#6, #29, #30, #32, #34, #42, #55, ...)
- Only REQ#33 showed catastrophic CC
- Others had CC=212–4620 (normal growth-like)
- At REQ#33, CR=36k = exactly BP1 (cross-session rules block ~30k tokens). BP2 (tools) and BP3 also missed — despite tools_bytes_hash being byte-identical

**Interpretation:** Shape demotion explains BP3/BP4 miss at MSG[56]. BP2 miss (tools byte-identical but apparently evicted) points to an Anthropic-side eviction (LRU? partial cache pool pressure?) that we cannot observe directly. The shape demotion was necessary but not sufficient for the catastrophic rebuild.

**Classification:** Partial rebuild with mixed causes. Shape-demotion contribution + server-side factor.

## Case 2 — wise2627 REQ#5 (2026-04-12)

**Symptom:** CR=50,317 → **0** (complete cache loss). CC=338 → 35,452.

**Context:**
- Session: `1090c5fd-4d81-40fb-8d98-102aa124e362` (wise2627)
- Proxy log for wise2627: last activity `18:06:19Z`
- REQ#5 session-JSONL timestamp: `18:25:18Z`
- Gap REQ#4 → REQ#5: 18.7 minutes
- **Proxy was NOT in path during REQ#5** — no proxy log entry exists for it; mitmproxy process had died silently

**Also observed:** Total input shrank ~15k tokens (REQ#4 total = 50,665, REQ#5 total = 35,467). Context_management probably dropped older tool_results server-side.

**Interpretation:**
- Without proxy, Claude Code 2.1.101 uses its default ephemeral TTL (~5min), not our 1h override
- 18.7min gap > 5min → all cache entries TTL-expired
- CC's built-in `context_management` additionally compacted old tool_results
- Nothing to do with shape demotion

**Classification:** Full rebuild. Root cause = **proxy process died**. Not a proxy bug, infrastructure bug.

**Mitigation (not yet implemented):**
- Health check for mitmdump process in `claude_proxy_start.sh`
- Auto-restart if mitmdump exits unexpectedly
- Warning in monitor when proxy log for active session is stale

## Open Patterns / Hypotheses

- **Shape demotion** (CC moving BP4 forward, demoting old BP anchor from list-with-block to plain string) is real and deterministic. Our proxy doesn't normalize → byte diff → at least BP3/BP4 miss at that msg position. Fix planned: `_normalize_user_content_shape()` in `cache.py`.
- **Server-side partial eviction**: observed in Case 1. BP2 missed despite byte-identical tools. We cannot introspect Anthropic's cache pool. Likely LRU under pool pressure.
- **Proxy death** invalidates all our protections at once (TTL override, BP placement, shape stability). Infrastructure reliability is as important as proxy correctness.

## What We Cannot Answer Yet

- Why Case 1 collapsed BP2 while other demotions in the same session didn't
- Whether Anthropic has per-account cache pools with unpredictable eviction
- Whether `context_management` field in the payload affects caching decisions server-side
- Whether TTL in our BP markers is actually honored for BP2 (tools) vs BP3/BP4 (messages)

## Reproducibility

- **Shape demotion:** fully deterministic — happens on every BP4 move (every user turn in a session)
- **Catastrophic rebuild from shape demotion:** NOT reliably reproducible — 1/11 in monitor_cc session
- **Proxy-death rebuild:** trivially reproducible — kill mitmdump mid-session

## Next Steps When Another Rebuild Is Observed

1. Capture session_id + REQ# + timestamp
2. Check if proxy log exists for that REQ# (if not → proxy died, Case 2 pattern)
3. If proxy log exists: extract sent_meta `prefix_hash_bp1..bp4` for rebuild req AND predecessor
4. Compare pairwise: which BP hash first diverges?
5. If all hashes match but CR still drops → server-side eviction (outside our control)
6. If a hash diverges → find the diff (msg shape, tool addition, system change)
7. Add the case to this file with full evidence
