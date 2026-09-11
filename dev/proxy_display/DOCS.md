# dev/proxy_display/

## Role
Byte-identity regression harness for `src/proxy_display/` render-cluster changes — verifies a
refactor of `format.py`/`render_turn.py`/`render_sections*.py`/`render_messages.py`/
`forwarded_parser.py` changes zero observable output. Touch when adding a new render-cluster
regression check; not for `pane.py`/`worker_proxy_pane.py` event-loop changes (see
`dev/pane_search/`, `dev/click_ui/`, `dev/pane_error_log/` for those).

## Flow
Reconstructs entries from a real forwarded dual-log, attaches stripped/injected/original overlays
the way `pane.py` does, grows `expand_states` until every discoverable key is expanded, then hashes
`format_proxy_block`'s output at several pane widths plus `render_system_blocks`/`render_tools`/
`render_messages` called directly per entry per width. Prints one `HASH:` line.

## Modules

### render_byte_identity.py (143 LOC)

**Purpose:** Byte-identity harness for the proxy_display render cluster — see Flow above.
**Reads:** forwarded/stripped/injected/original dual-log JSONL quartets under the resolved log
directory (default: the newest quartet under src/logs/dual_log in the main checkout — gitignored
runtime data, absent from a fresh worktree).
**Writes:** nothing — stdout only (`source`, `entries`, `expand_states keys`, `HASH` lines).
**Called by:** none — manual regression harness, run before and after a render-cluster refactor.
**Calls out:** `src.proxy_display.forwarded_parser` (`_parse_forwarded_log`, `_infer_model_family`),
`src.proxy_display.dual_log_accumulator` (`accumulate_dual_log`, `accumulate_original_tools`),
`src.proxy_display.proxy_pane_shared` (`_attach_overlay_references`), `src.proxy_display.format`
(`format_proxy_block`, `_is_standalone_entry`), `src.proxy_display.render_turn`
(`_resolve_prev_same_family`), `src.proxy_display.render_sections` (`render_tools`),
`src.proxy_display.render_sections_system` (`render_system_blocks`),
`src.proxy_display.render_messages` (`render_messages`) — all imported inside functions, per the
`block_dev_imports_src` hook's indentation-based exemption.

---

## Gotchas
- The default log source (newest quartet under src/logs/dual_log) is live and growing — a concurrent
  session's own proxy log can become "newest" between two runs. Set `RENDER_BYTE_IDENTITY_LOG_DIR` to
  a fixed directory holding a frozen copy of one quartet to pin a before/after comparison.
