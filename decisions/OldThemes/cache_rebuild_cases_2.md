## Case 8 — opus_trading REQ#70 (2026-05-03) — Server-Side Eviction, Identical Proxy Hashes

**Symptom:** CR=193,272 → **0**. CC=1,312 → 194,826. Full rebuild.

**Context:**
- Session: `f2b7f714-4b34-4c8b-a843-d3f5fc3b5bc9` (Trading, Opus orchestrator)
- Proxy log: `src/logs/api_requests_opus_trading_1777819084.jsonl`
- Session JSONL: `~/.claude/projects/-Users-brunowinter2000-Documents-ai-Trading/f2b7f714-4b34-4c8b-a843-d3f5fc3b5bc9.jsonl`
- Gap REQ#69 → REQ#70: 4.0 seconds (proxy ts 15:57:43.603Z → 15:57:47.645Z UTC; response ts 15:57:47.605Z → 15:57:49.763Z UTC)
- Proxy alive in path (sent_meta entries continuous before and after; sys_hash sequence stable in shape)
- Project state: worker `freqtrade-bootstrap` was running with `--no-worktree` in the same project tree, sharing the `~/.claude/projects/-Users-...-Trading/` JSONL directory with the Opus session

**Session JSONL records (deduplicated by usage block):**

| Record | ts (UTC) | input | CR | CC | out |
|---|---|---|---|---|---|
| 137 (REQ#69) | 15:57:47.605Z | 1 | 193,272 | 1,312 | 124 |
| **138 (REQ#70)** | **15:57:49.763Z** | **1** | **0** | **194,826** | **16** |
| 139 (REQ#71) | 15:59:20.* | 5 | 194,826 | 39 | 140 |

REQ#71 immediately recovered (CR=194,826) — cache was freshly written at REQ#70 and reusable on the next request, ruling out persistent infrastructure damage.

**Sent_meta comparison REQ#69 (c6b24907) vs REQ#70 (710280be):**

| Field | REQ#69 | REQ#70 | Notes |
|---|---|---|---|
| `sent_tools_bytes_hash` | `efaa5908` | `efaa5908` | **identical** |
| `sent_tools_hash` | `08d29ceb` | `08d29ceb` | **identical** |
| `sent_tools_count` | 7 | 7 | **identical** |
| `sent_cache_breakpoints` | sys=[2], tools=[6], messages=[134,136] | sys=[2], tools=[6], messages=[136,138] | structurally consistent — msg BPs advanced one turn |
| `sys_block_hashes[1..3]` | `f6b9974248, 1e168a7464, f00545c3d4` | `f6b9974248, 1e168a7464, f00545c3d4` | **identical** |
| `sys_block_hashes[0]` | `427102c3bf` | `fb93e0b22f` | DIFFERENT (see cch analysis below) |
| `msg0_block_hashes[0..4]` | `f00545c3d4, f00545c3d4, 7f14223263, 436ca9cc9b, d49b904d60` | (same) | **identical** |
| `msg_hashes[0..4]` (first 5) | `290f70db0f, 3dcb5a6f39, 024c1a44e4, f2f5555779, 5b9dccd0c5` | (same) | **identical** |
| `tool_hashes[0..4]` (first 5) | `93b215a840, bf5395bfec, 7bd46e1c38, d3cfad5786, 2404cc6662` | (same) | **identical** |
| `prefix_hash_bp1_sys` | `97c49dcf0a` | `98642b131d` | different — propagates from sys[0] change |
| `prefix_hash_bp2_tools` | `eff2bfb6a7` | `5f6676aebd` | different — propagates from sys[0] change |
| `prefix_hash_bp3_msg` | `741cc4a6e5` | `6fccb63d65` | different — propagates from sys[0] change |
| `prefix_hash_bp4_msg` | `f114fdeeb1` | `4daa34d155` | different — propagates from sys[0] change |

**Modifications list REQ#69 vs REQ#70:** identical 23-item set in same order:
`stripped_deferred_tools_sr, stripped_task_tools_nag×8, stripped_user_interrupt_sr×2, trimmed_task_notification×3, stripped_skills_sr, stripped_po_preview, replaced_system_prompt, stripped_session_guidance, stripped_3_unused_tools, injected_mcp_tools, stripped_tool_descs_7, stripped_sys3, injected_model_override`.

`stripped_msg_indices` identical: `[0, 14, 32, 36, 46, 60, 74, 78, 84, 94, 102, 106, 124, 128, 2]` (note msg-2 stripping at end of list — same in both).

`stripped_unused_tools_names`: `['Agent', 'ScheduleWakeup', 'ToolSearch']` (identical).

`deferred_tools_names`: 28 items (identical).

**Investigation step — diff_from_prev:**
- REQ#70: `+2 messages at end (first diff at [137])` — `messages_added: 2, messages_removed: 0, messages_modified: 0`. No modifications below index 137 in the proxy's outgoing diff view.

**The sys_block_hashes[0] change — the `cch=` red herring:**

`sys_block[0]` is the Claude Code billing header (81 chars):
- REQ#69: `x-anthropic-billing-header: cc_version=2.1.114.9e6; cc_entrypoint=cli; cch=88da6;`
- REQ#70: `x-anthropic-billing-header: cc_version=2.1.114.9e6; cc_entrypoint=cli; cch=c7117;`

Only the `cch=` 5-char hash differs. Cross-session validation: across all 108 proxy requests in this Opus session, **107 of 108 had a different `cch` from the previous request** (cch transitions on virtually every request). If `cch` were the cache key, we would observe ~107 rebuilds. Actual rebuilds in this session: 4 total — 3 at session start (REQ#1–#3, normal initial cache creation) + this one at REQ#70. **`cch` is NOT the cache key from Anthropic's perspective** — either the proxy normalizes it on the way out (not visible in the modifications list) or Anthropic's cache hashing ignores this billing header. Either way, the sys_block[0] hash divergence does NOT explain the rebuild.

**Falsification of user-proposed hypothesis:** "Proxy-Ports rumgemacht" — the user suspected that local diagnostic activity around mitmdump's port 8080 (lsof, curl probes through HTTPS_PROXY) caused the rebuild. Timing disproves this: REQ#70 at 15:57:49 UTC = 17:57:49 local, port-diagnostic activity began at 17:58 (worker's bot-start failure investigation, after REQ#70 had already completed). Port-related actions happened AFTER, not before, the rebuild.

**Classification:** Full rebuild. Root cause = **server-side cache eviction by Anthropic** (most likely interpretation). Same pattern as Case 7.

**Interpretation:**

- All proxy-observable factors byte-identical or expectedly different (messages +2 append, all stable hashes intact, modifications list deterministic in name+order)
- No rule file edits in the window (verified: no Case 3 pattern)
- 4-second gap excludes TTL expiry (5-minute default)
- Session had elevated rebuild rate today: 3 cache-creation events at start (vs typical 1 for a healthy session boot), suggesting non-trivial Sonnet/Opus shard pressure on 2026-05-03 around the Trading session window

**What We Cannot Answer Yet:**

- Whether the proxy's modifications list (`replaced_system_prompt`, `stripped_sys3`, `injected_mcp_tools`, etc.) produces strictly byte-deterministic output across requests. Monitor_CC instrumentation captures modification NAMES + ORDER but not the post-modification raw_payload bytes. To verify determinism we would need to add `post_modification_payload_hash` to sent_meta and confirm it stays stable across pre-modification-stable requests. Without this, "all proxy-observable factors identical" cannot be fully closed.
- Whether `--no-worktree` worker spawning in the same project directory has any cache-relevant side effect on the parent Opus session (sharing JSONL dir, sharing process namespace). No mechanism identified that could affect Anthropic's server-side cache, but unverified.

**Mitigation:**

None for the rebuild itself — server-side eviction is outside proxy control. If post-modification determinism becomes a concern, the instrumentation upgrade above would let us close that gap.

Operational lesson reinforced (already known): worker spawn must use worktrees by default. The `--no-worktree` choice in this session caused Token-Pane mislabeling in the Monitor_CC display (worker JSONL and Opus JSONL both landed in the same `~/.claude/projects/-Users-...-Trading/` dir, monitor's "newest session" heuristic confused which is which).

**Cross-ref:** `Case 7 (monitor_cc REQ#92, 2026-04-16)` — same diagnostic pattern (identical sent_meta hashes, ~20s gap, server-side eviction conclusion). Eighth case overall, second one classified as pure server-side eviction.

---

**Mitigation:**

No code fix proposed — root cause is not verified, a fix would be speculative.

Instrumentation upgrade in progress: per-message hash granularity in the middle range will be raised from a single rolling hash to 5-message rolling chunks. This will allow localizing any drift in msg[10..n-5] in future rebuilds. See worker `msg-hash-granular` (spawned from this session).

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
