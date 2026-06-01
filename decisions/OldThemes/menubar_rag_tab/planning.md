# menubar_rag_tab — Planning Narrative

## Design Decisions

### Lock file vs pgrep for status detection

Alternatives considered:
- **pgrep / process scanning:** find a running `rag-cli index-*` process, parse its args for collection name. Rejected — no reliable way to get progress (done/total) from process args alone; would require scraping stdout or using psutil; fragile if the command path changes.
- **`~/.rag-locks/rag.lock` (chosen):** already written by the RAG indexer; contains exactly the fields needed (collection, progress, started_at); the RAG repo defines its own staleness check (`os.kill(pid, 0)` + ESRCH = dead) which we mirror exactly. No extra IPC, no subprocess, just a JSON file read.

The lock file is the canonical source of truth for the indexer's own state — using it here keeps the two systems consistent.

### State placement: RagController (Queue pattern) vs app attrs (Bead pattern)

Two existing models:
- **Bead (Step 2/6):** panel NSPanel/NSStackView/toggle_btn refs live on `app` (`app._tracker_panel` etc.), open flag on `app._tracker_open`. Controller has the data state only.
- **Queue (Step 3/6):** ALL state including panel refs and open flag lives on the controller (`self._queue_panel`, `self._queue_open`). `app.queue` is the only app-level reference.

RAG uses the **Queue pattern**. Rationale: Bead's split-state is a refactor artifact (the Step 2 migration was deliberately incomplete — moving panel refs to the controller was deferred). Queue represents the target shape. RAG is new code with no legacy constraints, so the cleaner pattern applies. Result: `app.rag._rag_panel`, `app.rag._rag_open` — no `app._rag_*` attrs on CCMenuBarApp.

### 4-tab ring integration

Insertion between Sessions and Beads: `Sessions · RAG · Beads · Queue`.

Required changes to existing ring wiring:
- `_open_main_panel`: Cmd+→ changed from `tracker` to `rag` (Sessions previously went directly to Beads)
- `_open_tracker_panel`: Cmd+← changed from `main` to `rag` (Beads previously went back to Sessions; now goes back to RAG)
- Queue panel: both directions unchanged

New `_open_rag_panel` / `_close_rag_panel` follow the exact same pattern as tracker and queue.

### No `_rebuild_inner` re-entry guard for RAG

The Bead and Queue controllers have a `_rebuild_in_progress` guard because their rebuilds are expensive (NSGridView construction, multiple subviews). RAG rebuild is trivial (clear sv → add separator → add one NSTextField). No guard needed. If a concurrent rebuild were possible, the worst case is a double-clear of a one-item stack, not a correctness issue.

### Tick updates label in-place (no full rebuild)

Each tick calls `setAttributedStringValue_` on the cached `_rag_status_label`. This is ~10× cheaper than a full rebuild (no NSView allocation, no sv manipulations). The task prompt explicitly approved this: "the RAG line changes every tick while indexing; your `tick()` should update the label text in place each tick (cheap, just setString)."

### _format_elapsed error handling

`datetime.fromisoformat` raises `ValueError` on malformed timestamps. Wrapped in try/except → '?'. The outer `_read_rag_status` also wraps everything in `try/except Exception → _NO_INDEXING`, so any failure from _format_elapsed (if somehow not caught internally) also degrades gracefully.

### AppKit exception safety

All code in `_read_rag_status` and `tick` is wrapped in `try/except Exception → _NO_INDEXING` or similar. NSPanel callbacks in AppKit must not raise — unhandled Python exceptions in ObjC callbacks cause SIGABRT. The entire lock-read path is exception-safe.

## Rejected alternatives

- **Separate timer:** task prompt states to reuse the existing 1.5s tick — no new timer.
- **Per-document display:** task prompt explicitly says "no current-document name, no chunk breakdown" — single status line only.
- **subprocess to query rag-cli status:** overhead, no benefit over file read.
