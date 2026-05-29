# src/hooks/

## Role

Global CC safety hooks — PreToolUse scripts that intercept Bash, Edit, and Read tool calls and either **block** known-destructive patterns or **silently rewrite** known-broken patterns before execution. Registered in `~/.claude/settings.json` (global, fires for ALL projects on this machine, not just Monitor_CC). Each hook script reads CC's JSON payload from stdin and either exits 0 (allow / silent-rewrite via `hookSpecificOutput.updatedInput` JSON to stdout) or 2 (block, stderr shown to user).

**Two hook classes:**

- **Block hooks** (`block_*.py`) — exit 2 + stderr when detecting damage patterns (irreversible commands, context-flooding outputs). Damage-prevention only.
- **Rewrite hooks** (`rewrite_*.py` plus the recently-upgraded `block_path_typo.py`) — exit 0 + JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.{command|file_path}` containing the corrected input. Pattern-class: a broken input has a unique computable corrected form. CC v2.1+ supports this for Bash + Read + Write under `acceptEdits` mode (Issue [#47853](https://github.com/anthropics/claude-code/issues/47853) OP). Edit-Matcher exhibits an anomaly under investigation — see `decisions/OldThemes/tool_use_safety/2026-05-22_block_path_typo_edit_no_fire.md`.

Design rationale and statistics: `decisions/OldThemes/tool_use_safety/2026-05-12_session_findings.md`. Hook API capabilities and auto-rewrite conversion: `decisions/OldThemes/tool_use_safety/2026-05-22_hook_api_auto_rewrite_works.md`.

## Public Interface

Each hook script is a standalone `python3 <script>.py` entry invoked by CC. Not imported by any module. Install via `hook_setup.py` (run once).

## Modules

### _shell_strip.py (173 LOC)

**Purpose:** Shared utility — provides `_strip_non_shell_active(command)`, the position-preserving shell-region stripper used by six Bash-scanning hooks. Replaces heredoc bodies, single/double-quoted strings, and ANSI-C `$'...'` quotes with spaces of the same length before pattern matching runs. Command substitutions `$(...)` and backtick expressions are kept shell-active. Fail-open: any parse error returns the original command unchanged (never silently allows a blocked pattern due to a strip failure).
**Reads:** n/a (pure logic module, not a standalone script).
**Writes:** n/a.
**Called by:** `rewrite_chained_sleep.py`, `block_dangerous_kill.py`, `block_broad_grep.py`, `block_polling_loop.py`, `block_venv_no_redirect.py`, `block_worker_spawn_opus.py` via `sys.path` insertion + `from _shell_strip import _strip_non_shell_active`.
**Calls out:** stdlib only (no imports).

---

### _fire_log.py (44 LOC)

**Purpose:** Shared utility — provides `log_fire(hook_name, decision, tool_name, command, reason=None, rewritten=None, session_id=None)`, the single fire-event appender used by all 20 active hooks. Appends one JSON line per fire to `src/logs/hook_firing.jsonl`. For `decision="block"`: includes `reason` field (stderr text), omits `rewritten`. For `decision="rewrite"`: includes `rewritten` field (new command/path), omits `reason`. Fail-silent: any exception in the write path is swallowed so a logging failure never breaks the hook itself. Log path overridable via `MONITOR_CC_HOOK_FIRING_LOG` env var (used for test isolation in `dev/hook_smoke/`).
**Reads:** n/a (pure logic module, not a standalone script).
**Writes:** `src/logs/hook_firing.jsonl` (appends one line per fire; path resolved from `__file__` relative to `src/`).
**Called by:** all 21 active hook scripts via `sys.path` insertion + `from _fire_log import log_fire`. Called at the decision-point only (immediately before `sys.exit(2)` for blocks; immediately before `print(json.dumps(output))` for rewrites). NOT called on passthroughs.
**Calls out:** stdlib only (`json`, `os`, `datetime`).

---

### block_dangerous_kill.py (91 LOC)


**Purpose:** PreToolUse hook — blocks `pkill -f <pattern>` and `ps|grep|kill` pipe chains. Both patterns target processes via text substring matching against the full cmdline, which routinely kills unintended processes (CC worker sessions whose prompt text contains the matched string). Exits 2 + stderr with concrete safer alternatives. Exits 0 on any parse/internal error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with alternatives) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:**
- `pkill -f <anything>` — cmdline-substring matching, kills worker prompts
- `ps ... | ... grep ... | ... kill ...` — same problem via pipe chain

**Allowed patterns (not blocked):** `pkill -x <name>` (exact), `pkill <name>` (name-only), `kill <numeric_pid>`, `kill -<signal> <numeric_pid>`, `worker-cli kill <name>`, `launchctl bootout/kickstart`.

**Allowlist (`_PKILL_F_ALLOWLIST`):** explicit literal strings for `pkill -f` arguments that are safe to pass through. Checked against original (un-stripped) command via `_PKILL_F_ARG_RE` (handles single-quoted, double-quoted, unquoted). Conservative: any non-allowlisted `pkill -f` in the same command still blocks. Current entries: `"dolt sql-server"` (bd Beads SQL backend — bd's orphan-cleanup SIGKILLs any process with this cmdline string, making it impossible for a worker to carry it).

**Quote/heredoc stripping.** Before regex matching, `_strip_non_shell_active()` (imported from `_shell_strip.py`) removes heredoc bodies, single-quoted, double-quoted, and ANSI-C `$'...'` regions from the command string. Command substitutions `$(...)` and backtick expressions are kept shell-active. Eliminates false-positives where `pkill -f` appears as literal text inside heredoc bodies (test scaffolding, `bd comments add` session notes, Python string literals).

---

### block_polling_loop.py (132 LOC)

**Purpose:** PreToolUse hook — stateful frequency-based polling loop detector. Extracts a target fingerprint from each Bash command (`ps -p <N>` → `"pid:N"`, `tail -<N> <file>` → `"file:path"`), records it with timestamp and session_id in `src/logs/polling_state.jsonl`, and blocks when ≥ 3 polls hit the SAME target within 30 s in the SAME session. First and second polls always pass. Third poll in 30 s blocks. Different targets, different sessions, and one-off checks are never blocked. Exits 2 + stderr on threshold. Exits 0 on any parse or I/O error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`); `src/logs/polling_state.jsonl` (state).
**Writes:** stderr (one-line block message) on threshold; `src/logs/polling_state.jsonl` (appends + rewrites for self-pruning).
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`, `os`, `datetime`).

**Fingerprint forms:** `"pid:<N>"` from `ps -p <N>`; `"file:<path>"` from `tail -<N> <path>` (BSD short numeric form only; `tail -n N` long form not detected). First match wins.

**State schema:** `{ts: "2026-05-29T12:34:56Z", session_id: str, target: str}` — one JSONL line per poll invocation. Self-pruning: on each call, entries older than 30 s are pruned before writing back. monitor-24h backup sweep via `log_janitor` (`sweep_eligible=True`). Path overridable via `MONITOR_CC_POLLING_STATE` env var for test isolation.

**Concurrency note:** concurrent sessions writing simultaneously can cause one entry to be lost (under-count — never over-count). Acceptable: per-session keying means session B's polls never inflate session A's count. Documented in code.

**Allowed patterns:** `ps -p <PID>` alone (one-off); `tail -<N> file` alone (one-off); either appearing once or twice in 30 s; `tail -n N` long form; patterns in quoted strings or heredoc body.

**Antipattern context:** `block_unauthorized_background` blocks `run_in_background=true`, but workers can circumvent via shell `cmd &`. This hook catches the repeated-check pattern regardless of how the background was started.

**Quote/heredoc stripping.** `_strip_non_shell_active()` removes heredoc bodies and quoted regions before fingerprint extraction — prevents counting a `ps -p` example in a `worker-cli send` message.

**Smoke:** `dev/hook_smoke/test_block_polling_loop.py` (15 cases: frequency 3-poll sequence, different-target, single-check, no-target, session-isolation groups).

---

### block_chained_sleep.py.disabled

**Disabled 2026-05-24** — superseded by `rewrite_chained_sleep.py`. Renamed via `git mv` (file still in repo for history). Previously blocked all non-canonical `sleep N` chains. Replaced by a rewrite hook that strips trivial-sync sleeps (`echo`, `true` cmd_before) and passes load-bearing patterns through. See `decisions/OldThemes/hook_false_positives/sleep_pattern_audit_2026-05-24.md` for audit rationale.

---

### rewrite_chained_sleep.py (131 LOC)

**Purpose:** PreToolUse hook (Bash) — **rewrites** chained `sleep N` by stripping it when the immediately-preceding command is trivial-sync (`echo`, `true`). Sleep-first chains, load-bearing predecessors (`kill`, `pkill`, `launchctl`, `tmux`, etc.) and loop-body sleeps are passed through unchanged (no-op). Exits 0 in all cases (fail-open rewrite hook — never blocks). Uses `_shell_strip._strip_non_shell_active` for position-preserving heredoc + quote removal before tokenizing.
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stdout (JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.command`) when sleep(s) were stripped; nothing when no-op.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (same-dir import via `sys.path` insert).

**Strip condition (ALL must hold):**
1. A chain operator (`&&`, `||`, `;`) immediately precedes `sleep N` (only whitespace between op and sleep)
2. First token of the segment before that operator is in `_TRIVIAL = {'echo', 'true'}`
3. Sleep is NOT inside a `for|while|until ... done` span

**Pass-through (no-op) conditions:**
- Sleep-first chain (no preceding chain op) — intent is timing
- `cmd_before` not in `_TRIVIAL`
- Sleep inside loop body

**Smoke:** `dev/hook_smoke/test_rewrite_chained_sleep.py` (8 cases: 3 positive strip, 5 negative no-op).

---

### rewrite_rag_cli_search_noise.py (~95 LOC)

**Purpose:** PreToolUse hook (Bash) — **rewrites** `rag-cli search_hybrid` invocations by stripping downstream noise inside the logical command segment: pipes (`| head`, `| tail`, `| grep`, etc.), redirects (`>`, `>>`, `&>`, `<`, `2>&1`, `2>`), and single backgrounding `&`. Chains around the segment (`cd && rag-cli ...`, `rag-cli ... ; bd list`, `rag-cli ... || echo fail`) are preserved — only the rag-cli segment is cleaned. Scope is `search_hybrid` only; `read_document`, `list_collections`, `server`, etc. pass through unchanged. Exits 0 in all cases (fail-open rewrite hook — never blocks). Uses `_shell_strip._strip_non_shell_active` for position-preserving heredoc + quote removal before tokenizing.
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stdout (JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.command`) when noise was stripped; nothing when no-op.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (same-dir import via `sys.path` insert).

**Strip mechanic:**
1. Find `\brag-cli\s+search_hybrid\b` matches in the shell-stripped command.
2. For each match, determine its segment-end by scanning forward for `;`, `&&`, `||`, `)`, `\n`, or single `&` (not part of `&&`, `&>`, or `2>&1`).
3. Within `[match_end, segment_end)`, find the first noise marker (`|` excluding `||`, any redirect, or `2>&1`).
4. Strip from the noise marker through segment-end. If segment-end equals end-of-command, also eat leading whitespace before the noise (avoids trailing-space artifact); otherwise preserve it as separator to the trailing chain.

**Pass-through (no-op) conditions:**
- `rag-cli search_hybrid` invocation has no pipe/redirect inside its segment
- `rag-cli` subcommand is not `search_hybrid` (out of scope)
- `rag-cli search_hybrid` token appears inside a quoted string (blanked by `_strip_non_shell_active`)

**Smoke:** `dev/hook_smoke/test_rewrite_rag_cli_search_noise.py` (15 cases: 9 positive strip, 6 negative no-op).

---

### rewrite_reddit_index_background.py (67 LOC)

**Purpose:** PreToolUse hook (Bash) — **silently rewrites** invocations of the reddit RAG-indexer CLI (`reddit-cli index_subreddits` or `python cli.py index_subreddits`) by flipping `run_in_background` to `true` via `hookSpecificOutput.updatedInput`. The indexer takes ~75-100s wallclock per typical query (4 subs × 5 posts × ~1.1s/chunk Embedding-Latenz) which is too long for blocking Bash. Pairs with the `_INDEXER_CANONICAL` whitelist in `block_unauthorized_background.py` so the bg-flip survives the round-trip. Exits 0 in all cases (fail-open rewrite hook — never blocks). Uses `_shell_strip._strip_non_shell_active` for position-preserving heredoc + quote removal before pattern matching.
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command, run_in_background}}`).
**Writes:** stdout (JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.{command, run_in_background: true}`) when indexer CLI detected and rb not already true; nothing on passthrough.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (same-dir import via `sys.path` insert).

**Rewrite condition:** `run_in_background != true` AND command contains `\b(reddit-cli|cli\.py)\s+index_subreddits\b` after quote-stripping.

**Passthrough (no output):**
- Command already has `run_in_background=true` (nothing to do)
- Command does not match the indexer pattern
- Indexer pattern appears only in a quoted region (e.g. inside a `worker-cli send` message)
- Parse errors (fail-open)

---

### block_unauthorized_background.py (67 LOC)

**Purpose:** PreToolUse hook — **silently rewrites** any Bash command dispatched with `run_in_background=true` that is NOT the canonical orchestration timer `sleep N && echo done` AND NOT a whitelisted long-running tool, flipping `run_in_background` to `false` via `hookSpecificOutput.updatedInput`. Background mode hides stdout/stderr until completion, making long-running tools (rag-cli, python scripts, builds) unmonitorable — but legitimately-long tools (reddit-cli indexer, RAG `workflow.py index-dir`) are exempted via the whitelist. Exits 0 in all cases (fail-open rewrite hook — never blocks). Logs `decision="rewrite"` with `rewritten="run_in_background: true → false"`.
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command, run_in_background}}`).
**Writes:** stdout (JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.{command, run_in_background: false}`) on non-canonical bg; nothing on passthrough.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Rewrite condition:** `run_in_background=true` AND command does NOT match `_CANONICAL` (the `sleep N && echo done` timer form) AND does NOT match `_INDEXER_CANONICAL` (`\b(reddit-cli|cli\.py)\s+index_subreddits\b`) AND does NOT match `_RAG_INDEXER_CANONICAL` (`\bworkflow\.py\s+index-dir\b`).

**Passthrough (no output):**
- `sleep N && echo done` (optional whitespace, optional float N) with `run_in_background=true`
- `reddit-cli index_subreddits ...` / `cli.py index_subreddits ...` with `run_in_background=true` (long-running RAG-indexer, ~75-100s; paired with `rewrite_reddit_index_background.py`)
- `workflow.py index-dir ...` with `run_in_background=true` (RAG indexer — embedding-bound, minutes; NOT auto-backgrounded, explicit per-call choice; no rewrite-pair)
- Any command with `run_in_background=false` or field absent (foreground — no restriction)
- Parse errors (fail-open)

**No quote-stripping.** Checks the `run_in_background` bool field and the three whitelisted regexes — no general command-text scanning. The `_INDEXER_CANONICAL` regex uses word-boundaries (`\b`) which match the indexer pattern even mid-command (e.g. `cd /path && reddit-cli index_subreddits ...`). Indexer pattern appearing in a quoted region of an unrelated command would also match (rare false-positive — accepted trade-off vs adding quote-stripping cost).

---

### rewrite_background_sleep.py (61 LOC)

**Purpose:** PreToolUse hook (Bash) — **rewrites** background timer commands `sleep N && echo done` where N ≠ 600 to `sleep 600 && echo done`. Pairs with `block_unauthorized_background.py` which enforces the canonical timer FORM (only `sleep N && echo done` passes the background check); this hook enforces the canonical timer VALUE (N must be 600 per `tool-use.md`). Exits 0 in all cases (fail-open rewrite hook — never blocks). No quote-stripping needed: the canonical form is fully anchored and cannot contain quoted regions.
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command, run_in_background}}`).
**Writes:** stdout (JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.command`) when N ≠ 600; nothing on passthrough.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `os`, `re`, `sys`).

**Rewrite condition (ALL must hold):**
1. `run_in_background == True`
2. Command matches `^\s*sleep\s+(\d+(?:\.\d+)?)\s*&&\s*echo\s+done\s*$`
3. Captured N: `float(N) != 600`

**Passthrough (no output):**
- `run_in_background=false` or field absent — foreground, any sleep form allowed
- `sleep 600 && echo done` with `run_in_background=true` — already canonical value
- Any non-canonical command — form guard already handled by `block_unauthorized_background.py`
- Parse errors (fail-open)

**Smoke:** `dev/hook_smoke/test_rewrite_background_sleep.py` (8 cases: 3 positive rewrite, 5 negative no-op).

---

### block_broad_grep.py (104 LOC)

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
- `grep -r foo . | head -N` — output immediately piped to `head` (bounded, no context-flood risk)

**Head-bounded exemption.** `_grep_segment()` returns `(segment, after_segment)` where `after_segment` is everything from the pipe separator onward. `_is_head_bounded(after)` checks `^\s*\|\s*head\b` — true only when `head` is the DIRECT next pipe after the grep segment, not a head elsewhere in the chain.

**Quote/heredoc stripping.** Before segment extraction, `_strip_non_shell_active()` (from `_shell_strip.py`) removes heredoc bodies and quoted regions. Prevents false-positives when a `grep -r` example appears as a literal string inside a `worker-cli send` message or `bd create` description.

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

### block_read_directory.py (43 LOC)

**Purpose:** PreToolUse hook (Read) — blocks Read calls where `file_path` points to a directory. CC rejects these with "Read tool cannot read directories" — the hook surfaces this before the round-trip and suggests `ls` instead. Exits 2 + stderr. Exits 0 on any parse/internal error or nonexistent path (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {file_path}}`).
**Writes:** stderr (block message with `ls` alternative) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Read entry). Never imported.
**Calls out:** stdlib only (`json`, `os`).

**Blocked patterns:** `file_path` resolves to an existing directory (`os.path.isdir`).

**Allowed patterns:** file paths, nonexistent paths, missing/non-string field (all fail-open).

---

### block_read_oversize.py (53 LOC)

**Purpose:** PreToolUse hook (Read) — blocks Read calls on files >256KB when no `offset`, `limit`, or `pages` parameter is provided. CC rejects reads above 256KB with a size error — the hook surfaces this before the round-trip and suggests `grep` + targeted Read. Exits 2 + stderr with file size and fix. Exits 0 on any parse/stat error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {file_path, offset?, limit?, pages?}}`).
**Writes:** stderr (block message with grep + offset/limit fix) on violation only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Read entry). Never imported.
**Calls out:** stdlib only (`json`, `os`).

**Blocked patterns:** `file_path` is an existing file >256KB AND none of `offset`/`limit`/`pages` present in `tool_input`.

**Allowed patterns:** file ≤256KB; offset/limit/pages present (user already scoped); nonexistent file; stat error (all fail-open).

---

### block_read_worktree.py (56 LOC)

**Purpose:** PreToolUse hook (Read) — blocks Read calls on files inside `.claude/worktrees/` that are NOT inside the calling session's own worktree. Reading another session's worktree via the Read tool re-injects CLAUDE.md into context (context bloat / duplicate system prompt). Workers reading their own worktree files are allowed. Exits 2 + stderr with Bash alternatives (`cat`, `head`, `git -C <wt> show`). Exits 0 on any parse/internal error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {file_path}}`).
**Writes:** stderr (block message with Bash alternatives) on foreign-worktree match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Read entry). Never imported.
**Calls out:** stdlib only (`json`, `os`).

**Blocked patterns:** `file_path` contains `.claude/worktrees/` AND path is NOT under the current session's own worktree root (determined via `os.getcwd()`).

**Allowed patterns:** file_path outside any worktree; file_path inside the calling session's own worktree; main-session reads of non-worktree paths; parse errors (fail-open).

**Own-worktree detection.** Hook subprocess inherits the CC session's CWD. If CWD contains `.claude/worktrees/`, extract `<project>/.claude/worktrees/<name>` as the worktree root. Files starting with this root are own-worktree reads → allowed. Main sessions (no worktree in CWD) always produce block for worktree paths. `os.getcwd()` equality to session CWD confirmed empirically.

---

### block_bd_cli_worker.py (62 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks `bd` CLI invocations from inside a worker session (worktree CWD). Workers running `bd` commands write bead data to the worktree's `.beads/` copy, silently corrupting main-repo bead state on merge or worktree removal. Exits 2 + stderr. Exits 0 when not running from a worktree or on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`, `os`).

**Blocked patterns:** any Bash command containing `bd <subcommand|flag>` when `os.getcwd()` contains `.claude/worktrees/`.

**Allowed patterns:** any `bd` call from outside a worktree (main session); quoted `bd` examples in strings; non-`bd` commands; parse errors (fail-open).

---

### block_cd_drift.py (71 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks Bash commands that `cd` into a `.claude/worktrees/` path without `cd`-ing back at the end of the chain. Bash tool calls share CWD across invocations; a dangling worktree `cd` causes the next call to write to the wrong tree. Exits 2 + stderr with the fix. Exits 0 when the last `cd` target is not a worktree path, or on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with fix alternatives) on violation only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`, `os`).

**Blocked patterns:** command contains a `cd .claude/worktrees/...` target AND that worktree path is the LAST `cd` target (no cd-back).

**Allowed patterns:** `cd <worktree> && ... && cd <main-repo>` (cd-back at end); commands with no worktree `cd`; calls from inside a worktree (workers live there — hook skips entirely); parse errors (fail-open).

---

### block_dev_imports_src.py (55 LOC)

**Purpose:** PreToolUse hook (Write + Edit) — blocks dev/ scripts that import from `src/`. dev/ modules are self-contained pipeline probes; importing from `src/` breaks isolation and makes dev/ non-runnable without the full production tree. Fires on Write and Edit for files under a `dev/` path. Exits 2 + stderr. Exits 0 on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {file_path, content|new_string}}`).
**Writes:** stderr (block message with fix) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Write and PreToolUse/Edit entries). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:** Write or Edit where `file_path` matches `/dev/` AND the written content contains `^from src\.` or `^import src\.`.

**Allowed patterns:** files outside `dev/`; dev/ files without `src/` imports; parse errors (fail-open).

---

### block_except_pass.py (50 LOC)

**Purpose:** PreToolUse hook (Write + Edit) — blocks code that contains bare `except ...: pass` (silent exception swallow). Silently swallowing exceptions is prohibited — scripts must fail visibly when they cannot fulfill their purpose. Fires on Write and Edit for any file. Exits 2 + stderr with allowed alternatives. Exits 0 on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {content|new_string}}`).
**Writes:** stderr (block message with alternatives) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Write and PreToolUse/Edit entries). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:** `except [OptionalType]:\n    pass` — any bare exception-swallow block in written content.

**Allowed patterns:** `except ... : raise`; `except ... as e: logger...; raise`; `finally: resource.close()`; parse errors (fail-open).

---

### block_git_add_deps.py (61 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks `git add` commands that target dependency directories (`venv/`, `.venv/`, `node_modules/`). In worktrees these directories are symlinks pointing to the main repo; staging them creates circular self-references on merge. Exits 2 + stderr. Exits 0 on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:** `git add` (with optional `-C path`) where command also contains `venv/`, `.venv/`, or `node_modules/` as a target.

**Allowed patterns:** `git add` targeting specific files; `git add .` without a dependency directory in scope (no explicit dep target in the command); parse errors (fail-open).

---

### block_git_destructive.py (97 LOC)

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

### rewrite_bd_invalid_repo.py (128 LOC)

**Purpose:** PreToolUse hook (Bash) — detects `bd --repo <path>` invocations where `<path>` does not exist OR does not contain a `.beads/` subdirectory, and **auto-rewrites** by stripping the invalid `--repo <path>` token from the command. Created 2026-05-22 commit `6b37e94` after a real incident: `bd --repo /Users/brunowinter2000/Monitor_CC create ...` (typo — actual project is under `Documents/ai/`) auto-initialized an unwanted `.beads/dolt/` at the wrong path and triggered a dolt-server port collision. The hook strips invalid `--repo` flags so bd defaults to cwd (which has `.beads/`).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stdout (single-line JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.command` + `systemMessage`) on match; nothing on passthrough.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `os`, `re`).

**Detection:** regex `_REPO_TOKEN_RE` matches `--repo /path`, `--repo=/path`, `--repo "/path with spaces"`, `--repo '/path'`. Multiple `--repo` flags in one command and chained bd commands all detected in a single regex pass.

**Path validation (per detected `--repo` arg):**
1. Skip if path contains shell metachars (`$`, `` ` ``, `\`, `*`, `?`, `{`) — unresolvable at hook time, let through.
2. Resolve `~` and absolute via `os.path.expanduser` + `os.path.abspath`.
3. Validate: `os.path.isdir(resolved)` AND `os.path.isdir(resolved + '/.beads')`. Both required — either failure marks the `--repo` invalid.

**Rewrite logic:** span-based substitution removes only the matched `--repo <path>` spans from the original command (no regex-replace, no quoting complexity). Other args, flags, redirections, pipes preserved exactly. At most a double-space remains where the token was — harmless for shell.

**Allowed (passthrough):** `bd` calls without `--repo` (uses cwd default); `bd --repo <valid-path-with-beads>`; non-bd commands; shell-meta paths (`$PROJ_ROOT` etc.); parse errors (fail-open).

**Live verification (2026-05-22):** `bd --repo /Users/brunowinter2000/Wrong/Path create --title "test" --type task` produced bead `Monitor_CC-ggh6` (correct project prefix from cwd-default), `/Users/brunowinter2000/Wrong/` not auto-initialized.

---

### block_path_typo.py (119 LOC)

**Purpose:** PreToolUse hook (Bash + Read + Write + Edit) — detects path typos `.claire/` (tokenizer typo of `.claude/`) and `..letter` (double-dot immediately followed by lowercase letter, e.g. `..claude/`, `..src/`) and **auto-rewrites** them to `.claude/` and `../letter` respectively. Upgraded 2026-05-22 commit `ce8d220` from block-and-hint to auto-rewrite. File name preserved (`block_path_typo.py`) for `~/.claude/settings.json` compatibility; internal semantics are now rewrite.
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command|file_path[+old_string,new_string,replace_all for Edit]}}`).
**Writes:** stdout (single-line JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.{command|file_path[+all 4 Edit fields]}` + `systemMessage`) on match; nothing on passthrough.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash, PreToolUse/Read, PreToolUse/Write, and PreToolUse/Edit entries). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Detected patterns:**
- `.claire/` anywhere in command (Bash) or file_path (Read/Write/Edit), after quote-stripping
- `..letter` — two dots followed by lowercase letter in path context (boundary char `^`, `/`, whitespace, `=`)

**Rewrites:**
- `.claire/` → `.claude/` (literal `str.replace`)
- `..<letter>` → `../<letter>` (regex `(^|[/\s=])(\.\.)([a-z])` → `\1\2/\3`, preserves the boundary char and letter)

**Edit-specific:** `updatedInput` for Edit carries ALL 4 fields (`file_path`, `old_string`, `new_string`, `replace_all`) per Issue #47853 OP requirements — only `file_path` is rewritten, the other three are passed through unchanged from `tool_input`.

**Edit-Matcher anomaly:** the hook is registered for Edit but evidence suggests it doesn't fire on Edit tool calls (bash + Read confirmed working in same session). See `decisions/OldThemes/tool_use_safety/2026-05-22_block_path_typo_edit_no_fire.md`. The auto-rewrite form is correct; the issue is on the CC-side firing pipeline for Edit.

**Allowed (passthrough):** `.claude/` (correct spelling); `../` (valid parent traversal); quoted strings containing typo patterns (stripped before matching); parse errors (fail-open).

---

### block_venv_no_redirect.py (50 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks `./venv/bin/python <script>.py` calls that have no file redirect (`> file`) or `| tee`. Dev scripts produce verbose output that floods the context window; redirecting to `/tmp/` is mandatory (Rule 4, `tool-use.md`). Exits 2 + stderr with the required form. Exits 0 when redirect/tee present, or on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with required form) on violation only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:** `./venv/bin/python <anything>.py` (or `venv/bin/python ...`) without `> <file>` or `| tee` in the command.

**Allowed patterns:** command includes `> /tmp/file.md` or `| tee /tmp/file.md`; commands not matching the venv-python-script pattern; parse errors (fail-open).

**Quote/heredoc stripping.** Before pattern checks, `_strip_non_shell_active()` (from `_shell_strip.py`) removes quoted regions. Prevents false-positives when `./venv/bin/python dev/...` appears as a literal example inside a `worker-cli send` message.

---

### block_worker_spawn_opus.py (42 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks `worker-cli spawn` calls that specify `opus` as the model argument. Workers are always Sonnet; using Opus as a worker burns ~20–40× billing per token and eliminates the cross-model verification benefit. Exits 2 + stderr with the correct form. Exits 0 on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with correct model form) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:** `worker-cli spawn ... opus` — `opus` appearing anywhere after the `spawn` subcommand (in shell-active regions).

**Allowed patterns:** `worker-cli spawn <name> <prompt> <path> sonnet`; `worker-cli spawn` with no model (default = sonnet); `opus` in a quoted string argument; parse errors (fail-open).

**Quote/heredoc stripping.** Before pattern check, `_strip_non_shell_active()` (from `_shell_strip.py`) removes quoted regions. Prevents false-positives when `worker-cli spawn ... opus` appears as a literal example inside a `worker-cli send` message or documentation string.

---

### hook_setup.py (144 LOC)

**Purpose:** Idempotent installer with two defense layers. **Layer 1 — Worktree Guard:** `_guard_not_worktree()` checks `Path(__file__).resolve().parts` for consecutive `.claude`/`worktrees` components; exits 2 with a clear error message if the script is running from a worktree path — preventing dead-path registration. **Layer 2 — Stale-hook Sweep:** `_sweep_stale_hooks()` iterates ALL event keys in `settings["hooks"]` (not only `PreToolUse`), checks every `python3 <path>` entry, and removes any whose script path fails `os.path.exists()`; drops now-empty groups, saves atomically, then runs the normal add-loop. Re-running heals stale entries from any source (worktree accident, repo move, etc.).
**Reads:** `~/.claude/settings.json`.
**Writes:** `~/.claude/settings.json` (atomic via temp + `os.replace()`; up to two saves per run — one after sweep if stale entries found, one after add-loop if new entries installed).
**Called by:** User manually (`python3 src/hooks/hook_setup.py` from Monitor_CC root). Never imported.
**Calls out:** stdlib only (`json`, `os`, `pathlib`, `sys`).

**Usage:** `python3 src/hooks/hook_setup.py` — run once after clone or reinstall. Re-run any time to heal stale hook entries. Restart CC to activate new hooks.

**Note:** Must be run from the MAIN REPO root, not a worktree. The guard now enforces this — attempting to run from a worktree exits with exit code 2 and a clear message before touching settings.json.

---

## Gotchas

- **Auto-deploy via `.githooks/` (per-clone setup required).** The repo ships `.githooks/post-merge` and `.githooks/post-commit` — both fire `python3 src/hooks/hook_setup.py` automatically when a commit (merge or direct) touches `src/hooks/*`. This keeps `~/.claude/settings.json` in sync with the filesystem, preventing the stale-hook disaster class. Each clone must activate the hooks once:
  ```bash
  git config core.hooksPath .githooks
  ```
  This is a local config (not committed). Workers committing from worktrees are unaffected — `hook_setup.py`'s worktree guard (`_guard_not_worktree()`) exits 2, which the hook script swallows silently; settings.json is only updated when the hook fires from the main repo context (merge onto main, direct commit on main). Verification: after a commit touching `src/hooks/`, confirm `settings.json` under `~/.claude/` (user-level file, not in repo) has mtime fresher than the commit timestamp.

- **`log_fire` decision enum and API-impact semantics.** Three values are defined — only `"block"` and `"rewrite"` are live today; `"ui-notice"` is reserved for future hooks with no API impact:

  | decision | Mechanism | API impact | Record field |
  |---|---|---|---|
  | `"block"` | exit 2 + stderr | Agent sees error, may retry | `reason` (stderr text) |
  | `"rewrite"` | exit 0 + updatedInput JSON | Agent runs modified input silently | `rewritten` (change description) |
  | `"ui-notice"` | exit 0, UI-only side-effect | **None** — agent sees nothing | neither |

  Filter `"ui-notice"` from FP analysis: `jq 'select(.decision != "ui-notice")' src/logs/hook_firing.jsonl`.

- **Fail-open is mandatory.** All hooks exit 0 on any parse error or missing field — a hook must never block a legitimate tool call due to its own failure. A broken hook that blocks everything is a footgun.
- **Global registration.** Bash hooks fire for every Bash call; Edit hooks for every Edit call; Read hooks for every Read call — across all CC sessions on this machine (main sessions and workers). Keep hooks fast and narrowly scoped. Current timeout: 5s (set in `hook_setup.py`).
- **Absolute path in settings.json.** `hook_setup.py` writes the full resolved path of each hook script at install time. If the repo is moved, re-run `hook_setup.py` to update the paths. The sweep pass removes the old stale paths automatically on re-run.
- **Stale hooks block all Bash calls.** A stale `python3 <missing>.py` hook exits 2 (Python interpreter error for missing file), which CC treats as a block — every Bash command in every session fails globally. Recovery: re-run `hook_setup.py` from the main repo root (from a real terminal, not CC's Bash tool, since Bash is blocked). The sweep removes dead entries before the add-loop runs.
- **Seven hooks share a shell-region stripper (`_shell_strip.py`).** Before regex matching, `_strip_non_shell_active()` replaces heredoc bodies, single/double-quoted strings, and ANSI-C `$'...'` quotes with spaces of the same length (position-preserving). Command substitutions `$(...)` and backtick expressions are kept shell-active. Hooks using this: `rewrite_chained_sleep.py`, `block_dangerous_kill.py`, `block_broad_grep.py`, `block_polling_loop.py`, `rewrite_git_ambiguous.py`, `block_venv_no_redirect.py`, `block_worker_spawn_opus.py`. Fail-open: any parse error returns the original string unchanged — a malformed command is never incorrectly allowed by the stripper.
- **Cache-bust on settings.json edit.** Editing `~/.claude/settings.json` busts CC's prompt cache — full message rebuild on the next request. Expected cost; CC must be restarted anyway to pick up the hook.
- **PreToolUse exit codes.** Exit 0 = allow, exit 2 = block (CC shows stderr to user as the block reason), exit 1 = hook error (CC logs but does not block). This hook uses exit 2 on block, exit 0 on allow and on hook-internal errors.
- **`block_read_worktree.py` allows own-worktree reads.** Workers reading files in their own worktree via absolute path are now allowed. Cross-worktree reads (worker→other-worker) and main-session→worktree reads remain blocked.
- **All 21 hooks log fires via `_fire_log.log_fire()`.** Called at the decision-point only — NOT at hook start and NOT on passthroughs. The shared log `src/logs/hook_firing.jsonl` is append-forever; fail-silent on write errors so logging never breaks hook behavior. New hooks must add a `log_fire()` call at their decision-point as part of the implementation. Use `MONITOR_CC_HOOK_FIRING_LOG` env var in smoke tests to redirect to a temp file and avoid polluting the real log.
