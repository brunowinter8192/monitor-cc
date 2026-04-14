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
