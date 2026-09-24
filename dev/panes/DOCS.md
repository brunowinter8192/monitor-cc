# dev/panes/

## Role
Regression harnesses for `src/panes/` and its `src/format/` render helpers. Byte-identity harnesses
belong here for a `src/panes/` refactor needing a before/after correctness proof not already
covered elsewhere; plain assert-based correctness tests for a specific new render behavior belong
here too when it lives in `src/format/token_format.py` or a `src/panes/` module.

## Public Interface
No `__init__.py` in this directory. Entry paths: `./venv/bin/python
dev/panes/render_byte_identity.py` and `./venv/bin/python dev/panes/answering_model_line_test.py`.

## Flow
A byte-identity check renders a function's output over a fixed real or synthetic input, hashes the
result, and prints one `HASH:` line to stdout — run once before and once after a refactor and compare
hashes. An assert-based check calls the real render function over synthetic input and asserts the
exact returned lines.

## Modules

### render_byte_identity.py (175 LOC)

**Purpose:** Verification, not a self-checking test: byte-identity harness for the panes-split module boundaries: `build_cache_turns`,
`_format_warnings_pane`, and `format_cache_tracker`, hashed together into one value.
**Reads:** the frozen `fixtures/session_prefix_300.jsonl` (first 300 lines of a session; the hash
only ever used a 300-line prefix) by default, or the path in `PANES_BYTE_IDENTITY_JSONL` when set
(check 1 only; checks 2/3 are fully synthetic). Prints one `HASH:` line and asserts nothing: a human
compares the hash before and after a change.
**Writes:** nothing outside its own temp file (cleaned up on exit) — stdout only (one `HASH:` line).
**Called by:** none — manual regression harness, run before and after a `src/panes/` refactor.
**Calls out:** `src.panes.cache_turns` (`build_cache_turns`), `src.panes.warnings_render`
(`_format_warnings_pane`), `src.format` (`format_cache_tracker`) — imported via a function, not a
module-level `from src.` line, per the `block_dev_imports_src` hook.

---

### answering_model_line_test.py (151 LOC)

**Purpose:** Assert-based correctness test for `format.token_format._render_answering_model_line`
and the updated `_render_rate_limit_lines`/`read_response_log` full-entry shape — covers
equal/mismatch/missing-field/missing-entry cases and the exact rendered ANSI line for each.
**Reads:** no on-disk data — synthetic `call`/`response_rid_map` dicts defined in the module.
**Writes:** stdout verdict per strand, `md/answering_model_line_test.md` (fixed name). The seven `_test_*` functions run as parallel fail-fast strands via `dev/refactoring/strand_runner.py`.
**Called by:** none — manual regression guard, re-run after any change to `_render_answering_model_line`,
`_render_rate_limit_lines`, or `src/proxy_display/side_logs.py::read_response_log`.
**Calls out:** `src.format.token_format`, `src.colors` — imported via a function, not a module-level
`from src.` line, per the `block_dev_imports_src` hook.

---

### test_display_tripwires.py (     112 LOC)

**Purpose:** Five parallel strands: janitor partition and atomic write, janitor failure logged, synthetic-user fallback noted once per turn, `format_timestamp` states, rate-limit header states.
**Reads:** Temp files only; `MCFIX_TREE` selects the source tree so the same file runs against an extracted older tree.
**Writes:** stdout only (`PASS`/`FAIL` per strand).
**Called by:** none — manual test.
**Calls out:** `src.panes` (`log_janitor`, `cache_turns`), `src.utils`, `src.constants`, `src.format.token_format`.

---

## State
Neither module owns persistent state. `render_byte_identity.py`'s `_hash_cache_turns` writes to a
`tempfile.NamedTemporaryFile` it creates and deletes within the same function call; nothing
persists across runs in either module.
