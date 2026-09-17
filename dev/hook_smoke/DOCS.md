# dev/hook_smoke/

## Role
Smoke-test suite for `src/hooks/` — one test script per hook, verifying block/rewrite/pass-through
behavior via a JSON stdin payload or a direct function call. Touch this suite when adding a new
hook or changing existing hook logic. It is not itself a source of production behavior.

## Public Interface
No `__init__.py` in this directory. Each script is its own entry point, run directly, e.g.
`python3 dev/hook_smoke/<script>.py` (a few must run from the project root since their `HOOK` path
is relative).

## Flow
A JSON PreToolUse-shaped payload (or a direct function call for the stub-based scripts) goes in.
The hook script under test decides allow/block/rewrite. Exit code, stdout JSON, or stderr text is
compared against an expected table, printed as `PASS`/`FAIL` lines to stdout. Two scripts also read
a real corpus (`dev/cache/jsonl/`, the main checkout's `hook_firing.jsonl`) and write a report to
`md/`.

## Modules

### probe_bg_task_live.py (198 LOC)

**Purpose:** Live probe comparing an old 0-byte predicate against `_has_active_bg` for a real or
synthetic background task; benchmarks the `lsof` cache's per-tick cost.
**Reads:** a real background task's output file under `_TASKS_BASE`, or its own synthetic
subprocess writer.
**Writes:** `md/<date>_bg_task_detection_probe.md` (full mode only); stdout JSON (`--snapshot`).
**Called by:** none — manual CLI; `--snapshot` is safe standalone, full mode needs a live task.
**Calls out:** `menubar.proc_cache`.

---

### probe_replay_cli_chained.py (116 LOC)

**Purpose:** Replays every historical block fire of the 7 hooks `block_cli_chained.py` replaced,
reporting still-blocks vs. now-passes per old hook.
**Reads:** the main checkout's `src/logs/hook_firing.jsonl`.
**Writes:** `md/block_cli_chained_replay_report.md`.
**Called by:** none — manual CLI.
**Calls out:** none directly — drives `src/hooks/block_cli_chained.py` via `subprocess`.

---

### test_bg_task_detection.py (136 LOC)

**Purpose:** 6-case smoke for `_has_active_bg` — match/no-match/prefix-boundary units, a real
subprocess integration case, a fail-open case, and a TTL-gate case.
**Reads:** nothing external.
**Writes:** a scratch dir under the real `_TASKS_BASE`, cleaned up in a `finally`.
**Called by:** none — manual CLI.
**Calls out:** `menubar.proc_cache`.

---

### test_block_broad_find.py (91 LOC)

**Purpose:** 19-case smoke for `block_broad_find.py` — blocked broad-root `find` calls, allowed
narrower/targeted cases.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_broad_grep.py (79 LOC)

**Purpose:** 16-case smoke for `block_broad_grep.py` — blocked recursive-piped-to-non-head cases,
head-bounded and other exemptions.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_chained_sleep.py (60 LOC)

**Purpose:** 13-case smoke for the retired `block_chained_sleep.py.disabled` — canonical vs.
chained sleep placements, quoting/heredoc stripping.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — drives the retired hook file directly via `subprocess`.

---

### test_block_cli_chained.py (174 LOC)

**Purpose:** 45-case smoke for `block_cli_chained.py` — pipe/redirect/readback chain-abuse rules
across 8 wrapper CLIs, plus interpreter-path and cwd-resolved bypass forms.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI; must run from project root.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_dangerous_kill.py (83 LOC)

**Purpose:** 18-case smoke for `block_dangerous_kill.py` — `pkill -f` patterns, pipe-kill chains,
quoting exemptions, allowlist cases.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_gh_cli_local_path.py (77 LOC)

**Purpose:** 15-case smoke for `block_gh_cli_local_path.py` — blocked local-path arguments to two
`gh-cli` subcommands, pass and shell-strip cases.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_git_destructive.py (97 LOC)

**Purpose:** 21-case smoke for `block_git_destructive.py` — force-push/amend/no-verify/
allow-empty/config-write blocks, safe-op and FP-regression allow cases.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI; must run from project root.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_manual_worker_cleanup.py (89 LOC)

**Purpose:** 21-case smoke for `block_manual_worker_cleanup.py` — blocked `tmux kill-session`/
`git worktree remove` on worker targets, allowed non-worker forms.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_non_canonical_edit.py (131 LOC)

**Purpose:** 18-case smoke for the retired `block_non_canonical_edit.py.disabled` — always-block
edit forms, always-allow forms, the canonical `LINEEDIT` form, fail-open.
**Reads:** its own tempdir fixtures (existing/new files).
**Writes:** PASS/FAIL to stdout; its own tempdir, cleaned up via `atexit`.
**Called by:** none — manual CLI.
**Calls out:** none — drives the retired hook file directly via `subprocess`.

---

### test_block_po_read.py (117 LOC)

**Purpose:** 19-case smoke for `block_po_read.py` — blocked readers on a persisted-output path,
allow cases, and 3 real-file size-boundary cases.
**Reads:** its own tempdir fixtures.
**Writes:** PASS/FAIL to stdout; its own tempdir, cleaned up via `atexit`.
**Called by:** none — manual CLI; must run from project root.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_rag_cli_document_repeat.py (184 LOC)

**Purpose:** 7-case smoke for `block_rag_cli_document_repeat.py` — single/repeat/collection-wide/
cross-session/`delete`-subcommand and fail-open cases.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout; a fresh state tempfile per case.
**Called by:** none — manual CLI; must run from project root.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_rag_cli_index_isolated.py (126 LOC)

**Purpose:** 37-case smoke for `block_rag_cli_index_isolated.py` — blocked poll-then-index chain
shapes incl. substitution smuggling, allowed bare/cd-guarded/quoted cases.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI; must run from project root.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_rag_corpus_read.py (135 LOC)

**Purpose:** Smoke for `block_rag_corpus_read.py` — blocked raw-read commands over the rag-cli
corpus tree, allowed management ops and unrelated reads.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_rag_docs_layer.py (69 LOC)

**Purpose:** 11-case smoke for `block_rag_docs_layer.py` — `rag-cli search` against a `*-docs`
collection blocks without a `process-docs/%` filter, allows with it.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_read_worktree.py (64 LOC)

**Purpose:** Smoke for `block_read_worktree.py` — foreign-worktree reads blocked, own-worktree and
plain-path reads allowed.
**Reads:** its own `os.getcwd()` to detect whether it runs inside a worktree.
**Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_unauthorized_background.py (93 LOC)

**Purpose:** 16-case smoke for `block_unauthorized_background.py` — `sleep` kept exempt, any
`worker-cli wait` mention (canonical or not) excluded from this hook's opinion entirely (a quoted
mention does not exempt an unrelated command), other backgrounded commands forced to foreground.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI; must run from project root.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_block_worker_kill_while_working.py (111 LOC)

**Purpose:** Smoke for `decide()` in `block_worker_kill_while_working.py`, using the real
`_strip_non_shell_active` and a stub `status_fn`.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — imports `decide` directly via `sys.path.insert`.

---

### test_block_worker_send_while_working.py (121 LOC)

**Purpose:** Smoke for `decide()` in `block_worker_send_while_working.py` via the same stub
pattern, plus one real `subprocess` call for the malformed-stdin fail-open case.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — imports `decide` directly via `sys.path.insert`.

---

### test_fire_log.py (209 LOC)

**Purpose:** Regression for the shared hook fire-logging helper — block/rewrite decisions append
the expected record, an env-var log-path override is honored, tool-error writer works.
**Reads:** nothing external.
**Writes:** its own tempfiles, cleaned up per case.
**Called by:** none — manual CLI.
**Calls out:** `src.panes.warnings_persist` (`append_tool_errors`).

---

### test_header_capture.py (170 LOC)

**Purpose:** 13-case smoke for proxy header-capture logic — `anthropic-beta` extraction and
`_filter_response_headers()` exact-name/prefix filtering.
**Reads:** its own mock header objects — no live mitmproxy process required.
**Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.addon` (`_filter_response_headers`) — imported via `sys.path.insert`.

---

### test_hook_setup_main_branch_gate.py (122 LOC)

**Purpose:** 10-case smoke for the two-condition install gate in `hook_setup.py`'s
`decide_entries()` — committed-on-main AND present-in-tree, either failing skips.
**Reads:** nothing — stub `git_query_fn`/`tree_query_fn`.
**Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — imports `decide_entries` directly via `sys.path.insert`.

---

### test_log_janitor.py (68 LOC)

**Purpose:** 4-case smoke for `cleanup_old_jsonl` — old record dropped, recent/empty/naive-ts
records kept (fail-safe).
**Reads:** its own tempfile fixtures.
**Writes:** PASS/FAIL to stdout; its own tempfile.
**Called by:** none — manual CLI.
**Calls out:** none — imports `log_janitor` directly via `sys.path.insert` on `src/panes/`.

---

### test_rewrite_background_sleep.py (166 LOC)

**Purpose:** 14-case smoke for `rewrite_background_sleep.py` — sleep-shape rewrites to
`worker-cli wait`, no-op cases, and the worktree-cwd orchestrator-only guard.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — drives the hook via `subprocess` with an explicit `cwd` per case.

---

### test_rewrite_chained_sleep.py (211 LOC)

**Purpose:** 8-case (28-tuple) smoke for `rewrite_chained_sleep.py` — trivial `cmd_before` strips
the sleep, load-bearing `cmd_before`/loop-body/sleep-first shapes are no-ops.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI; must run from project root.
**Calls out:** none — drives the hook via `subprocess`.

---

### test_rewrite_worker_wait.py (124 LOC)

**Purpose:** 22-case smoke for `rewrite_worker_wait.py` — already-correct forms are a no-op,
missing/false `run_in_background` is forced true, an unambiguous leading `cd` is collapsed into
the positional-path form (dropped entirely when the wait already carries its own path), anything
chained beyond that leading `cd` still blocks, plus word-boundary and quoted-mention/heredoc-body
false-positive guards.
**Reads:** nothing. **Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI; must run from project root.
**Calls out:** none — drives the hook via `subprocess`.

---

### verify_block_non_canonical_edit_corpus.py (64 LOC)

**Purpose:** Ran the retired `block_non_canonical_edit.py`'s `_decide()` against every real corpus
record; cannot currently run since the target module is disabled.
**Reads:** `dev/cache/jsonl/bash_file_mods_*.jsonl` (read-only).
**Writes:** nothing directly — delegates to `verify_block_non_canonical_edit_report.py`.
**Called by:** none — cannot currently run, see Purpose.
**Calls out:** `src.hooks.block_non_canonical_edit` (`_decide`) — target retired.

---

### verify_block_non_canonical_edit_report.py (87 LOC)

**Purpose:** Pure markdown rendering for the corpus-verification report — verdict counts, BLOCK/
ERROR full lists, ALLOW spot-check — from an already-evaluated results list.
**Reads:** nothing — takes `results` as an argument.
**Writes:** `md/block_non_canonical_edit_corpus_report.md` — a historical snapshot, not
regenerated (its caller can no longer run).
**Called by:** `verify_block_non_canonical_edit_corpus.py`.

---

### test_version_purge.sh (140 LOC)

**Purpose:** 8-assertion smoke for the version-aware dual-log purge, mirroring
`_janitor_version_purge_jsonl_logs`/`_compute_proxy_hash` from `src/claude_proxy_start.sh`.
**Reads:** nothing — builds its own temp dir per case.
**Writes:** PASS/FAIL to stdout.
**Called by:** none — manual CLI, run via `bash dev/hook_smoke/test_version_purge.sh`.
**Calls out:** none — mirrors the production shell functions inline; keep in sync by hand.

---

## State
No persistent state lives in this directory. Every script builds its own synthetic state locally
(tempfiles/tempdirs, stub maps, or its own scratch dir under `_TASKS_BASE`) and discards it before
exit. `probe_replay_cli_chained.py` and `verify_block_non_canonical_edit_report.py` are the two
exceptions: they write into the tracked `md/` reports in this directory, which are historical
snapshots — re-running them regenerates the report against whatever corpus is live at run time,
which can drift from the committed snapshot without that being a code regression.
