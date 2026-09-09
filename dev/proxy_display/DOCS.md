# dev/proxy_display/

## Role

Development scripts for `src/proxy_display/` render-cluster changes — regression harnesses that
verify a refactor of `format.py`/`render_turn.py`/`render_sections*.py`/`render_messages.py`/
`forwarded_parser.py` changes zero observable output. Touch this directory when adding a new
render-cluster regression check; do not touch for `pane.py`/`worker_proxy_pane.py` event-loop
changes (see `dev/pane_search/`, `dev/click_ui/`, `dev/pane_error_log/` for those).

## Modules

### render_byte_identity.py

**Purpose:** Byte-identity regression harness for the proxy_display render cluster. Reconstructs
entries from a real forwarded dual-log (default: newest `*_forwarded.jsonl` under
`src/logs/dual_log/` in the MAIN checkout — reads only, never writes/commits log content),
attaches the stripped/injected/original overlays the same way `pane.py` does, then grows
`expand_states` by repeatedly rendering and flipping every newly-discovered key to expanded
(via `item_positions_out`, which — unlike `line_map` — captures every rendered key regardless of
viewport) until the key set stops growing. Hashes `format_proxy_block`'s full output at several
pane widths, plus `render_system_blocks`/`render_tools`/`render_messages` called directly per
entry per width (wider coverage than `format_proxy_block`'s own viewport can show even with a
huge `pane_height`, since those three are exercised identically regardless of scroll state).
Prints one `HASH: <hex>` line — run before and after a render-cluster change, the hash must match.

**`RENDER_BYTE_IDENTITY_LOG_DIR` env var** overrides the source directory (default: the live MAIN
checkout's `src/logs/dual_log/`). Needed because the default directory can itself grow between a
"before" and "after" run — e.g. this very worktree's own proxy session keeps appending to its
newest forwarded log while work is in progress. For a reproducible before/after comparison, copy
the newest `*_forwarded.jsonl` + its `_stripped`/`_injected`/`_original` siblings to a fixed `/tmp`
directory once, then point both runs at that directory via the env var. Never commit such a copy —
only the script and its hash output belong in this repo.

**Reads:** `*_forwarded.jsonl`/`*_stripped.jsonl`/`*_injected.jsonl`/`*_original.jsonl` under the
resolved log directory.
**Writes:** Nothing — stdout only (`source`, `entries`, `expand_states keys`, `HASH` lines).
**Called by:** Run manually from project root; imports are all local (inside functions), per the
`block_dev_imports_src` hook's indentation-based exemption.
**Calls out:** `src.proxy_display.forwarded_parser` (`_parse_forwarded_log`, `_infer_model_family`),
`src.proxy_display.dual_log_accumulator` (`accumulate_dual_log`, `accumulate_original_tools`),
`src.proxy_display.proxy_pane_shared` (`_attach_overlay_references`), `src.proxy_display.format`
(`format_proxy_block`, `_is_standalone_entry`), `src.proxy_display.render_turn`
(`_resolve_prev_same_family`), `src.proxy_display.render_sections` (`render_tools`),
`src.proxy_display.render_sections_system` (`render_system_blocks` — update the import path if
either function moves module again), `src.proxy_display.render_messages` (`render_messages`)

## Gotchas

**The default log source is live and growing.** Any script under this directory that reads
`src/logs/dual_log/` directly (rather than a frozen copy) can observe different data between two
runs in the same session, if that session's own worker/opus proxy log happens to be the newest
file. Use `RENDER_BYTE_IDENTITY_LOG_DIR` (or the equivalent pattern in a new script) to pin the
source when doing a before/after comparison.
