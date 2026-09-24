# dev/refactoring/

## Role
Holds the reports produced while refactoring this project against the code standard. Touch it when a refactor pass produces a finding list that a later session has to act on. It also holds the shared strand runner that the dev/ test suites use to run their case groups as parallel fail-fast subprocesses. Do not put refactor scripts here; the passes are driven by workers, not by committed tooling.

## Public Interface
No `__init__.py`. Report storage in `md/`, plus the importable helper `dev.refactoring.strand_runner` (`strand_workflow`, `check`), imported by the test suites of other dev/ areas after they put the repo root on `sys.path`.

## Flow
A refactor pass reads `src/` or `dev/`, a worker writes its finding list to `md/`, and a later session reads that list and decides what to change.

## Modules

### strand_runner.py (91 LOC)

**Purpose:** Runs a test script's case functions as parallel subprocess strands, one per function, each fail-fast, and reports which strands aborted.
**Reads:** the calling script's globals and argv (`--strand <name>` selects one function).
**Writes:** stdout verdicts; an optional fixed-name markdown report.
**Called by:** the strand-based test suites in `dev/pane_search`, `dev/pane_error_log`, `dev/display`, `dev/panes`, `dev/menubar_per_project`, `dev/model_selector`, `dev/proxy_instrumentation`, `dev/tmux_launcher`, `strand_runner_selftest.py`.
**Calls out:** none.

---

### strand_runner_selftest.py (97 LOC)

**Purpose:** Proves the runner's behaviour on throwaway strand scripts: parallel execution, fail-fast within a strand, sibling strands finishing after an abort, report content.
**Reads:** nothing; writes throwaway scripts to a temp directory.
**Writes:** stdout only.
**Called by:** none, manual.
**Calls out:** `strand_runner.py`.

---

## State
No state in the modules. `md/` holds dated report files, each written once and never mutated.
