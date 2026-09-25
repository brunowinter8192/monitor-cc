# dev/refactoring/

## Role
Holds the AST layout scan for dev/ with its reports, the shared helpers of dev/ scripts (strand runner, repo-root resolvers) and the proof harnesses that show a refactor changed no behavior. Touch when a pass needs a scan, proof or shared helper. Nothing here changes src.

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

### layout_scan.py (345 LOC)

**Purpose:** Scans every module under dev/ against the module layout rules and writes a violation report without a date, so reruns leave it unchanged.
**Reads:** all `.py` files under `dev/` and the top-level names of `src/`.
**Writes:** stdout summary; `md/layout_scan_report.md`, overwritten per run.
**Called by:** none; manual, exit code 1 while violations exist.
**Calls out:** none.

---

### layout_scan_imports.py (123 LOC)

**Purpose:** Import rules of the layout scan: relative and bare project imports, and function-local imports that no runtime reason justifies.
**Reads:** the parsed module handed in by `layout_scan.py`, the top-level names of `src/`.
**Writes:** nothing; returns findings.
**Called by:** `layout_scan.py`.
**Calls out:** none.

---

### live_log_isolation.py (36 LOC)

**Purpose:** Points the hook firing log, the home directory or the monitor root of the running test process at a temp directory, removed at exit.
**Reads:** nothing.
**Writes:** the environment variables `MONITOR_CC_HOOK_FIRING_LOG`, `HOME`, `MONITOR_CC_ROOT` of the calling process; a temp directory.
**Called by:** dev tests and probes that import `src.proxy`, `src.menubar` or run hook code in-process, before their first `src` import.
**Calls out:** none.

---

### live_log_writer_scan.py (143 LOC)

**Purpose:** Runs every guarded dev script in a sandbox copy with a temp HOME and reports the ones that change a live log path.
**Reads:** the tracked dev scripts; sizes and mtimes of the sandbox `src/logs`, the temp HOME, the live `src/logs` and the menubar application support directory.
**Writes:** `md/live_log_writer_scan_report.md`; a sandbox copy next to the worktree and a temp HOME, both left in place.
**Called by:** none; manual after adding tests that import `src` modules.
**Calls out:** `repo_roots.py`.

---

### repo_roots.py (40 LOC)

**Purpose:** Resolves the main project root and the repo root with logs for dev/ scripts that run from a worktree.
**Reads:** `.git` entries along the parent chain, `MONITOR_CC_ROOT`, `git rev-parse --git-common-dir`.
**Writes:** nothing.
**Called by:** `hook_error_correlation/analyze.py`, `tool_use_errors/A_error_cluster_audit.py`, `tool_use_analysis/cc_injection_audit.py`.
**Calls out:** none.

---

### pinned_harness_runner.py (73 LOC)

**Purpose:** Runs the byte-identity harnesses of the dev areas in parallel against a fixed dual-log snapshot and writes one result file per harness.
**Reads:** a snapshot directory of dual-log files, the harness scripts of dev/proxy, panes, proxy_display, gpu_pane, menubar, constants, workers, pane_flicker.
**Writes:** one result file per harness in the output directory; stdout summary.
**Called by:** manual, before and after a refactor.
**Calls out:** none

---

### import_smoke.py (80 LOC)

**Purpose:** Imports every src module in a fresh interpreter, solo and in five random orders, and writes one exit line per job.
**Reads:** the src tree of the given root.
**Writes:** a report file; stdout job and failure counts.
**Called by:** manual, before and after any import-time change.
**Calls out:** none

---

### ast_import_equivalence.py (62 LOC)

**Purpose:** Proves an import-only commit: normalizes relative imports to absolute and compares each changed file against a git base ref.
**Reads:** git base ref and the working tree.
**Writes:** stdout mismatch list.
**Called by:** manual.
**Calls out:** none

---

### ast_reorder_equivalence.py (52 LOC)

**Purpose:** Proves a reorder-only commit: compares the sorted top-level AST nodes of each changed file against a git base ref.
**Reads:** git base ref and the working tree.
**Writes:** stdout mismatch list.
**Called by:** manual.
**Calls out:** none

---

### stepdown_reorder.py (188 LOC)

**Purpose:** Reorders function definitions inside the FUNCTIONS section so that callers stand above callees; dry run unless --write is given.
**Reads:** src modules.
**Writes:** the reordered src modules with --write.
**Called by:** manual.
**Calls out:** none

---

### hook_matrix.py (108 LOC)

**Purpose:** Runs every src/hooks script as registered (python3 with an absolute path, from a cwd holding a decoy src package) over a fixed payload corpus and writes one line per hook and payload.
**Reads:** the hook scripts of the given root and a snapshot of the hook fire log.
**Writes:** a report file with return code, stdout, stderr and normalized fire-log records.
**Called by:** manual, before and after a hook change.
**Calls out:** none

---

### orch_diff_cases.py (623 LOC)

**Purpose:** Runs scripted scenarios against refactored orchestrators (strip passes, tool injection, bg escape, discover, ghostty, desktop detection, sweep, skills, hook writer, hook setup, pane loops, gpu status, monitor, launcher, ccwrap) and dumps a JSON result for diffing two roots.
**Reads:** the given root.
**Writes:** a JSON result file.
**Called by:** manual, run once per root and compared with cmp.
**Calls out:** none

---

### live_proxy_sandbox.py (92 LOC)

**Purpose:** Starts a real mitmdump on private ports from a hand-built live-copy layout that lacks the repo src/proxy, sends one request through a local upstream and checks the dual-log files.
**Reads:** src/proxy_addon.py, constants, monitor_root and the proxy package of this checkout.
**Writes:** a temp directory only; stdout report.
**Called by:** manual, after any change to the live-copy layout.
**Calls out:** none

---

### src_layout_scan.py (197 LOC)

**Purpose:** Scans src and the two root scripts for layout violations: comments, docstrings, relative imports, section order, orchestrator shape and logic, top-level statements, emojis.
**Reads:** `src/**/*.py`, `workflow.py`, `setup_py2app.py`.
**Writes:** stdout findings; exit 1 on any hard violation.
**Called by:** manual, at the end of a layout pass.
**Calls out:** none

---

### worker_proxy_sandbox.py (135 LOC)

**Purpose:** Runs the real `_worker_proxy_setup` of a given iterative-dev tree against a temp monitor root, temp marker and private ports and checks the worker proxy forwards a request and writes dual logs.
**Reads:** the iterative-dev tree passed as argument, monitor-cc `src/`.
**Writes:** a temp directory and a temp `/tmp/.monitor_cc_proxy_<id>` marker, removed at the end; stdout report.
**Called by:** manual, after any change to the live-copy layout or `worker_proxy.sh`.
**Calls out:** none

---

## State
No state in the modules. `md/` holds dated report files, each written once and never mutated.
