# Two-Level Progress (doc + chunk) in RAG Status Pane

## Problem
Menubar RAG pane showed `{collection}: 0/0 · {elapsed}` during a large index run (trading-reference, first doc Hamilton1994 = 1772 chunks). Root cause: the lock's `progress` dict was written ONLY per-document, after each doc completed — `update_progress(done=i+1, total=len(to_index))` in `_index_collection` (rag-cli `index_cmd.py`) and `_sync_one_collection` (rag-cli `sync.py`). During the first long document, no per-doc update had fired → `progress = {}` → menubar `progress.get('done',0)/('total',0)` = 0/0. `index_json_workflow` (rag-cli `indexer.py`) knew chunk progress but only printed it to stdout — never to the lock.

`rag-cli progress <collection>` showed the true 192/1772 because it queries Postgres (`query_progress` in rag-cli `db.py`: `COUNT(*)` stored chunks vs `MAX(total_chunks)` per document) — a different source the menubar does not read.

## Alternatives
| Option | Mechanism | Verdict |
|---|---|---|
| A — menubar reads DB | menubar queries the same Postgres signal as `rag-cli progress` (collection from lock, done/total from DB) | REJECTED — adds a DB query / `rag-cli` subprocess into the 1.5s GUI tick; violates the deliberate menubar design (pure JSON-file read, no IPC/subprocess — see `planning.md` § Lock file vs pgrep) |
| B — rag-cli logs both levels into the lock | `index_json_workflow` writes chunk-level progress into the lock per batch; menubar stays a pure lock reader | CHOSEN — single source of truth (the lock), menubar role unchanged, `rag-cli status` also benefits |

User ask: "rag-cli loggt vollumfänglich, die Menubar macht nur den Ablese-Teil." → Option B.

## Why two levels
Both granularities are needed because the queue mix varies:
- trading-reference: few huge docs → CHUNK level carries the live signal (e.g. 30/1772).
- reddit / gh-cli (one MD per post/issue/discussion): many small docs → DOCUMENT level carries it (e.g. 3/5).
Showing both covers the whole spectrum.

## Schema (chosen)
`progress` dict gains two OPTIONAL fields:
```
done, total, current_document, collection   ← always (document level)
chunks_done, chunks_total                   ← optional (current doc's chunk level)
```
Optional = backward compatible: omitted when not inside a batch loop; old readers use `.get()` and fall back. The currently-running index (old code in memory) keeps writing old-format locks.

## Threading
- `lock.update_progress(..., chunks_done=None, chunks_total=None)` — chunk fields written only when provided.
- `indexer.index_json_workflow(json_path, doc_done=None, docs_total=None)` — pre-loop write (`chunks_done=0`) signals doc start; per-batch write updates `chunks_done`.
- `index_cmd._index_collection` + `sync._sync_one_collection` pass `doc_done=i, docs_total=len(to_index)`.
- Post-doc `update_progress(done=i+1, ...)` (no chunk fields) preserved as the "doc finished" marker — drops chunk fields by omission.
- `done` consistently = docs COMPLETED. Menubar shows `done+1` when chunk fields present (= current doc number) → label stays stable `3/5` through doc 3's processing.

## Display (menubar `_read_rag_status`)
Three branches:
- chunks present → `{collection} · {done+1}/{total} docs · {chunks_done}/{chunks_total} chunks · {elapsed}`
- elif total>0 (between docs / old-format lock) → `{collection} · {done}/{total} docs · {elapsed}`
- else (empty progress) → `{collection} · {elapsed}`

rag-cli `status.format_status` + `lock._raise_busy` relabeled "chunks" → "N/M docs · X/Y chunks" (the old label wrongly said "chunks" for what were document counts).

## Verification status — LIVE-VERIFIED 2026-06-24

Live end-to-end verified during the trading-reference index run (doc 7/8 Tsay2010, 998 chunks):
- Writer (rag-cli): the live `~/.rag-locks/rag.lock` carries both levels and advances — `chunks_done` climbs in steps of 32 (the embedding batch size), `chunks_total` per current doc, `done`/`total` per doc.
- Reader (menubar): the rebuilt bundle renders branch 1 `{collection} · {done+1}/{total} docs · {chunks_done}/{chunks_total} chunks · {elapsed}`, re-read each 1.5s tick.

**Root-cause of the "feature invisible" symptom (the trap):** the menubar runs as a FROZEN py2app bundle (`~/Applications/monitor-cc-menubar.app`, `semi_standalone=False`) — code changes do NOT take effect on restart; the bundle must be REBUILT. The running bundle was from 2026-06-13, the feature merged 2026-06-24 → the merged-and-correct reader was never in the running bundle. The original "must be RESTARTED" note was the trap: a restart re-launches the same frozen bundle. Fix was `./venv/bin/python setup_py2app.py py2app` (rebuild + reinstall to ~/Applications + relaunch launchd). See `src/menubar/DOCS.md` Gotchas (frozen-bundle).

Mock-verification (pre-deploy, retained): rag-cli `update_progress` writes/omits chunk fields (5+2 asserts); menubar all three branches render + dead-PID → no-indexing (4 asserts + safety).

**Chunk-cadence finding (decided: leave as-is):** `chunks_done` advances per embedding batch (batch size 32, ~50s/batch on the 8B embedder), so the chunk number jumps +32 ~once/min while elapsed ticks every 1.5s — looks static over short watching windows. Not a bug: a 32-chunk batch is one atomic embedding call, no sub-batch progress exists. Smoother counting would require smaller batches → embedding-throughput cost. User: "good enough", leave as-is.

## IST
- Menubar: `decisions/menubar_rag_tab.md`
- rag-cli lock/status: rag-cli `decisions/infra02_lock_and_status.md`
