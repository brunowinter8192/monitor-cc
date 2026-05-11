# Proxy-Pane Drift Detection + sys[0] cch Cache-Break Theory

Archive of bead `Monitor_CC-7df`, closed 2026-04-23 after new session evidence revised the original cache-break hypothesis.

## Original Findings (REQ#30 Forensic, session 1776552429, 2026-04-19)

Two observations grouped into one bead:

### Part A — ΔT False-Positive in the Proxy-Pane

Session 1776552429 REQ#30 displayed the `ΔT` (tools changed) flag in the Proxy-Pane despite byte-identical tools vs the preceding request.

Evidence from the proxy log (prev=`b16a1e1c` vs cur=`983822ea`):

- `tools_count`: 11 == 11
- `tools_chars`: 25260 == 25260
- `tools_names`: identical (Bash, Edit, Glob, Grep, Read, Skill, Write, 4× mcp__plugin_iterative-dev_*)
- tools byte-hash: `f2b1996f` == `f2b1996f`
- `sent_tools_hash`: `8ae704ee` == `8ae704ee`
- `sent_tools_bytes_hash`: `434821df` == `434821df`
- all 11 individual `tool_hashes` match

Conclusion: drift-detection logic in `src/proxy_display/render_sections.py` or `parser.py` fires incorrectly. The display raises `ΔT` while all upstream evidence says tools are stable.

Status: not investigated further. Remains a latent display bug. If re-prioritized, fix direction: only raise `ΔT` when `sent_tools_bytes_hash` actually differs between consecutive requests.

### Part B — Original sys[0] cch Cache-Break Theory

Same REQ#30 saw `CR:0` / `CC:0` despite apparently stable prefix content. Initial analysis flagged sys[0] as the cache-breaker:

- sys[0] changes between requests: `cch=2a274` → `cch=b7d51` (81-char CC-Metadata block with per-request random hash)
- sys[1] (57c), sys[2] (92651c = rules), sys[3] (3066c) all byte-identical
- `sent_system_hash`: changes as consequence of sys[0] change
- `sys_block_hashes[0]`: `f23331` → `274d32`

Original hypothesis: sys[0] per-request cch-hash breaks the entire prefix cache from that point forward.

## Revised Analysis (session 1776956156 + worker sidecar-strip session 1776962446, 2026-04-23)

The original Part B hypothesis is wrong. sys[0] is not cache-relevant for Anthropic.

### Evidence 1 — sys[0] is `x-anthropic-billing-header`

The actual content of sys[0] across all sessions examined is a billing/tracking header, not a prompt component:

```
x-anthropic-billing-header: cc_version=2.1.114.9e6; cc_entrypoint=cli; cch=<hex>;
```

Where `<hex>` is a 5-character per-request random suffix.

### Evidence 2 — sys[0] changes every single request

Measured on session 1776956156 (main opus, sidecar-strip test session):

- 141 opus REQs, 140 unique sys[0] values (only 1 duplicate across the whole session)
- 139 of 140 consecutive REQ-pairs have a differing sys[0]
- Yet most REQs in this same session have substantial `CR > 0` cache hits

Measured on worker session 1776962446:

- 39 REQs, all 39 with unique sys[0] values
- Same cache-hit pattern — most REQs hit cache despite every sys[0] differing

If sys[0] were cache-relevant for Anthropic, every single REQ would rebuild. They don't. Anthropic must be ignoring the `x-anthropic-billing-header` block when computing cache keys.

### Evidence 3 — REQ#30 rebuild trigger is external, not in the payload

Direct byte-level comparison of worker session REQ#29 → REQ#30 (the observed rebuild):

- tools byte-identical (`tools_hash=e78bd2e6` in both)
- sys[1], sys[2], sys[3] byte-identical (`sys_block_hashes[1..3]` match)
- After stripping cache_control markers, `messages[0..54]` are bit-for-bit identical between #29 and #30 (REQ#30 has two new messages appended at indices 55 and 56, but the prefix up to 54 is unchanged)
- sent_meta `sent_tools_bytes_hash` identical (`efaa5908`)
- Only sys[0] differs — and per Evidence 1+2, that's not cache-relevant

The proxy's cache_control breakpoints were correctly placed (`[52, 54]` for REQ#29, `[54, 56]` for REQ#30 — BP3/BP4 shift forward as new messages arrive, which is expected and correct behavior).

Despite all this, REQ#30 produced `CR:0` (full rebuild), and the very next request REQ#31 at 16:47:44 UTC saw `CR:67,551` — full cache restored.

### Revised Root Cause — External Server-Side Eviction

The evidence pattern matches server-side cache eviction, not a prefix problem:

- REQ#30 flush happened precisely at the reported usage-limit reset moment (~16:47:40 UTC)
- REQ#30 sent the full prefix (because cache was flushed) and repopulated fresh cache segments at BP3 (msg[54]) and BP4 (msg[56])
- REQ#31 at 16:47:44 hit the segments just written by #30 → cache restored
- Main session was in a 3-minute pause at that moment (REQ#117 @16:46:48 → REQ#118 @16:49:52) — it did not observe a rebuild because it had no request during the flush window

The likely trigger is rate-limit-reset invalidating active cache slots server-side. Not provable from proxy data alone — would require Anthropic internals or a controlled reproduction across the reset boundary.

## Implications for Monitor_CC

### Part A — ΔT False-Positive

Still a real display bug. Currently closed because priority is low (visual-only, does not affect actual cache behavior). Should be reopened if drift-detection in the Proxy-Pane becomes a primary UX surface.

### Part B — sys[0] cch

Not a bug. The proxy's prefix-hash computation includes sys[0] and therefore flips on every request, producing `drift_report: {sys: [0]}` in every `sent_meta` entry. This is noise, not signal. Two possible cleanups, neither urgent:

1. Exclude sys[0] from `prefix_hash_bp1_sys` computation in `src/proxy/sent_meta.py` (or wherever prefix hashing lives). Drift-detection for sys would then only fire on sys[1..3] changes, which are cache-relevant.
2. Leave as-is. The sys[0] drift is visible in `sys_block_hashes[0]` for anyone investigating, but doesn't affect actual behavior. Documentation (this file) is enough to prevent future confusion.

### Rebuild-Trigger Investigation

When a CR:0 rebuild appears in an active session with a byte-identical prefix (tools + sys[1..3] + msg[0..n] content-stable after stripping cache_control), the likely cause is server-side and not reproducible from proxy payload alone. Investigation steps in decreasing order of cheapness:

1. Check timestamp for correlation with known rate-limit-reset events (subscription-level quota boundaries).
2. Check if another concurrent session (worker, parallel CC instance) was also rebuilding at the same moment — indicates global server eviction.
3. Check sent_meta's `prefix_hash_bp1..bp4` — if all four differ despite stable content, it's a proxy-side hash computation issue. If only sys-hash differs (via sys[0]), it's the benign case.
4. If prefix genuinely drifted at a message index, use `msg_hashes` array to localize — but only after ruling out (1)–(3).

## Quellen

- Session 1776552429, REQ#30 — original observation (2026-04-19)
- Session 1776956156, 141 opus REQs — sys[0] uniqueness measurement (2026-04-23)
- Worker session 1776962446, REQ#29–31 — prefix byte-identity confirmation + external-eviction pattern (2026-04-23)
- `src/proxy/cache.py` `_set_cache_breakpoints` — BP1=sys[2], BP2=last-non-defer-tool, BP3=first_diff-1, BP4=last-msg
- `src/proxy/cache.py` `_strip_all_cache_control` — confirms proxy strips CC's markers before sending
