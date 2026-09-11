# dev/tool_use_errors/

## Role
Empirical audit suite for the tool-errors log — determines which error patterns are agent-relevant
(keep) vs. strippable CC-wrapper noise, and verifies that `strip_hook_prefix.py` strips the
hook-error prefix before it reaches Anthropic.

## Flow
Loads the tool-errors log, clusters entries by error shape, classifies each bucket by a fixed match
rule, cross-checks proxy logs for the strip modification, and writes a findings report.

## Modules

### A_error_cluster_audit.py (365 LOC)

**Purpose:** Loads the tool-errors log, clusters entries by error shape (hook-prefixed, tool_use_error,
exit-code, rejection, bare-guidance), classifies each bucket's verdict, and cross-checks proxy logs
for `stripped_hook_error_prefix` modification entries to confirm the strip reaches Anthropic.
**Reads:** the tool-errors log and all proxy JSONL logs under src/logs.
**Writes:** `dev/tool_use_errors/md/<date>_error_cluster_audit.md`.
**Called by:** none — manual CLI, run via
`./venv/bin/python dev/tool_use_errors/A_error_cluster_audit.py`.
**Calls out:** none — stdlib JSONL/regex parsing only.
