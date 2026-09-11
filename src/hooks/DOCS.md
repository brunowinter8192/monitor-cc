# src/hooks/

## Role

Global Claude Code safety hooks: standalone scripts that intercept Bash, Edit, Read, and Write tool calls before they run and either block a destructive or context-flooding pattern (exit 2 + stderr, shown to the model) or silently rewrite a broken-but-correctable input (exit 0 + updated JSON on stdout). Hooks are registered machine-wide in the user-level Claude Code settings file by `hook_setup.py`, so a change here affects every Claude Code session on this machine, not only this project. Touch this directory to add or fix a mechanical, unconditionally-true command-safety rule. A rule that needs project-specific judgment or is advisory rather than mechanical belongs in a skill or rule file instead — a hook fires surgically only on the actual violation and costs nothing idle, so duplicating a hook-enforced rule as always-loaded skill prose is redundant.

## Public Interface

No `__init__.py` — this directory is not a Python package. Each script is a standalone `python3 <script>.py` entry point invoked by the Claude Code hook system through the user-level settings file. Installation/registration entry point: `hook_setup.py`.

## Flow

1. Claude Code writes the pending tool call (command / file_path / content, session_id) as JSON to the hook script's stdin.
2. The script parses stdin, optionally strips shell-inactive regions via `_shell_strip._strip_non_shell_active`, and evaluates one rule against the command or content.
3. On violation it prints a message to stderr and exits 2 (block); a rewrite hook instead prints updated-input JSON to stdout and exits 0; otherwise it exits 0 silently (allow).
4. Every block/rewrite decision is appended to `src/logs/hook_firing.jsonl` via `_fire_log.log_fire()`.
5. `hook_setup.py` reads `_HOOK_SCRIPTS` and writes matcher/command entries into the user-level settings file, gated per script on being committed on `main` and present in the current working tree.

## Modules

### _shell_strip.py (181 LOC)

**Purpose:** Position-preserving shell-region stripper — blanks heredoc bodies, single/double-quoted strings, and ANSI-C `$'...'` quotes to same-length spaces before pattern matching, keeping `$(...)` and backtick command substitutions active; fails open (returns the input unchanged) on any parse error.
**Reads:** n/a — pure function library, not a standalone script.
**Writes:** n/a.
**Called by:** `block_broad_find.py`, `block_broad_grep.py`, `block_busywait_loop.py`, `block_cli_chained.py`, `block_dangerous_kill.py`, `block_gh_cli_local_path.py`, `block_manual_worker_cleanup.py`, `block_pipe_scraper_isolated.py`, `block_po_read.py`, `block_rag_cli_document_repeat.py`, `block_rag_cli_index_isolated.py`, `block_rag_corpus_read.py`, `block_rag_docs_layer.py`, `block_search_subreddits_limit.py`, `block_venv_no_redirect.py`, `block_worker_kill_while_working.py`, `block_worker_send_background.py`, `block_worker_send_while_working.py`, `block_worker_spawn_placement.py`, `rewrite_chained_sleep.py` — same-directory `sys.path` insert + `from _shell_strip import _strip_non_shell_active`.

---

### _known_cli.py (81 LOC)

**Purpose:** `PROTECTED_SUBCOMMANDS` table and matcher functions resolving a Bash chain segment to one of the 8 policed CLIs (gh-cli, rag-cli, worker-cli, reddit-cli, websearch, linkedin, penny-cli, duallog), by wrapper name or by bare `python cli.py` interpreter form, and whether its subcommand is protected.
**Reads:** n/a.
**Writes:** n/a.
**Called by:** `block_cli_chained.py` — `resolve_cli_segment`, `is_protected_segment`, `tool_sub_name`.

---

### _fire_log.py (34 LOC)

**Purpose:** `log_fire(hook_name, decision, tool_name, command, ...)` appends one JSON line per hook decision; fails silently on write errors so logging never breaks a hook.
**Reads:** `MONITOR_CC_HOOK_FIRING_LOG` env var (log path override, used for test isolation).
**Writes:** `src/logs/hook_firing.jsonl` (append), path resolved relative to `__file__` unless overridden.
**Called by:** every active hook script in `src/hooks/` except `hook_setup.py` (30 scripts) — same-directory `sys.path` insert + `from _fire_log import log_fire`, called only at the decision point (never on passthrough).

---

### block_dangerous_kill.py (71 LOC)

**Purpose:** PreToolUse Bash hook blocking `pkill -f`/`pgrep -f`-into-`kill`/`ps|grep|kill` patterns that match processes by cmdline substring, which routinely kills unintended processes including worker sessions; carries a literal-string allowlist (`_PKILL_F_ALLOWLIST`) for known-safe `pkill -f` targets.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### rewrite_chained_sleep.py (133 LOC)

**Purpose:** PreToolUse Bash hook that strips a chained `sleep N` when the immediately preceding chain segment is a trivial read-only command or pair (`_TRIVIAL`/`_TRIVIAL_PAIRS`), leaving sleep-first, load-bearing, and loop-body sleeps untouched.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`, `tool_input.run_in_background`).
**Writes:** stdout (`hookSpecificOutput.updatedInput.command`) when a sleep was stripped; nothing on no-op.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_search_subreddits_limit.py (50 LOC)

**Purpose:** PreToolUse Bash hook blocking `reddit-cli search_subreddits`/`cli.py search_subreddits` calls that carry a `--limit` flag, so subreddit discovery always returns the full result set.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_unauthorized_background.py (59 LOC)

**Purpose:** PreToolUse Bash hook that force-flips `run_in_background` to `false` for any command dispatched in the background that is neither a sleep-only timer (`_SLEEP_ONLY_BG`) nor the canonical `worker-cli wait` form (`_WAIT_FORM`).
**Reads:** stdin (PreToolUse JSON: `tool_input.command`, `tool_input.run_in_background`).
**Writes:** stdout (`hookSpecificOutput.updatedInput.run_in_background: false`) on non-canonical background dispatch; nothing on passthrough.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### rewrite_background_sleep.py (65 LOC)

**Purpose:** PreToolUse Bash hook rewriting a backgrounded sleep-only command to `worker-cli wait`; skipped entirely when the hook's own working directory is inside a worktree path (contains the fragment .claude/worktrees/), so a worker's own background sleep is never promoted.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`, `tool_input.run_in_background`); `os.getcwd()` (worktree exemption).
**Writes:** stdout (`hookSpecificOutput.updatedInput.command: "worker-cli wait"`) when rewritten; nothing otherwise.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_broad_grep.py (87 LOC)

**Purpose:** PreToolUse Bash hook blocking recursive `grep -r`/`-R` calls with no `--include=` scope, no file-extension target, and no `| head` bound.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_broad_find.py (113 LOC)

**Purpose:** PreToolUse Bash hook blocking `find` over broad roots (home directory, filesystem root, the `.claude` subtree) with no `-maxdepth` predicate and no `| head` bound.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_cli_chained.py (167 LOC)

**Purpose:** PreToolUse Bash hook enforcing 3 rules across all 8 CLIs `_known_cli` knows: no piping a CLI segment into another command, no redirecting a protected subcommand's output to a file, no same-call readback (head/tail/cat/sed/awk/grep/less/more/wc) of a file any CLI segment redirected into; chaining with `;`/`&&`/`||` alongside any other command is otherwise unrestricted.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (one of 3 rule-specific block messages) on violation; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_gh_cli_local_path.py (90 LOC)

**Purpose:** PreToolUse Bash hook blocking `gh-cli get_file_content`/`gh-cli download_files` when a repo-path positional argument starts with `/` or `~`; `download_files --dest DIR` is exempted since `DIR` is a local landing directory by design.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message naming the offending value) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_rag_cli_index_isolated.py (75 LOC)

**Purpose:** PreToolUse Bash hook blocking any `rag-cli index` call that shares the Bash invocation with anything besides shell assignments and a `cd`, or that contains command/process substitution anywhere in the raw command; out of scope for all other `rag-cli` subcommands.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message) on violation; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_rag_docs_layer.py (100 LOC)

**Purpose:** PreToolUse Bash hook blocking `rag-cli search` on any `*-docs` collection that lacks a `--document`/`--exclude` filter whose value contains `process-docs`, keeping process-history and code-module search scoped to one RAG layer at a time.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message with the two valid filter forms) on violation; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_rag_corpus_read.py (81 LOC)

**Purpose:** PreToolUse Bash hook blocking raw-content-read commands (cat/grep/head/tail/sed/awk/rg/less/more) targeting a path under a `rag-*/data/documents` chunk-store tree, which bypasses `rag-cli`'s own ranking/formatting; file management (ls/rm/mv/mkdir) over the same tree stays allowed.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message naming both sanctioned `rag-cli` forms) on violation; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_noop_edit.py (40 LOC)

**Purpose:** PreToolUse Edit hook blocking Edit calls where `old_string` equals `new_string`, surfacing the no-op before the round-trip to Claude Code's own rejection.
**Reads:** stdin (PreToolUse JSON: `tool_input.old_string`, `tool_input.new_string`).
**Writes:** stderr (block message) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_read_directory.py (40 LOC)

**Purpose:** PreToolUse Read hook blocking Read calls whose `file_path` resolves to an existing directory (`os.path.isdir`), suggesting `ls` instead.
**Reads:** stdin (PreToolUse JSON: `tool_input.file_path`); filesystem (`os.path.isdir`).
**Writes:** stderr (block message) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_cd_drift.py (67 LOC)

**Purpose:** PreToolUse Bash hook blocking a Bash command whose LAST `cd` target is a worktree path (contains the fragment .claude/worktrees/) with no cd-back, since Bash tool calls share CWD across invocations and a dangling worktree `cd` misdirects the next call.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`); `os.getcwd()` (skips entirely when already running from inside a worktree).
**Writes:** stderr (block message with the fix) on violation; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_dev_imports_src.py (58 LOC)

**Purpose:** PreToolUse Write/Edit hook blocking `dev/` file content that imports `src.*`, exempting pytest-shaped files (`test_*.py`, `*_test.py`, `conftest.py`) under a `tests/` directory segment since a regression suite is meant to exercise the live `src/` tree.
**Reads:** stdin (PreToolUse JSON: `tool_input.file_path`, `tool_input.content` or `tool_input.new_string`).
**Writes:** stderr (block message) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_except_pass.py (46 LOC)

**Purpose:** PreToolUse Write/Edit hook blocking written content containing a bare `except ...: pass` block, enforcing that scripts fail visibly rather than swallow exceptions.
**Reads:** stdin (PreToolUse JSON: `tool_input.content` or `tool_input.new_string`).
**Writes:** stderr (block message with alternatives) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_git_add_deps.py (56 LOC)

**Purpose:** PreToolUse Bash hook blocking `git add` commands that target `venv/`, `.venv/`, or `node_modules/`, since these are symlinks into the main repo inside a worktree and staging them creates circular self-references on merge.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_git_destructive.py (90 LOC)

**Purpose:** PreToolUse Bash hook blocking `git commit --amend`, force-push (`--force`/`-f`/`--force-with-lease`), `--no-verify`, `git commit --allow-empty`, and any `git config` invocation that is not read-only.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message naming the violation + a suggestion) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_path_typo.py (108 LOC)

**Purpose:** PreToolUse Bash/Read/Write/Edit hook that auto-rewrites the typo `.claire/` to `.claude/` and `..<letter>` to `../<letter>` in the tool's command or path input; file kept named `block_path_typo.py` for settings-file matcher continuity even though it now rewrites rather than blocks.
**Reads:** stdin (PreToolUse JSON: `tool_input.command` for Bash, `tool_input.file_path` for Read/Write/Edit).
**Writes:** stdout (`hookSpecificOutput.updatedInput` + `systemMessage`) on a detected typo; nothing on passthrough.
**Called by:** Claude Code hook system, registered by `hook_setup.py` (Bash, Read, Write, and Edit matchers).

---

### block_venv_no_redirect.py (45 LOC)

**Purpose:** PreToolUse Bash hook blocking `venv/bin/python <script>.py` calls that have no `>` redirect or `| tee`, since unredirected dev-script output floods the context window.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message with the required form) on violation; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_worker_spawn_placement.py (91 LOC)

**Purpose:** PreToolUse Bash hook blocking `worker-cli spawn` calls that target a git root other than the current session's project, or that pass `--no-worktree`; skips entirely when the session itself runs from inside a worktree.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`); `os.getcwd()` (project-root resolution and worktree skip).
**Writes:** stderr (multi-line block message naming the allowed form) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_worker_send_background.py (51 LOC)

**Purpose:** PreToolUse Bash hook blocking `worker-cli send` dispatched with `run_in_background=true`, since send is a fire-once action that risks SIGTERM-kill (silent message loss) or racing the next orchestrator action if backgrounded.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`, `tool_input.run_in_background`).
**Writes:** stderr (block message with the fix) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_worker_kill_while_working.py (86 LOC)

**Purpose:** PreToolUse Bash hook blocking `worker-cli kill <name>` when a live `worker-cli status <name>` call reports the worker as `working`; double-gated (regex name capture + live status) so a kill right after a worker finishes is never falsely blocked.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`); `worker-cli status <name>` output (subprocess, 3s timeout, resolved by `shutil.which` then a plugin-cache glob fallback).
**Writes:** stderr (block message naming the worker) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`; `dev/hook_smoke/test_block_worker_kill_while_working.py` imports `decide()` directly.

---

### block_worker_send_while_working.py (86 LOC)

**Purpose:** Sibling of `block_worker_kill_while_working.py` applied to `worker-cli send` instead of `kill` — blocks `worker-cli send <name>` when a live `worker-cli status <name>` call reports the worker as `working`; same double-gate, code duplicated rather than shared per this hook family's convention of small, independent scripts.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`); `worker-cli status <name>` output (subprocess, 3s timeout, same resolution as the kill guard).
**Writes:** stderr (block message naming the worker) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`; `dev/hook_smoke/test_block_worker_send_while_working.py` imports `decide()` directly.

---

### block_manual_worker_cleanup.py (52 LOC)

**Purpose:** PreToolUse Bash hook blocking raw worker-cleanup commands that bypass `worker-cli kill <name>` and leave orphaned state: `tmux kill-session -t worker-*` and a direct `git worktree remove` on a worktree path; `git branch -D` is deliberately not policed since worker branches carry no distinguishing prefix.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message with the `worker-cli kill` alternative) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_po_read.py (67 LOC)

**Purpose:** PreToolUse Bash hook blocking shell reads (head/tail/grep/sed/awk/cut/less/more/cat/split/dd/etc.) that target a Claude Code persisted-output export path (contains `/.claude/`, ends `.txt`), which must be consumed via the Read tool to avoid acting on a partial result.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message naming the Read-tool paging escape) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_pipe_scraper_isolated.py (79 LOC)

**Purpose:** PreToolUse Bash hook blocking `python -m src.crawler.pipe_scraper` calls that share the invocation with anything besides shell assignments and a `cd`, or that contain command/process substitution, so the long-running scraper call can auto-background instead of blocking a worker on a chained poll.
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message) on violation; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_rag_cli_document_repeat.py (165 LOC)

**Purpose:** Stateful PreToolUse Bash hook blocking the 2nd (or later) single-document `rag-cli index`/`rag-cli delete --collection X --document Y` call to the same `(subcommand, collection)` within a 10-minute rolling window, across separate Bash invocations of the same session — a single one-off `--document` call always passes.
**Reads:** stdin (PreToolUse JSON: `session_id`, `tool_input.command`); `src/logs/rag_doc_repeat_state.jsonl` (own state, read-modify-write each call).
**Writes:** stderr (block message naming the collection-wide escape) on the 2nd+ call; `src/logs/rag_doc_repeat_state.jsonl` (rewritten in full each call — self-pruning to the 600s window, not append-only on disk).
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### block_busywait_loop.py (50 LOC)

**Purpose:** PreToolUse Bash hook blocking `while`/`until <status-check>; do sleep N; done` polling loops (a status/process/log check in the condition, a bare sleep as the only loop body).
**Reads:** stdin (PreToolUse JSON: `tool_input.command`).
**Writes:** stderr (block message) on match; exit 2.
**Called by:** Claude Code hook system, registered by `hook_setup.py`.

---

### hook_setup.py (211 LOC)

**Purpose:** Idempotent installer — registers every entry in `_HOOK_SCRIPTS` into the user-level Claude Code settings file, sweeping stale `python3 <missing-path>` entries first, and gating each script's install on being both committed on `main` and present in the current working tree.
**Reads:** the user-level Claude Code settings file (JSON); local `main`-branch git state (`git rev-parse`, `git cat-file -e`); working-tree filesystem (`os.path.exists`).
**Writes:** the user-level Claude Code settings file (atomic write via temp file + `os.replace()`).
**Called by:** run manually (`python3 src/hooks/hook_setup.py`, must run from the main repo root — a worktree guard exits 2 otherwise); `.githooks/post-merge` and `.githooks/post-commit` auto-run it when a commit touches `src/hooks/`; `dev/hook_smoke/test_hook_setup_main_branch_gate.py` imports `decide_entries()` directly.
**Calls out:** `git` CLI (subprocess, not a package import).

---

## State

- `_fire_log.py` owns `src/logs/hook_firing.jsonl` — append-only, written by every active hook at its decision point, read by nothing in this directory (external FP/incident analysis only).
- `block_rag_cli_document_repeat.py` owns `src/logs/rag_doc_repeat_state.jsonl` — read-modify-write on every qualifying call, self-pruned to a 600s window, keyed by `(session_id, "<subcommand>:<collection>")`.
- `hook_setup.py` owns the user-level Claude Code settings file (hook registration) — the only module in this directory that writes it; every other hook only reads its own stdin payload.

## Gotchas

- **Fail-open is mandatory.** Every hook exits 0 on any parse error or missing field — a hook must never block a legitimate tool call due to its own failure.
- **Hook timeout is 5s** (`_HOOK_TIMEOUT` in `hook_setup.py`). Hooks fire for every matching tool call across every Claude Code session on this machine (main sessions and workers) — keep new hooks fast and narrowly scoped.
- **`log_fire` decision values:** only `"block"` (exit 2 + stderr, `reason` field) and `"rewrite"` (exit 0 + updatedInput, `rewritten` field) are used by any current module; a third value `"ui-notice"` is reserved and unused. Filter it out of any fire-log analysis with `jq 'select(.decision != "ui-notice")'`.
- **PreToolUse exit codes:** 0 = allow, 2 = block (stderr shown to the model as the block reason), 1 = hook error (logged, not treated as a block).
- **Stale hooks block ALL Bash calls machine-wide.** A registered `python3 <path>` entry whose file no longer exists exits non-zero on every invocation, which Claude Code treats as a block — every Bash command in every session fails until fixed. Recovery: re-run `hook_setup.py` from the main repo root from a real terminal (not Claude Code's own Bash tool, since Bash is what's blocked); its stale-hook sweep runs before the add-loop.
- **`hook_setup.py` writes absolute paths.** Moving the repo checkout requires re-running `hook_setup.py` to refresh the registered paths; the sweep removes the old ones automatically.
- **Per-clone setup:** each clone must run `git config core.hooksPath .githooks` once (local config, not committed) for `.githooks/post-merge`/`post-commit` to auto-run `hook_setup.py` on commits touching `src/hooks/`. Without it, a merged hook script is not auto-registered.
- **Subprocess hooks must resolve plugin CLIs by absolute path, never by bare name.** Claude Code's hook execution environment has a stripped PATH that excludes local bin and plugin-cache bin directories; a bare `subprocess.run(['worker-cli', ...])` raises `FileNotFoundError`, which the fail-open catch turns into a silent no-fire. `block_worker_kill_while_working.py` and `block_worker_send_while_working.py` resolve via `shutil.which` first, then a glob fallback over the plugin-cache bin directory under the user's home — follow the same pattern for any new subprocess-invoking hook.
