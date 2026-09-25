# dev/refactoring/

## Role
Holds the AST layout scan for dev/ with its reports, reports from refactor passes, and shared helpers of dev/ scripts: the strand runner for parallel fail-fast test suites and the repo-root resolvers. Touch when a pass leaves a finding list or a dev/ script needs a shared helper.

## Public Interface
No `__init__.py`. Report storage in `md/`, plus the importable helper modules (strand runner, check group, repo-root resolvers), imported by scripts of other dev/ areas after they put the repo root on the path.

## Flow
A refactor pass reads `src/` or `dev/`, a worker writes its finding list to `md/`, and a later session reads that list and decides what to change.

## Modules

### strand_runner.py (94 LOC)

**Purpose:** Runs a test script's case functions as parallel subprocess strands, one per function, each fail-fast, and reports which strands aborted.
**Reads:** the calling script's globals and argv (a strand-name flag selects one function).
**Writes:** stdout verdicts; an optional fixed-name Markdown report.
**Called by:** the strand-based suites of many dev/ areas (pane_search, pane_error_log, display, panes, dual_log_cli, hook_smoke, proxy, proxy_dual_log and others) and the self-test.
**Calls out:** none.

---

### check_group.py (10 LOC)

**Purpose:** Prints a list of named check results and raises on any failed check, so a check group can be one strand.
**Reads:** nothing.
**Writes:** stdout PASS/FAIL lines and a count.
**Called by:** the `*_checks.py` scripts of gpu_pane, input and news_pane.
**Calls out:** none.

---

### strand_runner_selftest.py (100 LOC)

**Purpose:** Proves the runner's behavior on throwaway strand scripts: parallel execution, fail-fast within a strand, siblings finishing after an abort, report content.
**Reads:** nothing; writes throwaway scripts to a temp dir.
**Writes:** stdout only.
**Called by:** none; manual.
**Calls out:** `strand_runner.py`.

---

### layout_scan.py (336 LOC)

**Purpose:** Scans every module under dev/ against the module layout rules and writes a violation report without a date, so reruns leave it unchanged.
**Reads:** all `.py` files under `dev/` and the top-level names of `src/`.
**Writes:** stdout summary; `md/layout_scan_report.md`, overwritten per run.
**Called by:** none; manual, exit code 1 while violations exist.
**Calls out:** none.

---

### layout_scan_imports.py (110 LOC)

**Purpose:** Import rules of the layout scan: relative and bare project imports, and function-local imports that no runtime reason justifies.
**Reads:** the parsed module handed in by `layout_scan.py`, the top-level names of `src/`.
**Writes:** nothing; returns findings.
**Called by:** `layout_scan.py`.
**Calls out:** none.

---

### repo_roots.py (40 LOC)

**Purpose:** Resolves the main project root and the repo root with logs for dev/ scripts that run from a worktree.
**Reads:** `.git` entries along the parent chain, `MONITOR_CC_ROOT`, `git rev-parse --git-common-dir`.
**Writes:** nothing.
**Called by:** `hook_error_correlation/analyze.py`, `tool_use_errors/A_error_cluster_audit.py`, `tool_use_analysis/cc_injection_audit.py`.
**Calls out:** none.

---

## State
No state in the modules. `md/` holds dated report files, each written once and never mutated.
