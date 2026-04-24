# Background-Task Abort-and-Refire Cascade

Mechanism and billing impact of Claude Code's client-side stream cancellation triggered by incoming events (user input, background-task completions, task-notifications). Forensic evidence from session 1776977437 (2026-04-23).

Cascades are silent by default — session JSONL records only the final completed response. The proxy pane is the only surface that exposes aborted REQs. Costs accrue per-abort at the full context-read rate.

## Terminology

- **Cascade** — a sequence of N REQs fired in rapid succession where REQs 1..N-1 are aborted client-side before producing an assistant response; only the final REQ completes and writes a session-JSONL entry.
- **Abort-and-refire** — CC closes the HTTP SSE connection before `message_stop` is received, updates the pending message content with the incoming event, then opens a new API stream immediately.
- **Trigger event** — any event arriving while a REQ is actively streaming that causes CC to abort: user keystroke submissions (mid-stream input), background-task completion notifications, or subagent task-notifications (TN).
- **Cascade depth** — number of aborted REQs in a cascade (= total REQs − 1). A depth-3 cascade = 4 REQs, 3 aborted, 1 completed. Cost multiplier is roughly `(depth × cache_read_per_REQ) / cache_read_final`; for Case 1 with 277k CR tokens that is approximately 3× extra spend on cache reads alone.
- **Message-count stability** — the invariant that all cascade REQs share the same `message_count` value in the proxy log. Because aborted REQs produce no assistant turn, the message history length does not advance between cascade entries. This is the primary proxy-log indicator for cascades.

## Mechanism

CC maintains an event queue alongside each streaming REQ. Internally, CC's streaming client reads SSE events from the Anthropic API while simultaneously listening for events from the local event queue (user keystrokes, background-task completions, subagent notifications). The two listeners run concurrently. When the event queue fires, CC does not wait for the stream to drain — it cancels the HTTP connection immediately, even mid-token.

Three event classes can arrive while the stream is open that cannot be folded into the in-progress response:

1. **User input** — keystrokes submitted while the stream is open. CC appends a `[Request interrupted by user]` text-block to the last message slot and fires a new REQ with the user's new input appended.
2. **Background-task completion** — a `Bash(run_in_background=true)` task finishes and emits its result. CC appends a background-completion TN (task-notification) block to the message and refires. No `[Request interrupted by user]` marker is written — the abort is silent in session JSONL.
3. **Task-notification (TN)** — subagent finished, out-of-band tool result, or similar lifecycle event. CC appends a TN-block and refires, identical pattern to (2).

All three classes trigger the same abort sequence:
1. Close the SSE connection to the Anthropic API.
2. Mutate `messages[-1]` (or append a new user turn) with the incoming event content.
3. Open a new API stream with the updated payload.
4. Discard the aborted REQ's partial response — no session-JSONL `message.usage` entry is written.

If N trigger events arrive while streaming, each causes a fresh abort-and-refire: N events → N+1 REQs, N aborted, 1 completed. Events arriving during refiring also count — rapid user typing or multiple near-simultaneous background completions compound the cascade depth additively.

**What happens to in-flight tool_use?** If the stream was mid-tool-use (inside a `content_block_delta` for tool input_json), the partial tool input is discarded along with the rest of the stream. The next REQ restarts from scratch — no partial tool state is preserved.

**Detection signals:**
- _Proxy log:_ N consecutive `message_count=M, cache_breakpoints=[M-1]` entries with escalating `msg[M-1]` chars and the same overall message length but only the last has an entry in the session JSONL.
- _Session JSONL:_ `[Request interrupted by user]` text-blocks in the message history indicate at least one trigger-class-1 event. Background-task TNs leave no interrupt marker — the only signal is the block-count jump in the proxy log.
- _Monitor proxy pane:_ N rows with same `#N` display number, last row is the only one with non-zero output tokens (see § Monitor-Display Correlation).

**Idle state is safe.** If no REQ is currently streaming, background-task completions and TNs queue normally for inclusion in the next REQ without triggering any abort.

## Case 1 — session 1776977437 (2026-04-23)

**Symptom:** 4 Opus REQs between 22:21:52Z and 22:22:51Z UTC, all with `message_count=229` and `cache_breakpoints=[228]`. Only the final REQ produced a completed assistant response. Cascade depth = 3.

**Context:**
- Project: Monitor_CC
- Session JSONL: `~/.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor-CC/c2d68320-69d6-47b9-8c2e-9ddc7e0a5985.jsonl`
- Proxy log: `src/logs/api_requests_opus_monitor_cc_1776977437.jsonl`

**REQ table (msg[228] = the evolving final message slot):**

| # | Timestamp (UTC) | request_id (first 8) | msg[228] blocks | chars |
|---|---|---|---|---|
| A | 22:21:52.575 | `94522945` | 1 — user prompt only | 271 |
| B | 22:22:09.855 | `cf9af2e7` | 2 — + Background-TN | 357 |
| C | 22:22:26.751 | `fef7653b` | 5 — + 2× `[Request interrupted by user]` + new prompt | 497 |
| D | 22:22:51.313 | `f5997652` | 5 — + 2× interrupt + different new prompt | 434 |

**Session JSONL observations:**
- Two `[Request interrupted by user]` entries at 22:22:09.780 and 22:22:11.211 — matching the user-input trigger class; gap of 1.4 seconds between them.
- No `message.usage` entries for REQs A, B, or C — confirming all three were aborted before any assistant response was committed.
- REQ D completed at 22:23:21.423 (`req_011CaMV3zxTm3t7SpZNBuz2o`): `cache_read_input_tokens=277,469`, `cache_creation_input_tokens=181`, `input_tokens=6`, `output_tokens=1542`.

**Trigger sequence reconstruction:**
1. REQ A launched with initial user prompt (msg[228] = 1 block, 271 chars).
2. Background task completed while REQ A was streaming → CC aborted REQ A, appended TN block → REQ B. (No interrupt marker confirms this was trigger class 2, not class 1.)
3. User typed mid-stream at 22:22:09.780 → CC aborted REQ B, appended `[Request interrupted by user]` + new prompt → REQ C (5 blocks, 497 chars).
4. Second user interrupt at 22:22:11.211 (1.4 s later, different prompt text) → CC aborted REQ C → REQ D (5 blocks, 434 chars — slightly shorter because the second prompt was more concise).
5. REQ D streamed to completion at 22:23:21.423.

**Proxy-log forensic pattern (confirms abort without session JSONL):** All 4 proxy entries share `message_count=229` and `cache_breakpoints=[228]`. In a normal REQ sequence, `message_count` advances by 2 per turn (one user turn + one assistant turn). A run of N proxy entries with the same `message_count` value is a direct indicator of N cascade REQs — the message history didn't grow because none of the aborted REQs produced a committed assistant turn.

**Distinguishing trigger type from the table:** REQ A→B shows a char increase of only 86 chars with no interrupt marker in session JSONL → confirms trigger class 2 (background-TN only; no user input). REQ B→C and C→D both have `[Request interrupted by user]` markers in session JSONL → trigger class 1 (user input). The block count jumping from 2 to 5 at REQ C reflects: the 2 existing blocks + 2 interrupt text-blocks + 1 new user prompt block.

**Interpretation:** Three distinct trigger types contributed in sequence: background-task completion (A→B), then two rapid user-input triggers (B→C, C→D). The 59-second total wall-clock span (A to D completion) represents pure overhead — all substantive computation happened in REQ D.

## Billing Implication

The streaming API delivers `message_start` as the first SSE event, before any content blocks. This event already contains the final `usage` object with `input_tokens`, `cache_creation_input_tokens`, and `cache_read_input_tokens` set to their billed values — confirmed by the web-search tool-use example at `sources/Streaming_Messages4.md:65` and the basic streaming example at `sources/Streaming_Messages2.md:27` and `:88`.

By the pattern documented for refusal billing (`sources/Streaming_Refusals.md:25-28`): "Usage metrics are still provided in the response for billing purposes, even when the response is refused. You will be billed for output tokens up until the refusal." Client-side abort is structurally analogous to a refusal — the billing commitment is made at `message_start` delivery.

**Large-context factor:** the Case 1 session had `cache_read_input_tokens=277,469` at REQ D — near the upper end of a long Monitor_CC development session. At this context size, each aborted REQ costs ~$0.08 in cache-read charges alone (277k × $0.30/M). A depth-1 cascade (one background completion mid-stream) that would be negligible at 50k CR tokens becomes meaningfully expensive at 277k. Long-running sessions with large accumulated context are therefore disproportionately vulnerable to cascade overhead. This also means that the most productive time in a session (late, after many context-building REQs) is also the most expensive time to accidentally trigger a cascade.

**Note on cache-creation across cascade REQs:** Because `cache_creation_input_tokens` is non-zero for aborted REQs, Anthropic does write a cache entry at stream-open even before any content_block event arrives. This means the REQ-B cache entry at `cache_breakpoints=[228]` may or may not be reusable by REQ-C — it depends on whether msg[228]'s content (now 5 blocks instead of 2) aligns with the same prefix boundary. In practice the addition of TN blocks shifts the breakpoint position, so each aborted REQ writes a cache entry that the next REQ cannot fully hit. The net effect is `N × cache_creation` tokens wasted, not `1 × cache_creation` amortized.

**Consequence per aborted REQ:**
- Full `cache_read_input_tokens` billed (prefix hit against Anthropic's cache pool)
- Full `cache_creation_input_tokens` billed (prefix written to new cache entries during the stream)
- Full `input_tokens` billed (uncached portion of input)
- Output tokens billed only up to the abort point — typically zero to a handful of thinking/text tokens if the stream was killed early

**Worst-case overhead for the Case 1 depth-3 cascade** (Opus tariffs, approximate):
- 3× ~277k cache-read tokens × $0.30/M ≈ **$0.25**
- 3× ~181 cache-creation tokens × $18.75/M ≈ **<$0.01**
- 3× few hundred wasted output/thinking tokens × $75/M ≈ **$0.05**
- Network overhead: 4× the full 229-message request payload transmitted

Total wasted spend vs. a single clean REQ: ~$0.30 for a 59-second interaction.

**Latency compounding:** each abort-and-refire adds one full round-trip: TLS handshake, Anthropic routing, TTFB for `message_start`, and the thinking prefix before the first content token. For Opus this is typically 3–8 seconds per REQ before useful output begins. A depth-3 cascade adds 9–24 seconds of dead latency on top of the actual response time. In Case 1, REQ A started at 22:21:52 and REQ D completed at 22:23:21 — 89 seconds total. REQ D's actual completion after its own stream-open was ~30 seconds, so ~60 seconds were lost to cascade overhead.

## Monitor-Display Correlation

`src/proxy_display/format.py:94`:

```python
opus_req_num = sum(len(t.get('api_calls', [])) for t in turns[:turn_idx])
```

`turns.api_calls` is populated from session-JSONL completed assistant responses via `token_pane.build_cache_turns`. Aborted streams produce no session-JSONL `message.usage` entry → do not populate `api_calls` → do not advance `opus_req_num`.

**Effect:** all N REQs in a cascade map to the same `opus_req_num` in the proxy display. The Case 1 cascade shows 4 consecutive proxy-pane entries all labelled `#115` (or whichever completed REQ preceded the cascade). The visual signature of a cascade in the proxy pane is:

- N consecutive rows with the same `#N` display number
- Rapidly growing `msg[last]` block count and char count across the rows
- Timestamps clustered within a 60-second window
- Only the final row has a non-zero `output_tokens` value (the others show `out=0` or a small thinking count)

Bead `13t` tracks the red-background collision marker added to the proxy pane to surface same-number cascades visually. Without the marker, cascades are easy to miss because the REQ rows look like normal consecutive requests until you notice the repeated display number.

## Policy

While an Opus (or any model) stream is in flight or a new REQ is imminent:

1. **No mid-stream user input.** Every completed keystroke submission cancels the current stream and fires a new REQ. Wait for the current stream to complete before sending the next message. Typing while Opus is responding produces at minimum a depth-1 cascade and can compound quickly with fast typing.
2. **Max one background task in flight at any time.** Every background-task completion event can abort the current stream. Serialize `Bash(run_in_background=true)` spawns — launch the next task only after the previous task's TN has been processed by a completed REQ, not while any REQ is streaming.
3. **For parallel worker orchestration:** never fan out N background tasks while a stream is active. Instead, batch workers behind a single orchestrator agent that waits for all workers to finish and emits ONE completion event at the end. This reduces N potential abort triggers to 1. Practically: spawn all workers in one REQ with explicit `run_in_background=true` orchestration logic, then wait for all workers to report idle before resuming top-level work. The wait itself does not keep a stream open — only active Opus reasoning keeps a stream open.

**Non-obvious implication:** a depth-1 cascade (single background completion while Opus is thinking) is often invisible — the user sees one answer and assumes one REQ fired. The proxy pane is the only surface that shows the aborted REQ. Regular inspection of the proxy pane during long orchestration sessions reveals whether cascade patterns are accumulating.

## Reproducibility

- **Cascade from background-task completion:** fully deterministic — any `Bash(run_in_background=true)` task that completes while a REQ is streaming will abort the stream. Reproducible by spawning a short background task immediately before a long Opus prompt.
- **Cascade from user input:** fully deterministic — any text submitted to CC while a stream is open triggers abort-and-refire. Reproducible by typing during Opus response generation.
- **Cascade from TN (subagent):** deterministic in principle but depends on subagent timing; harder to reproduce on demand.
- **Severity (cost):** scales linearly with session context size (CR tokens). A fresh-session cascade at 30k CR costs ~10× less than a late-session cascade at 277k CR.

## Sources

- Session JSONL: `~/.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor-CC/c2d68320-69d6-47b9-8c2e-9ddc7e0a5985.jsonl`
- Proxy log: `src/logs/api_requests_opus_monitor_cc_1776977437.jsonl`
- `sources/Streaming_Messages4.md:65` — `message_start` event with `cache_creation_input_tokens` and `cache_read_input_tokens` already set in `usage` (web-search streaming example)
- `sources/Streaming_Messages2.md:27` — basic streaming `message_start` showing `usage` delivered as first event
- `sources/Streaming_Messages2.md:88` — tool-use streaming `message_start` confirming `usage` pattern
- `sources/Streaming_Refusals.md:25-28` — billing commitment at stream-open; analog for client-side abort
- Bead `2lm` (closed) — forensic investigation of session 1776977437 that produced the Case 1 data
- Related beads: `ds5` (background-task orchestration rules), `p8w` (parallel worker spawn control), `13t` (proxy display cascade marker / same-number collision highlighting)
- `decisions/pipe05_proxy_cache.md` — proxy cache architecture; cache_read billing context and BP layout
- `decisions/OldThemes/cache_rebuild_cases.md` — companion doc for cache-rebuild forensics; structural pattern reference for this file
