# src/hooks/

## Role

Global Claude Code safety hooks: standalone scripts that intercept Bash, Edit, Read and Write tool calls and either block a destructive or context-flooding pattern or silently rewrite a correctable input. Registered machine-wide, so a change affects every session. Touch for mechanical, unconditionally true command-safety rules; judgment-based or advisory rules belong in skills or rule files.

## Public Interface

No `__init__.py`; this directory is not a Python package. Each script is a standalone entry point invoked by the Claude Code hook system via the user-level settings file. Registration entry point: `hook_setup.py`.

## Flow

1. Claude Code writes the pending tool call as JSON to the hook script's stdin.
2. The script optionally strips shell-inactive regions via `_shell_strip.py` and evaluates one rule.
3. On violation it writes to stderr and exits 2 (block); a rewrite hook prints updated-input JSON to stdout and exits 0; otherwise it exits 0 silently.
4. Every block or rewrite decision is appended to the hook fire log via `_fire_log.py`.
5. `hook_setup.py` writes matcher/command entries for each script into the user-level settings file.

## Modules

### _shell_strip.py (186 LOC)

**Purpose:** position-preserving shell-region stripper that blanks heredocs and quoted strings before pattern matching; a library, not a hook.
**Reads:** n/a.
**Writes:** n/a.
**Called by:** `block_broad_find.py`, `block_broad_grep.py`, `block_busywait_loop.py`, `block_cli_chained.py`, `block_dangerous_kill.py`, `block_gh_cli_local_path.py`, `block_manual_worker_cleanup.py`, `block_pipe_scraper_isolated.py`, `block_po_read.py`, `block_rag_cli_document_repeat.py`, `block_rag_cli_index_isolated.py`, `block_rag_corpus_read.py`, `block_rag_docs_layer.py`, `block_search_subreddits_limit.py`, `block_unauthorized_background.py`, `block_venv_no_redirect.py`, `block_worker_kill_while_working.py`, `block_worker_send_background.py`, `block_worker_send_while_working.py`, `block_worker_spawn_placement.py`, `rewrite_chained_sleep.py`, `rewrite_worker_wait.py`.
**Calls out:** none.

---

### _known_cli.py (86 LOC)

**Purpose:** table and matchers resolving a Bash chain segment to one of the policed project CLIs and deciding whether its subcommand is protected.
**Reads:** n/a.
**Writes:** n/a.
**Called by:** `block_cli_chained.py`.
**Calls out:** none.

---

### _fire_log.py (36 LOC)

**Purpose:** appends one JSON line per hook decision to the fire log; a write failure never breaks a hook.
**Reads:** optional log-path override environment variable (test isolation).
**Writes:** `src/logs/hook_firing.jsonl` (append).
**Called by:** every active hook script in this directory except `hook_setup.py`.
**Calls out:** none.

---

### block_dangerous_kill.py (72 LOC)

**Purpose:** PreToolUse Bash hook blocking process kills that match by command-line substring, with a small allowlist of known-safe targets.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### rewrite_chained_sleep.py (134 LOC)

**Purpose:** PreToolUse Bash hook that strips a chained sleep after a trivial read-only command, leaving load-bearing sleeps untouched.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** updated command JSON on stdout when rewritten.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_search_subreddits_limit.py (51 LOC)

**Purpose:** PreToolUse Bash hook blocking subreddit-search calls that carry a result limit flag.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_unauthorized_background.py (65 LOC)

**Purpose:** PreToolUse Bash hook that forces background dispatch off for every command except sleep-only timers and the canonical worker wait form.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** updated background flag on stdout when flipped.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### rewrite_background_sleep.py (67 LOC)

**Purpose:** PreToolUse Bash hook rewriting a backgrounded sleep-only command to the worker wait form; skipped inside worktrees.
**Reads:** stdin (PreToolUse JSON payload). Current working directory.
**Writes:** updated command JSON on stdout when rewritten.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_broad_grep.py (88 LOC)

**Purpose:** PreToolUse Bash hook blocking recursive grep with no include scope, file target or head bound.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_broad_find.py (111 LOC)

**Purpose:** PreToolUse Bash hook blocking find over broad roots with no depth limit or head bound.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_cli_chained.py (173 LOC)

**Purpose:** PreToolUse Bash hook enforcing piping, redirect and same-call readback rules for the policed CLIs known to `_known_cli.py`.
**Reads:** stdin (PreToolUse JSON payload). Session working directory as fallback.
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_gh_cli_local_path.py (92 LOC)

**Purpose:** PreToolUse Bash hook blocking gh-cli file fetches whose repo-path argument is a local absolute or home path.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_rag_cli_index_isolated.py (76 LOC)

**Purpose:** PreToolUse Bash hook requiring rag-cli index calls to run alone in their Bash invocation, without substitutions.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_rag_docs_layer.py (102 LOC)

**Purpose:** PreToolUse Bash hook blocking searches on docs collections that lack a process-docs layer filter.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_rag_corpus_read.py (82 LOC)

**Purpose:** PreToolUse Bash hook blocking raw content reads inside a RAG chunk-store tree; file management stays allowed.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_noop_edit.py (41 LOC)

**Purpose:** PreToolUse Edit hook blocking edits whose old and new strings are identical.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_read_directory.py (38 LOC)

**Purpose:** PreToolUse Read hook blocking reads of a directory path.
**Reads:** stdin (PreToolUse JSON payload). Filesystem type check.
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_cd_drift.py (70 LOC)

**Purpose:** PreToolUse Bash hook blocking a command that ends with a cd into a worktree path and no cd back.
**Reads:** stdin (PreToolUse JSON payload). Current working directory.
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_dev_imports_src.py (59 LOC)

**Purpose:** PreToolUse Write/Edit hook blocking dev/ content that imports the src tree, exempting pytest-shaped files under tests.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_except_pass.py (47 LOC)

**Purpose:** PreToolUse Write/Edit hook blocking content with a bare except-pass block.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_git_add_deps.py (59 LOC)

**Purpose:** PreToolUse Bash hook blocking git add of dependency directories that are symlinks inside worktrees.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_git_destructive.py (93 LOC)

**Purpose:** PreToolUse Bash hook blocking amend, force push, no-verify, empty commits and non-read-only git config.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_path_typo.py (111 LOC)

**Purpose:** PreToolUse Bash/Read/Write/Edit hook auto-rewriting known path typos; name kept for settings matcher continuity although it rewrites.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** updated input JSON and system message on stdout when a typo is found.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_venv_no_redirect.py (46 LOC)

**Purpose:** PreToolUse Bash hook blocking venv python script runs that have no output redirect.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_worker_spawn_placement.py (92 LOC)

**Purpose:** PreToolUse Bash hook blocking worker spawns that target a foreign git root or disable the worktree; skipped inside worktrees.
**Reads:** stdin (PreToolUse JSON payload). Current working directory.
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_worker_send_background.py (52 LOC)

**Purpose:** PreToolUse Bash hook blocking worker sends dispatched in the background.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### rewrite_worker_wait.py (90 LOC)

**Purpose:** PreToolUse Bash hook normalising every worker wait mention (forced background, leading cd collapse); blocks unfixable chains.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** updated input JSON on stdout when rewritten; stderr and exit 2 on an unfixable chain.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_worker_kill_while_working.py (94 LOC)

**Purpose:** PreToolUse Bash hook blocking a worker kill while a live status check reports the worker as working.
**Reads:** stdin (PreToolUse JSON payload). Live worker status via subprocess.
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_worker_send_while_working.py (94 LOC)

**Purpose:** PreToolUse Sibling of the kill guard applied to worker sends; deliberately duplicated rather than shared.
**Reads:** stdin (PreToolUse JSON payload). Live worker status via subprocess.
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_manual_worker_cleanup.py (53 LOC)

**Purpose:** PreToolUse Bash hook blocking raw tmux and git-worktree cleanup that bypasses the worker kill command.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_po_read.py (93 LOC)

**Purpose:** PreToolUse Bash hook blocking shell reads of small persisted-output export files, pointing at the poread tool.
**Reads:** stdin (PreToolUse JSON payload). Target file size from disk.
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_pipe_scraper_isolated.py (80 LOC)

**Purpose:** PreToolUse Bash hook requiring pipe-scraper calls to run alone in their Bash invocation.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_rag_cli_document_repeat.py (173 LOC)

**Purpose:** PreToolUse Stateful Bash hook blocking repeated single-document rag-cli index or delete calls within a rolling window.
**Reads:** stdin (PreToolUse JSON payload). Its own state file under `src/logs/`.
**Writes:** stderr block message; rewrites its state file.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### block_busywait_loop.py (51 LOC)

**Purpose:** PreToolUse Bash hook blocking while/until polling loops whose body is only a sleep.
**Reads:** stdin (PreToolUse JSON payload).
**Writes:** stderr block message; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.
**Calls out:** none.

---

### hook_setup.py (207 LOC)

**Purpose:** idempotent installer registering every hook script into the user-level Claude Code settings file, sweeping stale entries first.
**Reads:** the user-level settings file; local main-branch git state; the working tree.
**Writes:** the user-level settings file (atomic replace).
**Called by:** run manually from the main repo root; `.githooks/post-merge` and `.githooks/post-commit`; `dev/hook_smoke/test_hook_setup_main_branch_gate.py`.
**Calls out:** `git` CLI (subprocess).

---

## State

- `_fire_log.py` owns the hook fire log; append-only, written by every active hook, read by nothing in this directory.
- `block_rag_cli_document_repeat.py` owns its own repeat-state file under `src/logs/`.
- `hook_setup.py` is the only writer of the user-level settings file.
