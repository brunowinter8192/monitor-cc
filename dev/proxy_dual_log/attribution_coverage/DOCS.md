# dev/proxy_dual_log/attribution_coverage/

## Role
Read-only coverage analysis: can every stripped or injected entry in the dual-log corpus be attributed to a proxy strip or inject function? One unit of `dev/proxy_dual_log/`, split out because its files import only each other.

## Public Interface
No `__init__.py`. Entry path: `./venv/bin/python dev/proxy_dual_log/attribution_coverage/attribution_coverage.py`.

## Flow
Every stripped and injected log pair of the dual log is loaded, each modification is classified against the real proxy strip vocabulary, and the aggregated coverage stats are written to a dated Markdown report.

## Modules

### attribution_coverage.py (51 LOC)

**Purpose:** CLI entry point for the coverage analysis.
**Reads:** all stripped and injected log pairs of the dual log, resolved against the main checkout from a worktree.
**Writes:** `attribution_coverage_reports/<YYYYMMDD>.md` at the area root, not in this subfolder.
**Called by:** none; manual CLI.
**Calls out:** `src.proxy.strip_vocab` via `importlib`; `attribution_coverage_analyse.py`, `attribution_coverage_report.py`.

---

### attribution_coverage_classify.py (83 LOC)

**Purpose:** Owns field attribution maps, span-format detection, message classification and coverage percentages.
**Reads:** nothing; pure functions.
**Writes:** nothing.
**Called by:** `attribution_coverage_analyse.py`, `attribution_coverage_report.py`, `attribution_coverage.py`.
**Calls out:** none.

---

### attribution_coverage_analyse.py (140 LOC)

**Purpose:** Pair discovery, JSONL loading and the strip and inject analysers building aggregated stats.
**Reads:** paired stripped and injected logs.
**Writes:** nothing; returns stats, residuals and false positives.
**Called by:** `attribution_coverage.py`.
**Calls out:** `attribution_coverage_classify.py`.

---

### attribution_coverage_report.py (248 LOC)

**Purpose:** Builds the Markdown report: attribution tables, residual analysis, false-positive evidence and gap status.
**Reads:** the aggregated stats from the analyser.
**Writes:** returns the report as a string.
**Called by:** `attribution_coverage.py`.
**Calls out:** `attribution_coverage_classify.py`; `src.proxy.strip_vocab` via its own `importlib` load.

---

## State
No shared or mutating state. The entry and report modules each resolve the area and project roots once at import time; the corpus lookup falls back to the main checkout because the corpus is gitignored (see process-docs).
