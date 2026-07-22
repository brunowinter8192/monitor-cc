# rag-cli search_hybrid Hard-Renamed to search, Hooks Updated, 2026-07-22

## Trigger

rag-cli's search subcommand was hard-renamed `search_hybrid` → `search` (no alias — the old name stopped resolving). Three Monitor_CC hooks hardcode the subcommand literal as part of their anchor/detection logic and needed a matching update to keep firing on real rag-cli invocations:

- `rewrite_rag_cli_search_noise.py` — `_RAG_RE` anchor
- `block_rag_docs_layer.py` — `_RAG_RE` anchor + `_find_collection` token-equality check
- `rewrite_chained_sleep.py` — `_TRIVIAL_PAIRS` exact-pair entry `('rag-cli', 'search_hybrid')`

## Scope check before renaming

Confirmed via grep across `src/hooks/` that no `search_keyword`/`search_dense` subcommand exists (both were removed from rag-cli previously) — ruling out the concern that a bare `\bsearch\b` anchor could over-match a sibling subcommand that still needed distinguishing. The rename to a bare `search` anchor was therefore safe with no additional disambiguation needed.

## Untouched by design

`block_rag_cli_chained.py` was NOT touched — its anchor logic blocks ANY `rag-cli <subcommand>` chained with a non-rag-cli command; it never hardcodes `search_hybrid`, so the rename didn't affect its matching behavior. Its DOCS.md entry still contains one illustrative `rag-cli search_hybrid "q" coll | grep foo` example (line ~360 in `src/hooks/DOCS.md`) — left as-is since it demonstrates the block pattern, not a live regex anchor.

## Verification — this session (rename task) and recap

`py_compile` clean on the 3 hooks. `grep -c "search_hybrid"` on all 3 hook files: 0/0/0. Smoke tests (real subprocess invocations): `test_rewrite_rag_cli_search_noise.py` 15/15, `test_block_rag_docs_layer.py` 11/11, `test_rewrite_chained_sleep.py` 31/31 — all passing. DOCS.md updated in the same commit as the code change (not deferred to recap). Live deploy onto the real `~/.claude/settings.json` not attempted from this worktree (`hook_setup.py`'s worktree guard fires by design); deferred to the orchestrator after merge.
