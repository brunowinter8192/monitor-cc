# RAG Pane — update_docs Progress Reporting (Variant A)

2026-06-09. The menubar RAG pane (`RagController`, reads `~/.rag-locks/rag.lock`) is a LIVE
indexing-progress indicator. During `rag-cli update_docs` it showed `unknown: 0/0` — `sync.py` never
called `lock.update_progress`, and update_docs has no single `args.collection`.

## Decision

**Variant A chosen** — accurate live done/total during any run (incl. update_docs). **Variant B
rejected** — a persistent "N docs indexed per collection" count in the idle state. User: "let's not
overload it." The pane stays a live indicator; when nothing runs it shows "no indexing
currently running".

## Mechanism (implemented)

- rag-cli `lock.update_progress(done, total, current_document, collection=None)` — optional
  `collection` added to the progress dict (`src/rag/lock.py`).
- `sync.py:_sync_one_collection` calls it per document (per-collection counter; resets on the next
  collection — intentional, the label shows which collection runs). cli.py `index` also passes
  `collection=args.collection`.
- Menubar `_read_rag_status`: label = `args.collection or progress.collection or Path(args.input).name
  or 'unknown'`. Result: `monitor-cc-docs: 3/8 · 5s` instead of `unknown: 0/0`.

## Status

Implemented + LIVE-VERIFIED — the lock carried real `done/total/current_document/collection` during a
real update_docs run (1→4 of 4, collection `monitor-cc-docs`); menubar rendering sample-tested.
