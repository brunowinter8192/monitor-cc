# dev/hook_error_correlation/

## Role
Overlays the tool-error log against the hook config in `src/hooks/` to classify which errors are still reachable (false-positive candidates) versus stale. Touch when auditing hook false-positive reports.

## Public Interface
No `__init__.py`. Entry point is direct invocation: `python3 dev/hook_error_correlation/analyze.py`.

## Flow
`analyze.py` loads the error and hook-fire logs, resolves each error's triggering command through the matching proxy log, replays the active hook as a subprocess, classifies each entry, and hands the result to `analyze_report.py` for the Markdown report.

## Modules

### analyze.py (166 LOC)

**Purpose:** Resolves each logged error's triggering command, replays the active hook against it and classifies reachability.
**Reads:** `src/logs/tool_errors.jsonl`, `src/logs/hook_firing.jsonl`, proxy JSONL logs.
**Writes:** `reports/<date>.md`; runs hook scripts as subprocesses.
**Called by:** none; run manually.
**Calls out:** `analyze_report.py`.

---

### analyze_report.py (202 LOC)

**Purpose:** Pure Markdown rendering of the correlation report from the data the analyzer collected.
**Reads:** nothing; receives data as arguments.
**Writes:** nothing; returns a string.
**Called by:** `analyze.py`.
**Calls out:** none.

---

## State
Paths are resolved once at import time and read-only afterward. Replaying a blocking hook appends to the production hook-fire log, a live side effect on shared state (see process-docs).
