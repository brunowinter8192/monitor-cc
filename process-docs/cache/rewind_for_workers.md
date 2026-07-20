# /rewind for Workers — Cache Behavior

## Question

Workers die at the context limit. Anthropic `/rewind` resets the conversation state in
the main session to an earlier REQ — for Opus without a cache rebuild, because the
cached prefix still exists within the 5-min TTL. Does the feature work similarly
cache-friendly for workers?

## Hypotheses

- **V1:** each worker has its own conversation_id → own cache scope → `/rewind` in a
  worker reuses a cached prefix like main-Opus → the lever works.
- **V2:** worker and main share cache scope → `/rewind` in a worker references a REQ
  from a different conversation → uncached → rebuild → no lever.

Suspected: V2 — workers share a cache per project with the main session, since main is
the only main session in the project.

## Verification Test (small, not run)

1. Spawn a worker, accumulate 5-10 REQs.
2. `/rewind` in the worker to REQ N (e.g. N=3 of 10).
3. Fire the next REQ, measure `cache_read`.
4. ≈ prev_REQ_3's prefix → V1. ≈ 0 → V2.
5. Compare against a main-session rewind as baseline.

## Status

Spec only. Test not executed. Parked — no high pressure, since worker context
management is manageable without the `/rewind` lever anyway (fresh spawn + aggressive
reuse).

## Sources

- Anthropic `/rewind` docs
- worker-cli / `src/spawn/tmux_spawn.sh`
