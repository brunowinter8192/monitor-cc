# Thinking Audit: proxy-on vs proxy-off Comparison

## Status Quo

Gut feeling in a session on 2026-04-28: thinking seems to trigger more often or for longer in proxy-on sessions than in proxy-off sessions. No empirical data on this at the time — no dev script that extracts `type=thinking` block lengths per REQ from the session JSONLs in `~/.claude/projects/` and delivers distribution statistics (mean/median/p90/p99/% with thinking>0).

## Evidence

Anecdotal only. No measurement. No A/B comparison.

## Recommendation (target state)

**Parked — no further work planned.**

Reason: the proxy is used permanently in every session (strip logic, logging, cache display, worker configuration etc. all depend on it). A proxy-on vs proxy-off comparison is academic — there is no real case where we'd go without the proxy. Even if the hypothesis is true (proxy → more/longer thinking), the consequence wouldn't be "turn off the proxy" but a proxy-internal optimization, which is plannable independent of the comparison.

If a run does become interesting at some point (e.g. proxy-modification variant A vs B), the implementation is trivial:
- `dev/thinking_audit/audit.py`
- Reads the session JSONL from `~/.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor_CC/<session>.jsonl`
- Walks assistant-turn entries, collects all `type=thinking` blocks from `.message.content[]`, sums `len(thinking.text)` per REQ
- Token counts from `.message.usage` (output_tokens; the thinking-tokens reservation under adaptive is included in cache_creation_input_tokens)
- CLI `--session <id>`, `--compare <a> <b>`, output markdown with aggregates
- Self-contained, one file, no src/ change

## Open Questions

None — the topic is parked.

## Sources

- A closed tracking task from 2026-04-28, parked instead of implemented
