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
- Otherwise format: `{collection}: {done}/{total} · {elapsed}`
  - `collection` = `args.collection`, fallback `progress.collection`, fallback `Path(args.input).name`, fallback `'unknown'`
  - `progress.collection` is set per-collection during `update_docs` runs → shows real name (e.g. `monitor-cc-meta: 3/8 · 5s`) instead of old `unknown: 0/0 · elapsed`
  - `done`/`total` from `progress` dict (defaults 0/0 when absent)
  - `elapsed` = `now(utc) - started_at`, formatted `{M}m{SS}s` when minutes > 0, else `{S}s`

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

**Live lock file schema** (post-consolidation, rag-cli `index` command):
```json
{
  "pid": 12345,
  "command": "index",
  "kind": "index",
  "args": {"collection": "gh_reference"},
  "started_at": "2026-06-10T12:00:00.000000+00:00",
  "status": "running",
  "progress": {"done": 5, "total": 20, "current_document": "foo.md"},
  "heartbeat": "2026-06-10T12:00:30.000000+00:00"
}
```

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
