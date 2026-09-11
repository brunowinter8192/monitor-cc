# dev/workers/

## Role
Development scripts for `src/workers/` changes — regression harnesses that verify a refactor of
`worker_pane.py`/`worker_format.py`/sibling modules changes zero observable output. Touch when adding
a new workers-pane regression check; not for `src/proxy_display/` changes (see `dev/proxy_display/`,
`dev/pane_search/` for those).

## Flow
Builds a synthetic worker list plus one worker's turns loaded from a real worker JSONL, renders
across a matrix of argument combinations at two pane widths, and hashes every rendered output triple.

## Modules

### format_byte_identity.py (144 LOC)

**Purpose:** Byte-identity harness for `format_workers_block` — builds a synthetic 3-worker list
(varied status/tokens/context_pct/purpose), expands one with turns loaded from a real worker JSONL
(bounded to a fixed-size prefix, falling back to synthetic turns if none exists), renders across a
matrix of frozen/selected/copy-feedback/search-state argument combinations at two pane widths, and
hashes every rendered `(all_lines, line_keys, regions_out)` triple.
**Reads:** one worker JSONL file under the user's Claude Code projects directory, or the path in
`WORKERS_BYTE_IDENTITY_JSONL` when set.
**Writes:** nothing — stdout only (one `HASH:` line).
**Called by:** none — manual regression harness, run before and after a `src/workers/` refactor.
**Calls out:** `src.jsonl` (`read_new_lines`, `parse_jsonl_lines`, `extract_cache_turns`),
`src.workers.worker_format` (`format_workers_block`).

---

## Gotchas
- The default JSONL source (newest file under the user's Claude Code projects directory) can be a
  live, actively-growing transcript, including this very agent's own session file. The harness
  mitigates this by bounding to a fixed-size prefix, but for a fully pinned before/after comparison
  across a longer work session, set `WORKERS_BYTE_IDENTITY_JSONL` to a one-time snapshot.
