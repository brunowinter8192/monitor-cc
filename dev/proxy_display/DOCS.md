# dev/proxy_display/

## Role
Regression checks for `src/proxy_display/` render-cluster changes — a byte-identity harness
verifying a refactor of `format.py`/`render_turn.py`/`render_sections*.py`/`render_messages.py`/
`forwarded_parser.py` changes zero observable output, plus targeted unit tests for individual
render-cluster predicates. Touch when adding a new render-cluster regression check; not for
`pane.py`/`worker_proxy_pane.py` event-loop changes.

## Public Interface
No `__init__.py` in this directory. Entry paths: `./venv/bin/python
dev/proxy_display/render_byte_identity.py` and `./venv/bin/python
dev/proxy_display/test_standalone_sidecar.py`.

## Flow
`render_byte_identity.py` reconstructs entries from a real forwarded dual-log, attaches
stripped/injected/original overlays the way `pane.py` does, grows `expand_states` until every
discoverable key is expanded, then hashes `format_proxy_block`'s output at several pane widths plus
`render_system_blocks`/`render_tools`/`render_messages` called directly per entry per width, and
prints one `HASH:` line. `test_standalone_sidecar.py` builds synthetic entries in-process instead
and asserts PASS/FAIL against a specific predicate/rendering outcome.

## Modules

### render_byte_identity.py (115 LOC)

**Purpose:** Byte-identity harness for the proxy_display render cluster — see Flow above.
**Reads:** forwarded/stripped/injected/original dual-log JSONL quartets under the resolved log
directory (default: the newest quartet under src/logs/dual_log in the main checkout, overridable
via `RENDER_BYTE_IDENTITY_LOG_DIR` to pin a frozen quartet for a stable before/after comparison).
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

### test_standalone_sidecar.py (107 LOC)

**Purpose:** Regression guard confirming `format._is_standalone_entry`'s existing haiku check
already excludes every CC-internal zero-tool sidecar shape observed in real data from
`render_turn.render_turn_expanded`'s numbered `#N` REQ sequence.
**Reads:** nothing external — synthetic in-process entries.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual regression guard, re-run after touching
`format._is_standalone_entry` or `render_turn.render_turn_expanded`'s numbering logic.
**Calls out:** `src.proxy_display.format` (`_is_standalone_entry`), `src.proxy_display.render_turn`
(`render_turn_expanded`), `src.utils` (`_ANSI_ESCAPE_RE`) — imported inside functions, per the
`block_dev_imports_src` hook's indentation-based exemption.

---

### test_req_prefix_turn_headers.py (213 LOC)

**Purpose:** Regression test for the `REQ #n` row prefix, `Turn` header rows, continue-safe forwarded parsing and REQ-number/turn-header parity with `format_cache_tracker`, on synthetic forwarded lines and turns.
**Reads:** nothing external — a temp forwarded JSONL and in-process turns.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual regression test.
**Calls out:** `src.proxy_display.forwarded_parser`, `src.proxy_display.format`, `src.format.token_format`, `src.utils` — imported inside functions.

---

### verify_req_numbering.py (132 LOC)

**Purpose:** Side-by-side check of one turn: proxy pane rows versus token pane rows for a real dual-log session, plus a pairwise (number, turn) equality verdict.
**Reads:** `_forwarded`/`_response` under the main checkout's `src/logs/dual_log`, the matching transcript under `~/.claude/projects` (found by request_id).
**Writes:** `dev/proxy_display/md/verify_req_numbering_<stem>_turn<N>.md` and stdout.
**Called by:** none — run manually: `python dev/proxy_display/verify_req_numbering.py <stem> <turn>`.
**Calls out:** `src.proxy_display.*`, `src.dual_log_cli.usage` (`_find_transcript`), `src.panes.cache_turns`, `src.format.token_format`.

---

## State
Neither module owns persistent state — `render_byte_identity.py` reads a dual-log quartet fresh
per run and writes nothing; `test_standalone_sidecar.py` builds and discards its synthetic entries
within one function call.
