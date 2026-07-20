# CC Source Code Investigation — Tracker

## Background

2026-04-28: a research worker ran 2 passes over GH issues + source-leak repos + binary
extraction (v2.1.121), found 12+ undocumented env vars, uncovered the watchdog
mechanism, and reverse-engineered 429/529 handling and the fast-mode cooldown. Output:
`dev/cc_source_research/20260428_env_var_inventory_v2.1.121.md` (205 LOC, 67 confirmed
env vars in 5 categories + 8 dead-code fragments).

Finding: the CC binary + leak repos are a rich, largely untapped source. Investigation
thread with many sub-questions, one worker pass per sub-question.

## Sub-Question Status

### Done

1. **Complete env-var inventory (v2.1.121)** —
   `dev/cc_source_research/20260428_env_var_inventory_v2.1.121.md`. Latency-subset
   recommendations for `settings.json:env` documented
   (`CLAUDE_STREAM_IDLE_TIMEOUT_MS=300000`, `CLAUDE_ENABLE_STREAM_WATCHDOG=1`,
   `CLAUDE_ENABLE_BYTE_WATCHDOG=1`, `CLAUDE_SLOW_FIRST_BYTE_MS=8000`). 6 open questions
   in the MD.

### Open (prioritized, at time of writing)

**High — direct latency levers:**

2. **CC behavior toward mitmproxy** — HTTPS_PROXY env reads, TLS/cert validation,
   anti-MitM/cert pinning, header diffs, stream/SSE health probes. First worker attempt
   in April hit its context limit without starting the task. A fresh worker per
   sub-question is needed.
3. **Cache-control logic** — how CC decides which messages get cached, ephemeral vs
   persistent, cache-key composition. Complementary to the latency track.
4. **Background-task / async-agent delivery** — the `<task-notification>` injection
   mechanism (v2.1.121 uses TN, no longer `[SYSTEM NOTIFICATION]` SR), race conditions,
   buffer sizes. Hint: `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS` suggests a separate path.

**Medium — architecture/behavior:**

5. Model-selection routing (`--fallback-model`, `FALLBACK_FOR_ALL_PRIMARY_MODELS`,
   fast-mode cooldown state machine).
6. Context-compaction logic (pruning heuristics when the window is full).
7. Tool-definition loading (deferred tools, ToolSearch, skill activation, lazy load).
8. Telemetry pipeline (`tengu_*` events, endpoints, blockable?).

**Low — exploratory:**

9. Hidden features / codenames (`02-hidden-features-and-codenames.md` from the decompile
   repo).
10. Plan-mode internals (SR templates, transition logic).
11. Hooks system (lifecycle phases, race conditions).

## Lesson — Worker Reuse for Research

The cc-perf-research worker had already completed sub-1 + 2 prior GH-research passes →
context exhausted at the start of sub-2. **Research sub-questions are individually
context-heavy** (binary extraction + GH search): max 1-2 per worker lifetime. Plan a
fresh worker per sub-question.

## Approach (if reactivated)

- One worker pass per sub-question, with the github-search skill active.
- Output as a markdown section under `dev/cc_source_research/`.
- Findings with a concrete fix need → own bead.
- Findings that are knowledge only → investigation doc.
- Reused sources (decompile repos, binary versions, NPM tarballs) → `sources/sources.md`.

## Out of Scope

- Anthropic API server-side internals (no source available).
- Model internals.
- Ad-hoc bugfixing from findings → own bead, not here.

## Cross-Project Spillover

A worker wrote a tool wishlist into the `MCP/github` project's own process-history
surface. Friction points: the npm binary-extract chain (9 calls, 205MB), comment-
pagination blindness on GH issue #26224 (30/90), missing version-awareness in repo
search (post-leak vs pre-leak vars).

## Sources

- GH Issues #49500, #33949, #26224.
- Decompile repos (alanisme, thepono1 INSIGHTS).
- Binary strings v2.1.121 (extracted locally to `/tmp/package/claude` at
  investigation time).
