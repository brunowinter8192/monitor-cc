# Chunk Redundancy in Retrieval + Size Variance (observed 2026-06-02)

## Trigger

Surfaced during **Reddit-MCP e2e validation** — NOT a Reddit-pipe issue (that pipe works e2e). This is RAG-side. `rag-cli search_hybrid "how to extract data from reddit api" reddit_posts` (top_k=10, reranked) returned two result slots — **rank 5 and rank 8** — that are **different chunks of the SAME document** (`pushshift__c65qy3.md`, chunk 1 and chunk 2) with **overlapping content**: the same `u/ukpolbot` PRAW code snippet appears in both.

Separately, chunk sizes across the result set look visibly uneven.

Post-level dedup is NOT the cause — `index_subreddits` hash dedup (post_id + title-hash) correctly indexed `c65qy3` exactly once. This is a chunking + retrieval-layer phenomenon, independent of source-level dedup.

## Two concerns

### 1. Same-document chunk redundancy in search results

- Chunking at the time: 2000 chars / **400 char overlap** (word-aligned), recursive character split — see rag-cli's own chunking-decision record.
- The 400-char overlap duplicates boundary text across adjacent chunks → the ukpolbot snippet sits at the chunk1/chunk2 boundary → present in both.
- `search_hybrid` returns the top-k chunks with **no collapse/dedup by parent document** → two near-duplicate chunks of one doc consume two of the 10 result slots.
- Effect: redundant results, fewer distinct documents surfaced per query, wasted top-k budget, and duplicated context handed to any downstream LLM.

Question: should search collapse/dedup chunks by document (keep highest-scoring chunk per doc, OR merge adjacent same-doc chunks)? Layer: rag-cli's own search-layer decision record.

### 2. Irregular chunk sizes

- Recursive character split on hierarchical separators (`\n\n → \n → . → ! → ? → space`) ends each chunk at the nearest separator before the 2000-char target → variable sizes **by construction**.
- Markdown-structured docs amplify this: reddit post MDs (title, `---`, selftext, `---`, tree-grouped comment blocks with `###` headers) contain many `\n\n` boundaries → frequent early breaks → high size variance, some very small fragments.
- rag-cli's own chunking-decision record already names the root cause: "No markdown-awareness (headers not treated as boundaries). No content-adaptive splitting."
- Chunk stats vary across collections: one A_chunking_stats report avg 843 / median 889 / max 1190; another avg 1736 with 80% in the 1500-2000 bucket.

Question: does the size variance (tiny fragmented chunks) hurt retrieval quality, or is it benign? Would markdown-aware splitting (headers as boundaries) or a min-size floor (merge small fragments) help for structured docs like reddit posts?

## Status

Observation only — not yet investigated. The target state in rag-cli's own chunking-decision record (keep 2000 / 400, recursive split) is **unchanged**; this observation does NOT yet justify a config change. To converge, needs:

- (a) Characterize how often same-doc chunk redundancy occurs across real queries (frequency, impact on distinct-doc recall).
- (b) Measure whether doc-level chunk dedup/merge in `search_hybrid` improves distinct-document recall without losing relevant context.
- (c) Assess whether chunk size variance / small fragments correlate with retrieval misses on markdown-structured corpora.

Note: rag-cli's own chunking-decision record already tracks a related "2000 vs 1000 chars A/B" open question; this theme adds the **overlap-driven redundancy** and **markdown-structure size-variance** angles, which are distinct from the raw chunk-size question.

## References

- rag-cli's own chunking-decision record — chunking state/target (2000/400 recursive split, no markdown-awareness, no content-adaptive splitting)
- rag-cli's own search-layer decision record (where chunk-collapse-by-document would live)
- `dev/indexing/A_chunking_stats.py` — existing chunk-size distribution analysis tool
- Observed in: Reddit-MCP `reddit_posts` collection, query "how to extract data from reddit api", result ranks 5 & 8 = `pushshift__c65qy3.md` chunks 1 & 2
