# dev/refactoring/

## Role
Holds reports from refactor passes against the code standard, plus the shared strand runner that dev/ test suites use to run case groups as parallel fail-fast subprocesses. Touch when a pass leaves a finding list for a later session. No refactor scripts belong here.

## Public Interface
No `__init__.py`. Report storage in `md/`, plus the importable strand runner module, imported by test suites of other dev/ areas after they put the repo root on the path.

## Flow
A refactor pass reads `src/` or `dev/`, a worker writes its finding list to `md/`, and a later session reads that list and decides what to change.

## Modules

### strand_runner.py (91 LOC)

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

### strand_runner_selftest.py (97 LOC)

**Purpose:** Proves the runner's behavior on throwaway strand scripts: parallel execution, fail-fast within a strand, siblings finishing after an abort, report content.
**Reads:** nothing; writes throwaway scripts to a temp dir.
**Writes:** stdout only.
**Called by:** none; manual.
**Calls out:** `strand_runner.py`.

---

## State
No state in the modules. `md/` holds dated report files, each written once and never mutated.
