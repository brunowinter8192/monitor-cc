# dev/tool_use_errors/

## Role
Empirical audit suite for the tool-errors log: determines which error patterns are agent-relevant versus strippable CC-wrapper noise, and verifies the hook-error prefix strip reaches Anthropic stripped.

## Public Interface
No `__init__.py`. Entry path: `./venv/bin/python dev/tool_use_errors/A_error_cluster_audit.py`.

## Flow
Loads the tool-errors log, clusters entries by error shape, classifies each bucket, cross-checks proxy logs for the strip modification and writes a findings report.

## Modules

### A_error_cluster_audit.py (37 LOC)

**Purpose:** Entry script: resolves worktree-aware log paths and drives load, cluster, cross-check and report.
**Reads:** nothing directly; resolves the log and report paths.
**Writes:** nothing directly; delegates to the report module.
**Called by:** none; manual CLI.
**Calls out:** `error_cluster_extraction.py`, `error_cluster_crosscheck.py`, `error_cluster_report.py`.

---

### error_cluster_extraction.py (39 LOC)

**Purpose:** Loads the tool-errors log and clusters entries by error shape.
**Reads:** the tool-errors log passed in by the caller.
**Writes:** nothing; returns the buckets.
**Called by:** `A_error_cluster_audit.py`.
**Calls out:** none; stdlib only.

---

### error_cluster_crosscheck.py (69 LOC)

**Purpose:** Scans proxy logs for the hook-prefix strip modification to confirm the strip reaches Anthropic and whether the hook-prefixed bucket predates it.
**Reads:** all proxy request logs under the logs directory passed in.
**Writes:** nothing; returns the cross-check result.
**Called by:** `A_error_cluster_audit.py`.
**Calls out:** none; stdlib only.

---

### error_cluster_report.py (241 LOC)

**Purpose:** Classifies each bucket's verdict, formats the Markdown findings report and writes it to disk.
**Reads:** the finished entries, buckets and cross-check result.
**Writes:** `dev/tool_use_errors/reports/<date>_error_cluster_audit.md`.
**Called by:** `A_error_cluster_audit.py`.
**Calls out:** `error_cluster_extraction.py`.

---

## State
The entry script resolves the path values once at import time; the three library modules hold no state.
