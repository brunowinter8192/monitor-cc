# Tokenizer Baseline — chars/token Ratios for Claude Models

**Status:** PARKED — methodological dead-end with current data access. Resume later.

## Goal

Establish accurate chars-per-token ratios for Claude's own tokenizer to enable precise impact estimation for proxy optimization decisions (e.g. "stripping X chars saves Y Claude tokens"). Needed because `tiktoken cl100k_base` undercounts Claude's actual tokenization by ~35-75% on our content.

## What We Have

- `dev/session_analysis/06_char_token_ratio.py` — single-session analyzer with no-thinking filter
- Report: `dev/session_analysis/04_reports/20260417_002739_token_ratios_live.md` (live Opus 4.7 session, 70 requests)
- Historical batch report: `dev/session_analysis/04_reports/20260416_223326_token_ratios.md` (10 sessions, 485 requests)

## Working Anchor (from pre-Opus-4.7 sessions)

Multiple historical sessions with NO interleaved thinking show:
- Known prefix: 154,550 chars → 41,975 tokens = **3.68 chars/token**
- Full-Rebuild Ratio (CR=0): 3.42 chars/token (stddev 0.11, N=3)

This is our best working estimate. Usable for rough proxy-optimization calculations.

## Why It Got Stuck

### 1. Thinking Contamination (Opus 4.7 adaptive default)

- Opus 4.7 uses `thinking: adaptive` by default — thinking blocks present in 42/70 requests in live session (60% contamination rate)
- Per `sources/TokenCounting2.md`: "Thinking blocks from previous assistant turns are ignored and do not count toward your input tokens; Current assistant turn thinking does count"
- Per `sources/ExtendedThinking3.md:68`: "From the model's perspective, tool use loops are part of the assistant turn" — so thinking inside tool loops remains "current turn" and DOES count as input tokens
- Result: CC in tool-loop requests includes thinking-output tokens that have no corresponding chars in our payload → ratio calculations break

### 2. Filter "no-thinking-in-response" insufficient

- Script filters out requests where response has thinking blocks
- Clean requests remaining in live session: N=8
- Those 8 show extreme variance (ratio 0.028–7.787 chars/token) → filter doesn't catch all contamination
- Root cause hypothesis: tool-loop continuations propagate thinking-token accounting across requests even when the current response itself has no thinking

### 3. `/count_tokens` API blocked for Max subscription

Live-tested on 2026-04-17:
- OAuth token (from Max subscription) rejected on `/count_tokens` endpoint
- Without `oauth-2025-04-20` beta header → `401 "OAuth authentication is currently not supported"`
- With beta header → `400 "max_tokens: Extra inputs are not permitted"` (canned rejection, even with empty `{}` payload)
- OAuth works fine on `/messages` (verified — 429 rate-limited but auth accepted)

**Conclusion:** Anthropic blocks `/count_tokens` for subscription users. Only API keys work.

### 4. Per-Segment Regression Impossible

- sys[] content is CONSTANT per session (std=0 across 485 requests)
- tools[] content is CONSTANT per session
- Only messages[] varies
- Linear regression can't isolate per-segment ratios when N-1 variables have zero variance

### 5. Per-Model Tokenization Differences

Anthropic's tokenizer differs noticeably across model families (Haiku/Sonnet/Opus, and across generations 3.x/4.x/4.7). A single "chars/token" number cannot be universal — any baseline would need per-model measurements. Combined with blockers 1-4 this makes a complete ratio table impractical with current data access.

## Paths Forward (when we resume)

### Option A — Synthetic Test via `/messages` with OAuth

- Works today (OAuth accepted on /messages)
- Craft specific controlled payloads (known chars, no thinking, various content types)
- Response `usage.input_tokens` gives exact ground truth
- Python script, ~10-20 test calls, 5 minutes
- Costs: ~1-2% of 5h Opus quota per run
- Requires CC-idle window (concurrent-request conflicts otherwise)

### Option B — API Key + `/count_tokens`

- $5-10 deposit on Anthropic Console for API key
- `/count_tokens` is free, no rate limit concerns for small studies
- Can analyze our existing proxy logs retroactively by replaying payloads to /count_tokens
- Cleanest methodology
- Downside: separate auth from CC's Max plan

### Option C — Accept 3.68 as Working Ratio

- Document in `decisions/pipe05_proxy_cache.md` as baseline assumption
- Mark as "approximate, based on pre-Opus-4.7 data"
- Sufficient for decisions like "strip X → save X/3.68 tokens"
- Per-segment breakdowns remain pending

## Methodology Experiments Tried (All Insufficient)

### Linear regression over 485 requests
- sys/tools had std=0 → non-invertible design matrix
- Result: nonsense coefficients

### Delta-method (CC / Δmsg_chars per request)
- Assumed CC maps cleanly to new message chars
- Reality: CC also absorbs thinking tokens, BP movement costs, signature replays
- Result: ratio range 0.028–7.787, median 2.47 — way off from anchor 3.68

### No-thinking-response filter
- Filtered requests where assistant response has no thinking blocks
- Still doesn't catch tool-loop contamination
- Only 8/70 requests pass filter, still high variance

## Related Files

- `dev/session_analysis/06_char_token_ratio.py` — current analyzer (single-session, Opus-only, no-thinking filter)
- `dev/session_analysis/04_reports/*_token_ratios*.md` — historical reports
- `sources/TokenCounting1.md`, `TokenCounting2.md` — Anthropic docs on token counting
- `sources/ExtendedThinking*.md` — thinking blocks, signatures, billing semantics
- `sources/AdaptiveThinking1.md`, `AdaptiveThinking2.md` — adaptive thinking on Opus 4.7

## Related Bead

- `Monitor_CC-fyl` — tokenizer-baseline (parked with this decision file)
