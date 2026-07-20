# gpu_pane — Preset Discovery & Collections

## State as of the removal task

`_discover_preset_names()` (`status.py:17`) calls `rag-cli server presets --json` with a 3s
timeout. On success returns `[p['name'] for p in payload]`. On any failure
(FileNotFoundError / TimeoutExpired / JSONDecodeError / KeyError) returns `[]`. `PRESET_NAMES`
is a module-level constant set at import time; frozen for process lifetime. Pane respawn
(Ctrl+R) re-imports the module and re-runs discovery.

`_fetch_collections()` (`status.py:182`) calls `rag-cli list_collections --json` with a 5s
timeout; returns `[{collection, chunks}]` on success, `[]` on any failure. Polled every 30s
(`COLLECTIONS_POLL_INTERVAL`) independent of the 2s GPU-server tick.

**Empty-preset behavior:** when `PRESET_NAMES == []`, `all_statuses()` returns
`preset_statuses = []` and all running servers land in `arbitrary`. Pane renders the
`GPU Servers` header with no preset rows. Digit-key handler gate (`idx < len(PRESET_NAMES)`)
blocks all toggle actions safely. No error marker, no fabricated names.

## Evidence

**Real presets at the time** (from `rag-cli server presets --json` on production RAG):
```
['embedding-8b', 'embedding-0.6b', 'reranker-0.6b', 'reranker-8b', 'generator-4b', 'splade']
```
6 names; only `splade` overlaps the former hardcoded fallback `['embedding', 'reranker', 'splade']`.

**Divergence:** the former fallback list was stale at removal time — 2 of 3 names
(`embedding`, `reranker`) no longer exist as presets; `embedding-8b`, `embedding-0.6b`,
`reranker-0.6b`, `reranker-8b`, `generator-4b` were invisible. A rag-cli failure would have
silently shown the 3 stale names instead of the 6 real ones.

**Reference pattern:** `_fetch_collections()` has always returned `[]` on failure. Its
collections block shows `(none indexed)` when empty — no fabricated content. The preset block
now mirrors this pattern.

## Recommendation (target state)

Keep — the state described above is the implemented and correct state. `_discover_preset_names` returns `[]`
on failure; pane renders an empty preset block. No re-hardcoding warranted (any static list
drifts again on next RAG server addition).

## Open Questions

None.

## Sources

Feature history (lock-exempt rationale, --json flag, 30s cadence) and route-consolidation
narrative (masking-fallback removal) — see the companion entry in this area.
