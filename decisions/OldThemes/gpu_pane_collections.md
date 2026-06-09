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

---

## Preset-Discovery Masking Fallback — Removal (route-consol task)

### Why the fallback was (c) MASKING

`_discover_preset_names()` returned `['embedding', 'reranker', 'splade']` on any rag-cli
failure. At the time of removal the real presets were:

```
['embedding-8b', 'embedding-0.6b', 'reranker-0.6b', 'reranker-8b', 'generator-4b', 'splade']
```

Only `splade` overlapped. A rag-cli failure would silently surface 3 stale names (2 no longer
exist as presets) instead of the 6 real ones — hiding the failure AND showing fabricated data.
This is the definition of category (c) MASKING: the fallback produces something DIFFERENT from
what the primary route would deliver, concealing a real gap.

### Removal principle

The binding user decision: a monitor must NOT carry a fallback that masks a rag-cli normal-
operation failure. On failure, `_discover_preset_names` returns `[]` and the GPU Servers block
renders with no preset rows — empty, no fabricated names. The user notices a rag-cli failure
directly when running a query; the monitor does not need to proxy-display it.

### Mirror to `_fetch_collections`

`_fetch_collections()` has returned `[]` on failure since its introduction (see "30s cadence"
section above). Its block shows `(none indexed)` when empty — no fabricated content, no error
marker. The preset block now mirrors this identical pattern.

### Consumer empty-safety (verified Phase A)

| Consumer | Code | Empty-safe? |
|---|---|---|
| `status.py:79` | `if name in PRESET_NAMES` | Yes — membership test on `[]`, never True |
| `status.py:87` | `[... for n in PRESET_NAMES]` | Yes — comprehension over `[]` → `[]` |
| `pane.py:55` | `if idx < len(PRESET_NAMES)` | Yes — `0 > 1` False, gate blocks line 56 |
| `pane.py:56` | `name = PRESET_NAMES[idx]` | Yes — only reached through gate |
| `pane.py:117` | `name = PRESET_NAMES[idx]` in `_toggle_server` | Yes — callable only through gate |

### Footer removal (same task)

The legend line `[1-N] toggle presets  click [start]/[stop]/[restart]  ●=healthy ...` was
removed from `_render_pane` alongside the fallback fix. The hint was cosmetically wrong with
0 presets (showed `[1] toggle presets` when pressing 1 did nothing). With a static preset
list the hint had been informative; with dynamic discovery the count is not known statically.
The anomalies block (`⚠ N anomalies (see logs/gpu_pane.log)`) is an operational alert —
untouched.

### Files changed

- `src/gpu_pane/status.py` — `_discover_preset_names` returns `[]` on failure (220→219 LOC)
- `src/gpu_pane/pane.py` — footer legend block removed (327→318 LOC)
- `decisions/gpu_pane_collections.md` — created (IST/Evidenz/SOLL)
- `src/gpu_pane/DOCS.md` — fallback mentions removed; Gotcha line-85 rewritten; footer hint removed
