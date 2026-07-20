# lock_kind — Indexing Detection via kind Field

## Problem

After rag-cli consolidation (workflow.py removed), the global RAG lock (`~/.rag-locks/rag.lock`) is acquired by EVERY rag-cli command except `status` and `server`. The menubar's `_read_rag_status()` gate used `command.startswith('index')` to identify indexing runs. This worked when only `index-dir`, `index-file`, `index-json` existed (all start with `"index"`). After consolidation:

- New command names: `index` (was `index-dir`) → still passes `startswith('index')` ✅
- `update_docs` → does NOT start with `"index"` → menubar showed "no indexing currently running" even while update_docs held the lock ❌
- `search_hybrid`, `list_*`, `delete` → also hold the lock → could in theory show false-positive indexing status ❌

## Decision: kind field in lock JSON

Rather than extend the `startswith` hack to include `update_docs`, we add a semantic `kind` field to the lock JSON. The classification "is this indexing?" lives in `lock.py` (lock-protocol concern), not in `cli.py` (caller concern).

**Mechanism:**
- `lock.py` INFRASTRUCTURE: `_INDEXING_COMMANDS = frozenset({"index", "update_docs"})`
- `acquire.__init__` data dict: `"kind": "index" if command in _INDEXING_COMMANDS else "query"`
- No signature change to `acquire(command, args)` — determination is internal
- Menubar gate: read `kind`; if absent (old lock), fall back to `command.startswith('index')`

**Indexing-command set:** `{"index", "update_docs"}`. `delete` is destructive but not embedding — stays `"query"`. Future indexing commands (if any) only require updating `_INDEXING_COMMANDS`.

## Input-model: Option A (no --input re-add)

Before consolidation, gh-cli and searxng called `workflow.py index-dir --input <dir>` with an arbitrary input directory. The new `rag-cli index` reads only from `data/documents/<collection>/`.

gh-cli already wrote MDs to `RAG_ROOT/data/documents/<collection>/` (verified: `index_issues.py:18`, `index_discussions.py:16`, `index_releases.py:28`). The input dir was the same as the collection dir — no `--input` needed. Fix was purely caller-side: replace `workflow.py index-dir --input data/documents/X` with `rag-cli index --collection X`.

searxng SKILL.md set `OUTPUT_DIR` to an arbitrary path, then called `workflow.py index-dir --input "$OUTPUT_DIR"`. Fix: set `OUTPUT_DIR = $RAG_ROOT/data/documents/$COLLECTION` so cleaned MDs land in the collection dir before calling `rag-cli index --collection "$COLLECTION"`.

Option B (re-add `--input` to rag-cli) was rejected: adds dead-weight complexity; consumers already use the correct dir tree.

## Parse compat

`parse_chunk_count` regex in gh-cli (`r"Done: \d+ files indexed \((\d+) chunks\)"`) matches the new `rag-cli index` collection-wide output (`cli.py:321-323`): `"Done: N files indexed (X chunks), Y skipped, Z adopted"` — unchanged.

## Backward compat

Locks written before the `kind` field (pre-consolidation format: `command="index-dir"` etc.) handled by the `command.startswith('index')` fallback in `_read_rag_status`. Both code paths coexist; the `kind` path takes precedence.
