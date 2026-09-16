# dev/proxy_dual_log/attribution_coverage/

## Role
Read-only coverage analysis — can every stripped/injected entry in the dual-log corpus be
attributed to a proxy strip/inject function? One unit of `dev/proxy_dual_log/` (see the area's own
DOCS.md); split out because its 4 files import only each other.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python
dev/proxy_dual_log/attribution_coverage/attribution_coverage.py`.

## Flow
Every `*_stripped.jsonl`/`*_injected.jsonl` pair under `src/logs/dual_log` is loaded, each
modification is classified against `strip_vocab.RULES` (loaded from the real `src/proxy/`), and
the aggregated coverage stats are written to a dated Markdown report.

## Modules

### attribution_coverage.py (51 LOC)

**Purpose:** CLI entry point for the read-only coverage analysis — can every stripped/injected
entry be attributed to a proxy function?
**Reads:** all `*_stripped.jsonl`/`*_injected.jsonl` pairs under `src/logs/dual_log` (resolved
against the main checkout when run from a worktree, since that data is gitignored and worktree-local).
**Writes:** `attribution_coverage_reports/<YYYYMMDD>.md` (the reports directory stays at the area
root, `dev/proxy_dual_log/`, not in this subfolder).
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.strip_vocab` (loaded via `importlib`); `attribution_coverage_analyse.py`,
`_report.py`.

---

### attribution_coverage_classify.py (83 LOC)

**Purpose:** Owns the top-level-field attribution maps, span-format detection, strip/inject message
classification, and coverage percentage calculation.
**Reads:** nothing — pure classification functions.
**Writes:** nothing.
**Called by:** `attribution_coverage_analyse.py`, `_report.py`, `attribution_coverage.py`.
**Calls out:** none.

---

### attribution_coverage_analyse.py (140 LOC)

**Purpose:** Pair discovery, JSONL loading, and the per-section strip+inject analysers that build
aggregated coverage stats.
**Reads:** paired `*_stripped.jsonl`/`*_injected.jsonl` files.
**Writes:** nothing — returns stats/residuals/false-positives.
**Called by:** `attribution_coverage.py`.
**Calls out:** `attribution_coverage_classify.py`.

---

### attribution_coverage_report.py (248 LOC)

**Purpose:** Builds the Markdown report — strip/inject attribution tables, residual analysis,
false-positive evidence, and gap-coverage status.
**Reads:** the aggregated stats from `attribution_coverage_analyse.py`.
**Writes:** returns the report as a string.
**Called by:** `attribution_coverage.py`.
**Calls out:** `attribution_coverage_classify.py`; `src.proxy.strip_vocab` (own `importlib` load).

---

## State
No shared or mutating state across modules. `attribution_coverage.py` and
`attribution_coverage_report.py` each independently resolve `_AREA_ROOT`/`_PROJECT_ROOT` (by
walking up from `__file__` until the directory named `proxy_dual_log` is found) once at import
time; the dual-log corpus lookup falls back from the project root to the main-checkout root
(stripping a trailing `.claude/worktrees/<name>` when present) if the direct path doesn't exist,
since that corpus is gitignored and worktree-local copies never have it.
