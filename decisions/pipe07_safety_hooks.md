# pipe07 — Safety Hooks (PreToolUse)

## Status Quo (IST)

36 safety hooks registered globally in `~/.claude/settings.json`. All 36 call `log_fire()` (from shared `src/hooks/_fire_log.py`) at their decision-point, appending fire-events to `src/logs/hook_firing.jsonl` (append-forever, fail-silent). Passthroughs are not logged. Rewrite hooks (exit 0 + `updatedInput` JSON): `rewrite_background_sleep`, `rewrite_bd_invalid_repo`, `rewrite_chained_sleep`, `rewrite_rag_cli_search_noise`, `rewrite_searxng_scrape_noise`, `rewrite_worker_cli_capture_noise`, `rewrite_worker_cli_response_noise`; additionally `block_path_typo` and `block_unauthorized_background` use rewrite semantics (exit 0 + `updatedInput`) despite their `block_` prefix names. Disabled (renamed `.py.disabled`): `block_chained_sleep`, `block_polling_loop`, `block_log_read`, `rewrite_reddit_index_background`, `rewrite_pipe_background`.

### Hook 1 — `block_dangerous_kill.py` (`src/hooks/block_dangerous_kill.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call in every CC session on this machine
- **Command:** `python3 <absolute-path>/src/hooks/block_dangerous_kill.py` (absolute path written at install time by `hook_setup.py`)
- **Timeout:** 5s
- **Install:** `python3 src/hooks/hook_setup.py` from project root (idempotent)

**Blocked patterns:**
- `pkill -f <pattern>` — `\bpkill\s+(-[^\s]*\s+)*-f\b`
- `ps ... | ... grep ... | ... kill ...` — `\bps\b.+\|.+\bgrep\b.+\|.+\bkill\b`

**Allowed patterns (not blocked):** `pkill -x <name>`, `pkill <name>` (no `-f`), `kill <numeric_pid>`, `kill -<signal> <numeric_pid>`, `worker-cli kill <name>`, `launchctl` operations.

**Allowlist (`_PKILL_F_ALLOWLIST`):** explicit literal arguments to `pkill -f` that are safe to pass through. Current entries:
- `"dolt sql-server"` — bd Beads SQL backend forced restart. bd's own orphan-cleanup SIGKILLs any process whose cmdline contains this string, so no worker can carry it in its prompt. Checked against original command (not shell-stripped, since stripping blanks quoted args). Conservative: any non-allowlisted `pkill -f` in the same command still blocks.

### Hook 2 — `rewrite_chained_sleep.py` (`src/hooks/rewrite_chained_sleep.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — same scope as hook 1
- **Command:** `python3 <absolute-path>/src/hooks/rewrite_chained_sleep.py`
- **Timeout:** 5s
- **Replaced:** `block_chained_sleep.py` disabled 2026-05-24 (renamed → `.disabled`) after sleep-pattern audit showed trivial-sync pattern was 30.4% of violations.

**Behavior:** REWRITE hook (exits 0 always, never blocks). Strips `sleep N` when the immediately-preceding segment is in `_TRIVIAL` (single-token) or `_TRIVIAL_PAIRS` (two-token exact pair). Pass-through (no-op) for all other patterns.

**Allowlist:**

`_TRIVIAL` (single-token — first token of preceding segment):
```
echo, true, grep, cat, ls, wc, head, tail, find
```

`_TRIVIAL_PAIRS` (two-token exact pair — `(tokens[0], tokens[1])` of preceding segment):
```
(git, status), (git, log), (git, diff), (git, show)
(rag-cli, search_hybrid)
(worker-cli, status), (worker-cli, list), (worker-cli, response)
```

**Multi-token rationale:** bare `git`, `rag-cli`, `worker-cli` in `_TRIVIAL` would strip after `git push/pull/fetch/merge/commit`, `rag-cli index/update_docs`, `worker-cli send/spawn/kill/merge` — all potentially load-bearing. Pairing with the exact read-only subcommand gives a narrow, FP-safe gate. `(tokens[0], tokens[1])` is a frozenset-of-tuples exact lookup — no substring or prefix matching.

**Flag-handling limitation (known):** when a flag sits between command and subcommand — e.g. `git -C <path> status` where `tokens[1]='-C'` not `'status'` — the pair `('git', '-C')` is not in `_TRIVIAL_PAIRS`, so the sleep is conservatively NOT stripped. Fail-toward-preserve: missing a strip is safe; an incorrect strip of a load-bearing sleep is not. A narrow special-case for `git -C <path> <subcmd>` was evaluated and rejected — it would require index arithmetic (`tokens[3]`) that breaks for `git -C path --no-pager status` and `git -c k=v status` variations.

**Strip condition (ALL must hold):**
1. A chain operator (`&&`, `||`, `;`) immediately precedes `sleep N`
2. First token of the preceding segment is in `_TRIVIAL`, OR `(tokens[0], tokens[1])` is in `_TRIVIAL_PAIRS`
3. Sleep is NOT inside a `for|while|until ... done` span

**Pass-through (no-op) — sleep preserved as-is:**
- Sleep-first chain (no preceding op) — timer intent
- cmd_before not in `_TRIVIAL` and pair not in `_TRIVIAL_PAIRS` (load-bearing: `git push/pull/commit`, `rag-cli index/update_docs`, `worker-cli send/kill`, `launchctl`, `pkill`, `tmux`, etc.)
- `git/rag-cli/worker-cli` with a flag between command and subcommand (e.g. `git -C <path> status`) — conservatively NOT stripped (fail-toward-preserve)
- Single `&` background operator — not in `_CHAIN_RE` (`r';|&&|\|\|'`), so `tail -f log & sleep N` has no preceding chain op → sleep-first path → no strip
- Loop body sleep
- Any parse/internal error (fail-open)

**Shell-region stripping:** uses `_shell_strip._strip_non_shell_active` (same-dir import) before tokenizing — heredoc bodies and quoted strings replaced with spaces of equal length. Prevents false-positive on `sleep` inside heredoc/string literals.

**Smoke:** `dev/hook_smoke/test_rewrite_chained_sleep.py` (31 cases: 18 strip / 13 pass-through). Note: launchctl is covered by the 8 original cases; the 15 new strip + 8 new critical no-strip bring the total to 31.

### Hook 3 — `block_unauthorized_background.py` (`src/hooks/block_unauthorized_background.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — same scope as hooks 1 and 2
- **Command:** `python3 <absolute-path>/src/hooks/block_unauthorized_background.py`
- **Timeout:** 5s

**Detection:** `tool_input.run_in_background == true`

**Allowlist:** full command must match `_CANONICAL` — any sleep-only form: bare `sleep N` OR `sleep N && echo <anything>` (regex: `^\s*sleep\s+\d+(?:\.\d+)?\s*(?:&&\s*echo\b[^;&|\n]*)?\s*$`). No other whitelist — ALL non-sleep-timer background commands are foreground-forced.

**Blocked patterns (foreground-forced):**
- Any `run_in_background=true` command that is NOT a sleep-only timer — e.g. `rag-cli update_docs .`, `python3 script.py`, `reddit-cli index_subreddits`, `workflow.py index-dir`, builds, test runners, pipelines

**Allowed:** any sleep-only background command — `sleep N`, `sleep N && echo done`, `sleep N && echo "custom text"` — any command with `run_in_background=false` or field absent. Hook-order independent: both the raw sleep-only form and the already-normalized `sleep 600 && echo done` are exempt, so a sleep timer is never foreground-forced regardless of whether `rewrite_background_sleep` (Hook 18) runs first.

**Rationale:** background mode hides stdout/stderr until completion, making long-running tools unmonitorable. `rag-cli update_docs .` with `run_in_background=true` ran 2m36s with no live output — the triggering incident. Enforces Rule 12 from `~/.claude/shared-rules/global/tool-use.md`. Sleep-only exemption broadened after fire-log evidence that `sleep 45 && echo "bg-ack-probe done"` (custom echo text) was incorrectly foreground-forced. Whitelist removed: the proxy injection layer now handles "background done" signalling; all non-timer background is forced to foreground.

**Fail-open:** exits 0 on any parse/internal error; `(None, False)` default on exception means missing/invalid fields are treated as foreground — never blocks on hook failure.

### Hook 4 — `block_broad_grep.py` (`src/hooks/block_broad_grep.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"`
- **Command:** `python3 <absolute-path>/src/hooks/block_broad_grep.py`
- **Timeout:** 5s

**Detection:** `\bgrep\b` with recursive flag (`-r`/`-R`, combined or standalone) AND no `--include=` present AND last arg doesn't end in a known file extension

**Allowlist:** `--include=` present; last arg ends in `.py`/`.md`/`.sh`/`.json`/`.jsonl`/`.yaml`/`.yml`/`.toml`/`.ts`/`.js`/`.go`/`.rs`/`.txt`/`.cfg`/`.ini`/`.sql`/`.html`/`.css`; `git grep` (exempted); output piped immediately to `head` (head-bounded, no context-flood risk)

**Blocked patterns:**
- `grep -rn <pattern> src/` — directory target, no scope
- `grep -rn <pattern> .` — dot, no scope
- `grep -rnl <pattern> ~/.claude/` — any broad tree

**Allowed:** `grep -rn pattern src/ --include='*.py'`; `grep -rn pattern workflow.py`; `grep -n pattern file.py` (no `-r`); `grep -r foo . | head -N` (head-bounded)

**Head-bounded exemption:** `_grep_segment()` returns `(segment, after_segment)`. If `after_segment` starts with `| head` (direct next pipe), the output is bounded → no context flood → passes. `_is_head_bounded(after)` checks `^\s*\|\s*head\b` on `after_segment` only, ensuring the head belongs to this grep's output, not a head earlier in the chain.

**Rationale:** 23 Rule-3 violations in 5 recent monitor_cc logs (900 tool_use blocks, 2026-05-20 compliance run). Highest non-hooked violation count.

**Fail-open:** exits 0 on any parse/internal error; `git grep` exempted; nonexistent file in segment → no match → allow.

### Hook 5 — `block_noop_edit.py` (`src/hooks/block_noop_edit.py`)

- **Registration:** `PreToolUse` / `matcher: "Edit"`
- **Command:** `python3 <absolute-path>/src/hooks/block_noop_edit.py`
- **Timeout:** 5s

**Detection:** `tool_input.old_string == tool_input.new_string` (pure string comparison)

**Blocked patterns:** Edit where both strings are present, non-None, and identical

**Allowed:** different strings; missing/non-string fields (fail-open)

**Rationale:** CC rejects these with "No changes to make" — hook surfaces the error before the round-trip, saves one wasted tool call.

**Fail-open:** exits 0 when either field absent, not a string, or JSON error.

### Hook 6 — `block_read_directory.py` (`src/hooks/block_read_directory.py`)

- **Registration:** `PreToolUse` / `matcher: "Read"`
- **Command:** `python3 <absolute-path>/src/hooks/block_read_directory.py`
- **Timeout:** 5s

**Detection:** `os.path.isdir(tool_input.file_path)`

**Blocked patterns:** `file_path` resolves to an existing directory

**Allowed:** file paths, nonexistent paths, missing/non-string field (fail-open)

**Rationale:** CC rejects these with "Read tool cannot read directories" — hook surfaces the error before the round-trip.

**Fail-open:** exits 0 when `file_path` absent, not a string, or `isdir()` raises.

### Hook 7 — `block_read_oversize.py` (`src/hooks/block_read_oversize.py`)

- **Registration:** `PreToolUse` / `matcher: "Read"`
- **Command:** `python3 <absolute-path>/src/hooks/block_read_oversize.py`
- **Timeout:** 5s

**Detection:** `os.path.getsize(file_path) > 262144` AND no `offset`/`limit`/`pages` in `tool_input`

**Blocked patterns:** file >256KB with no read-scoping parameters

**Allowed:** file ≤256KB; `offset`/`limit`/`pages` present; stat error (fail-open)

**Rationale:** CC rejects reads above 256KB with a size error — hook surfaces the error before the round-trip and provides the `grep` + offset/limit fix path inline.

**Fail-open:** exits 0 when `file_path` absent, not a string, file doesn't exist, or `getsize()` raises.

### Hook 9 — `block_bd_cli_worker.py` (`src/hooks/block_bd_cli_worker.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_bd_cli_worker.py`
- **Timeout:** 5s

**Detection:** `os.getcwd()` contains `.claude/worktrees/` AND quote-stripped command matches `bd <subcommand|flag>` at statement start or after a chain operator (`[;&|\n]`)

**Blocked patterns:** any `bd create`, `bd close`, `bd comments add`, `bd export`, etc. from inside a worker session

**Allowed patterns:** `bd` calls from main sessions (no worktree in CWD); quoted `bd` examples in strings; non-`bd` commands; parse errors (fail-open)

**Rationale:** Workers run in git worktrees. Worktrees contain a copy of `.beads/` state — `bd` writes from inside a worktree go to the worktree copy, NOT the main repo. On merge or worktree removal this data is silently lost or corrupts the main repo's bead history. Bead operations are Opus's exclusive responsibility.

**Fail-open:** exits 0 on any parse/internal error; skips when not in a worktree.

### Hook 10 — `block_cd_drift.py` (`src/hooks/block_cd_drift.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_cd_drift.py`
- **Timeout:** 5s

**Detection:** quote-stripped command contains a `cd .claude/worktrees/...` target AND that worktree path is the LAST `cd` target (no cd-back at end of chain)

**Blocked patterns:** `cd <worktree> && git diff` (no cd-back); `cd <worktree>` as final statement

**Allowed patterns:** `cd <worktree> && ... && cd <main-repo>` (cd-back present); commands with no worktree `cd`; calls from inside a worktree (hook skips when own CWD is a worktree); parse errors (fail-open)

**Rationale:** Bash tool calls share CWD across invocations (Rule 16, `tool-use.md`). A dangling `cd` into a worktree persists to the next Bash call, causing edits to land in the wrong tree. The fix is either a cd-back or using `git -C <path>` + absolute paths throughout.

**Fail-open:** exits 0 on any parse error; hook skips entirely when its own CWD is a worktree (workers legitimately live in their worktree).

### Hook 11 — `block_dev_imports_src.py` (`src/hooks/block_dev_imports_src.py`)

- **Registration:** `PreToolUse` / `matcher: "Write"` and `matcher: "Edit"` — fires for every Write and Edit tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_dev_imports_src.py`
- **Timeout:** 5s

**Detection:** `file_path` matches `/dev/` AND written content (`content` for Write, `new_string` for Edit) contains `^from src\.` or `^import src\.` (multiline)

**Blocked patterns:** any dev/ script importing from the `src/` package

**Allowed patterns:** dev/ files without `src/` imports; files outside `dev/`; parse errors (fail-open)

**Rationale:** dev/ scripts are self-contained pipeline probes and migration candidates (dev-convention.md Rule 5). Importing from `src/` breaks this isolation: the probe no longer tests an independent alternative but extends the production code path, and becomes non-runnable on any host without the full `src/` tree installed.

**Fail-open:** exits 0 on any parse error; non-Write/Edit tool_name returns `(None, None)` → allow.

### Hook 12 — `block_except_pass.py` (`src/hooks/block_except_pass.py`)

- **Registration:** `PreToolUse` / `matcher: "Write"` and `matcher: "Edit"` — fires for every Write and Edit tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_except_pass.py`
- **Timeout:** 5s

**Detection:** written content matches `except\s*(?:\w+\s*)?:\s*[\r\n]+\s*pass\b` (multiline) — covers `except: pass`, `except Exception: pass`, `except SomeError: pass`

**Blocked patterns:** any bare exception swallow in written Python code

**Allowed patterns:** `except ... : raise`; `except ... as e: logger...; raise`; `finally: resource.close()`; non-Write/Edit calls; parse errors (fail-open)

**Rationale:** Silently swallowing exceptions produces invisible bugs — the script continues with wrong state and no error signal (code-standards.md § Error Handling). The hook enforces the "Fail-Fast" rule at write time rather than at review time.

**Fail-open:** exits 0 on any parse error; non-Write/Edit tool_name returns None → allow.

### Hook 13 — `block_git_add_deps.py` (`src/hooks/block_git_add_deps.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_git_add_deps.py`
- **Timeout:** 5s

**Detection:** quote-stripped command matches `\bgit\s+(?:-C\s+\S+\s+)?add\b` AND also matches `\b(?:venv|\.venv|node_modules)/?(?:\s|$)`

**Blocked patterns:** `git add venv/`, `git add .venv/`, `git add node_modules/`, or `git add <anything> venv/` with an explicit dep-dir argument

**Allowed patterns:** `git add` targeting specific non-dep files; `git add .` without explicit dep-dir token in the command; parse errors (fail-open)

**Rationale:** Worktrees contain symlinked dependency directories pointing to the main repo's real directories. Staging these symlinks creates circular self-references on merge (the symlink in the merged result points at itself). worker-rules.md § Never Commit Dependency Directories.

**Fail-open:** exits 0 on any parse error; quote-stripping prevents false positives from dep names in quoted strings.

### Hook 14 — `block_git_destructive.py` (`src/hooks/block_git_destructive.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_git_destructive.py`
- **Timeout:** 5s

**Detection:** five compiled regex patterns applied to quote-stripped command; all five `_PATTERNS` connectors and `_GIT_CONFIG_RE` use `[^|;&\n]*` (newline in exclusion class) — a match cannot span across lines of a multi-line command, closing the cross-line false positive (e.g. `git push` on one line + `[ -f file ]` on a later line). `git config` write-variant detected separately (excludes `--list|--get|--show-origin|...` read-only flags)

**Blocked patterns:**
- `git commit --amend` — never amend existing commits
- `git push --force` / `--force-with-lease` / `-f` — never force push
- `git commit|push --no-verify` — never skip hooks
- `git commit --allow-empty` — never empty commits
- `git config` (write variant) — config changes are user decisions, not Opus-driven

**Allowed patterns:** standard `git commit`, `git push`, `git config --list|--get|--show-origin|...`; parse errors (fail-open)

**Rationale:** Enforces the Git CLI Safety Protocol from `tool-use.md` § Git CLI § Rules. Each blocked pattern has caused irreversible damage or lost work in prior sessions — amend rewrites history, force-push overwrites remote, `--no-verify` bypasses safety hooks, empty commits add noise.

**Fail-open:** exits 0 on any parse error; `_GIT_CONFIG_RE` checks only the `git config` segment, not the full command.

### Hook 15 — `block_path_typo.py` (`src/hooks/block_path_typo.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"`, `matcher: "Read"`, `matcher: "Write"`, `matcher: "Edit"` — fires for all four tool types
- **Command:** `python3 <absolute-path>/src/hooks/block_path_typo.py`
- **Timeout:** 5s

**Detection:** for Bash, checks `tool_input.command`; for Read/Write/Edit, checks `tool_input.file_path`. Two patterns tested on the quote-stripped string:
- `\.claire/` — tokenizer typo of `.claude/`
- `(?:^|/|\s|=)\.\.[a-z]` — double-dot immediately followed by a lowercase letter

**Blocked patterns:**
- `.claire/worktrees/...`, `.claire/settings.json`, etc. — wrong letter sequence
- `..claude/`, `..src/`, `..bin/` etc. — double-dot path component (not valid parent traversal)

**Allowed patterns:** `.claude/` (correct); `../` (valid traversal); parse errors (fail-open)

**Rationale:** Rule 13 (`tool-use.md`). `.claire/` is a systematic tokenizer error that produces `FileNotFoundError` on every tool call. `..letter` double-dot paths are never valid path components — `../` (two dots + slash) is the only correct form. Blocking at write time avoids a wasted round-trip.

**Fail-open:** exits 0 on any parse error; unrecognized `tool_name` returns empty target list → allow.

### Hook 16 — `block_venv_no_redirect.py` (`src/hooks/block_venv_no_redirect.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_venv_no_redirect.py`
- **Timeout:** 5s

**Detection:** command matches `\.?\.?/?venv/bin/python\s+\S+\.py\b` AND does NOT contain `>\s*\S+` (file redirect) AND does NOT contain `\|\s*tee\b`

**Blocked patterns:** `./venv/bin/python dev/area/script.py` with no output redirect

**Allowed patterns:** `./venv/bin/python script.py > /tmp/out.md 2>&1`; `... | tee /tmp/out.md`; non-venv-python commands; parse errors (fail-open)

**Rationale:** Dev scripts produce verbose debug output that floods the context window when sent to stdout. Rule 4 (`tool-use.md`) requires redirecting noisy output to a file and grepping the signal. This hook enforces the required form before the call executes.

**Fail-open:** exits 0 on any parse error; pattern must match `venv/bin/python *.py` — non-matching commands pass through immediately.

### Hook 17 — `block_worker_spawn_opus.py` (`src/hooks/block_worker_spawn_opus.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_worker_spawn_opus.py`
- **Timeout:** 5s

**Detection:** command matches `\bworker-cli\s+spawn\b.*\bopus\b` (DOTALL — opus anywhere after `spawn`)

**Blocked patterns:** `worker-cli spawn <name> <prompt> <path> opus` — opus specified as model argument

**Allowed patterns:** `worker-cli spawn ... sonnet`; `worker-cli spawn ...` with no model arg (default = sonnet); parse errors (fail-open)

**Rationale:** Workers are always Sonnet (workers-1.md § Worker Model). Opus as a worker burns ~20–40× billing per token and eliminates the independent cross-model verification perspective (both sides share the same architecture). The hook prevents accidental or copy-paste spawns with the wrong model.

**Fail-open:** exits 0 on any parse error.

### `block_background_sleep_nonworker.py` (`src/hooks/block_background_sleep_nonworker.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — registered immediately BEFORE Hook 18 (`rewrite_background_sleep.py`) in `_HOOK_SCRIPTS`; a blocked timer never reaches the rewrite hook
- **Command:** `python3 <absolute-path>/src/hooks/block_background_sleep_nonworker.py`
- **Timeout:** 5s

**Gate:** `run_in_background == True` AND command matches `_SLEEP_ONLY_BG` (same regex as Hook 18) AND the **last non-timer Bash command** for this session was NOT `worker-cli` (any subcommand).

**Rationale:** The only legitimate sleep-timer is the worker-wait poll loop — every timer in that loop is immediately preceded by a `worker-cli spawn/status/send`. A timer after any other command (e.g. `rag-cli index`, a build) is a redundant "wait" for a self-notifying background task; the orchestrator should go idle instead. The gate is: `last-cmd starts with worker-cli` → allow; anything else (including no prior cmd) → block.

**State mechanism:** `logs/last_cmd_state.jsonl` — one JSONL entry per session `{ts, session_id, cmd}`. Written on every non-timer Bash call (replaces own session entry + prunes entries >24h). Timer calls never write state. Path overridable via `MONITOR_CC_LAST_CMD_STATE`.

**Fail-open split:**
- IO/parse exception on state read (`_READ_ERROR` sentinel) → exit 0 (allow — transient error must not block entire worker loop).
- State read succeeded but no entry found for session → exit 2 (BLOCK — genuine no-prior-command case).

**worker-cli detection:** `_strip_non_shell_active(stored_cmd)` → `(?:^|[;&|\n])\s*worker-cli\b` (`.search`) — matches any `worker-cli` subcommand appearing at the start of the string OR immediately after a shell separator (`;`, `&`, `|`, newline). Covers bare `worker-cli ...` and all cd-prefixed spawn forms (`cd /p ; worker-cli ...`, `cd /p && worker-cli ...`, `cd /p\nworker-cli ...`).

**Block message:** "Go idle immediately. Stop whatever you are doing and go idle. A background Bash task self-notifies via its completion notice — do NOT set a timer to wait for it. Timers are ONLY for polling a worker you just spawned/messaged (worker-cli)."

**Fail-open:** exits 0 on any parse error in `_parse_input`; `_is_worker_cli` returns False for None/empty (no-prior BLOCK is intentional, not a fail-open case).

**Smoke:** `dev/hook_smoke/test_block_background_sleep_nonworker.py` (10 cases: rag-cli→BLOCK, worker-cli spawn→ALLOW, worker-cli status→ALLOW, no-prior→BLOCK, `cd /p ; worker-cli spawn`→ALLOW, `cd /p && worker-cli status`→ALLOW, `cd /p\nworker-cli spawn` live-repro form→ALLOW, non-timer-bg→exits-0+state-written, state-written confirmed by subsequent BLOCK, IO-error→fail-open ALLOW). All 10 passing.

---

### Hook 18 — `rewrite_background_sleep.py` (`src/hooks/rewrite_background_sleep.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — same scope as hooks 1–17
- **Command:** `python3 <absolute-path>/src/hooks/rewrite_background_sleep.py`
- **Timeout:** 5s

**Detection:** `tool_input.run_in_background == true` AND command matches `_SLEEP_ONLY_BG` (bare `sleep N` OR `sleep N && echo <anything>`: `^\s*sleep\s+\d+(?:\.\d+)?\s*(?:&&\s*echo\b[^;&|\n]*)?\s*$`) AND command is NOT already the exact target `"sleep 600 && echo done"`.

**Rewrite:** entire command replaced with `sleep 600 && echo done`

**Passthrough (no output):**
- `run_in_background=false` or field absent — foreground, any form allowed
- Command is exactly `sleep 600 && echo done` — already the canonical target (`command.strip() == _TARGET`)
- Any non-sleep-only command — `_SLEEP_ONLY_BG` fails to match; `block_unauthorized_background` (Hook 3) handles non-canonical bg commands
- Parse errors (fail-open)

**Rationale:** `tool-use.md` specifies Opus timers MUST always be 600s. Hook 3 exempts any sleep-only background command; this hook normalizes ALL of them to the canonical 10-minute form. Complementary layer: Hook 3 never foreground-forces a sleep-only timer; Hook 18 normalizes any sleep-only timer whose form or duration differs from the canonical target. Covers bare `sleep N`, custom echo text (fire-log: `sleep 45 && echo "bg-ack-probe done"` was the triggering incident), and non-600 durations.

**Fail-open:** exits 0 on any parse/internal error; missing `run_in_background` defaults to `False` → immediate passthrough.

**Smoke:** `dev/hook_smoke/test_rewrite_background_sleep.py` (11 cases: 5 positive rewrite, 6 negative no-op).

### Hook 19 — `rewrite_worker_cli_response_noise.py` (`src/hooks/rewrite_worker_cli_response_noise.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — same scope as hooks 1–18
- **Command:** `python3 <absolute-path>/src/hooks/rewrite_worker_cli_response_noise.py`
- **Timeout:** 5s

**Detection:** `\bworker-cli\s+response\b` in shell-active regions of the command

**Strip condition (ALL must hold):**
1. The shell-active command contains `worker-cli response` as a whole token
2. Within the response segment (up to the next `&&`, `||`, `;`, `)`, `\n`, or single `&`), a noise marker is found: `|` (excluding `||`), `>`, `>>`, `&>`, `<`, `2>`, `2>&1`
3. Strip from the noise marker through segment-end; eat leading whitespace only when segment extends to end-of-command

**Pass-through (no-op):**
- `worker-cli response X` with no pipe/redirect inside its segment
- Any subcommand other than `response`: `capture`, `status`, `list`, `send`, `merge`, `spawn`, `kill`, `revive` — anchor regex cannot match them
- `worker-cli response` token appearing inside a quoted string (blanked by `_strip_non_shell_active`)
- Parse errors (fail-open)

**Rationale:** `worker-cli response` prints the full last assistant message to stdout — output bounded and context-destined. Adding `| head`, `| tail`, or `> file` truncates the message silently. Critical no-op: `worker-cli capture X | tail -40` is a documented legitimate fallback; `capture` is guaranteed out of scope by the exact-subcommand anchor. Direct clone of `rewrite_rag_cli_search_noise.py` with anchor swapped to `\bworker-cli\s+response\b`.

**Smoke:** `dev/hook_smoke/test_rewrite_worker_cli_response_noise.py` (16 cases: 9 positive strip, 7 negative no-op including the critical `worker-cli capture | tail` pass-through).

### Hook 20 — `block_worker_kill_while_working.py` (`src/hooks/block_worker_kill_while_working.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_worker_kill_while_working.py`
- **Timeout:** 5s

**Detection (double-gate):**
1. Regex `\bworker-cli\s+kill\s+([\w.-]+)` on shell-stripped command captures the name token. `[\w.-]+` excludes trailing shell metacharacters: `worker-cli kill foo;` → `foo`, `worker-cli kill foo && x` → `foo`. Quoted/heredoc `worker-cli kill X` inside a send-message body is blanked by `_strip_non_shell_active` → no match → allow.
2. For each captured name, runs `worker-cli status <name>` subprocess (timeout 3s) via `_resolve_worker_cli()` — resolves the binary by **absolute path** (`shutil.which` first; fallback: `glob ~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/*/bin/worker-cli`, newest). If unresolvable → `''` → allow. Registry auto-resolves project path. Blocks iff the first whitespace token of the output equals exactly `'working'`.

**Hook-env PATH gotcha:** CC's hook execution environment provides a PATH that does NOT include the plugin-cache bins. A subprocess-hook calling a plugin CLI by bare name → `FileNotFoundError` → fail-open → hook silently never fires. This was a live bug: the kill-guard let working-worker kills through until fixed in `_resolve_worker_cli()`. **General pattern for any future subprocess-hook:** resolve plugin CLIs by absolute path (`shutil.which` + plugin-cache glob), never by bare name.

**Blocked patterns:** `worker-cli kill <name>` when `worker-cli status <name>` first token is `working`

**Allowed patterns (ALL of these allow):** any status ≠ `working` (idle, idle force-stopped, exited, unknown); nonexistent worker (status exit 1 → `''`); subprocess timeout or error; quoted kill inside a `worker-cli send` message; heredoc body kill; parse/JSON errors; any exception (fail-open)

**Block message:** tells user the worker is working, to stop it first (ESC or `worker-cli send '<name>' 'stop'`), wait until idle, then kill.

**Known accepted residual:** a shell comment carrying the literal kill + a live-working-worker-name blocks (e.g. `echo hi # worker-cli kill foo` where `foo` is working). Consistent with the whole hook family — none of the 31 hooks strip shell comments. The double-gate makes this FP require both the comment text to name a real worker AND that worker to be actively working simultaneously.

**Fail-open:** outer `except Exception: sys.exit(0)` in the workflow function ensures ANY unexpected error exits 0. Status subprocess: `TimeoutExpired`, `FileNotFoundError`, and all other errors → return `''` → allow. Per-name status_fn exception inside `decide()` → `status = ''` → continue checking remaining names.

**Smoke:** `dev/hook_smoke/test_block_worker_kill_while_working.py` (13 cases: 3 block, 9 allow, 1 accepted-residual block).

### Hook 22 — `rewrite_rag_cli_search_noise.py` (`src/hooks/rewrite_rag_cli_search_noise.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — same scope as hooks 1–21
- **Command:** `python3 <absolute-path>/src/hooks/rewrite_rag_cli_search_noise.py`
- **Timeout:** 5s

**Detection:** `\brag-cli\s+search_hybrid\b` in shell-active regions of the command

**Strip condition (ALL must hold):**
1. Shell-active command contains `rag-cli search_hybrid` as a whole token
2. Within the `search_hybrid` segment (up to the next `&&`, `||`, `;`, `)`, `\n`, or single `&`), a noise marker is found: `|` (excluding `||`), `>`, `>>`, `<<`, `&>`, `<`, `2>`, `2>&1`
3. Strip from the noise marker through segment-end; eat leading whitespace only when segment extends to end-of-command (avoids trailing-space artifact)

**Pass-through (no-op):**
- `rag-cli search_hybrid <coll> <query>` with no pipe/redirect inside its segment
- Any `rag-cli` subcommand other than `search_hybrid` (`read_document`, `list_collections`, `server`, etc.) — anchor cannot match
- `rag-cli search_hybrid` appearing inside a quoted string (blanked by `_strip_non_shell_active`)
- Parse errors (fail-open)

**Rationale:** `search_hybrid` output is bounded and meant to land directly in context. Adding `| head`, `| tail`, or `> file` truncates results silently. Chains around the segment are preserved (`cd && rag-cli ... && bd list` → only the rag-cli segment is cleaned).

**Smoke:** `dev/hook_smoke/test_rewrite_rag_cli_search_noise.py` (15 cases: 9 positive strip, 6 negative no-op).

---

### Hook 23 — `rewrite_searxng_scrape_noise.py` (`src/hooks/rewrite_searxng_scrape_noise.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — same scope as hooks 1–22
- **Command:** `python3 <absolute-path>/src/hooks/rewrite_searxng_scrape_noise.py`
- **Timeout:** 5s

**Detection:** `\bsearxng-cli\s+scrape_url\b` in shell-active regions of the command

**Strip condition (ALL must hold):**
1. Shell-active command contains `searxng-cli scrape_url` as a whole token
2. Within the `scrape_url` segment (up to the next `&&`, `||`, `;`, `)`, `\n`, or single `&`), a noise marker is found: `|` (excluding `||`), `>`, `>>`, `<<`, `&>`, `<`, `2>`, `2>&1`
3. Strip from the noise marker through segment-end; eat leading whitespace only when segment extends to end-of-command

**Pass-through (no-op):**
- `searxng-cli scrape_url <url>` with no pipe/redirect inside its segment
- Any `searxng-cli` subcommand other than `scrape_url` (`search_web`, `search_engine_drilldown`, `download_pdf`) — those produce bounded output and pass through unchanged
- `searxng-cli scrape_url` appearing inside a quoted string (blanked by `_strip_non_shell_active`)
- Parse errors (fail-open)

**Rationale:** `scrape_url` output is bounded (15k PruningContentFilter cap) and meant to land directly in context. A `> /tmp/file 2>&1` redirect mixes crawl4ai browser logs into what appears to be page content. Real incident: a redirected scrape_url produced a false "content stops after section 3" impression and an apparent `=== LOG RECORD ===` leak — both display artifacts of the truncating command, not the scraper. Direct clone of `rewrite_rag_cli_search_noise.py` with anchor swapped to `\bsearxng-cli\s+scrape_url\b`.

**Smoke:** `dev/hook_smoke/test_rewrite_searxng_scrape_noise.py` (16 cases: 9 positive strip, 7 negative no-op).

---

### Hook 24 — `block_worker_send_background.py` (`src/hooks/block_worker_send_background.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_worker_send_background.py`
- **Timeout:** 5s

**Detection:** `tool_input.run_in_background == true` AND shell-stripped command matches `\bworker-cli\s+send\b`

**Blocked patterns:** any `worker-cli send <name> <message>` dispatched with `run_in_background=true`

**Allowed patterns:** `worker-cli send` with `run_in_background=false` or field absent; commands without `worker-cli send`; `worker-cli send` appearing inside a quoted string (blanked by `_strip_non_shell_active`); parse errors (fail-open)

**Rationale:** `worker-cli send` is a fire-once, must-confirm action. Backgrounding means the send subprocess may be SIGTERM-killed before delivering the message (exit 143, silent message loss), or the orchestrator's next action runs before the send completes. Canonical pattern: send in a standalone foreground Bash call; any background timer (`sleep 600 && echo done`) dispatched as a SEPARATE Bash call.

**Fail-open:** exits 0 when `run_in_background` is absent, false, or not a bool; exits 0 on any parse error.

---

### Hook 27 — `block_search_subreddits_limit.py` (`src/hooks/block_search_subreddits_limit.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_search_subreddits_limit.py`
- **Timeout:** 5s

**Detection:** shell-stripped command contains `\b(reddit-cli|cli\.py)\s+search_subreddits\b` AND a `--limit` flag appears after the subcommand match position

**Blocked patterns:**
- `reddit-cli search_subreddits "crypto news" --limit 5` — caps the full result set
- `cli.py search_subreddits "query" --limit 10` — same via raw CLI

**Allowed patterns:** `reddit-cli search_subreddits "query"` without `--limit`; commands not containing `search_subreddits`; parse errors (fail-open)

**Rationale:** Subreddit discovery must return the full result set — the caller selects 3–5 subreddits from ALL matches. Capping with `--limit` prematurely hides candidates, defeating the discovery purpose. `_LIMIT_RE` is searched only after `_SEARCH_RE` matches; non-matching commands exit immediately.

**Fail-open:** exits 0 on any parse error; early exit before `_LIMIT_RE` check when `search_subreddits` not found.

---

### Hook 28 — `block_gh_cli_chained.py` (`src/hooks/block_gh_cli_chained.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_gh_cli_chained.py`
- **Timeout:** 5s

**Detection:** shell-stripped command contains one of the 7 gh-cli search/research tools (`search_repos`, `search_code`, `get_repo_tree`, `get_file_content`, `index_issues`, `index_discussions`, `index_releases`) AND after splitting on `&&`, `||`, `;`, `|`, `\n`, space-bounded `&`, at least one segment does NOT start with one of those 7 tools.

**Blocked patterns:**
- `gh-cli search_repos "q" | grep foo` — piped to a non-search command
- `gh-cli index_issues "q" o/r && rag-cli index docs` — chained with rag-cli
- `gh-cli get_file_content o/r path | head -10` — piped to head

**Allowed patterns:**
- `gh-cli index_issues "q" o/r --limit 30` — standalone with tool-native args
- `gh-cli index_issues "a" o/r && gh-cli index_discussions "b" o/r` — multiple search/research calls combined
- `gh-cli get_file_content o/r path > /tmp/out.txt` — redirect is not a `_SEPARATOR_RE` token (`>&`/`2>&1` have no whitespace before `&` and survive intact)
- `gh-cli list_issues o/r | grep open` — issue-management commands (`list_issues`, `get_issue`, `create_issue`, `update_issue`, `delete_issue`) don't match `_GH_SEARCH_RE` → early exit
- Parse errors (fail-open)

**Rationale:** Search/research tools must run standalone so their full output reaches context. Piping through `grep`/`head`/`tail`/`sed`/`awk`/`wc` forces reconstruction from fragments. Tool-native args (`--offset`, `--limit`, `--path`, `--metadata-only`, `--sort-by`) narrow results without truncating output.

**Smoke:** `dev/hook_smoke/test_block_gh_cli_chained.py` (18 cases: 9 block, 6 pass-standalone/two-chained/redirect, 2 exempt-issue-command, 1 single-quote strip, 1 heredoc strip).

---

### Hook 29 — `rewrite_bd_invalid_repo.py` (`src/hooks/rewrite_bd_invalid_repo.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/rewrite_bd_invalid_repo.py`
- **Timeout:** 5s

**Detection:** command contains `\bbd\b` AND `_REPO_TOKEN_RE` matches `--repo /path`, `--repo=/path`, `--repo "path"`, or `--repo 'path'` AND the extracted path does not exist OR contains no `.beads/` subdirectory.

**Rewrite:** matched `--repo <path>` token(s) are span-removed from the original command (no regex-replace; pure span deletion). At most a double-space remains where the token was — harmless for shell. Multiple `--repo` flags in one command all detected and removed in a single regex pass.

**Passthrough (no output):**
- `bd` commands without `--repo` (use cwd default)
- `bd --repo <valid-path-with-.beads/>` — both `isdir(path)` and `isdir(path/.beads)` pass
- Non-`bd` commands; shell-meta paths (`$PROJ_ROOT`, `` `pwd` ``, etc.) — unresolvable at hook time, let through
- Any exception (outer `except Exception: sys.exit(0)` wraps the workflow)

**Path validation per detected `--repo` arg:**
1. Skip if path contains `$`, `` ` ``, `\`, `*`, `?`, `{` — shell-meta, unresolvable at hook time
2. `os.path.expanduser` + `os.path.abspath` → resolved form
3. `os.path.isdir(resolved)` AND `os.path.isdir(resolved + '/.beads')` — both required

**Rationale:** Created after real incident: `bd --repo /Users/brunowinter2000/Monitor_CC create ...` (path typo — actual project under `Documents/ai/`) auto-initialized an unwanted `.beads/dolt/` at the wrong path and triggered a dolt-server port collision. The hook strips invalid `--repo` flags so `bd` defaults to cwd (which has `.beads/`).

**Live verification (2026-05-22):** `bd --repo /Users/brunowinter2000/Wrong/Path create --title "test" --type task` produced bead `Monitor_CC-ggh6` (correct project prefix from cwd-default), `/Users/brunowinter2000/Wrong/` not auto-initialized.

**Fail-open:** outer `except Exception: sys.exit(0)` in workflow guarantees pass-through on any unexpected error.

---

### Hook 30 — `block_worker_spawn_placement.py` (`src/hooks/block_worker_spawn_placement.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_worker_spawn_placement.py`
- **Timeout:** 5s

**Detection:** hook skips entirely when own CWD contains `.claude/worktrees/` (workers don't spawn workers). For main sessions: shell-stripped command matches `\bworker-cli\s+spawn\s+(\S+)\s+(\S+)\s+(\S+)` (extracts name, prompt, project_path). Two independent checks (either triggers block):
1. `\bworker-cli\s+spawn\b.*--no-worktree\b` anywhere in the shell-stripped command
2. `project_path` argument resolves to a different git-root than the session's own CWD

**Blocked patterns:**
- `worker-cli spawn <name> <prompt> /different/project` — cross-project spawn
- `worker-cli spawn <name> <prompt> c --no-worktree` — worktree-less spawn

**Allowed patterns:**
- `project_path` of `c` or `.` (resolve to current project by definition → no root comparison needed)
- Same-project absolute/relative path resolving to the same git-root
- Any command without `worker-cli spawn`; spawn from inside a worktree CWD (hook skips entirely)
- `project_path` or current-root resolution failure (fail-open)
- Parse errors (fail-open)

**Project-root resolution** (mirrors worker-cli's `resolve_project_path`):
1. `os.path.abspath(expanduser(path))` → absolute form
2. Strip `/.claude/worktrees/<name>` suffix if present
3. `os.path.realpath()` — normalises symlink components (`/Users` vs `/System/Volumes/Data/Users`)
4. Walk parent dirs until `.git` directory found → project root; `None` if filesystem root reached

Comparison is **case-insensitive** (`.lower()` on both roots) — macOS FS is case-insensitive.

**Rationale:** Workers always run in a worktree of the current project. Cross-project spawns write to the wrong tree. `--no-worktree` leaves the worker without isolation — all writes land in the project root, conflicting with the main session.

**Fail-open:** exits 0 when CWD is a worktree; exits 0 on path-resolution failure; exits 0 on any parse error.

**Known limitation (2026-06-23):** static command-string analysis is blind to a dynamic `project_path` — `worker-cli spawn ... "$(pwd)"` (after a `cd <other>`) is seen as the literal `"$(pwd)"`, resolves to the hook's own cwd git-root, and fail-opens. Only EXPLICIT absolute paths to another project are caught. Primary enforcement moved to `worker-cli spawn` itself (forces the home worktree into `PROXY_PROJECT_PATH` at runtime); this hook remains a fast pre-filter. See `decisions/OldThemes/worker_spawn_placement_enforcement.md`.

---

### Hook 31 — `block_manual_worker_cleanup.py` (`src/hooks/block_manual_worker_cleanup.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_manual_worker_cleanup.py`
- **Timeout:** 5s

**Detection:** two independent patterns applied to the shell-stripped command; either triggers the block:
1. `\btmux\s+kill-session\b[^;&|\n]*\s-t\s*worker-` — `tmux kill-session` whose `-t` target starts with `worker-`
2. `\bgit\s+(?:-C\s+\S+\s+)?worktree\s+remove\b[^;&|\n]*\.claude/worktrees/` — `git worktree remove` targeting `.claude/worktrees/`

`[^;&|\n]*` (replacing `.*`) prevents either pattern from bridging across shell separators (`;`, `&`, `|`, newline). This closes the cross-command false positive: `tmux kill-session -t main ; cmd -t worker-x` does not block because the `-t worker-x` belongs to a different segment.

**Blocked patterns:**
- `tmux kill-session -t worker-monitor-cc-hook-docs` — kills worker tmux session directly
- `tmux kill-session -a -t worker-foo` — same with extra flags
- `tmux kill-session -tworker-foo` — no-space form (`-tNAME`)
- `git worktree remove .claude/worktrees/hook-docs` — removes worker worktree directly
- `git -C /repo worktree remove .claude/worktrees/hook-docs` — same with `-C` flag
- `git worktree remove --force .claude/worktrees/hook-docs` — same with `--force`

**Allowed patterns (not blocked):**
- `worker-cli kill <name>` — the recommended atomic cleanup path (no pattern match)
- `tmux kill-session -t main` / `-t my-regular-session` — non-`worker-` target
- `tmux kill-session` (no `-t`) — kills current session, no target specified
- `git worktree remove /some/other/path` — path outside `.claude/worktrees/`
- `git worktree list` / `git worktree add ...` — non-remove subcommands
- `git branch -D <anything>` — excluded by design (worker branches have no distinguishing prefix; blocking would FP on legitimate feature-branch deletes)
- Patterns inside quoted strings (blanked by `_strip_non_shell_active`) — e.g. `worker-cli send foo 'tmux kill-session -t worker-bar'`
- Cross-separator patterns — e.g. `tmux kill-session -t main ; echo -t worker-x`

**Rationale:** The safe cleanup path is `worker-cli kill <name>` (atomic: tmux kill-session + worktree remove + branch delete + registry clear). Performing those steps RAW leaves partial/orphaned state: a bare `tmux kill-session` leaves the worktree and registry intact; a bare `git worktree remove` leaves the session still running. `git branch -D` alone has no distinguishing worker-branch prefix and cannot orphan a session or worktree, so it is excluded.

**Fail-open:** exits 0 on any parse error; `_parse_command()` returns `(None, None)` on any exception → immediate exit 0.

**Smoke:** `dev/hook_smoke/test_block_manual_worker_cleanup.py` (21 cases: 8 block, 13 allow including 2 separator cases and 2 quoted-string cases).

---

### Hook 32 — `rewrite_worker_cli_capture_noise.py` (`src/hooks/rewrite_worker_cli_capture_noise.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — same scope as hooks 1–31
- **Command:** `python3 <absolute-path>/src/hooks/rewrite_worker_cli_capture_noise.py`
- **Timeout:** 5s

**Detection:** `\bworker-cli\s+capture\b` in shell-active regions of the command

**Strip condition (ALL must hold):**
1. Shell-active command contains `worker-cli capture` as a whole token
2. Within the `capture` segment (up to the next `&&`, `||`, `;`, `)`, `\n`, or single `&`), a pipe is found: `|` excluding `||`
3. Strip from the pipe through segment-end; eat leading whitespace only when segment extends to end-of-command

**Pipe-only — redirects are explicitly preserved:**
`worker-cli capture X > /tmp/file` is a legitimate pattern (save the clean output to disk). The noise regex is `(?<!\|)\|(?!\|)` — a single `|` only. Redirects (`>`, `>>`, `2>&1`, `&>`, `<`) are NOT stripped. This is the sole difference from `rewrite_worker_cli_response_noise` (Hook 19), which strips both pipes and redirects.

**`--raw` survives:** the `--raw` flag sits between the anchor end and the pipe. Range-strip begins at the pipe position → `--raw` is never inside the strip range → preserved. `worker-cli capture X --raw | tail -40` rewrites to `worker-cli capture X --raw`.

**Pass-through (no-op):**
- `worker-cli capture X` with no pipe inside its segment
- `worker-cli capture X > /tmp/file` — redirect, not a pipe → no noise marker found
- `worker-cli capture X --raw` — flag, no pipe
- Any subcommand other than `capture`: `response`, `status`, `list`, `send`, `merge`, `spawn`, `kill`, `revive` — anchor cannot match
- `worker-cli capture` appearing inside a quoted string (blanked by `_strip_non_shell_active`)
- Parse errors (fail-open)

**Rationale:** `worker-cli capture` (iterative-dev plugin, 2026-06 redesign) now returns clean, scoped-to-last-prompt output on stdout directly. Appending `| tail -40` / `| grep X` re-truncates the already-complete output and stacks duplicate lines in context. Direct clone of `rewrite_worker_cli_response_noise.py` with anchor swapped to `\bworker-cli\s+capture\b` and `_NOISE_RE` narrowed to pipe-only.

**Fail-open:** exits 0 on any parse/internal error.

**Smoke:** `dev/hook_smoke/test_rewrite_worker_cli_capture_noise.py` (17 cases: 5 positive strip, 1 `--raw`-survives strip, 3 redirect-preserved no-op, 8 negative no-op including `worker-cli response | tail` and `worker-cli send` quoted-capture pass-throughs).

---

### Hook 34 — `block_broad_find.py` (`src/hooks/block_broad_find.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_broad_find.py`
- **Timeout:** 5s

**Detection (ALL three must hold to block):**
1. At least one search root is BROAD — after `os.path.expanduser` + `os.path.normpath`: equals home dir, equals `/`, or equals/is under `~/.claude/`
2. No `-maxdepth N` predicate in the find segment
3. Output is NOT immediately `| head`-bounded (`after_segment` does not start with `| head`)

**Root extraction:** tokenises the find segment, skips leading global options (`-H`, `-L`, `-P`, `-O<level>`, `-D debugopts`), collects tokens until the first predicate (token starting with `-`, `(`, `!`, `,`). Each root normalised by replacing `$HOME`/`${HOME}` prefix with `~` first, then `os.path.expanduser` + `os.path.normpath` — covers bare forms AND all subpath forms (`$HOME/.claude`, `${HOME}/foo`) uniformly. Trailing slashes handled by `normpath` (`~/` → home).

**Broad-root set (intentionally tight):**
- `~`, `~/`, `$HOME`, `${HOME}` — home directory in any form
- `/` — filesystem root
- `~/.claude` or any path under it — the `.claude` subtree (hundreds of session/worktree dirs)

Non-broad (pass-through): `.`, relative paths, specific project paths, `~/Documents`, `~/Library`, etc.

**Blocked patterns:**
- `find ~/.claude -type d -iname '*searxng*'` — trigger incident: traversed whole `.claude` tree, ~80 results, context flood
- `find ~ -name foo` — home dir, unbounded
- `find ~/ -type f` — trailing-slash home (normalised by `normpath`)
- `find $HOME -type f` — env-var home
- `find / -name bar` — filesystem root
- `find ~/.claude/projects -type d` — subpath under `.claude`
- `find $HOME/.claude -type d` — same damage class, `$HOME` prefix form

**Allowed patterns:**
- `find ~/.claude -type d ... | head -20` — head-bounded → no context-flood risk
- `find ~ -maxdepth 2 -name foo` — maxdepth limits traversal
- `find src/ -name '*.py'` — non-broad root
- `find . -type f` — dot is not broad
- `find /Users/x/Documents/ai/project -name '*.py'` — specific project path
- `echo "find ~ -name foo"` — quoted: blanked by `_strip_non_shell_active`

**Head-bounded exemption.** `_find_segment()` returns `(segment, after_segment)`. `_is_head_bounded(after)` checks `^\s*\|\s*head\b` on `after_segment` only — head is the DIRECT next pipe. A `| head` further downstream in the chain does NOT exempt. Rationale: output between the find and the eventual head is still unbound (intermediate commands may buffer/log it). A `| tee`, `| wc`, or `| grep` immediately after find does NOT exempt — only `| head` immediately produces bounded output without logging the full tree.

**Rationale:** unbounded `find` over a broad tree is the same context-flood damage class as broad recursive `grep` (`block_broad_grep`, Hook 4): both traverse large directory trees and dump unbounded results into context. The difference is that `grep -r` has `--include` scoping; `find` has `-maxdepth` and `| head`. A `find` with `-maxdepth 1` or piped to `| head -20` is bounded and carries no flood risk — those are not blocked. A plain `find ~ -name foo` or `find ~/.claude -type d ...` without any limit is a flood hazard equivalent to `grep -r . --include=` — blocked on damage principle. Deliberately NOT hooked: `ls -lT | head`, bounded `find` with `-maxdepth`, or any output-bounded query — bounded output is friction/style, not damage. The block-on-damage principle from the hook design: only block when irreversible harm or context flooding is certain; pass through any form with a demonstrable bound.

**Fail-open:** exits 0 on any parse/internal error. `_parse_command()` returns `(None, None)` on exception. `_extract_roots()` returns `[]` if segment does not start with `find` token. Any path normalisation error returns the token unchanged — which then fails the broad-root check and passes through.

**Smoke:** `dev/hook_smoke/test_block_broad_find.py` (19 cases: 8 block including real incident + trailing-slash + `$HOME` bare + `$HOME/.claude` subpath + multi-root; 11 pass including head-bounded, maxdepth, non-broad roots, quoted args, word-boundary).

---

### Hook 35 — `block_rag_cli_chained.py` (`src/hooks/block_rag_cli_chained.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_rag_cli_chained.py`
- **Timeout:** 5s

**Detection:** shell-stripped command contains `\brag-cli\b` (anchor — early exit if absent); split on `_SEPARATOR_RE` (`&&`, `||`, `;`, `|`, `\n`, space-bounded `&`; redirects `>`, `2>&1` are NOT separators); find the FIRST segment whose `.strip()` starts with `'rag-cli'`; every segment AFTER that index must also start with `'rag-cli'` — if any does not → block (exit 2). Segments BEFORE the first rag-cli segment are unrestricted.

**Blocked patterns:**
- `rag-cli index --collection x ; tail /tmp/x.txt` — rag-cli followed by tail via `;`
- `rag-cli index --collection x && echo done` — rag-cli followed by echo via `&&`
- `rag-cli search_hybrid "q" coll | grep foo` — rag-cli followed by grep via `|`
- `rag-cli list_documents coll | head` — rag-cli followed by head via `|`

**Allowed patterns:**
- `rag-cli index --collection x > /tmp/x.txt` — redirect is not a `_SEPARATOR_RE` token; single segment, nothing after
- `[ -f .rag-docs.json ] && rag-cli update_docs .` — guard before first rag-cli, nothing after
- `cd /some/path && rag-cli index --collection x` — cd before first rag-cli, nothing after
- `rag-cli delete --collection x && rag-cli index --collection x` — both segments start with rag-cli
- any command with no `rag-cli` — anchor exits early, not policed
- `rag-cli` inside single-quoted string or heredoc body — blanked by `_strip_non_shell_active`, anchor fails
- Parse errors (fail-open)

**Rationale:** The orchestrator chains `rag-cli index ... ; tail <log>` (start + read in one command) and then poll-loops. The chained non-rag-cli command is structurally impossible to allow: rag-cli operations produce output that reaches context only via their own exit; piping or chaining to `tail`/`grep`/`head`/`echo` either truncates that output or bypasses it entirely. Segments before the first rag-cli (guards, `cd`) are allowed because they do not follow a rag-cli call and carry no truncation risk. Registered AFTER `rewrite_rag_cli_search_noise.py` in `_HOOK_SCRIPTS` so that hook's `updatedInput` (noise-stripped command) is seen before this block check fires.

**Smoke:** `dev/hook_smoke/test_block_rag_cli_chained.py` (11 cases: 4 block, 7 allow including redirect/guard/cd/two-rag-cli/no-rag-cli/single-quote/heredoc).

---

## Evidenz

**2026-05-22 hook-block analysis** (`dev/hook_firing/reports/2026-05-22_012326.md`, 7 days of CC sessions across all projects):

| Hook | Total blocks | FP | FP rate |
|---|---|---|---|
| `block_chained_sleep` | 29 | 13 | 45% |
| `block_dangerous_kill` | 16 | 0 | 0% |
| `block_read_worktree` | 11 | 0 | 0% |
| `block_broad_grep` | 7 | 0 | 0% |

All 13 FPs for `block_chained_sleep` were `sleep N ≤ 5` after side-effect command (`launchctl`, `pkill`, `worker-cli kill`, `kill -0`). Settling-time allowance added in Hook 2 (2026-05-22).

**2026-05-22 tool-use error analysis** (`dev/tool_use_errors/reports/2026-05-22_opus.md`, 3 Opus JSONL files, 672 tool_use blocks, 25 failures):

| Pattern | Violations | Hookability |
|---|---|---|
| `git diff/log` with bare branch name, missing `--` | 2 | pre-rewritable → Hook 18 |
| Diagnostic `&&` chain (Rule 11) | 10 | prompt-hook-candidate |
| Hook-blocked (existing hooks) | 14 | already handled |

**2026-05-20 compliance run** (5 recent monitor_cc logs, 900 tool_use blocks):

| Rule | Violations | Hook status |
|---|---|---|
| Rule 12 (sleep) | 54 | Rewritten by hook #2 (rewrite_chained_sleep) for trivial-sync patterns; load-bearing pass-through |
| Rule 3 (grep scope) | 23 | Blocked by hook #4 (block_broad_grep) going forward |
| Rule 9 (Read before Edit) | 1 | Not hookable (requires session state) |
| Rule 10 (git dev ambiguity) | 1 | Not hookable (reliable detection requires dir check + repo path parsing) |
| Uncategorized | 19 | Launchctl/menubar errors — not rule violations |

Logs: 5 most recent `api_requests_opus_monitor_cc_*.jsonl` (script superseded by persistent `src/logs/tool_errors.jsonl`, 2026-05-24).

---

**2026-05-12 session findings** (`decisions/OldThemes/tool_use_safety/2026-05-12_session_findings.md`, 67 proxy logs, 2026-05-06 → 2026-05-12):

| Metric | Value |
|---|---|
| Total `pkill -f` calls across 6 days | 267 |
| Concentrated in single session (searxng, 2026-05-08) | 246 (92%) |
| Monitor_CC session 2026-05-09 | 9 |
| Session 2026-05-12 | 18 |
| Workers killed by this pattern (2026-05-12 alone) | 3 (`menubarfix`, `mbarfix2`, `mbarlive`) |

Root-cause mechanism: CC worker processes carry `claude.exe --dangerously-skip-permissions # Worker — <FULL PROMPT TEXT>` as cmdline. Prompt text routinely contains strings like `workflow.py --mode menubar`. `pkill -f <pattern>` matches against the full cmdline → SIGTERM kills the worker (exit 143 = 128+15).

Burst characteristic: 246/267 = 92% of calls came from ONE session. Once the antipattern fires, it fires many times. A hook would have blocked all 246 in that session.

## Recommendation (SOLL)

**Background/foreground simplification (2026-06-24) — SHIPPED, IST = SOLL.** Model: force ALL non-timer background → foreground (Hook 3, whitelist trimmed to sleep-timer only); the two proxy injections (`strip_bg_launch_ack` "go idle" + `strip_bg_completed` "background done") carry all signalling. Removed Hooks 8/21/33 (polling + log-read blockers) and 25/26 (force-to-bg). Backed by smoke 9/9 (`dev/hook_smoke/test_block_unauthorized_background.py`), live-verify (`.log` read passes; zero stale registrations post-merge → no Bash lockout), and the auto-background evidence (CC auto-backgrounds a long foreground job emitting the catchable ack). No shell-`&` foreground hook built — see Offene Fragen. Full narrative: `decisions/OldThemes/tool_use_safety/2026-06-24_background_foreground_simplification.md`.

Remaining hooks — Keep + audit logging. Pending:
- `rewrite_chained_sleep` (Hook 2): re-audit in ~5–7 days. If `rag-cli`, `bd`, `worker-cli` (mixed tokens from 2026-05-24 audit) show safe strip pattern for read-only subcommands, expand `_TRIVIAL` set. Script: `dev/sleep_pattern_analysis/analyze.py`. Audit: `decisions/OldThemes/hook_false_positives/sleep_pattern_audit_2026-05-24.md`.
- Next candidate: Rule-9 violations (Read before Edit) — requires session state, not statically detectable from a single payload → likely NOT hookable.

## Offene Fragen

- **shell-`&` work-hiding (accepted residual, 2026-06-24):** Hook 3 forces only the CC `run_in_background` flag → foreground; a shell-level `cmd &` (incl. `nohup … &`) bypasses it, produces NO CC ack, NO proxy injection, runs detached/invisible. A `work-cmd &` could thus be polled unguarded (block_polling_loop / block_log_read removed). NOT closed: forcing shell-`&` foreground would break legit `nohup`/launchd daemon launches (daemon never completes → no wake). No frequency evidence → block-on-evidence principle → revisit with a targeted hook only if fire-log shows real `work-cmd &` polling. See `decisions/OldThemes/tool_use_safety/2026-06-24_background_foreground_simplification.md`.
- **Next antipattern:** Rule-9 (Read before Edit/Write) — 1 violation in 2026-05-20 run; requires session state to detect (which files were read this session), not hookable from a single tool_input payload alone.
- **Migration threshold:** when is a negative rule in `tool-use.md` mature enough to be retired in favour of a hook? Proposed criterion: pattern fires ≥3× in a 7-day window AND can be reliably regex-captured without false positives.
- **Worker-local suppression:** should workers running in worktrees be able to suppress specific hooks? Currently no mechanism — global registration means all hooks fire everywhere.

## Quellen

- `decisions/OldThemes/tool_use_safety/2026-05-12_session_findings.md` — session findings, 267-call quantification, hook design rationale
- `src/menubar/hook_setup.py` — registration pattern mirrored by `src/hooks/hook_setup.py`
- Anthropic PreToolUse hook reference: exit-code semantics (0 = allow, 2 = block with stderr, 1 = hook error)
