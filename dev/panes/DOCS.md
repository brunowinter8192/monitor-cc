# dev/panes/

## Role
Regression harnesses for `src/panes/` and its `src/format/` render helpers: byte-identity harnesses for refactors and assert-based tests for specific render behavior. Add here when a `src/panes/` or token-format change needs a proof not covered elsewhere.

## Public Interface
No `__init__.py`. Entry paths: `./venv/bin/python dev/panes/render_byte_identity.py`, `answering_model_line_test.py` and `test_display_tripwires.py`.

## Flow
The identity harness renders over a fixed real or synthetic input, hashes the result and prints one hash for before/after comparison. The assert-based tests call the real render or janitor functions over synthetic input and assert exact output, as parallel fail-fast strands.

## Modules

### render_byte_identity.py (175 LOC)

**Purpose:** Verification aid, not a self-checking test: hashes the output of the panes-split module boundaries into one value for before/after comparison.
**Reads:** a frozen session-prefix fixture by default, or a path from an env var; other checks are synthetic.
**Writes:** stdout only, plus a temp file cleaned up on exit.
**Called by:** none; run before and after a `src/panes/` refactor.
**Calls out:** `src.panes.cache_turns`, `src.panes.warnings_render`, `src.format`, imported lazily to satisfy the dev-imports-src hook.

---

### answering_model_line_test.py (151 LOC)

**Purpose:** Assert-based test of the answering-model line and rate-limit lines: equal, mismatch and missing-field cases with exact rendered output.
**Reads:** nothing on disk; synthetic dicts.
**Writes:** stdout verdict per strand; `md/answering_model_line_test.md`.
**Called by:** none; re-run after changes to those render paths or the response-log reader.
**Calls out:** `src.format.token_format`, `src.colors`, the strand runner in `dev/refactoring/`.

---

### test_display_tripwires.py (112 LOC)

**Purpose:** Five parallel strands: janitor partition and atomic write, janitor failure logged, synthetic-user fallback noted once per turn, timestamp states, rate-limit header states.
**Reads:** temp files only; an env var selects the source tree so the file can run against an older tree.
**Writes:** stdout only.
**Called by:** none; manual test.
**Calls out:** `src.panes`, `src.utils`, `src.constants`, `src.format.token_format`.

---

## State
No persistent state. The identity harness writes and deletes one temp file within a call.
