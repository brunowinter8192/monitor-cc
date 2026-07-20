# menubar_rag_tab

## Status Quo (IST)

RAG tab is the second panel in the four-tab ring `Sessions · RAG · Beads · Queue`. Implemented as `RagController` in `src/menubar/rag_controller.py`, instantiated as `app.rag` in `CCMenuBarApp.__init__`.

**Lock file:** `~/.rag-locks/rag.lock` — written by the RAG indexer while running, deleted on completion.

**Status line logic (`_read_rag_status()`):**
- File absent or unreadable/invalid JSON → `no indexing currently running`
- File present: read `pid`, call `os.kill(pid, 0)`:
  - `ESRCH` (ProcessLookupError) → dead process → `no indexing currently running`
  - `EPERM` (PermissionError) → process exists → treat as alive
- Gate on `kind` field (present in locks written by rag-cli post-consolidation):
  - `kind` present: `kind != 'index'` → `no indexing currently running`
  - `kind` absent (backward compat — old lock format): `command.startswith('index')` fallback
- Otherwise format — three branches based on lock `progress` dict contents:
  1. **`chunks_done` + `chunks_total` present** (mid-document embedding): `{collection} · {done+1}/{total} docs · {chunks_done}/{chunks_total} chunks · {elapsed}` — `done+1` gives the 1-based current-doc number because `done` = completed-doc count when chunk updates fire.
  2. **`total > 0`, no chunk fields** (between docs, or old-format lock): `{collection} · {done}/{total} docs · {elapsed}`.
  3. **`total == 0` or empty `progress` dict** (initial lock state): `{collection} · {elapsed}`.
  - `collection` = `args.collection`, fallback `progress.collection`, fallback `Path(args.input).name`, fallback `'unknown'`
  - `elapsed` = `now(utc) - started_at`, formatted `{M}m{SS}s` when minutes > 0, else `{S}s`
  - Separator unified to `·` throughout (was `:` before done/total)

**Polling:** `RagController.tick(sessions)` called every `POLL_INTERVAL = 1.5s` by `CCMenuBarApp._tick`. Updates the NSTextField label in-place via `setAttributedStringValue_` (no full rebuild per tick — cheap).

**Ring wiring** (Cmd+→ / Cmd+←):
- Sessions → RAG → Beads → Queue → Sessions (forward)
- Sessions ← RAG ← Beads ← Queue ← Sessions (backward)

**Header strings (4 panels):**
- main: `[Sessions] · RAG · Beads · Queue     Auto-Jump: {state}`
- rag: `Sessions · [RAG] · Beads · Queue     Auto-Jump: {state}`
- tracker: `Sessions · RAG · [Beads] · Queue     Auto-Jump: {state}`
- queue: `Sessions · RAG · Beads · [Queue]     Auto-Jump: {state}`

## Evidenz

**Live lock file schema** (post-two-level-progress, rag-cli `index` command):
```json
{
  "pid": 12345,
  "command": "index",
  "kind": "index",
  "args": {"collection": "trading-reference"},
  "started_at": "2026-06-10T12:00:00.000000+00:00",
  "status": "running",
  "progress": {
    "done": 2,
    "total": 5,
    "current_document": "large_doc.md",
    "collection": "trading-reference",
    "chunks_done": 30,
    "chunks_total": 1772
  },
  "heartbeat": "2026-06-10T12:00:30.000000+00:00"
}
```

`chunks_done`/`chunks_total` appear only during a document's embedding batch loop. Between documents (after the per-doc END marker fires) and for old-format locks, these fields are absent — `_read_rag_status` falls back to branch 2 (doc-level only).

**Lock file scope (post-consolidation):** `rag.lock` is acquired by ALL rag-cli commands except `status` and `server` (cli.py lines 131-148). The `kind` field distinguishes indexing ops from query/delete ops. `kind="index"` set for `{"index", "update_docs"}`; `kind="query"` for all others (`_INDEXING_COMMANDS` frozenset in `lock.py`).

**`update_docs` in the gate:** `update_docs` acquires the lock with `command="update_docs"`, `kind="index"`. Without the `kind` gate, the old `command.startswith('index')` check silently excluded it — the menubar showed "no indexing" during `update_docs` runs. The new gate catches it correctly. `update_docs` now writes `progress.collection` (per-collection name as it iterates) into the lock's `progress` dict; the menubar reads this as the label fallback, showing e.g. `monitor-cc-meta: 3/8 · 5s` instead of the old `unknown: 0/0 · elapsed`.

**Backward compat:** locks written before the `kind` field was added (pre-consolidation) had `command="index-dir"`, `"index-file"`, or `"index-json"`. The `command.startswith('index')` fallback handles these correctly.

**PID staleness:** The RAG repo's own staleness check uses `os.kill(pid, 0)` with `ProcessLookupError → dead`. Mirrored exactly here.

## Recommendation (SOLL)

Keep — feature as corrected, no further eval pending.

## Offene Fragen

None.

## Quellen

RAG lock file schema: observed from live indexing run (`gh_reference` collection, 307 documents).
