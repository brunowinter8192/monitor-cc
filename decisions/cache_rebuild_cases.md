# Cache Rebuild Cases — Log

Observed cache-rebuild events with as much forensic detail as we can capture. Goal: accumulate enough cases to recognize patterns. Each case needs root cause hypothesis + evidence + gaps.

## Terminology

- **Rebuild** = CR drops significantly while CC jumps, indicating Anthropic cache miss on a substantial prefix portion
- **Partial rebuild** = BP1 still hits (CR ≈ 30k from cross-session rules) but BP2/BP3/BP4 miss
- **Full rebuild** = CR=0 or near-zero, nothing cached

## Status Quo (IST)

- Proxy strips all CC cache_control markers via `_strip_all_cache_control()` in `src/proxy/cache.py`
- Proxy sets its own BPs with `ttl:"1h"` (`cc_marker = {"type":"ephemeral","ttl":"1h"}`)
- BP layout (pre bp-layout-v2): BP1=sys[2], BP2=last tool without defer_loading, BP3+BP4=messages (rolling, move forward each turn)
- BP layout (post bp-layout-v2): BP1 removed; Tools Anchor=prev last non-defer tool (only when tools grew); Tools End=current last non-defer tool; BP3+BP4=messages unchanged
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

## Case 4 — monitor_cc REQ#24 + REQ#25 (2026-04-13) — Root Cause Unknown

**Symptom:** Two consecutive rebuilds after a tool-add turn, with a confirmed recovery in the same session structure of a previous session.

| REQ# | CR | CC | Classification |
|---|---|---|---|
| #23 | 102,618 | 318 | healthy |
| **#24** | **10,449** | **93,693** | **REBUILD** — CR dropped to 10k floor |
| **#25** | **10,449** | **94,116** | **SECOND REBUILD** |
| #26 | 104,565 | 179 | recovered |

**Context:**
- Session: `05a801e6-663a-4fc7-93ab-20e603edb5ba` (Monitor_CC, current session)
- Proxy log: `src/logs/api_requests_opus_monitor_cc_1776029591.jsonl`
- Gap REQ#23 → REQ#24: one turn, ~10 seconds
- **Proxy was alive in path** (sys_hash `9af1d89d0b` stable across all 44 opus requests of this session — verified in sent_meta)

**Investigation steps:**

1. **Prefix hashes (sent_meta) compared REQ#23 vs REQ#24:**
   - `sys_hash`: identical (`9af1d89d0b`) — system content unchanged
   - `tools_hash` (bp2, last non-deferred tool): identical — bp2 anchor tool unchanged
   - `tools_bytes_hash`: changed — expected, because tools set grew (new deferred tools appended)
   - `bp3_msg` / `bp4_msg` hashes: advanced by one turn — expected rolling behaviour

2. **Raw_payload byte-diff tools section REQ#23 vs REQ#24:**
   - All bytes through Write's cc_marker (`...","cache_control":{"type":"ephemeral","ttl":"1h"}}`) are byte-identical between REQ#23 and REQ#24
   - First diff at char 36,866 in the tools section: `]` → `, {"name":"mcp__plugin_iterative-dev_iterative-dev__worker_capture",...}`
   - Pattern: 5 new deferred tools appended after Write (tools count 10 → 15)

3. **Messages byte-diff REQ#23 vs REQ#24:**
   - Only 1 diff: msg[44] cc_marker removed (BP4 rolled forward to msg[46])
   - Identical to healthy baseline REQ#22→#23 (also a msg[44] cc_marker removal from BP4 rolling)
   - No shape demotion, no content change in observable message positions

4. **ToolSearch as cause: excluded.** Previous session (proxy log `1776017395.jsonl`) had 13 tool-count changes across REQ#16, #17, #34, #35, #118, #123, #141, #174–#179 — none caused a rebuild.

5. **Cross-session falsification of "Write last→middle causes rebuild" hypothesis:**
   - Previous session REQ#33→#34: tools 10 → 16, byte-identical Write cc_marker transition, `]` → `, {"name":"mcp__plugin_iterative-dev_iterative-dev__worker_capture",...}` (same deferred tool family)
   - CR transition: 36,211 → **104,859** (full cache recovery, not a rebuild)
   - Hypothesis FALSIFIED — the observable byte-level conditions were identical, outcomes were opposite

**Falsification table:**

```
                      Write bytes_after   tools       CR transition        Outcome
CURRENT REQ#23→#24    ']' → ', {"'        10 → 15     102,618 → 10,449     REBUILD
PREV    REQ#33→#34    ']' → ', {"'        10 → 16     36,211  → 104,859    RECOVERY
```

**Classification:** Double rebuild. **Root cause: Unknown.** All byte-level observable conditions (sys, tools up to BP2, bp3/bp4 msg patterns) were identical between the rebuild case and a known-good recovery case in the previous session.

**Interpretation (all hypotheses unverified):**

- **Middle-range msg_hashes blind spot** _(unverified)_: Current instrumentation hashes msg[10..n-5] as a single rolling hash. A drift in this range is detectable (rolling hash changes) but not localizable. Possibly a message in the middle range was shape-demoted or content-drifted in REQ#24 in a way not visible through existing per-message granularity. Cannot rule this out or confirm it with current tooling.

- **Server-side cache pool eviction** _(unverified, unobservable)_: Anthropic's cache pool state is opaque. The 10k floor CR (`10,449`) matches the BP1-only pattern (cross-session sys[0]+sys[1]+sys[2] layer), suggesting BP2 and BP3 both missed simultaneously despite byte-identical content — consistent with a pool eviction, also observed in Case 1. Plausible but unverifiable from our side.

- **Proxy code version drift between sessions** _(unverified)_: The live-copy of the proxy package is frozen at session start. The current and previous sessions may have had different proxy versions, meaning different BP placement logic, message normalization, or fixation behaviour for paths not covered by sys_hash. Sys_hash identical across both sessions, so fixation path was stable. Other code paths not verified as identical.

**What We Cannot Answer Yet:**

- Which concrete message in the middle range msg[10..41] changed between REQ#23 and REQ#24, if any
- Whether Anthropic's cache key is byte-wise strict or tolerates structural equivalence (e.g., list-of-one-text-block vs plain string)
- Why the previous session tolerated the identical `]`→`, {"` tool-append transition without a rebuild (and in fact recovered)
- Whether the double rebuild (REQ#24 and REQ#25) shares the same cause or whether the second rebuild is a separate eviction event

**Mitigation:**

No code fix proposed — root cause is not verified, a fix would be speculative.

## Case 5 — Tool Growth (Plugin Activation) — Lookback Window Breach

**Symptom:** Cache rebuild triggered when a new MCP plugin is activated mid-session, appending N new tool definitions to `tools[]`. CR drops despite byte-identical tools content up to the old BP2 position.

**Root cause (design):** The proxy sets a single tools breakpoint (BP2) at the current last non-defer tool. When N new tools are appended, BP2 moves to the new last tool. The old cached prefix entry — written at the previous BP2 position (say, tool index 10) — is now at least N+1 blocks behind the new BP2 (tool index 10+N). If N+1 > 20, Anthropic's 20-block lookback window cannot reach the old entry: the lookup walks at most 20 positions back from the new BP2 and stops before reaching index 10. The cache miss is guaranteed regardless of content identity.

**Anthropic docs reference (PC2, PC5):**
- PC2: "The lookback window is 20 blocks. The system checks at most 20 positions per breakpoint, counting the breakpoint itself as the first."
- PC2: "Add a second breakpoint closer to that position from the start so a write accumulates there before you need it."
- PC5: "You only need multiple breakpoints if: A growing conversation pushes your breakpoint 20 or more blocks past the last cache write, putting the prior entry outside the lookback window."

**Fix (implemented in `bp-layout-v2`, commit on branch):**

New tools BP strategy: two markers instead of one.
- **Anchor marker**: set at `prev_tools_count - 1` (the last tool from the previous request). Keeps the old cached prefix inside the lookback window even after growth.
- **End marker**: set at the current last non-defer tool (same as old BP2). Caches the newly appended tools.
- Collapses to one marker when tool count is unchanged (anchor == end).
- On shrink or first request: only end marker (no anchor needed).
- Neither marker may land on a `defer_loading: true` tool — both walk backward past defer tools.

Additionally, BP1 (system[2]) is removed. System content is cached implicitly as part of the tools→system→messages prefix leading to BP3 (the message anchor). Dropping BP1 frees one marker slot, keeping total markers within the Anthropic limit of 4.

**Classification:** Deterministic rebuild for plugin activations that add ≥20 tools. Preventable by proxy.

**State tracking:** `ProxyAddon.prev_tools_count_by_model: Dict[str, int]` stores `len(tools)` after each sent request, keyed by model_family. Passed into `_set_cache_breakpoints` as `prev_tools_count`.

Instrumentation upgrade in progress: per-message hash granularity in the middle range will be raised from a single rolling hash to 5-message rolling chunks. This will allow localizing any drift in msg[10..n-5] in future rebuilds. See worker `msg-hash-granular` (spawned from this session).

### Tool INSERT — a distinct mechanism from APPEND

The Case 4 cross-session falsification above applies to tool **APPEND** — where new tools are added at the END of `tools[]` beyond BP2. That case is benign: bytes before BP2 are unchanged, cache is intact. The falsification table confirms this: `]` → `, {"name":"mcp__plugin_iterative-dev..."` at the end caused a recovery, not a rebuild.

**Tool INSERT is different.** When Claude Code's deferred-builtin lifecycle inserts a new tool alphabetically in the MIDDLE of `tools[]` — before the last non-defer tool (BP2) — the byte prefix up to BP2 changes. BP2's logical anchor tool ("Write") is stable, but the bytes before it shifted.

**Live reproduction in `src/logs/api_requests_opus_monitor_cc_1776099723.jsonl` REQ#2 → REQ#3 (2026-04-13):**

| Field | REQ#2 | REQ#3 | Delta |
|---|---|---|---|
| tools_count | 10 | 13 | +3 |
| prefix hash (up to BP2=Write) | `5858f5aa49c6` | `d8ac54449f94` | CHANGED |
| prefix bytes before BP2 | 36,652 | 37,555 | +903 |

The three inserted tools: `CronList`, `ListMcpResourcesTool`, `mcp__plugin_iterative-dev_iterative-dev__bead_list` — all with `defer_loading=True`, inserted alphabetically BEFORE Write.

Session JSONL usage impact:
- REQ#2: CR=58,376 CC=187
- REQ#3: CR=37,228 CC=21,733 — **21k cache rebuild**

**Mechanism:** BP2 picks the last non-defer tool ("Write" in both cases). Logical BP2 position is stable, but byte identity of the prefix before BP2 breaks because alphabetical insert places new defer-tools between existing tools in the array — shifting every subsequent byte.

**Fix:** Proxy tool injection (Monitor_CC-o9b, worker `tool-inject-v2`). ToolSearch stripped entirely from every request. CC deferred built-ins (CronList, ListMcpResourcesTool etc.) go into `TOOL_BLOCKLIST`. iterative-dev schemas injected at REQ#1 from a persistent schema store (`src/logs/mcp_tool_schemas/`). New plugins via `activate_plugin` MCP tool are APPENDED after existing tools — never inserted in the middle. This eliminates the INSERT mutation at its source: the proxy controls `tools[]` from REQ#1, so Claude Code never gets the opportunity to mutate it mid-session.

**Status:** Merged on branch `tool-inject-v2`, pending Stage 3 live verification (next session).

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
