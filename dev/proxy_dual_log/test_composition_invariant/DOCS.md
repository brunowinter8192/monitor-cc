# dev/proxy_dual_log/test_composition_invariant/

## Role
CI-style regression test plus the underlying multi-pass span-composition probe it imports as a module. One unit of `dev/proxy_dual_log/`, split out because its files import only each other.

## Public Interface
No `__init__.py`. Entry paths: `./venv/bin/python dev/proxy_dual_log/test_composition_invariant/test_composition_invariant.py` (regression test, synthetic fixture) and `composition_probe.py` (manual probe, real corpus).

## Flow
The test loads a synthetic fixture corpus and asserts the two composition invariants for every modified block via the probe's span algebra. The probe runs the same algebra over the real corpus and writes a Markdown report.

## Modules

### test_composition_invariant.py (137 LOC)

**Purpose:** Regression test asserting the two composition invariants for every modified block of a synthetic corpus.
**Reads:** `fixtures/invariant_corpus.jsonl` at the area root, not in this subfolder.
**Writes:** stdout summary; exits 1 on any violation.
**Called by:** none; manual CLI, CI-suitable exit code.
**Calls out:** `composition_probe.py`.

---

### composition_probe.py (229 LOC)

**Purpose:** CLI entry point proving multi-pass span composition over the original content and validating two reconstruction invariants.
**Reads:** the dual-log corpus present at run time.
**Writes:** `01_reports/composition_probe_<date>.md` at the area root.
**Called by:** `test_composition_invariant.py`; otherwise run manually.
**Calls out:** `src.proxy.strip_bg_completed`; the ops, passes and corpus modules of this directory.

---

### composition_probe_ops.py (145 LOC)

**Purpose:** The span algebra: cache-control strip, text and op extraction, span-list edit primitive and invariant checking.
**Reads:** nothing; pure transforms.
**Writes:** nothing.
**Called by:** the probe, passes and corpus modules and the test.
**Calls out:** none.

---

### composition_probe_passes.py (61 LOC)

**Purpose:** Runs the production proxy passes plus wakeup dedup in sequence, collecting per-block ops from each pass's return value.
**Reads:** the message list passed in.
**Writes:** nothing; returns final messages and ops.
**Called by:** the probe, corpus module and the test.
**Calls out:** `src.proxy.rules`; `composition_probe_ops.py`.

---

### composition_probe_corpus.py (141 LOC)

**Purpose:** Scans the fixed corpus stems, running every modified block through the pass chain and aggregating stats.
**Reads:** the fixed stems' original logs of the dual log.
**Writes:** nothing; returns stats dicts.
**Called by:** `composition_probe.py`.
**Calls out:** `composition_probe_ops.py`, `composition_probe_passes.py`.

---

## State
No shared or mutating state. Roots are resolved independently per module; the corpus lookup falls back to the main checkout. All fixed corpus stems are rotated off disk (see process-docs for the resulting behavior).
