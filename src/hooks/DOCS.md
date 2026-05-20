# src/hooks/

## Role

Global CC safety hooks — PreToolUse scripts that intercept Bash, Edit, and Read tool calls and block known-destructive patterns before execution. Registered in `~/.claude/settings.json` (global, fires for ALL projects on this machine, not just Monitor_CC). Each hook script reads CC's JSON payload from stdin and exits 0 (allow) or 2 (block, stderr shown to user).

Design rationale and statistics: `decisions/OldThemes/tool_use_safety/2026-05-12_session_findings.md`.

## Public Interface

Each hook script is a standalone `python3 <script>.py` entry invoked by CC. Not imported by any module. Install via `hook_setup.py` (run once).

## Modules

### block_dangerous_kill.py (86 LOC)

**Purpose:** PreToolUse hook — blocks `pkill -f <pattern>` and `ps|grep|kill` pipe chains. Both patterns target processes via text substring matching against the full cmdline, which routinely kills unintended processes (CC worker sessions whose prompt text contains the matched string). Exits 2 + stderr with concrete safer alternatives. Exits 0 on any parse/internal error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with alternatives) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:**
- `pkill -f <anything>` — cmdline-substring matching, kills worker prompts
- `ps ... | ... grep ... | ... kill ...` — same problem via pipe chain

**Allowed patterns (not blocked):** `pkill -x <name>` (exact), `pkill <name>` (name-only), `kill <numeric_pid>`, `kill -<signal> <numeric_pid>`, `worker-cli kill <name>`, `launchctl bootout/kickstart`.

**Quote-aware matching.** Patterns must appear at command start OR after a shell separator (`;`, `&`, `|`, newline) — substrings inside `"..."` or `'...'` quoted arguments are stripped before regex match (`_strip_quoted` helper). Prevents the false-positive where a `bd comments add "...pkill -f..."` command (writing the pattern as text into a bead) gets blocked. Not a full shell parser; handles balanced quotes with simple backslash-escape.

---

### block_chained_sleep.py (57 LOC)

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

**No quote-stripping.** Unlike `block_dangerous_kill.py`, this hook does not strip quoted substrings before matching. The word-boundary regex (`\bsleep\s+\d+(?:\.\d+)?\b`) avoids false positives on substrings like `overslept`, but `echo "sleep 5 ..."` where the number appears inside a quoted argument would technically fire. No realistic CC workflow echoes a sleep command with a number inside a string argument, so this is an acceptable simplification.

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

### hook_setup.py (80 LOC)

**Purpose:** One-shot idempotent installer — adds `PreToolUse` entries to `~/.claude/settings.json` for each hook script, with per-hook matcher (`Bash`, `Edit`, or `Read`). Loops over `_HOOK_ENTRIES` (tuples of command + matcher); skips any entry already present by exact command string. Atomic write via temp + `os.replace`. Supports all 7 current hooks across 3 matchers.
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
- **`block_chained_sleep.py` has no quote-stripping.** The word-boundary regex avoids `overslept`-style substrings but does not strip quoted arguments before matching. `echo "sleep 5 ..."` (number inside a quoted arg) would fire. Acceptable — no realistic CC workflow hits this.
- **Cache-bust on settings.json edit.** Editing `~/.claude/settings.json` busts CC's prompt cache — full message rebuild on the next request. Expected cost; CC must be restarted anyway to pick up the hook.
- **PreToolUse exit codes.** Exit 0 = allow, exit 2 = block (CC shows stderr to user as the block reason), exit 1 = hook error (CC logs but does not block). This hook uses exit 2 on block, exit 0 on allow and on hook-internal errors.
