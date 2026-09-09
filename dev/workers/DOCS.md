# dev/workers/

## Role

Development scripts for `src/workers/` changes — regression harnesses that verify a refactor of
`worker_pane.py`/`worker_format.py`/its sibling modules changes zero observable output. Touch
this directory when adding a new workers-pane regression check; do not touch for
`src/proxy_display/` changes (see `dev/proxy_display/`, `dev/pane_search/` for those).

## Modules

### format_byte_identity.py

**Purpose:** Byte-identity regression harness for `src.workers.worker_format.format_workers_block`.
Builds a synthetic 3-worker list (varied status/tokens/context_pct/purpose), expands one of them
with turns loaded from a real worker JSONL under `~/.claude/projects/` when one exists (bounded to
its first 200 lines and the first 10 extracted turns — a stable prefix even if the source file
keeps growing; falls back to synthetic turns otherwise), renders across a matrix of
`(frozen, selected_name, copy_feedback, search_match_set/search_current_key/search_query)`
argument combinations at two pane widths (`os.get_terminal_size()` monkeypatched —
`format_workers_block` detects width internally, no width parameter), and hashes every rendered
`(all_lines, line_keys, regions_out)` triple.

**`WORKERS_BYTE_IDENTITY_JSONL` env var** overrides the source JSONL path — needed to pin a
before/after comparison to the exact same bytes when the default "newest JSONL under
`~/.claude/projects/`" pick can itself be a different file across two runs, or (rarer, since the
harness already bounds to a fixed-size prefix) a session actively growing during the comparison
window. Same pitfall class as `dev/proxy_display/render_byte_identity.py`'s
`RENDER_BYTE_IDENTITY_LOG_DIR` — see that module's own Gotcha. Snapshot a real JSONL to a fixed
path once, then point both runs at it via the env var for full reproducibility.

**Reads:** One worker JSONL file under `~/.claude/projects/*/` (or `$WORKERS_BYTE_IDENTITY_JSONL`).
**Writes:** Nothing — stdout only (one `HASH: <hex>` line).
**Called by:** Run manually from project root; imports are all local (inside functions), per the
`block_dev_imports_src` hook's indentation-based exemption.
**Calls out:** `src.jsonl` (`read_new_lines`, `parse_jsonl_lines`, `extract_cache_turns`),
`src.workers.worker_format` (`format_workers_block`)

## Gotchas

**The default JSONL source can be a live, actively-growing transcript.** Any script under this
directory that reads `~/.claude/projects/` directly (rather than a frozen copy) risks picking THIS
very agent's own session file as "newest". `format_byte_identity.py` mitigates this by bounding to
a fixed-size prefix of whatever file it reads (append-only growth past that point never changes
the read content) — for a fully pinned before/after comparison across a longer work session, still
prefer `WORKERS_BYTE_IDENTITY_JSONL` pointed at a one-time snapshot.
