# src/hooks/

## Role

Global CC safety hooks — PreToolUse scripts that intercept Bash, Edit, and Read tool calls and block known-destructive patterns before execution. Registered in `~/.claude/settings.json` (global, fires for ALL projects on this machine, not just Monitor_CC). Each hook script reads CC's JSON payload from stdin and exits 0 (allow) or 2 (block, stderr shown to user).

Design rationale and statistics: `decisions/OldThemes/tool_use_safety/2026-05-12_session_findings.md`.

## Public Interface

Each hook script is a standalone `python3 <script>.py` entry invoked by CC. Not imported by any module. Install via `hook_setup.py` (run once).

## Modules

### block_dangerous_kill.py (238 LOC)

**Purpose:** PreToolUse hook — blocks `pkill -f <pattern>` and `ps|grep|kill` pipe chains. Both patterns target processes via text substring matching against the full cmdline, which routinely kills unintended processes (CC worker sessions whose prompt text contains the matched string). Exits 2 + stderr with concrete safer alternatives. Exits 0 on any parse/internal error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with alternatives) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:**
- `pkill -f <anything>` — cmdline-substring matching, kills worker prompts
- `ps ... | ... grep ... | ... kill ...` — same problem via pipe chain

**Allowed patterns (not blocked):** `pkill -x <name>` (exact), `pkill <name>` (name-only), `kill <numeric_pid>`, `kill -<signal> <numeric_pid>`, `worker-cli kill <name>`, `launchctl bootout/kickstart`.

**Quote/heredoc stripping.** Before regex matching, `_strip_non_shell_active()` (same scanner as `block_chained_sleep.py`) removes heredoc bodies, single-quoted, double-quoted, and ANSI-C `$'...'` regions from the command string. Command substitutions `$(...)` and backtick expressions are kept shell-active. Eliminates false-positives where `pkill -f` appears as literal text inside heredoc bodies (test scaffolding, `bd comments add` session notes, Python string literals).

---

### block_chained_sleep.py (228 LOC)

**Purpose:** PreToolUse hook — blocks any `sleep <N>` token in a Bash command that is NOT the exact canonical orchestration timer form `sleep N && echo done`. Chained forms (`cmd; sleep N && echo done`, `sleep N && other_cmd`, poll loops) are rejected because the menubar auto-abort sends SIGTERM to the sleep PID, which exits the entire chained shell with code 143 and destroys pre-sleep output. Exits 2 + stderr with the canonical form and reason. Exits 0 on any parse/internal error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with canonical form) on violation only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:**
- `cmd_before; sleep N && echo done` — commands chained BEFORE the sleep
- `sleep N && other_cmd` — commands chained AFTER the sleep (non-`echo done` continuation)
- `until ...; do sleep N; done` and other loop forms

**Allowed patterns:**
- `sleep N && echo done` (optional leading/trailing whitespace, optional float N) — the one canonical timer form

**Quote/heredoc stripping.** Before `_SLEEP_TOKEN` matching, `_strip_non_shell_active()` runs a single-pass character scanner that replaces heredoc bodies, single-quoted strings, double-quoted strings, and ANSI-C `$'...'` quotes with spaces. Command substitutions `$(...)` and backtick expressions are kept shell-active so `sleep` inside them still triggers a block. Fail-open: any parse error (unclosed quote, heredoc without terminator) returns the original string unmodified. Smoke: `dev/hook_smoke/test_block_chained_sleep.py` (13 cases).

---

### block_unauthorized_background.py (56 LOC)

**Purpose:** PreToolUse hook — blocks any Bash command dispatched with `run_in_background=true` that is NOT the exact canonical orchestration timer `sleep N && echo done`. Background mode hides stdout/stderr until completion, making long-running tools (rag-cli, python scripts, builds) unmonitorable. Exits 2 + stderr with the canonical form and reason. Exits 0 on any parse/internal error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command, run_in_background}}`).
**Writes:** stderr (block message with canonical form) on violation only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:**
- Any command with `run_in_background=true` that is NOT `sleep N && echo done`
- Examples: `rag-cli update_docs .`, `python3 script.py`, build commands, test runners

**Allowed patterns:**
- `sleep N && echo done` (optional leading/trailing whitespace, optional float N) with `run_in_background=true`
- Any command with `run_in_background=false` or field absent (foreground — no restriction)

**No quote-stripping.** Checks only the `run_in_background` bool field and the canonical regex — no command-text scanning for partial patterns.

---

### block_broad_grep.py (82 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks recursive `grep -r`/`-R` calls on directories when no `--include=` scope is present. Unrestricted recursive grep matches JSONL logs, node_modules, and vendored content, producing 10MB+ output that floods the context window. Exits 2 + stderr with fix options. Exits 0 on any parse/internal error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with fix options) on violation only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:**
- `grep -rn <pattern> <dir>` without `--include=` where last arg is not a specific file
- `grep -R <pattern> .` and similar broad recursive scans

**Allowed patterns:**
- `grep -rn pattern src/ --include='*.py'` — has `--include` scope
- `grep -rn pattern workflow.py` — last arg is a specific file (ends in known extension)
- `grep -n pattern file.py` — no recursive flag
- `git grep -r ...` — git grep uses gitignore, exempted

**No quote-stripping.** Extracts the grep segment up to the first pipe/chain operator; skips `git grep`. False-positive risk near zero for the scoped forms above.

---

### block_noop_edit.py (42 LOC)

**Purpose:** PreToolUse hook (Edit) — blocks Edit calls where `old_string == new_string`. CC rejects these with "No changes to make: old_string and new_string are exactly the same" — the hook surfaces this before the round-trip. Exits 2 + stderr. Exits 0 on any parse/internal error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {old_string, new_string}}`).
**Writes:** stderr (block message with re-read advice) on violation only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Edit entry). Never imported.
**Calls out:** stdlib only (`json`).

**Blocked patterns:** any Edit where `old_string` and `new_string` are identical non-None strings.

**Allowed patterns:** any Edit with different strings; missing/non-string fields (fail-open).

---

### block_read_directory.py (45 LOC)

**Purpose:** PreToolUse hook (Read) — blocks Read calls where `file_path` points to a directory. CC rejects these with "Read tool cannot read directories" — the hook surfaces this before the round-trip and suggests `ls` instead. Exits 2 + stderr. Exits 0 on any parse/internal error or nonexistent path (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {file_path}}`).
**Writes:** stderr (block message with `ls` alternative) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Read entry). Never imported.
**Calls out:** stdlib only (`json`, `os`).

**Blocked patterns:** `file_path` resolves to an existing directory (`os.path.isdir`).

**Allowed patterns:** file paths, nonexistent paths, missing/non-string field (all fail-open).

---

### block_read_oversize.py (57 LOC)

**Purpose:** PreToolUse hook (Read) — blocks Read calls on files >256KB when no `offset`, `limit`, or `pages` parameter is provided. CC rejects reads above 256KB with a size error — the hook surfaces this before the round-trip and suggests `grep` + targeted Read. Exits 2 + stderr with file size and fix. Exits 0 on any parse/stat error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {file_path, offset?, limit?, pages?}}`).
**Writes:** stderr (block message with grep + offset/limit fix) on violation only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Read entry). Never imported.
**Calls out:** stdlib only (`json`, `os`).

**Blocked patterns:** `file_path` is an existing file >256KB AND none of `offset`/`limit`/`pages` present in `tool_input`.

**Allowed patterns:** file ≤256KB; offset/limit/pages present (user already scoped); nonexistent file; stat error (all fail-open).

---

### block_read_worktree.py (65 LOC)

**Purpose:** PreToolUse hook (Read) — blocks Read calls on files inside `.claude/worktrees/` that are NOT inside the calling session's own worktree. Reading another session's worktree via the Read tool re-injects CLAUDE.md into context (context bloat / duplicate system prompt). Workers reading their own worktree files are allowed. Exits 2 + stderr with Bash alternatives (`cat`, `head`, `git -C <wt> show`). Exits 0 on any parse/internal error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {file_path}}`).
**Writes:** stderr (block message with Bash alternatives) on foreign-worktree match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Read entry). Never imported.
**Calls out:** stdlib only (`json`, `os`).

**Blocked patterns:** `file_path` contains `.claude/worktrees/` AND path is NOT under the current session's own worktree root (determined via `os.getcwd()`).

**Allowed patterns:** file_path outside any worktree; file_path inside the calling session's own worktree; main-session reads of non-worktree paths; parse errors (fail-open).

**Own-worktree detection.** Hook subprocess inherits the CC session's CWD. If CWD contains `.claude/worktrees/`, extract `<project>/.claude/worktrees/<name>` as the worktree root. Files starting with this root are own-worktree reads → allowed. Main sessions (no worktree in CWD) always produce block for worktree paths. `os.getcwd()` equality to session CWD confirmed empirically.

---

### block_bd_cli_worker.py (69 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks `bd` CLI invocations from inside a worker session (worktree CWD). Workers running `bd` commands write bead data to the worktree's `.beads/` copy, silently corrupting main-repo bead state on merge or worktree removal. Exits 2 + stderr. Exits 0 when not running from a worktree or on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`, `os`).

**Blocked patterns:** any Bash command containing `bd <subcommand|flag>` when `os.getcwd()` contains `.claude/worktrees/`.

**Allowed patterns:** any `bd` call from outside a worktree (main session); quoted `bd` examples in strings; non-`bd` commands; parse errors (fail-open).

---

### block_cd_drift.py (77 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks Bash commands that `cd` into a `.claude/worktrees/` path without `cd`-ing back at the end of the chain. Bash tool calls share CWD across invocations; a dangling worktree `cd` causes the next call to write to the wrong tree. Exits 2 + stderr with the fix. Exits 0 when the last `cd` target is not a worktree path, or on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with fix alternatives) on violation only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`, `os`).

**Blocked patterns:** command contains a `cd .claude/worktrees/...` target AND that worktree path is the LAST `cd` target (no cd-back).

**Allowed patterns:** `cd <worktree> && ... && cd <main-repo>` (cd-back at end); commands with no worktree `cd`; calls from inside a worktree (workers live there — hook skips entirely); parse errors (fail-open).

---

### block_dev_imports_src.py (62 LOC)

**Purpose:** PreToolUse hook (Write + Edit) — blocks dev/ scripts that import from `src/`. dev/ modules are self-contained pipeline probes; importing from `src/` breaks isolation and makes dev/ non-runnable without the full production tree. Fires on Write and Edit for files under a `dev/` path. Exits 2 + stderr. Exits 0 on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {file_path, content|new_string}}`).
**Writes:** stderr (block message with fix) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Write and PreToolUse/Edit entries). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:** Write or Edit where `file_path` matches `/dev/` AND the written content contains `^from src\.` or `^import src\.`.

**Allowed patterns:** files outside `dev/`; dev/ files without `src/` imports; parse errors (fail-open).

---

### block_except_pass.py (60 LOC)

**Purpose:** PreToolUse hook (Write + Edit) — blocks code that contains bare `except ...: pass` (silent exception swallow). Silently swallowing exceptions is prohibited — scripts must fail visibly when they cannot fulfill their purpose. Fires on Write and Edit for any file. Exits 2 + stderr with allowed alternatives. Exits 0 on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {content|new_string}}`).
**Writes:** stderr (block message with alternatives) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Write and PreToolUse/Edit entries). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:** `except [OptionalType]:\n    pass` — any bare exception-swallow block in written content.

**Allowed patterns:** `except ... : raise`; `except ... as e: logger...; raise`; `finally: resource.close()`; parse errors (fail-open).

---

### block_git_add_deps.py (66 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks `git add` commands that target dependency directories (`venv/`, `.venv/`, `node_modules/`). In worktrees these directories are symlinks pointing to the main repo; staging them creates circular self-references on merge. Exits 2 + stderr. Exits 0 on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:** `git add` (with optional `-C path`) where command also contains `venv/`, `.venv/`, or `node_modules/` as a target.

**Allowed patterns:** `git add` targeting specific files; `git add .` without a dependency directory in scope (no explicit dep target in the command); parse errors (fail-open).

---

### block_git_destructive.py (96 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks destructive git operations: `git commit --amend`, `git push --force`/`-f`/`--force-with-lease`, `git commit/push --no-verify`, `git commit --allow-empty`, and `git config` modifications (read-only config variants allowed). Enforces the Git Safety Protocol from `tool-use.md`. Exits 2 + stderr with the specific violation and a suggestion. Exits 0 on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with label + suggestion) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:**
- `git commit --amend`
- `git push --force` / `--force-with-lease` / `-f`
- `git commit|push --no-verify`
- `git commit --allow-empty`
- `git config` (modify — write operations); read-only flags (`--list`, `--get`, `--show-origin`, etc.) are exempt

**Allowed patterns:** `git commit` (without `--amend`/`--no-verify`/`--allow-empty`); `git push` (without force flags); `git config --list|--get|...` (read-only); parse errors (fail-open).

---

### block_path_typo.py (82 LOC)

**Purpose:** PreToolUse hook (Bash + Read + Write + Edit) — blocks commands or file paths containing known path typos: `.claire/` (tokenizer misspelling of `.claude/`) and `..letter` (double-dot immediately followed by a lowercase letter, e.g. `..claude/`, `..src/`). Fires for all four tool types, inspecting `command` (Bash) or `file_path` (Read/Write/Edit). Exits 2 + stderr with the specific typo class. Exits 0 on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command|file_path}}`).
**Writes:** stderr (typo-specific block message) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash, PreToolUse/Read, PreToolUse/Write, and PreToolUse/Edit entries). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:**
- `.claire/` anywhere in command or file_path (after quote-stripping)
- `..letter` — two dots immediately followed by a lowercase letter in a path context (`^`, `/`, whitespace, `=` prefix)

**Allowed patterns:** `.claude/` (correct spelling); `../` (valid parent traversal); quoted strings containing the typo pattern; parse errors (fail-open).

---

### block_venv_no_redirect.py (53 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks `./venv/bin/python <script>.py` calls that have no file redirect (`> file`) or `| tee`. Dev scripts produce verbose output that floods the context window; redirecting to `/tmp/` is mandatory (Rule 4, `tool-use.md`). Exits 2 + stderr with the required form. Exits 0 when redirect/tee present, or on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with required form) on violation only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:** `./venv/bin/python <anything>.py` (or `venv/bin/python ...`) without `> <file>` or `| tee` in the command.

**Allowed patterns:** command includes `> /tmp/file.md` or `| tee /tmp/file.md`; commands not matching the venv-python-script pattern; parse errors (fail-open).

---

### block_worker_spawn_opus.py (47 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks `worker-cli spawn` calls that specify `opus` as the model argument. Workers are always Sonnet; using Opus as a worker burns ~20–40× billing per token and eliminates the cross-model verification benefit. Exits 2 + stderr with the correct form. Exits 0 on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with correct model form) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:** `worker-cli spawn ... opus` — `opus` appearing anywhere after the `spawn` subcommand.

**Allowed patterns:** `worker-cli spawn <name> <prompt> <path> sonnet`; `worker-cli spawn` with no model (default = sonnet); parse errors (fail-open).

---

### hook_setup.py (98 LOC)

**Purpose:** One-shot idempotent installer — adds `PreToolUse` entries to `~/.claude/settings.json` for each hook script, with per-hook matcher (`Bash`, `Edit`, or `Read`). Loops over `_HOOK_ENTRIES` (tuples of command + matcher); skips any entry already present by exact command string. Atomic write via temp + `os.replace`. Supports all 17 current hooks across 3 matchers.
**Reads:** `~/.claude/settings.json`.
**Writes:** `~/.claude/settings.json` (atomic via temp + `os.replace()`).
**Called by:** User manually (`python3 src/hooks/hook_setup.py` from Monitor_CC root). Never imported.
**Calls out:** stdlib only (`json`, `os`, `pathlib`).

**Usage:** `python3 src/hooks/hook_setup.py` — run once after clone or reinstall. Installs all hooks in `_HOOK_SCRIPTS`. Restart CC to activate.

---

## Gotchas

- **Fail-open is mandatory.** All hooks exit 0 on any parse error or missing field — a hook must never block a legitimate tool call due to its own failure. A broken hook that blocks everything is a footgun.
- **Global registration.** Bash hooks fire for every Bash call; Edit hooks for every Edit call; Read hooks for every Read call — across all CC sessions on this machine (main sessions and workers). Keep hooks fast and narrowly scoped. Current timeout: 5s (set in `hook_setup.py`).
- **Absolute path in settings.json.** `hook_setup.py` writes the full resolved path of each hook script at install time. If the repo is moved, re-run `hook_setup.py` to update the paths.
- **`block_chained_sleep.py` strips non-shell-active regions before matching.** Heredoc bodies, single/double-quoted strings, and ANSI-C quotes are replaced with spaces before the `_SLEEP_TOKEN` regex runs. `$(...)` and backtick expressions are kept active. False-positive on `echo "sleep 5"` or heredoc-body sleeps no longer fires.
- **Cache-bust on settings.json edit.** Editing `~/.claude/settings.json` busts CC's prompt cache — full message rebuild on the next request. Expected cost; CC must be restarted anyway to pick up the hook.
- **PreToolUse exit codes.** Exit 0 = allow, exit 2 = block (CC shows stderr to user as the block reason), exit 1 = hook error (CC logs but does not block). This hook uses exit 2 on block, exit 0 on allow and on hook-internal errors.
- **`block_read_worktree.py` allows own-worktree reads.** Workers reading files in their own worktree via absolute path are now allowed. Cross-worktree reads (worker→other-worker) and main-session→worktree reads remain blocked.
