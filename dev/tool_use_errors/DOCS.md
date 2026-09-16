# dev/tool_use_errors/

## Role
Empirical audit suite for the tool-errors log — determines which error patterns are agent-relevant
(keep) vs. strippable CC-wrapper noise, and verifies that `strip_hook_prefix.py` strips the
hook-error prefix before it reaches Anthropic.

## Flow
Loads the tool-errors log, clusters entries by error shape, classifies each bucket by a fixed match
rule, cross-checks proxy logs for the strip modification, and writes a findings report.

## Modules

### A_error_cluster_audit.py (50 LOC)

**Purpose:** Entry script — resolves log paths (worktree-aware) and drives
load -> cluster -> cross-check -> report.
**Reads:** nothing directly — resolves `TOOL_ERRORS_LOG`/`LOGS_DIR`/`REPORTS_DIR` paths.
**Writes:** nothing directly — delegates to `error_cluster_report.write_report`.
**Called by:** none — manual CLI, run via
`./venv/bin/python dev/tool_use_errors/A_error_cluster_audit.py`.
**Calls out:** `error_cluster_extraction`, `error_cluster_crosscheck`, `error_cluster_report`.

### error_cluster_extraction.py (41 LOC)

**Purpose:** Loads the tool-errors log and clusters entries by error shape (hook-prefixed,
tool_use_error, exit-code, rejection, bare-guidance).
**Reads:** the tool-errors log (path passed in by the caller).
**Writes:** nothing — returns the bucket dict.
**Called by:** `A_error_cluster_audit.py`.
**Calls out:** none — stdlib JSONL/regex parsing only.

### error_cluster_crosscheck.py (73 LOC)

**Purpose:** Scans available proxy JSONL logs for the `stripped_hook_error_prefix` modification to
confirm the strip reaches Anthropic, and checks whether the hook-prefixed bucket predates it.
**Reads:** all `api_requests_*.jsonl` proxy logs under the logs directory passed in by the caller.
**Writes:** nothing — returns the cross-check result dict.
**Called by:** `A_error_cluster_audit.py`.
**Calls out:** none — stdlib JSONL parsing only.

### error_cluster_report.py (245 LOC)

**Purpose:** Classifies each bucket's verdict, formats the full markdown findings report section
by section, and writes it to disk.
**Reads:** the finished `entries`/`buckets`/cross-check dict from the orchestrator.
**Writes:** `dev/tool_use_errors/reports/<date>_error_cluster_audit.md`.
**Called by:** `A_error_cluster_audit.py`.
**Calls out:** `error_cluster_extraction` (`_EXIT_CODE_RE`).
