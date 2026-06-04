# gpu_pane RAG Collections Block

## Feature

Added a RAG Collections block to the GPU pane (`src/gpu_pane/`). The pane previously showed only GPU servers + today's errors. It now shows a third block — RAG Collections — listing every indexed collection with its chunk count. One row per collection, read-only, no buttons.

## lock-exempt Rationale

`list_collections_workflow` (rag-cli `src/rag/retriever.py`) is a pure Postgres `SELECT collection, COUNT(*) FROM documents GROUP BY collection` — no embedding server, no GPU, no file I/O. Before this change, `rag-cli list_collections` went through the global advisory flock lock (`cli.py:140`, `src/rag/lock.py:acquire`) alongside every other command except `status` and `server`. Calling it during an indexing run returned `LockBusyError` (exit 1), making the gpu_pane unable to poll collection counts while indexing was active — exactly the moment when counts change.

Fix: `list_collections` gets an early-return in `cli.py` before the lock acquisition block (mirroring the `status` / `server` pattern). The lock is advisory between rag-cli processes; Postgres MVCC handles concurrent reads against the INSERT writes made by `index`/`update_docs`. There is no correctness requirement for the advisory flock to cover a pure read.

`search_hybrid` correctly stays locked: it calls the embedding server (GPU, network), which the flock helps serialize under resource pressure.

## `--json` flag

`rag-cli list_collections` output was human-readable text only (`format_collections`). Machine consumers (gpu_pane subprocess) need `[{"collection": str, "chunks": int}]`. Added `--json` / `dest="output_json"` to the argparser; `_dispatch` branches on it to output `json.dumps(results)`. `results` from `list_collections_workflow` is already `list[dict]` — one line change.

## 30s cadence

Collection counts change only when `index`, `update_docs`, or `delete` completes — operations that take at minimum seconds, usually minutes. Polling at the 2s GPU server tick rate would make 15 subprocess calls per minute for data that's static almost all the time.

Decision: `COLLECTIONS_POLL_INTERVAL = 30.0` s, independent of `GPU_POLL_INTERVAL = 2.0` s. Separate `last_collections_refresh` timestamp in `run_gpu_loop`. Also fires on force-refresh ('r' key) so user can get an immediate update after manually running an index. `_fetch_collections()` in `status.py` follows the `_discover_preset_names` pattern: `subprocess.run` with `timeout=5`, returns `[]` on any failure (Postgres down, rag-cli missing, JSON parse error).

## Verified

Smoke: `acquire("update_docs", {})` held while `rag-cli list_collections --json` ran → exit 0, valid JSON, no LockBusyError. 17 real collections returned. `py_compile` clean on both changed files.
