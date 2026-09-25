# dev/proxy_display/

## Role
Regression checks for `src/proxy_display/` render-cluster changes: a byte-identity harness proving a refactor changes no observable output, plus unit tests for individual render predicates and states. Not for pane event-loop changes.

## Public Interface
No `__init__.py`. Entry paths: `./venv/bin/python dev/proxy_display/render_byte_identity.py` and the `test_*.py` and `verify_req_numbering.py` scripts.

## Flow
The identity harness rebuilds entries from a real forwarded dual log, attaches overlays as the pane does, expands every discoverable key and hashes the render output at several pane widths. The tests build synthetic entries in-process and assert outcomes, as parallel fail-fast strands (strand runner in `dev/refactoring/`).

## Modules

### test_pd10_lazy_messages.py (105 LOC)

**Purpose:** Four strands proving the lazy-message fix: no error for an expanded entry without messages, unmatched flow raises, failed toggle keeps state, reparse clears expand state.
**Reads:** synthetic entries and temp files; an env var selects the source tree so the file can run against an older tree.
**Writes:** stdout only.
**Called by:** none; manual test.
**Calls out:** `src.proxy_display` (parser, shared pane, format, pane modules).

---

### test_session_marker_states.py (111 LOC)

**Purpose:** Four strands for session-marker states: absent marker is None, worker error scan scope and logging, proxy pane without session start, warnings refresh without marker.
**Reads:** temp directories via the monitor root env var.
**Writes:** stdout only.
**Called by:** none; manual test.
**Calls out:** `src.proxy_display`, `src.panes`, `src.core.monitor`.

---

### test_forwarded_tripwires.py (95 LOC)

**Purpose:** Four strands for forwarded-log tripwires: missing marker noted once, short or empty marker raises, marker log id used, delta request without earlier state raises.
**Reads:** temp directories only.
**Writes:** stdout only.
**Called by:** none; manual test.
**Calls out:** `src.proxy_display.forwarded_parser`.

---

### render_byte_identity.py (116 LOC)

**Purpose:** Verification aid, not a test: hashes the render cluster output over one real dual-log quartet for before/after comparison.
**Reads:** forwarded, stripped, injected and original logs of the newest quartet in the main checkout, or a pinned copy via an env var.
**Writes:** stdout only.
**Called by:** none; run before and after a render-cluster refactor.
**Calls out:** the parser, accumulator, shared pane, format and render modules of `src.proxy_display`, imported inside functions.

---

### test_standalone_sidecar.py (93 LOC)

**Purpose:** Regression guard that the standalone-entry check excludes every observed CC-internal zero-tool sidecar shape from the numbered REQ sequence.
**Reads:** nothing external; synthetic entries.
**Writes:** stdout only.
**Called by:** none; re-run after touching that check or REQ numbering.
**Calls out:** `src.proxy_display.format`, `.render_turn`, `src.utils`.

---

### test_req_prefix_turn_headers.py (358 LOC)

**Purpose:** Regression test for the REQ row prefix, turn header rows, right-aligned times, HTTP status marker, continue-safe parsing and REQ-number parity with the token pane.
**Reads:** nothing external; a temp forwarded JSONL and in-process turns.
**Writes:** stdout only.
**Called by:** none; manual test.
**Calls out:** `src.proxy_display.forwarded_parser`, `.format`, `src.format.token_format`, `src.utils`.

---

### verify_req_numbering.py (162 LOC)

**Purpose:** Side-by-side check of one turn: proxy pane rows versus token pane rows for a real session, with a pairwise equality verdict.
**Reads:** live dual-log files of the main checkout and the matching transcript under the user's Claude projects directory; hardcoded paths.
**Writes:** `md/verify_req_numbering_<stem>_turn<N>.md` and stdout.
**Called by:** none; verification on live data, so results change as logs rotate.
**Calls out:** `src.proxy_display.*`, `src.dual_log_cli.usage`, `src.panes.cache_turns`, `src.format.token_format`.

---

## State
No persistent state. The identity harness reads a quartet fresh per run; the tests build and discard synthetic entries.
