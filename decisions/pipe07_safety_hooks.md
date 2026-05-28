# pipe07 — Safety Hooks (PreToolUse)

## Status Quo (IST)

18 safety hooks registered globally in `~/.claude/settings.json`. All 18 call `log_fire()` (from shared `src/hooks/_fire_log.py`) at their decision-point, appending fire-events to `src/logs/hook_firing.jsonl` (append-forever, fail-silent). Passthroughs are not logged. 14 block hooks (exit 2) + 4 rewrite hooks (exit 0 + updatedInput JSON): `rewrite_bd_invalid_repo`, `rewrite_chained_sleep`, `rewrite_background_sleep`, `block_path_typo` (legacy name, rewrite semantics).

### Hook 1 — `block_dangerous_kill.py` (`src/hooks/block_dangerous_kill.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — fires for every Bash tool call in every CC session on this machine
- **Command:** `python3 <absolute-path>/src/hooks/block_dangerous_kill.py` (absolute path written at install time by `hook_setup.py`)
- **Timeout:** 5s
- **Install:** `python3 src/hooks/hook_setup.py` from project root (idempotent)

**Blocked patterns:**
- `pkill -f <pattern>` — `\bpkill\s+(-[^\s]*\s+)*-f\b`
- `ps ... | ... grep ... | ... kill ...` — `\bps\b.+\|.+\bgrep\b.+\|.+\bkill\b`

**Allowed patterns (not blocked):** `pkill -x <name>`, `pkill <name>` (no `-f`), `kill <numeric_pid>`, `kill -<signal> <numeric_pid>`, `worker-cli kill <name>`, `launchctl` operations.

### Hook 2 — `rewrite_chained_sleep.py` (`src/hooks/rewrite_chained_sleep.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — same scope as hook 1
- **Command:** `python3 <absolute-path>/src/hooks/rewrite_chained_sleep.py`
- **Timeout:** 5s
- **Replaced:** `block_chained_sleep.py` disabled 2026-05-24 (renamed → `.disabled`) after sleep-pattern audit showed trivial-sync pattern was 30.4% of violations.

**Behavior:** REWRITE hook (exits 0 always, never blocks). Strips `sleep N` when the immediately-preceding command token is in `_TRIVIAL = frozenset({'echo', 'true'})`. Pass-through (no-op) for all other patterns.

**Strip condition (ALL must hold):**
1. A chain operator (`&&`, `||`, `;`) immediately precedes `sleep N`
2. First token of the preceding segment is `echo` or `true`
3. Sleep is NOT inside a `for|while|until ... done` span

**Pass-through (no-op) — sleep preserved as-is:**
- Sleep-first chain (no preceding op) — timer intent
- cmd_before not in `_TRIVIAL` (load-bearing: `kill`, `launchctl`, `pkill`, `tmux`, etc.)
- Loop body sleep
- Any parse/internal error (fail-open)

**Shell-region stripping:** uses `_shell_strip._strip_non_shell_active` (same-dir import) before tokenizing — heredoc bodies and quoted strings replaced with spaces of equal length. Prevents false-positive on `sleep` inside heredoc/string literals.

**Smoke:** `dev/hook_smoke/test_rewrite_chained_sleep.py` (8 cases, 3 strip / 5 pass-through).

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

### Hook 18 — `rewrite_background_sleep.py` (`src/hooks/rewrite_background_sleep.py`)

- **Registration:** `PreToolUse` / `matcher: "Bash"` — same scope as hooks 1–17
- **Command:** `python3 <absolute-path>/src/hooks/rewrite_background_sleep.py`
- **Timeout:** 5s

**Detection:** `tool_input.run_in_background == true` AND command matches `^\s*sleep\s+(\d+(?:\.\d+)?)\s*&&\s*echo\s+done\s*$` AND captured N ≠ 600

**Rewrite:** entire command replaced with `sleep 600 && echo done`

**Passthrough (no output):**
- `run_in_background=false` or field absent — foreground, any form allowed
- `sleep 600 && echo done` with `run_in_background=true` — already canonical value
- Any non-canonical command — form guard already handled by `block_unauthorized_background` (Hook 3)
- Parse errors (fail-open)

**Rationale:** `tool-use.md` specifies Opus timers MUST always be 600s. `block_unauthorized_background` (Hook 3) enforces the FORM (`sleep N && echo done` only); this hook enforces the VALUE (N = 600). Complementary layer — no overlap: Hook 3 passes canonical form through; Hook 18 normalizes any remaining N ≠ 600. Hooks are independent: Hook 3 produces no output for canonical forms so only Hook 18's rewrite reaches CC.

**Fail-open:** exits 0 on any parse/internal error; missing `run_in_background` defaults to `False` → immediate passthrough.

**Smoke:** `dev/hook_smoke/test_rewrite_background_sleep.py` (8 cases: 3 positive rewrite, 5 negative no-op).

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

Keep current 17 hooks + audit logging (no change needed). Pending evaluation after rollout:
- Do hooks #9–17 (2026-05-22 batch) intercept violations without false positives in live sessions?
- `rewrite_chained_sleep` (Hook 2): re-audit in ~5–7 days. If `rag-cli`, `bd`, `worker-cli` (mixed tokens from 2026-05-24 audit) show safe strip pattern for read-only subcommands, expand `_TRIVIAL` set. Script: `dev/sleep_pattern_analysis/analyze.py`. Audit: `decisions/OldThemes/hook_false_positives/sleep_pattern_audit_2026-05-24.md`.
- Next candidate: Rule-9 violations (Read before Edit) — requires session state, not statically detectable from a single payload → likely NOT hookable.

## Offene Fragen

- **Next antipattern:** Rule-9 (Read before Edit/Write) — 1 violation in 2026-05-20 run; requires session state to detect (which files were read this session), not hookable from a single tool_input payload alone.
- **Migration threshold:** when is a negative rule in `tool-use.md` mature enough to be retired in favour of a hook? Proposed criterion: pattern fires ≥3× in a 7-day window AND can be reliably regex-captured without false positives.
- **Worker-local suppression:** should workers running in worktrees be able to suppress specific hooks? Currently no mechanism — global registration means all hooks fire everywhere.

## Quellen

- `decisions/OldThemes/tool_use_safety/2026-05-12_session_findings.md` — session findings, 267-call quantification, hook design rationale
- `src/menubar/hook_setup.py` — registration pattern mirrored by `src/hooks/hook_setup.py`
- Anthropic PreToolUse hook reference: exit-code semantics (0 = allow, 2 = block with stderr, 1 = hook error)
