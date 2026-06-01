# menubar_rag_tab

## Status Quo (IST)

RAG tab is the second panel in the four-tab ring `Sessions · RAG · Beads · Queue`. Implemented as `RagController` in `src/menubar/rag_controller.py`, instantiated as `app.rag` in `CCMenuBarApp.__init__`.

**Lock file:** `~/.rag-locks/rag.lock` — written by the RAG indexer while running, deleted on completion.

**Status line logic (`_read_rag_status()`):**
- File absent or unreadable/invalid JSON → `no indexing currently running`
- File present: read `pid`, call `os.kill(pid, 0)`:
  - `ESRCH` (ProcessLookupError) → dead process → `no indexing currently running`
  - `EPERM` (PermissionError) → process exists → treat as alive
- `command` does not start with `index` → `no indexing currently running`
- Otherwise format: `{collection}: {done}/{total} · {elapsed}`
  - `collection` = `args.collection`, fallback `Path(args.input).name`, fallback `'unknown'`
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

**Live lock file schema** (confirmed from running indexer during development, pid 54231):
```json
{
  "pid": 54231,
  "command": "index-dir",
  "args": {"collection": "gh_reference", "input": "/abs/path/..."},
  "started_at": "2026-06-01T19:17:53.347821+00:00",
  "status": "running",
  "progress": {"done": 70, "total": 307, "current_document": "..."},
  "heartbeat": "2026-06-01T20:07:23.720890+00:00"
}
```

**Lock file scope:** `rag.lock` is acquired only by the three indexing commands (`index-dir`, `index-file`, `index-json`). Server and search commands use a separate lock file (`server_lock`). The `command.startswith('index')` gate is belt-and-suspenders — in practice any `rag.lock` will have an `index-*` command.

**PID staleness:** The RAG repo's own staleness check uses `os.kill(pid, 0)` with `ProcessLookupError → dead`. Mirrored exactly here.

## Recommendation (SOLL)

Keep — feature as built, no eval pending.

## Offene Fragen

None.

## Quellen

RAG lock file schema: observed from live indexing run (`gh_reference` collection, 307 documents).
