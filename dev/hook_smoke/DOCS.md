# dev/hook_smoke/

## Role
Smoke-test suite for `src/hooks/`: one test script per hook, verifying block, rewrite and pass-through behavior via a JSON stdin payload or a direct function call. Touch when adding or changing a hook. One script is excluded from the runner because it fails against the current proxy addon (see process-docs).

## Public Interface
No `__init__.py`. Each script is its own entry point, run directly from any directory; `python3 dev/hook_smoke/run_all.py` runs all test modules as parallel strands.

## Flow
A JSON PreToolUse-shaped payload (or a direct call for stub-based scripts) goes in, the hook under test decides allow, block or rewrite, and exit code, stdout JSON or stderr text is compared against an expected table and printed as pass/fail lines. Two scripts read a real corpus and write a report to `md/`.

## Modules

### hook_runner.py (38 LOC)

**Purpose:** Shared helper running one hook script from the repo root with an isolated fire log, plus the fail-fast abort used by table tests.
**Reads:** the hook script under `src/hooks/`.
**Writes:** a per-call temp fire log, removed after the call.
**Called by:** every `test_*.py` in this directory.
**Calls out:** none.

---

### run_all.py (69 LOC)

**Purpose:** Runs every test module of this directory as one parallel fail-fast strand and writes a fixed-name report.
**Reads:** the `test_*.py` modules (executed via `runpy`).
**Writes:** `md/run_all.md`, overwritten per run.
**Called by:** none; manual CLI.
**Calls out:** the strand runner in `dev/refactoring/`.

---

### probe_bg_task_live.py (198 LOC)

**Purpose:** Live probe comparing an old zero-byte predicate against the current active-background check on a real or synthetic task; benchmarks the process-cache tick cost.
**Reads:** a real background task output file, or its own synthetic writer.
**Writes:** `md/<date>_bg_task_detection_probe.md` in full mode; JSON on stdout in snapshot mode.
**Called by:** none; manual CLI, snapshot mode is safe standalone, full mode needs a live task.
**Calls out:** `menubar.proc_cache`.

---

### probe_replay_cli_chained.py (116 LOC)

**Purpose:** Replays every historical block fire of the hooks the chained-CLI hook replaced, reporting still-blocks versus now-passes per old hook.
**Reads:** the main checkout hook-fire log.
**Writes:** `md/block_cli_chained_replay_report.md`.
**Called by:** none; manual CLI.
**Calls out:** none directly; drives the hook via `subprocess`.

---

### test_bg_task_detection.py (152 LOC)

**Purpose:** Smoke for the active-background check: match, no-match, prefix boundary, a real subprocess case, fail-open and TTL gate.
**Reads:** nothing external; the tasks base is redirected to a scratch dir.
**Writes:** a scratch dir under the temp dir, removed on exit.
**Called by:** none; manual CLI.
**Calls out:** `menubar.proc_cache`.

---

### test_block_broad_find.py (82 LOC)

**Purpose:** Smoke for the broad-find hook: blocked broad-root calls, allowed narrower cases.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_block_broad_grep.py (70 LOC)

**Purpose:** Smoke for the broad-grep hook: blocked recursive piped cases, head-bounded and other exemptions.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_block_chained_sleep.py (51 LOC)

**Purpose:** Smoke for the retired chained-sleep hook: canonical versus chained placements, quoting and heredoc stripping.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** none; drives the retired hook file via `subprocess`.

---

### test_block_cli_chained.py (166 LOC)

**Purpose:** Smoke for the chained-CLI hook: pipe, redirect and readback abuse across wrapper CLIs, plus interpreter-path and cwd bypass forms.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI from the project root.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_block_dangerous_kill.py (74 LOC)

**Purpose:** Smoke for the dangerous-kill hook: pattern kills, pipe-kill chains, quoting exemptions and allowlist cases.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_block_gh_cli_local_path.py (68 LOC)

**Purpose:** Smoke for the gh-cli local-path hook: blocked local-path arguments, pass and shell-strip cases.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_block_git_destructive.py (88 LOC)

**Purpose:** Smoke for the destructive-git hook: force-push, amend, no-verify and config-write blocks, safe ops and false-positive regressions.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI from the project root.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_block_manual_worker_cleanup.py (80 LOC)

**Purpose:** Smoke for the manual worker cleanup hook: blocked session-kill and worktree-remove on worker targets, allowed non-worker forms.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_block_non_canonical_edit.py (123 LOC)

**Purpose:** Smoke for the retired non-canonical edit hook: always-block and always-allow forms, the canonical line-edit form and fail-open.
**Reads:** its own temp-dir fixtures.
**Writes:** stdout; its own temp dir, cleaned via `atexit`.
**Called by:** none; manual CLI.
**Calls out:** none; drives the retired hook file via `subprocess`.

---

### test_block_po_read.py (109 LOC)

**Purpose:** Smoke for the persisted-output read hook: blocked readers, allow cases and real-file size-boundary cases.
**Reads:** its own temp-dir fixtures.
**Writes:** stdout; its own temp dir, cleaned via `atexit`.
**Called by:** none; manual CLI from the project root.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_block_rag_cli_document_repeat.py (167 LOC)

**Purpose:** Smoke for the rag-cli document-repeat hook: single, repeat, collection-wide, cross-session, delete and fail-open cases.
**Reads:** nothing.
**Writes:** stdout; a fresh state temp file per case.
**Called by:** none; manual CLI from the project root.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_block_rag_cli_index_isolated.py (117 LOC)

**Purpose:** Smoke for the isolated rag-cli index hook: blocked poll-then-index shapes including substitution smuggling, allowed bare and guarded forms.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI from the project root.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_block_rag_corpus_read.py (126 LOC)

**Purpose:** Smoke for the rag corpus read hook: blocked raw reads over the corpus tree, allowed management ops and unrelated reads.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_block_rag_docs_layer.py (60 LOC)

**Purpose:** Smoke for the rag docs-layer hook: docs-collection search blocks without the process-docs filter and allows with it.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_block_unauthorized_background.py (84 LOC)

**Purpose:** Smoke for the unauthorized-background hook: sleep exempt, worker wait excluded from its opinion, other backgrounded commands forced to foreground.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI from the project root.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_block_worker_kill_while_working.py (130 LOC)

**Purpose:** Smoke for the worker-kill decision function using the real shell-strip and a stub status function.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** none; imports the decision function via `sys.path.insert`.

---

### test_block_worker_send_while_working.py (155 LOC)

**Purpose:** Smoke for the worker-send decision function via the same stub pattern, plus one real subprocess for malformed-stdin fail-open.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** none; imports the decision function via `sys.path.insert`.

---

### test_fire_log.py (163 LOC)

**Purpose:** Regression for the shared hook fire-logging helper: block and rewrite decisions append the expected record and an env override is honored.
**Reads:** nothing external.
**Writes:** its own temp dirs, removed per case.
**Called by:** `run_all.py`; manual CLI.
**Calls out:** none.

---

### test_header_capture.py (173 LOC)

**Purpose:** Smoke for proxy header-capture logic: beta-header extraction and response-header filtering.
**Reads:** its own mock header objects; no live mitmproxy.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** `src.proxy.addon` via `sys.path.insert`.

---

### test_hook_setup_main_branch_gate.py (139 LOC)

**Purpose:** Smoke for the two-condition install gate of hook setup: committed on main and present in tree, either failing skips.
**Reads:** nothing; stub git and tree queries.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** none; imports the entry decision function via `sys.path.insert`.

---

### test_hook_trace_lines.py (250 LOC)

**Purpose:** Provokes each observed hook degradation and asserts the trace line while exit semantics stay unchanged.
**Reads:** nothing.
**Writes:** stdout only; all hook logs go to temp paths.
**Called by:** none; manual CLI, cases run in parallel threads.
**Calls out:** none; drives hooks via `subprocess` and direct module loads.

---

### test_log_janitor.py (65 LOC)

**Purpose:** Smoke for the JSONL log janitor: old record dropped, recent, empty and naive-timestamp records kept.
**Reads:** its own temp-file fixtures.
**Writes:** stdout only; its own temp file.
**Called by:** none; manual CLI.
**Calls out:** none; imports the janitor via `sys.path.insert` on `src/panes/`.

---

### test_rewrite_background_sleep.py (156 LOC)

**Purpose:** Smoke for the background-sleep rewrite hook: sleep shapes rewritten to worker wait, no-op cases and the worktree-cwd guard.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** none; drives the hook via `subprocess` with an explicit cwd per case.

---

### test_rewrite_chained_sleep.py (202 LOC)

**Purpose:** Smoke for the chained-sleep rewrite hook: trivial predecessors strip the sleep, load-bearing shapes are no-ops.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI from the project root.
**Calls out:** none; drives the hook via `subprocess`.

---

### test_rewrite_worker_wait.py (115 LOC)

**Purpose:** Smoke for the worker-wait rewrite hook: correct forms no-op, background forced true, leading cd collapsed, other chains still block, false-positive guards.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI from the project root.
**Calls out:** none; drives the hook via `subprocess`.

---

### verify_block_non_canonical_edit_corpus.py (64 LOC)

**Purpose:** Ran the retired non-canonical edit hook against every real corpus record; cannot currently run because the target is disabled.
**Reads:** `dev/cache/jsonl/bash_file_mods_*.jsonl`, read-only.
**Writes:** nothing directly; delegates to the report module.
**Called by:** none; cannot currently run.
**Calls out:** `src.hooks.block_non_canonical_edit`, retired.

---

### verify_block_non_canonical_edit_report.py (87 LOC)

**Purpose:** Pure Markdown rendering of the corpus-verification report from an evaluated results list.
**Reads:** nothing; results as argument.
**Writes:** `md/block_non_canonical_edit_corpus_report.md`, a historical snapshot.
**Called by:** `verify_block_non_canonical_edit_corpus.py`.
**Calls out:** none.

---

### test_version_purge.sh (120 LOC)

**Purpose:** Smoke for the version-aware dual-log purge, mirroring the launcher shell functions inline; keep in sync by hand.
**Reads:** nothing; own temp dir per case.
**Writes:** stdout only.
**Called by:** none; run via `bash dev/hook_smoke/test_version_purge.sh`.
**Calls out:** none; mirrors production shell functions.

---

## State
No persistent state. Every script builds and discards its own synthetic state. The replay probe and the report renderer write into tracked `md/` reports that are historical snapshots; regenerating them against the live corpus can drift from the committed snapshot without being a code regression.
