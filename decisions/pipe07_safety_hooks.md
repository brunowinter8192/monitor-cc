# pipe07 — Safety Hooks (PreToolUse)

## Status Quo (IST)

18 safety hooks registered globally in `~/.claude/settings.json`:

### Hook 1 — `block_dangerous_kill.py` (`src/hooks/block_dangerous_kill.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call in every CC session on this machine
- **Command:** `python3 <absolute-path>/src/hooks/block_dangerous_kill.py` (absolute path written at install time by `hook_setup.py`)
- **Timeout:** 5s
- **Install:** `python3 src/hooks/hook_setup.py` from project root (idempotent)

**Blocked patterns:**
- `pkill -f <pattern>` — `\bpkill\s+(-[^\s]*\s+)*-f\b`
- `ps ... | ... grep ... | ... kill ...` — `\bps\b.+\|.+\bgrep\b.+\|.+\bkill\b`

**Allowed patterns (not blocked):** `pkill -x <name>`, `pkill <name>` (no `-f`), `kill <numeric_pid>`, `kill -<signal> <numeric_pid>`, `worker-cli kill <name>`, `launchctl` operations.

### Hook 2 — `block_chained_sleep.py` (`src/hooks/block_chained_sleep.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — same scope as hook 1
- **Command:** `python3 <absolute-path>/src/hooks/block_chained_sleep.py`
- **Timeout:** 5s

**Detection:** `_SLEEP_TOKEN = \bsleep\s+\d+(?:\.\d+)?\b` anywhere in shell-active portion of command (after heredoc/quote stripping). Also reads `tool_input.run_in_background`.

**Allowlist:**
- Full command matches `^\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*$` (canonical timer) — always allowed
- OR: `_is_settling_time_allow()` returns True: foreground (`run_in_background=False`), no loop keyword, N ≤ 5, side-effect command present in stripped text

**Side-effect commands** (`_SIDE_EFFECT_RE`, mirrored from `dev/hook_firing/analyze.py`):
`pkill`, `launchctl`, `kickstart`, `bootout`, `worker-cli kill`, `systemctl`, `kill -<digit>`

**Blocked patterns:**
- `cmd_before; sleep N && echo done` — commands chained before the sleep
- `sleep N && other_cmd` — non-`echo done` continuation after sleep
- Poll loops: `until ...; do sleep N; done`, `while ...; do sleep N; done`
- Non-canonical `sleep N` with `run_in_background=true`
- Non-canonical `sleep N > 10` in any chain

**Allowed patterns:**
- `sleep N && echo done` (bare, optional whitespace/float) — the one canonical orchestration timer form
- `launchctl bootout ... ; sleep 1 ; echo done` — settling-time after side-effect, N ≤ 5
- `pkill -x menubar && sleep 2 ; echo restarted` — same class

**Rationale:** 45% FP rate (13/29 blocks) measured 2026-05-22 (`dev/hook_firing/reports/2026-05-22_012326.md`). All 13 FPs were `sleep N ≤ 5` after a side-effect command — legitimate restart/kill settling waits. Core protection (SIGTERM/menubar abort path) unaffected: orchestration timer (`run_in_background=True`) and polling loops remain blocked.

**Fail-open:** exits 0 on any parse/internal error — never block on hook failure.

### Hook 3 — `block_unauthorized_background.py` (`src/hooks/block_unauthorized_background.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — same scope as hooks 1 and 2
- **Command:** `python3 <absolute-path>/src/hooks/block_unauthorized_background.py`
- **Timeout:** 5s

**Detection:** `tool_input.run_in_background == true`

**Allowlist:** full command must match `^\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*$`

**Blocked patterns:**
- Any `run_in_background=true` command that is NOT the canonical timer — e.g. `rag-cli update_docs .`, `python3 script.py`, builds, test runners

**Allowed:** `sleep N && echo done` with `run_in_background=true` — the one canonical orchestration timer form; any command with `run_in_background=false` or field absent

**Rationale:** background mode hides stdout/stderr until completion, making long-running tools unmonitorable. `rag-cli update_docs .` with `run_in_background=true` ran 2m36s with no live output — the triggering incident. Enforces Rule 12 from `~/.claude/shared-rules/global/tool-use.md`.

**Fail-open:** exits 0 on any parse/internal error; `(None, False)` default on exception means missing/invalid fields are treated as foreground — never blocks on hook failure.

### Hook 4 — `block_broad_grep.py` (`src/hooks/block_broad_grep.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"`
- **Command:** `python3 <absolute-path>/src/hooks/block_broad_grep.py`
- **Timeout:** 5s

**Detection:** `\bgrep\b` with recursive flag (`-r`/`-R`, combined or standalone) AND no `--include=` present AND last arg doesn't end in a known file extension

**Allowlist:** `--include=` present; last arg ends in `.py`/`.md`/`.sh`/`.json`/`.jsonl`/`.yaml`/`.yml`/`.toml`/`.ts`/`.js`/`.go`/`.rs`/`.txt`/`.cfg`/`.ini`/`.sql`/`.html`/`.css`; `git grep` (exempted)

**Blocked patterns:**
- `grep -rn <pattern> src/` — directory target, no scope
- `grep -rn <pattern> .` — dot, no scope
- `grep -rnl <pattern> ~/.claude/` — any broad tree

**Allowed:** `grep -rn pattern src/ --include='*.py'`; `grep -rn pattern workflow.py`; `grep -n pattern file.py` (no `-r`)

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

### Hook 8 — `block_read_worktree.py` (`src/hooks/block_read_worktree.py`)

- **Registration:** `PreToolUse` / `matcher: "Read"` — fires for every Read tool call
- **Command:** `python3 <absolute-path>/src/hooks/block_read_worktree.py`
- **Timeout:** 5s

**Detection:** `tool_input.file_path` contains `.claude/worktrees/` AND the path is NOT under the calling session's own worktree root (derived from `os.getcwd()`)

**Blocked patterns:** Read on a foreign worktree path (main session reading a worker's file, or one worker reading another worker's file) — triggers CLAUDE.md re-injection into context

**Allowed patterns:** file_path outside any worktree; file_path inside the calling session's own worktree; parse errors (fail-open)

**Rationale:** Reading any file under `.claude/worktrees/...` via the Read tool re-injects CLAUDE.md as a system-reminder, bloating the context window and potentially duplicating the system prompt. Added 2026-05-21 during friction-reduction pass.

**Fail-open:** exits 0 on any parse error; `_is_own_worktree()` returns False on any `os.getcwd()` exception → conservative block rather than silent allow for unknown CWD.

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

**Detection:** five compiled regex patterns applied to quote-stripped command; `git config` write-variant detected separately (excludes `--list|--get|--show-origin|...` read-only flags)

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

### Hook 18 — `rewrite_git_ambiguous.py` (`src/hooks/rewrite_git_ambiguous.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call
- **Command:** `python3 <absolute-path>/src/hooks/rewrite_git_ambiguous.py`
- **Timeout:** 5s
- **Hook type:** block-with-hint (exit 2 + one-line stderr). Originally designed as `updatedInput` rewrite (allow + JSON), but live testing 2026-05-22 confirmed CC does NOT apply `updatedInput` for general PreToolUse + `allow` decisions on Bash — that path is restricted to the `AskUserQuestion` tool (per CC CHANGELOG line 1324). General Bash rewrite would require `permissionDecision: "ask"` (CHANGELOG line 2629), which adds confirmation friction — rejected by design. Hook detects the same patterns and surfaces a one-line stderr hint; the model retries with `--` appended manually.

**Detection (blocks when ALL true):**
1. Command matches `\bgit\b.*?\b(diff|log|show)\b` (DOTALL)
2. No standalone ` -- ` path separator present (regex: `(?:^|\s)--(?:\s|$)`)
3. Either a range token (`[\w./:-]+\.\.[\w./:-]*`) OR a bare ref name (first non-flag token after subcommand matches `^[a-zA-Z0-9][a-zA-Z0-9_/\-]*$`)

**Stderr message:** "BLOCKED: git diff/log/show with bare ref or ..-range — append ` -- ` after the git subcommand args (before any pipe or redirect) to disambiguate branch/ref from path."

**Blocked patterns:**
- `git diff dev --stat` — bare ref name `dev`, no `--` separator
- `git log dev..HEAD` — range token `dev..HEAD`, no `--` separator
- `git -C /path diff dev` — bare ref name `dev`

**Retry forms (user/model appends ` -- ` after subcommand args):**
- `git diff dev --stat --`
- `git log dev..HEAD --`
- `git -C /path diff dev --`

**Passthrough (no block):**
- `git log dev..HEAD -- src/foo.py` — already has ` -- ` separator
- `git diff --stat` — no range token, no bare ref
- `git commit -m "fix"` — not diff/log/show

**Coverage note:** addresses both violation forms from 2026-05-22 data (`dev/tool_use_errors/reports/2026-05-22_opus.md`): bare-name form (`git diff dev --stat`) and range form (`git diff dev..HEAD`). 2 violations in 672 tool_use blocks from 3 Opus JSONL files.

**Edge case (multi-git chain):** when a single Bash invocation chains multiple git commands with one having ` -- ` and another not (e.g. `git diff dev -- --stat ; git diff main`), the second command's missing `--` is masked by the first's presence — hook sees `_has_path_separator=True` for the whole chain. Rare in practice. Recommend not chaining git diff/log/show calls in one Bash invocation.

**Fail-open:** exits 0 with no output (passthrough) on any parse/internal error.

## Evidenz

**2026-05-22 hook-block analysis** (`dev/hook_firing/analyze.py`, `dev/hook_firing/reports/2026-05-22_012326.md`, 7 days of CC sessions across all projects):

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

Hook 18 (`rewrite_git_ambiguous`) covers the 2 `git-ambiguous` violations.

---

**2026-05-20 compliance run** (`dev/tool_use_errors/analyze.py`, 5 recent monitor_cc logs, 900 tool_use blocks):

| Rule | Violations | Hook status |
|---|---|---|
| Rule 12 (sleep) | 54 | Blocked by hook #2 (block_chained_sleep) going forward |
| Rule 3 (grep scope) | 23 | Blocked by hook #4 (block_broad_grep) going forward |
| Rule 9 (Read before Edit) | 1 | Not hookable (requires session state) |
| Rule 10 (git dev ambiguity) | 1 | Not hookable (reliable detection requires dir check + repo path parsing) |
| Uncategorized | 19 | Launchctl/menubar errors — not rule violations |

Script: `dev/tool_use_errors/analyze.py`; logs: 5 most recent `api_requests_opus_monitor_cc_*.jsonl`.

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

Keep current 18 hooks (no change needed). Pending evaluation after rollout:
- Do hooks #9–18 (2026-05-22 batch) intercept violations without false positives in live sessions?
- `block_chained_sleep` settling-time allowance: verify 45% FP rate drops after rollout (baseline: 13/29 blocks were FP per `dev/hook_firing/reports/2026-05-22_012326.md`).
- `rewrite_git_ambiguous` original `updatedInput` plan: REFUTED 2026-05-22 — CC PreToolUse + `allow` + `updatedInput` does NOT apply on Bash (per CHANGELOG line 1324, this path is `AskUserQuestion`-tool-specific). Hook converted to block-with-hint (exit 2 + stderr). See `decisions/OldThemes/tool_use_safety/2026-05-22_hook_api_capabilities.md` Finding 1 for the empirical correction. Future option: re-enable `updatedInput` if Anthropic extends the API to cover general PreToolUse.
- Next candidate: Rule-9 violations (Read before Edit) — requires session state, not statically detectable from a single payload → likely NOT hookable.

## Offene Fragen

- **Next antipattern:** Rule-9 (Read before Edit/Write) — 1 violation in 2026-05-20 run; requires session state to detect (which files were read this session), not hookable from a single tool_input payload alone.
- **Migration threshold:** when is a negative rule in `tool-use.md` mature enough to be retired in favour of a hook? Proposed criterion: pattern fires ≥3× in a 7-day window AND can be reliably regex-captured without false positives.
- **Worker-local suppression:** should workers running in worktrees be able to suppress specific hooks? Currently no mechanism — global registration means all hooks fire everywhere.

## Quellen

- `decisions/OldThemes/tool_use_safety/2026-05-12_session_findings.md` — session findings, 267-call quantification, hook design rationale
- `src/menubar/hook_setup.py` — registration pattern mirrored by `src/hooks/hook_setup.py`
- Anthropic PreToolUse hook reference: exit-code semantics (0 = allow, 2 = block with stderr, 1 = hook error)
