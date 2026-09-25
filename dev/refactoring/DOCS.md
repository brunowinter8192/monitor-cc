# dev/refactoring/

## Role
Holds refactor-pass reports, the shared strand runner for parallel fail-fast test suites, and the proof harnesses (byte identity, import smoke, AST equivalence) that show a refactor changed no behavior. Touch when a pass needs proof or leaves findings. Nothing here changes src.

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

### pinned_harness_runner.py (63 LOC)

**Purpose:** Runs the byte-identity harnesses of the dev areas in parallel against a fixed dual-log snapshot and writes one result file per harness.
**Reads:** a snapshot directory of dual-log files, the harness scripts of dev/proxy, panes, proxy_display, gpu_pane, menubar, constants, workers, pane_flicker.
**Writes:** one result file per harness in the output directory; stdout summary.
**Called by:** manual, before and after a refactor.
**Calls out:** none

---

### import_smoke.py (68 LOC)

**Purpose:** Imports every src module in a fresh interpreter, solo and in five random orders, and writes one exit line per job.
**Reads:** the src tree of the given root.
**Writes:** a report file; stdout job and failure counts.
**Called by:** manual, before and after any import-time change.
**Calls out:** none

---

### ast_import_equivalence.py (47 LOC)

**Purpose:** Proves an import-only commit: normalizes relative imports to absolute and compares each changed file against a git base ref.
**Reads:** git base ref and the working tree.
**Writes:** stdout mismatch list.
**Called by:** manual.
**Calls out:** none

---

### ast_reorder_equivalence.py (38 LOC)

**Purpose:** Proves a reorder-only commit: compares the sorted top-level AST nodes of each changed file against a git base ref.
**Reads:** git base ref and the working tree.
**Writes:** stdout mismatch list.
**Called by:** manual.
**Calls out:** none

---

### stepdown_reorder.py (162 LOC)

**Purpose:** Reorders function definitions inside the FUNCTIONS section so that callers stand above callees; dry run unless --write is given.
**Reads:** src modules.
**Writes:** the reordered src modules with --write.
**Called by:** manual.
**Calls out:** none

---

### hook_matrix.py (90 LOC)

**Purpose:** Runs every src/hooks script as registered (python3 with an absolute path, from a cwd holding a decoy src package) over a fixed payload corpus and writes one line per hook and payload.
**Reads:** the hook scripts of the given root and a snapshot of the hook fire log.
**Writes:** a report file with return code, stdout, stderr and normalized fire-log records.
**Called by:** manual, before and after a hook change.
**Calls out:** none

---

### orch_diff_cases.py (587 LOC)

**Purpose:** Runs scripted scenarios against refactored orchestrators (strip passes, tool injection, bg escape, discover, ghostty, desktop detection, sweep, skills, hook writer, hook setup, pane loops, gpu status, monitor, launcher, ccwrap) and dumps a JSON result for diffing two roots.
**Reads:** the given root.
**Writes:** a JSON result file.
**Called by:** manual, run once per root and compared with cmp.
**Calls out:** none

---

### live_proxy_sandbox.py (93 LOC)

**Purpose:** Starts a real mitmdump on private ports from a hand-built live-copy layout that lacks the repo src/proxy, sends one request through a local upstream and checks the dual-log files.
**Reads:** src/proxy_addon.py, constants, monitor_root and the proxy package of this checkout.
**Writes:** a temp directory only; stdout report.
**Called by:** manual, after any change to the live-copy layout.
**Calls out:** none

---

## State
No state in the modules. `md/` holds dated report files, each written once and never mutated.
