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

## Case 3 — monitor_cc REQ#108 + REQ#109 (2026-04-12)

**Symptom:** Two consecutive back-to-back rebuilds.
- REQ#107: CR=202,412  CC=591 (normal)
- REQ#108: CR=10,449   **CC=193,621**
- REQ#109: CR=36,517   **CC=169,298**
- REQ#110: CR=205,815  CC=1,165 (recovered)

**Context:**
- Session: `b0f70ffe-5ab3-49a6-b9ef-58f616f18a8a` (Monitor_CC, same session as Case 1)
- Proxy log: `src/logs/api_requests_opus_monitor_cc_1776017395.jsonl`
- Gap REQ#107 → #108: 14 seconds. REQ#108 → #109: 15 seconds.
- Proxy alive in path (verified via `ps aux | grep mitmdump`)

**What changed:**

Proxy log shows a system[2] char-count jump and a msg[0] block[0] char-count jump across consecutive requests:

| proxy # | timestamp | sys chars | sys[2] hash | msg0[0] hash |
|---|---|---|---|---|
| #109 | 20:35:46 | 69,435 | `781ea18b45` | `cfe32ba8ec` |
| #110 | 20:35:52 | **70,272** (+837) | **`08d3a4b252`** | `cfe32ba8ec` |
| #111 | 20:36:07 | 70,272 | `08d3a4b252` | **`a1462ef527`** (+1,161) |
| #112 | 20:36:22 | 70,272 | `08d3a4b252` | `a1462ef527` |

**Root cause (verified):** Self-inflicted. During this session's IMPROVE phase the assistant edited two rule files:
- `~/.claude/shared-rules/global/verify-before-execution.md` (appended ~837 chars "Correlation Check" section) → goes into sys[2]
- `~/.claude/shared-rules/proj_monitor/monitor-proxy.md` (extended ~1,161 chars "Cache-Rebuild Investigation Pattern") → goes into msg[0] block[0] (project rules injection)

The proxy's rule-loader (`_load_global_rules`, `_load_project_rules`) caches on file mtime. Each edit changed the mtime → next request reloaded the file → injected content changed → full prefix cache invalidation.

**Two rebuilds, not one:** the two edits were ~15 seconds apart, each triggering one independent cache invalidation.

**Interpretation:** Any edit to a rule file the proxy reads at request time is a cache-killer. This is not a theoretical risk — it happened while documenting Cases 1 and 2 in the very same session.

**Classification:** Partial-to-full rebuild per event. Root cause = **proxy loads rule content from files with mtime-based reload; editing those files during an active session invalidates the prefix**.

**Mitigation (to be implemented in `Monitor_CC-dye`):**
- Fixate sys[2] and msg[0] project_rules block at session start. First request of a session reads the files normally; all subsequent requests use the cached bytes, ignoring mtime. File edits only take effect in the NEXT session.
- Rule-family: **`rule-file-edit-during-session`** — added to `proj_monitor/monitor-proxy.md` Rule-Family catalog.

### Reproduction in the same session — worker sess#7 (2026-04-12, same day)

While implementing the mitigation, a second instance of Case 3 was triggered accidentally. The `prefix-fixation` worker (spawned in this session for the Monitor_CC-dye fix) experienced a cache rebuild on its own sess#7 response:

| Worker proxy # | timestamp | msg[0][0] chars | msg[0][0] hash |
|---|---|---|---|
| #9 | 21:07:23 | 36,977 | `16fecf9afa` |
| #10 | 21:09:06 | 37,326 (+349) | `e85378b7c7` |
| #11 | 21:13:06 | 37,326 | `e85378b7c7` |

Session CR/CC: sess#6 CR=55,502 CC=3,773 (normal) → **sess#7 CR=22,742 CC=44,275** (rebuild) → sess#8 CR=67,017 CC=2,370 (recovered).

Between worker proxy #9 and #10 the assistant edited `~/.claude/shared-rules/proj_monitor/monitor-proxy.md` (+349 chars) to add the `rule-file-edit-during-session` entry to the Rule-Family catalog — i.e. while documenting Case 3 into the rules, triggering a fresh Case 3 instance in the worker's proxy.

Worker proxies use live-copy of the `src/proxy/` package (isolated from git merges) but NOT live-copy of the rule-content files — both the main proxy and the worker proxy read the shared rule files directly and honor their mtime. Any rule edit during an active session affects ALL running proxies that read those files.

**Implication:** the mitigation (session-state fixation in `ProxyAddon.fixated`) applies equally to main and worker proxies. Commit `96e5c98` implements it for both.

### Mitigation implemented (commit 96e5c98, 2026-04-12)

`ProxyAddon.fixated: dict[model_family → {sys2_text, msg0_pr_block/msg0_pr_block_str}]` captures the injected sys[2] text and msg[0] project_rules block on the first request per (proxy process, model_family). On subsequent requests `_apply_fixation()` overwrites the freshly-loaded content with the cached bytes. Rule-file edits during an active session no longer affect running proxies — the change only takes effect after the proxy restarts.

Additionally the same commit adds per-block/per-tool/per-msg hash instrumentation (`sys_block_hashes`, `tool_hashes`, `msg_hashes`, `msg0_block_hashes`) and a `drift_report` field in `sent_meta`, so future rebuilds can be diagnosed at the byte-diff level automatically instead of manually forensicing proxy logs.

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
