# RAG Helpfulness Evaluation

## Status Quo

Hard rule in `~/.claude/shared-rules/opus/workers-1.md` § "RAG-First on Code Exploration": RAG-cli search before any explicit `ls`/`grep`/`Read` chain when exploring unfamiliar code territory. Rationale: DOCS.md + process-docs + CLAUDE.md are indexed — RAG gives architecture-level context in one call that would take 5-10 tool calls to reconstruct manually.

Gut feeling from production sessions: valuable for status-quo/decision/DOCS questions ("why is X this way", "where does Y live"). Less valuable when the file location is already known (then `Read` directly is cheaper). Still unclear: how well RAG covers questions that require combining multiple concepts, or where the search term isn't clearly present in the index text.

## Observations from Production Sessions

**Queries are often too specific.** Observed pattern: Opus phrases queries that read like "reading bead comments" — very close to the immediate task context, little semantic variation. Example: instead of "NSPanel cursor rects non-key window" more like "enableCursorRects NonactivatingPanel". That hits documents with exactly this phrase, but lets thematically related chunks slip through.

**Single-query topics let a lot slip through.** One query per topic covers only one semantic angle. For multi-step matters (e.g. "why doesn't cursorUpdate_ fire") there is often no single chunk containing all relevant aspects — the answer requires several chunks that different queries would trigger. If Opus only fires one query, recall stays low.

**Queries read like reading-bead-comments.** Queries often mirror the current state of knowledge instead of asking open questions. That leads to confirmation bias in retrieval: what's found is what's already known, not what's still missing. A more useful query strategy would be "what does the index know about X that I don't know yet?" — but that's hard to phrase as a query.

**Consequence:** RAG-First is clearly valuable for decision-, DOCS-, and architecture-type questions. For bug diagnosis and investigative questions the added value is more questionable — there, direct `grep` / `Read` dominates because the relevant information sits in code lines, not in prose.

## Eval Plan

**Step 1 — Data extraction from proxy logs**

Source: `src/logs/api_requests_*.jsonl` — contain all rag-cli tool calls of Opus sessions as JSON payloads. Extract via a dev/ script:

- All `rag-cli search_hybrid` / `search` / `search_keyword` calls
- Per call: query text, collection, top-k, session timestamp
- Aggregate by topic (session cluster): how many queries per topic, which collections, top-k distribution
- Signal: how many topics were handled with a single query vs reformulated multiple times

**Step 2 — Eval methodology**

Three scoring dimensions per query result:

| Dimension | Measurement | Signal |
|---|---|---|
| Hit rate | Did something usable come back in the top-k? | Yes/No per query |
| Follow-up rate | Did Opus have to follow up (same topic, another query)? | Count of follow-up queries per topic |
| Recall proxy | Was the relevant document found that should have been found? | Requires ground truth — manual for a sample |

For automatic evaluation: hit rate + follow-up rate derivable from proxy logs. Recall proxy requires manual annotation of a sample (10-20 topics).

Output: a report MD with per-session query inventory + a rating per query (Useful / Too-narrow / Too-broad / Miss).

**Step 3 — Classify WIN-RAG vs WIN-Direct vs Tie**

After annotation: per topic, decide whether RAG or a direct `Read`/`grep` would have been the more efficient strategy:

- **WIN-RAG:** RAG delivered a sufficient answer on the first query; the direct approach would have cost 3+ tool calls
- **WIN-Direct:** the file location was known or easily inferable; RAG cost an extra query round with no added value
- **Tie:** both would have been comparable

Goal: refine the rule "RAG-First when ..., direct when ..." with an empirical basis instead of a gut feeling.

## Core Trade-off

**Specificity vs noise.** Specific queries have high precision (what comes back is relevant) but low recall (what's missing goes unnoticed). Broad queries increase recall at the cost of noise in the result set. Mitigable with a reranker, but only when good chunks are in the retrieval set.

**Single-query vs reformulation rounds.** 2-3 complementary queries per topic (e.g. one technical + one conceptual + one problem-oriented) substantially increase recall. Cost: 2-3x more tool calls for retrieval. Net often cheaper than one round of `Read`-drilling, more expensive than a direct `grep` when the answer sits in a known file.

**Known file location as the switch.** The strongest predictor of "direct beats RAG" is whether Opus already knows which file is affected. If yes: `Read` + `grep` directly. If no (architecture question, cross-cutting concern, "where does X even live"): RAG-First remains the right choice.

## Open Questions

- What sample size is sufficient for statistically robust conclusions? Estimate: 30-50 topics from ~10 sessions.
- Which topics to take? Representative across query types (architecture / bug-diagnosis / lookup) or targeted at the weak classes?
- How to score without ground truth? Proxy signal: follow-up-query rate as a recall proxy (a high follow-up rate = the first query was too narrow). Limitation: Opus doesn't always explicitly reformulate.
- Must be orchestrated as a dev/ script (not ad-hoc) to be reproducible. Output: a report MD with a per-session inventory.
- Is the RAG-First rule as sensible for workers as for Opus? Workers have a narrower task scope — "known file location" may dominate more strongly there.

## Phase B — Auto-Metrics Run (2026-05-20)

### Implementation

`dev/tool_use_analysis/rag_query_audit.py` (350 LOC, commit `36b2c54`) — extracts all `rag-cli search_hybrid/search/search_keyword` calls from proxy logs, clusters per session via greedy chain-link (token-Jaccard ≥ 0.20, stopwords excluded), computes auto-metrics, writes a report MD with manual annotation columns left as `_`.

Auto-metrics: `query_count`, `follow_up` (bool: count > 1), `result_chars`, `chunk_count` (per query, from tool_result content), `top_k`, `collection`, `truncated` (CC 5k/5k split signature).

Manual columns for review: `hit_quality` (Useful / Too-narrow / Too-broad / Miss) per query, `classification` (WIN-RAG / WIN-Direct / Tie) per topic.

CLI: `--jaccard T` (default 0.20) — the user can re-run with different thresholds during review.

### Run-Output Snapshot

Report: `dev/tool_use_analysis/20260520_rag_query_audit.md`.

| Metric | Value |
|---|---|
| Sessions analyzed | 15 (10 with rag-cli usage, 5 with 0 calls) |
| Total events | 2957 |
| Unique rag-cli calls | 44 |
| Unique topics (jaccard ≥ 0.20) | 36 |
| Single-query topics | 31 |
| Multi-query (follow-up) topics | 5 |
| Calls in follow-up rounds | 13 / 44 (29%) |
| Misses (chunk_count = 0) | 8 |
| Truncated results | 1 |
| Calls without tool_result | 13 (data gap — likely Bash compound calls lose tool_use_id pairing) |
| Collections | Monitor_CC-meta (30), Monitor_CC-features (12), RAG-meta (2) |

Sampling bias: all 44 calls are `search_hybrid`. `search_keyword` / `search_dense` was never used. RAG multi-model wasn't either.

### What Was Directly Visible (before manual annotation)

- Top follow-up: **T024** with 4 queries (cursor rects/edges) — the most likely "RAG couldn't find" signal
- **T028** (DOCS pattern audit, 3 queries, all 0 chunks) — a strong WIN-Direct candidate
- Real misses (small result_chars + 0 chunks): T001, T002, T013, T015, T020, T028 (3 queries)

### What Remained Open

- Manual annotation of the `hit_quality` + `classification` columns in `20260520_rag_query_audit.md` — a follow-up session
- From that: rule refinement "RAG-First when X, direct when Y" in `workers-1.md` § RAG-First on Code Exploration
- Data-gap investigation: 13/44 (30%) calls without tool_result — on re-run, check whether it's an extractor bug (Bash compound with multiple rag-cli's) or a genuine "result missing in log"

## Sources

- `src/logs/api_requests_opus_monitor_cc_*.jsonl` — proxy-log data source for rag-cli call extraction
- `dev/tool_use_analysis/rag_query_audit.py` — extraction + clustering + metrics + report writer
- `dev/tool_use_analysis/20260520_rag_query_audit.md` — run output (auto-metrics + empty manual columns)
- `~/.claude/shared-rules/opus/workers-1.md` § RAG-First on Code Exploration — the hard rule at the time

## Session 2026-05-23 — Tool Inventory + Use-Case Audit

### CLI Tool Inventory (Post-Reduction)

`rag-cli` reduced to 9 subcommands (was 11). `search` (pure semantic) and `search_keyword` (BM25) removed — never used in 44 calls across 15 sessions.

| Subcommand | Purpose |
|---|---|
| `search_hybrid` | Dense + sparse fusion; default for all queries |
| `list_collections` | List collections with `--filter` |
| `list_documents` | List documents in a collection (`--filter`, `--document`) |
| `progress` | Indexing progress |
| `read_document` | Read chunk context (`--before N`, `--after N`) |
| `delete` | Delete a collection or document |
| `status` | Server health (embedding/reranker/splade) |
| `update_docs` | Re-index from `.rag-docs.json` |
| `server` | Manage server presets (start/stop/restart/list/status) |
| ~~`search`~~ | REMOVED — pure semantic, 0/44 calls |
| ~~`search_keyword`~~ | REMOVED — BM25-only, 0/44 calls |

### Standard Use-Case Profile

Findings from the Phase-B evaluation (44 calls, 15 sessions, 36 topics):

- **100% hybrid** — all 44 calls `search_hybrid`; removal of `search`/`search_keyword` was data-driven
- **86% single-query** (31/36 topics) — Opus rarely reformulates; recall gaps from missing follow-ups
- **14% multi-query** (5/36 topics, 13 of the 44 calls) — follow-up rate as a recall-proxy signal
- **8 real misses** (chunk_count = 0): T001, T002, T013, T015, T020, T028
- **Collection split:** Monitor_CC-meta 30 calls (68%), Monitor_CC-features 12 calls (27%), RAG-meta 2 calls (5%)
- **13 calls without tool_result** (29%) — data gap, likely a Bash-compound ID mismatch in the extractor

### Collection Content Mapping

| Collection | Content | Usage (44 calls) |
|---|---|---|
| `Monitor_CC-meta` | process-docs, DOCS.md files, CLAUDE.md, sources/sources.md | 30 (68%) |
| `Monitor_CC-features` | process-docs (old area docs) | 12 (27%) |
| `Monitor_reference` | 337 chunks of Anthropic API docs (see below) | 0 (0%) |

### The Reference Collection as an Untapped Lever

`Monitor_reference` contains 337 chunks of Anthropic API docs: AdaptiveThinking, PromptCaching, ExtendedThinking, ContextEditing, ProgToolCalling, Citations, Files, ContextWindow, Compaction, FastMode, FineGrained, Effort, Msgs, PDF_support among others. Never queried in any of the 44 calls — 0% usage rate.

Use-case examples for misses that could have hit there: T001/T002 (prompt-caching behavior → `PromptCaching` chunks exist), T015/T020 (context-window behavior → `ContextWindow`/`Compaction` chunks exist). The collection is indexed and ready — what's missing is the rule to actively query it for API-docs questions.

### Naming Drift

`Monitor_reference` deviates from the consistency pattern: `RAG_reference`, `searxng_reference` → the correct form would be `Monitor_CC_reference`. `_CC` was omitted at the initial reindex. Fix: rename the collection at the next reindex → `Monitor_CC_reference`.

### Best Production Config (from the RAG project's own eval)

| Parameter | Value | Evidence |
|---|---|---|
| Fusion | CC α=0.8 | +3 pp snippet recall vs RRF — from rag-cli's own fusion-decision record |
| Reranking | False (default off) | Technical docs: −8.5 pp NDCG@3; doc recall +4 pp, snippet −1 pp + ~2s latency — trade-off rejected — from rag-cli's own reranking-decision record |
| HYBRID_CANDIDATES | 50 dense + 50 sparse | — |
| top-k default | 12 | Corrected from "20 (10–50 valid)" in the shared rule |

### Pending (Follow-On Session)

- **Manual annotation** — 36 topics in `dev/tool_use_analysis/20260520_rag_query_audit.md`; fill in the `hit_quality` + `classification` columns → rule refinement "RAG-First when X, direct when Y"
- **Audit-script bug fix** — clarify the 13/44 calls (29%) without tool_result in `dev/tool_use_analysis/rag_query_audit.py` (Bash-compound ID mismatch?)
- **Replay probe of the 8 misses** — fire the same queries against `Monitor_reference`; check whether Anthropic-docs chunks close the gaps
- **Collection rename** — `Monitor_reference` → `Monitor_CC_reference` at the next reindex
