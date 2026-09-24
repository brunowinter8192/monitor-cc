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
Converted suites run as parallel strands through `dev/refactoring/strand_runner.py`: `python <file>` starts one subprocess per strand (`--strand <name>`), each strand aborts at its first failing `check`, sibling strands still finish, and the exit code is 1 if any strand aborted. The strand names are the module constant `_STRANDS`.

## Modules

### test_pd10_lazy_messages.py (      95 LOC)

**Purpose:** Four parallel strands proving the PD10 fix: no TypeError for an expanded entry without messages, lazy load raises on an unmatched flow, a failed toggle keeps the state, reparse clears expand states.
**Reads:** Synthetic entries and temp files only; `MCFIX_TREE` selects the source tree (default: this repo) so the same file also runs against an extracted older tree.
**Writes:** stdout only (`PASS`/`FAIL` per strand).
**Called by:** none — manual test.
**Calls out:** `src.proxy_display` (`forwarded_parser`, `proxy_pane_shared`, `format`, `pane`, `worker_proxy_pane`).

---

### test_session_marker_states.py (     102 LOC)

**Purpose:** Four parallel strands for the session-marker states: absent marker is `None`, worker error scan scope and skip logging, proxy pane without session start, warnings refresh without marker.
**Reads:** Temp directories via `MONITOR_CC_ROOT`; `MCFIX_TREE` selects the source tree.
**Writes:** stdout only (`PASS`/`FAIL` per strand).
**Called by:** none — manual test.
**Calls out:** `src.proxy_display` (`parser`, `side_logs`, `pane`), `src.panes` (`warnings_pane`, `warnings_render`), `src.core.monitor`.

---

### test_forwarded_tripwires.py (      86 LOC)

**Purpose:** Four parallel strands for the forwarded-log tripwires: missing marker noted once, short or empty marker raises, marker log id used, delta request without earlier state raises.
**Reads:** Temp directories only; `MCFIX_TREE` selects the source tree.
**Writes:** stdout only (`PASS`/`FAIL` per strand).
**Called by:** none — manual test.
**Calls out:** `src.proxy_display.forwarded_parser`.

---

### render_byte_identity.py (116 LOC)

**Purpose:** Byte-identity harness for the proxy_display render cluster — see Flow above.
**Reads:** forwarded/stripped/injected/original dual-log JSONL quartets under the resolved log
directory (default: the newest quartet under src/logs/dual_log in the main checkout, overridable
via `RENDER_BYTE_IDENTITY_LOG_DIR` to pin a frozen quartet for a stable before/after comparison).
**Writes:** nothing — stdout only (`source`, `entries`, `expand_states keys`, `HASH` lines).
**Kind:** verification aid, not a test: it prints a hash and asserts nothing, a human compares two runs taken before and after a change. Default input is the newest live `_forwarded.jsonl` under the live dual-log directory; pin it with `RENDER_BYTE_IDENTITY_LOG_DIR` pointing at a copied corpus.
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

### test_standalone_sidecar.py (93 LOC)

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

### test_req_prefix_turn_headers.py (358 LOC)

**Purpose:** Regression test for the `REQ #n` row prefix, `Turn` header rows, right-aligned times (one column, truncation, same time in both panes), the HTTP status marker and `status:` line, continue-safe forwarded parsing and REQ-number/turn-header parity with `format_cache_tracker`, on synthetic forwarded lines and turns.
**Reads:** nothing external — a temp forwarded JSONL and in-process turns.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual regression test.
**Calls out:** `src.proxy_display.forwarded_parser`, `src.proxy_display.format`, `src.format.token_format`, `src.utils` — imported inside functions.

---

### verify_req_numbering.py (160 LOC)

**Purpose:** Side-by-side check of one turn: proxy pane rows versus token pane rows for a real dual-log session, plus a pairwise (number, turn, time) equality verdict, rendered at width 62.
**Reads:** `_forwarded`/`_response` under the main checkout's `src/logs/dual_log`, the matching transcript under `~/.claude/projects` (found by request_id).
**Writes:** `dev/proxy_display/md/verify_req_numbering_<stem>_turn<N>.md` and stdout.
**Kind:** verification on live data, not a test: it asserts nothing beyond printing a pairwise verdict, and it reads the live dual-log directory and `~/.claude/projects` from hardcoded paths with no env seam. The result changes as the logs grow or rotate; the stem and turn are the arguments.
**Called by:** none — run manually: `python dev/proxy_display/verify_req_numbering.py <stem> <turn>`.
**Calls out:** `src.proxy_display.*`, `src.dual_log_cli.usage` (`_find_transcript`), `src.panes.cache_turns`, `src.format.token_format`.

---

## State
Neither module owns persistent state — `render_byte_identity.py` reads a dual-log quartet fresh
per run and writes nothing; `test_standalone_sidecar.py` builds and discards its synthetic entries
within one function call.
