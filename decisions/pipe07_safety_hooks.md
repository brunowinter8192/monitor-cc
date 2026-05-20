# pipe07 — Safety Hooks (PreToolUse)

## Status Quo (IST)

Seven safety hooks registered globally in `~/.claude/settings.json`:

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

**Detection:** `\bsleep\s+\d+(?:\.\d+)?\b` anywhere in `tool_input.command`

**Allowlist:** full command must match `^\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*$`

**Blocked patterns:**
- `cmd_before; sleep N && echo done` — commands chained before the sleep
- `sleep N && other_cmd` — non-`echo done` continuation after sleep
- Poll loops: `until ...; do sleep N; done`, `while ...; do sleep N; done`

**Allowed:** `sleep N && echo done` (bare, optional whitespace/float) — the one canonical orchestration timer form

**Rationale:** when the menubar auto-abort fires SIGTERM on the sleep PID, the entire chained shell exits 143 and pre-sleep output is lost. This enforces Rule 12 from `~/.claude/shared-rules/global/tool-use.md`.

**Fail-open:** both hooks exit 0 on any parse/internal error — never block on hook failure.

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

## Evidenz

**2026-05-20 compliance run** (`dev/tool_use_analysis/rule_compliance.py`, 5 recent monitor_cc logs, 900 tool_use blocks):

| Rule | Violations | Hook status |
|---|---|---|
| Rule 12 (sleep) | 54 | Blocked by hook #2 (block_chained_sleep) going forward |
| Rule 3 (grep scope) | 23 | Blocked by hook #4 (block_broad_grep) going forward |
| Rule 9 (Read before Edit) | 1 | Not hookable (requires session state) |
| Rule 10 (git dev ambiguity) | 1 | Not hookable (reliable detection requires dir check + repo path parsing) |
| Uncategorized | 19 | Launchctl/menubar errors — not rule violations |

Script: `dev/tool_use_analysis/rule_compliance.py`; logs: 5 most recent `api_requests_opus_monitor_cc_*.jsonl`.

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

Keep current seven hooks (no change needed). Pending evaluation after rollout:
- Do hooks #4-7 intercept violations without false positives in live sessions?
- Next candidate: Rule-9 violations (Read before Edit) — 1 violation in 5-log sample, low frequency, but the hook would be simple (check tool_input.file_path was recently read — requires session state, not statically detectable from a single payload → likely NOT hookable).

## Offene Fragen

- **Next antipattern:** Rule-9 (Read before Edit/Write) — 1 violation in 2026-05-20 run; requires session state to detect (which files were read this session), not hookable from a single tool_input payload alone.
- **Migration threshold:** when is a negative rule in `tool-use.md` mature enough to be retired in favour of a hook? Proposed criterion: pattern fires ≥3× in a 7-day window AND can be reliably regex-captured without false positives.
- **Worker-local suppression:** should workers running in worktrees be able to suppress specific hooks? Currently no mechanism — global registration means all hooks fire everywhere.

## Quellen

- `decisions/OldThemes/tool_use_safety/2026-05-12_session_findings.md` — session findings, 267-call quantification, hook design rationale
- `src/menubar/hook_setup.py` — registration pattern mirrored by `src/hooks/hook_setup.py`
- Anthropic PreToolUse hook reference: exit-code semantics (0 = allow, 2 = block with stderr, 1 = hook error)
