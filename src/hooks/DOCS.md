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

### _shell_strip.py (194 LOC)

**Purpose:** Shared utility — provides `_strip_non_shell_active(command)`, the position-preserving shell-region stripper used by twenty Bash-scanning hooks. Replaces heredoc bodies, single/double-quoted strings, and ANSI-C `$'...'` quotes with spaces of the same length before pattern matching runs. Command substitutions `$(...)` and backtick expressions are kept shell-active. Fail-open: any parse error returns the original command unchanged (never silently allows a blocked pattern due to a strip failure). `_strip_impl` is decomposed into 6 private scan helpers (`_scan_heredoc`, `_scan_ansi_c_quote`, `_scan_cmd_subst`, `_scan_backtick`, `_scan_single_quote`, `_scan_double_quote`), each returning `(fragment, new_i)`.
**Reads:** n/a (pure logic module, not a standalone script).
**Writes:** n/a.
**Called by:** `block_background_sleep_nonworker.py`, `block_broad_find.py`, `block_broad_grep.py`, `block_dangerous_kill.py`, `block_gh_cli_chained.py`, `block_manual_worker_cleanup.py`, `block_rag_cli_chained.py`, `block_search_subreddits_limit.py`, `block_venv_no_redirect.py`, `block_worker_kill_while_working.py`, `block_worker_send_background.py`, `block_worker_spawn_opus.py`, `block_worker_spawn_placement.py`, `rewrite_chained_sleep.py`, `rewrite_rag_cli_search_noise.py`, `rewrite_searxng_scrape_noise.py`, `rewrite_worker_cli_capture_noise.py`, `rewrite_worker_cli_response_noise.py` via `sys.path` insertion + `from _shell_strip import _strip_non_shell_active`.
**Calls out:** stdlib only (no imports).

---

### _fire_log.py (44 LOC)

**Purpose:** Shared utility — provides `log_fire(hook_name, decision, tool_name, command, reason=None, rewritten=None, session_id=None)`, the single fire-event appender used by all 33 active hooks. Appends one JSON line per fire to `src/logs/hook_firing.jsonl`. For `decision="block"`: includes `reason` field (stderr text), omits `rewritten`. For `decision="rewrite"`: includes `rewritten` field (new command/path), omits `reason`. Fail-silent: any exception in the write path is swallowed so a logging failure never breaks the hook itself. Log path overridable via `MONITOR_CC_HOOK_FIRING_LOG` env var (used for test isolation in `dev/hook_smoke/`).
**Reads:** n/a (pure logic module, not a standalone script).
**Writes:** `src/logs/hook_firing.jsonl` (appends one line per fire; path resolved from `__file__` relative to `src/`).
**Called by:** all 36 active hook scripts via `sys.path` insertion + `from _fire_log import log_fire`. Called at the decision-point only (immediately before `sys.exit(2)` for blocks; immediately before `print(json.dumps(output))` for rewrites). NOT called on passthroughs.
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

### block_chained_sleep.py.disabled

**Disabled 2026-05-24** — superseded by `rewrite_chained_sleep.py`. Renamed via `git mv` (file still in repo for history). Previously blocked all non-canonical `sleep N` chains. Replaced by a rewrite hook that strips trivial-sync sleeps (`echo`, `true` cmd_before) and passes load-bearing patterns through. See `decisions/OldThemes/hook_false_positives/sleep_pattern_audit_2026-05-24.md` for audit rationale.

---

### rewrite_chained_sleep.py (143 LOC)

**Purpose:** PreToolUse hook (Bash) — **rewrites** chained `sleep N` by stripping it when the immediately-preceding segment is in `_TRIVIAL` (single-token read-only-fast commands) or `_TRIVIAL_PAIRS` (two-token exact pairs for safe subcommands of multi-verb CLIs). Sleep-first chains, load-bearing predecessors, and loop-body sleeps are passed through unchanged (no-op). Exits 0 in all cases (fail-open rewrite hook — never blocks). Uses `_shell_strip._strip_non_shell_active` for position-preserving heredoc + quote removal before tokenizing.
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stdout (JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.command`) when sleep(s) were stripped; nothing when no-op.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (same-dir import via `sys.path` insert).

**Allowlist:**
- `_TRIVIAL` (first token of preceding segment): `echo`, `true`, `grep`, `cat`, `ls`, `wc`, `head`, `tail`, `find`
- `_TRIVIAL_PAIRS` (`(tokens[0], tokens[1])` exact pair): `(git,status)`, `(git,log)`, `(git,diff)`, `(git,show)`, `(rag-cli,search_hybrid)`, `(worker-cli,status)`, `(worker-cli,list)`, `(worker-cli,response)`

**Strip condition (ALL must hold):**
1. A chain operator (`&&`, `||`, `;`) immediately precedes `sleep N` (only whitespace between op and sleep)
2. `tokens[0]` of the preceding segment is in `_TRIVIAL`, OR `(tokens[0], tokens[1])` is in `_TRIVIAL_PAIRS`
3. Sleep is NOT inside a `for|while|until ... done` span

**Pass-through (no-op) conditions:**
- Sleep-first chain (no preceding chain op) — intent is timing
- cmd not in `_TRIVIAL` and pair not in `_TRIVIAL_PAIRS` (e.g. `git push`, `rag-cli index`, `worker-cli send/kill`, `launchctl`, `tmux`)
- Flag between command and subcommand (e.g. `git -C <path> status` → `tokens[1]='-C'` → pair not found → no strip; conservatively fail-toward-preserve)
- Single `&` background operator — not in `_CHAIN_RE`, so sleep has no preceding chain op → no strip
- Sleep inside loop body

**Smoke:** `dev/hook_smoke/test_rewrite_chained_sleep.py` (31 cases: 18 strip, 13 pass-through).

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

### rewrite_worker_cli_response_noise.py (107 LOC)

**Purpose:** PreToolUse hook (Bash) — **rewrites** `worker-cli response` invocations by stripping downstream noise inside the logical command segment: pipes (`| head`, `| tail`, `| grep`, etc.), redirects (`>`, `>>`, `&>`, `<`, `2>&1`, `2>`), and single backgrounding `&`. Chains around the segment (`cd && worker-cli response ...`, `worker-cli response ... ; bd list`, `worker-cli response ... || echo fail`) are preserved — only the response segment is cleaned. Scope is `response` only; `capture`, `status`, `list`, `send`, `merge`, `spawn`, `kill`, `revive` pass through unchanged. Critical guaranteed no-op: `worker-cli capture X | tail -40` (documented legitimate fallback) — the anchor `\bworker-cli\s+response\b` cannot match `capture`. Direct clone of `rewrite_rag_cli_search_noise.py` with anchor swapped. Exits 0 in all cases (fail-open rewrite hook — never blocks). Uses `_shell_strip._strip_non_shell_active` for position-preserving heredoc + quote removal before tokenizing.
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stdout (JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.command`) when noise was stripped; nothing when no-op.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (same-dir import via `sys.path` insert); `_fire_log.log_fire`.

**Strip mechanic:**
1. Find `\bworker-cli\s+response\b` matches in the shell-stripped command.
2. For each match, determine its segment-end by scanning forward for `;`, `&&`, `||`, `)`, `\n`, or single `&` (not part of `&&`, `&>`, or `2>&1`).
3. Within `[match_end, segment_end)`, find the first noise marker (`|` excluding `||`, any redirect, or `2>&1`).
4. Strip from the noise marker through segment-end. If segment-end equals end-of-command, also eat leading whitespace before the noise (avoids trailing-space artifact); otherwise preserve it as separator to the trailing chain.

**Pass-through (no-op) conditions:**
- `worker-cli response` invocation has no pipe/redirect inside its segment
- `worker-cli` subcommand is not `response` (out of scope — anchor cannot match other subcommands)
- `worker-cli response` token appears inside a quoted string (blanked by `_strip_non_shell_active`)

**Smoke:** `dev/hook_smoke/test_rewrite_worker_cli_response_noise.py` (16 cases: 9 positive strip, 7 negative no-op including the critical `worker-cli capture | tail` pass-through).

---

### rewrite_worker_cli_capture_noise.py (109 LOC)

**Purpose:** PreToolUse hook (Bash) — **rewrites** `worker-cli capture` invocations by stripping downstream pipes inside the logical command segment. Redirects (`>`, `>>`, `2>&1`, `&>`, `<`) are **preserved** — `worker-cli capture X > /tmp/file` is a legitimate pattern (save clean output to disk). Scope is `capture` only; `response`, `status`, `list`, `send`, `merge`, `spawn`, `kill`, `revive` pass through unchanged. `--raw` flag (sits before any pipe) is never inside the strip range and survives automatically. Chains around the segment (`cd && worker-cli capture ...`, `worker-cli capture ... ; echo done`) are preserved — only the capture segment is cleaned. Exits 0 in all cases (fail-open rewrite hook — never blocks). Uses `_shell_strip._strip_non_shell_active` for position-preserving heredoc + quote removal before tokenizing. Direct clone of `rewrite_worker_cli_response_noise.py` with anchor swapped to `\bworker-cli\s+capture\b` and `_NOISE_RE` narrowed to pipe-only (`(?<!\|)\|(?!\|)`).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stdout (JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.command`) when pipe noise was stripped; nothing when no-op.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (same-dir import via `sys.path` insert); `_fire_log.log_fire`.

**Strip mechanic:**
1. Find `\bworker-cli\s+capture\b` matches in the shell-stripped command.
2. For each match, determine its segment-end by scanning forward for `;`, `&&`, `||`, `)`, `\n`, or single `&` (not part of `&&`, `&>`, or `2>&1`).
3. Within `[match_end, segment_end)`, find the first pipe `|` (excluding `||`). Redirects are not noise — no redirect patterns in `_NOISE_RE`.
4. Strip from the pipe through segment-end. If segment-end equals end-of-command, also eat leading whitespace before the pipe (avoids trailing-space artifact); otherwise preserve it as separator to the trailing chain.

**Pass-through (no-op) conditions:**
- `worker-cli capture` invocation has no pipe inside its segment
- `worker-cli capture X > /tmp/file` — redirect is not a pipe → no noise marker → unchanged
- `worker-cli capture X --raw` — flag, no pipe
- `worker-cli` subcommand is not `capture` (out of scope — anchor cannot match other subcommands)
- `worker-cli capture` token appears inside a quoted string (blanked by `_strip_non_shell_active`)

**Smoke:** `dev/hook_smoke/test_rewrite_worker_cli_capture_noise.py` (17 cases: 5 positive strip, 1 `--raw`-survives strip, 3 redirect-preserved no-op, 8 negative no-op).

---

### rewrite_searxng_scrape_noise.py (~95 LOC)

**Purpose:** PreToolUse hook (Bash) — **rewrites** `searxng-cli scrape_url` invocations by stripping downstream noise inside the logical command segment: pipes (`| head`, `| tail`, `| sed`, `| grep`), redirects (`>`, `>>`, `&>`, `<`, `2>&1`, `2>`), and single backgrounding `&`. Direct clone of `rewrite_rag_cli_search_noise.py` with the anchor swapped to `\bsearxng-cli\s+scrape_url\b`. Rationale: `scrape_url` output is bounded (15k PruningContentFilter cap) and meant to land directly in context; a `> /tmp/file 2>&1` redirect followed by `| head` truncates the page and mixes crawl4ai browser logs into what looks like content (real incident — gave a "content stops after section 3" false impression and an apparent `=== LOG RECORD ===` leak that were both display artifacts of the truncating command, not the scraper). Scope is `scrape_url` only; `search_web`, `search_engine_drilldown`, `download_pdf` produce bounded output and pass through unchanged. Chains around the segment (`cd && scrape_url ...`, `scrape_url ... ; bd list`, `scrape_url ... || echo fail`) are preserved — only the scrape segment is cleaned. Exits 0 in all cases (fail-open rewrite hook — never blocks). Uses `_shell_strip._strip_non_shell_active` for position-preserving heredoc + quote removal before tokenizing.
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stdout (JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.command`) when noise was stripped; nothing when no-op.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (same-dir import via `sys.path` insert); `_fire_log.log_fire`.

**Strip mechanic:** identical to `rewrite_rag_cli_search_noise.py` — find `\bsearxng-cli\s+scrape_url\b` matches, scan forward to segment-end (`;`, `&&`, `||`, `)`, `\n`, single `&`), strip the first noise marker through segment-end. Eats leading whitespace only when the segment extends to end-of-command.

**Pass-through (no-op) conditions:**
- `searxng-cli scrape_url` invocation has no pipe/redirect inside its segment
- subcommand is not `scrape_url` (search_web / search_engine_drilldown / download_pdf out of scope)
- `searxng-cli scrape_url` token appears inside a quoted string (blanked by `_strip_non_shell_active`)

**Smoke:** `dev/hook_smoke/test_rewrite_searxng_scrape_noise.py` (16 cases: 9 positive strip, 7 negative no-op).

---

### block_background_sleep_nonworker.py (143 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks sleep-only background timers (`run_in_background=True` + `_SLEEP_ONLY_BG` match) when the **last non-timer Bash command** in the session was NOT a `worker-cli` command. Rationale: the only legitimate sleep-timer is the worker-wait poll loop, where every timer is immediately preceded by a `worker-cli spawn/status/send`. A timer after any other command (e.g. `rag-cli index`, a build) is a redundant "wait" for a self-notifying background task — the orchestrator should go idle instead. Exits 2 + stderr on block. Exits 0 for all non-timer commands (after recording state). Exits 0 (fail-open) on any IO/parse error. Fails open on state-read IO errors (a transient error must NOT start blocking legitimate worker-wait timers for the whole session).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command, run_in_background}, session_id}`); `logs/last_cmd_state.jsonl` (per-session latest non-timer command).
**Writes:** `logs/last_cmd_state.jsonl` (updated on every non-timer Bash call — one entry per session, self-pruning at 24h); stderr (block message) on block only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Registered BEFORE `rewrite_background_sleep.py` — a blocked timer never reaches the rewrite hook. Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (worker-cli detection on stored cmd); `_fire_log.log_fire`; stdlib (`datetime`, `json`, `os`, `re`, `sys`).

**Timer detection:** `run_in_background == True AND _SLEEP_ONLY_BG.match(command)` — same regex as `rewrite_background_sleep.py`: `^\s*sleep\s+\d+(?:\.\d+)?\s*(?:&&\s*echo\b[^;&|\n]*)?\s*$`.

**worker-cli detection:** `_strip_non_shell_active(stored_cmd)` → `^\s*worker-cli\b` — matches any `worker-cli` subcommand (`spawn`, `status`, `send`, …) as the leading token.

**State file (`logs/last_cmd_state.jsonl`):** JSONL, one entry per session: `{"ts": "...", "session_id": "...", "cmd": "..."}`. On every non-timer Bash call: read → drop own session entry + drop entries >24h old → append new entry → overwrite (one-per-session, self-pruning). Timer calls never write state. Path overridable via `MONITOR_CC_LAST_CMD_STATE` env var (test isolation).

**Fail-open split:**
- IO/parse exception on state read (`_READ_ERROR` sentinel) → exit 0 (allow — transient error must not block worker loop).
- State read succeeded but no entry found for session → BLOCK (genuine no-prior-command case).

**Block message (user-specified):** "Go idle immediately. Stop whatever you are doing and go idle. A background Bash task self-notifies via its completion notice — do NOT set a timer to wait for it. Timers are ONLY for polling a worker you just spawned/messaged (worker-cli)."

**Smoke:** `dev/hook_smoke/test_block_background_sleep_nonworker.py` (7 cases: (a) rag-cli last → BLOCK, (b) worker-cli spawn last → ALLOW, (c) worker-cli status last → ALLOW, (d) no prior → BLOCK, (e) non-timer bg → exits 0 + state written, (e-verify) state-written confirmed by subsequent timer BLOCK, (f) IO error → fail-open ALLOW).

---

### block_search_subreddits_limit.py (54 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks `reddit-cli search_subreddits` and `cli.py search_subreddits` invocations that carry a `--limit` flag. Subreddit discovery must return the full result set; capping it prematurely hides candidates. Exits 2 + stderr. Exits 0 on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (same-dir import via `sys.path` insert); `_fire_log.log_fire`.

**Blocked patterns:** `reddit-cli search_subreddits "query" --limit N`; `cli.py search_subreddits "query" --limit N` — `--limit` caps the result set before the caller can select from it.

**Allowed patterns:** `reddit-cli search_subreddits "query"` without `--limit`; commands not containing `search_subreddits`; parse errors (fail-open). `_LIMIT_RE` is searched only after `_SEARCH_RE` matches — non-matching commands exit at the first gate.

---

### block_unauthorized_background.py (67 LOC)

**Purpose:** PreToolUse hook — **silently rewrites** any Bash command dispatched with `run_in_background=true` that is NOT a sleep-only timer, flipping `run_in_background` to `false` via `hookSpecificOutput.updatedInput`. Sleep-only commands (bare `sleep N` OR `sleep N && echo <anything>`) are always exempt — both the raw form and the normalized `sleep 600 && echo done` — so a sleep timer is never foreground-forced regardless of hook execution order. All other background commands are foreground-forced without exception. Exits 0 in all cases (fail-open rewrite hook — never blocks). Logs `decision="rewrite"` with `rewritten="run_in_background: true → false"`.
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command, run_in_background}}`).
**Writes:** stdout (JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.{command, run_in_background: false}`) on non-canonical bg; nothing on passthrough.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Rewrite condition:** `run_in_background=true` AND command does NOT match `_CANONICAL` (any sleep-only form: bare `sleep N` OR `sleep N && echo <anything>`, regex `^\s*sleep\s+\d+(?:\.\d+)?\s*(?:&&\s*echo\b[^;&|\n]*)?\s*$`).

**Passthrough (no output):**
- Any sleep-only command (`sleep N`, `sleep N && echo done`, `sleep N && echo "custom text"`) with `run_in_background=true` — `_CANONICAL` matches all sleep-only forms
- Any command with `run_in_background=false` or field absent (foreground — no restriction)
- Parse errors (fail-open)

**No quote-stripping.** Checks the `run_in_background` bool field and `_CANONICAL` only — no general command-text scanning.

---

### rewrite_background_sleep.py (62 LOC)

**Purpose:** PreToolUse hook (Bash) — **rewrites** ANY sleep-only background command to the canonical `sleep 600 && echo done`. Matches bare `sleep N` OR `sleep N && echo <anything>` (regex `_SLEEP_ONLY_BG`). Already-canonical guard: `command.strip() == _TARGET` (exact string match, not N comparison). Pairs with `block_unauthorized_background.py` which exempts all sleep-only background commands from foreground-forcing; this hook normalizes all of them to the canonical 10-minute timer. Exits 0 in all cases (fail-open rewrite hook — never blocks).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command, run_in_background}}`).
**Writes:** stdout (JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.command`) when command is a non-canonical sleep-only form; nothing on passthrough.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `os`, `re`, `sys`).

**Rewrite condition (ALL must hold):**
1. `run_in_background == True`
2. Command matches `_SLEEP_ONLY_BG`: `^\s*sleep\s+\d+(?:\.\d+)?\s*(?:&&\s*echo\b[^;&|\n]*)?\s*$`
3. `command.strip() != "sleep 600 && echo done"`

**Passthrough (no output):**
- `run_in_background=false` or field absent — foreground, any sleep form allowed
- `command.strip() == "sleep 600 && echo done"` — already the canonical target
- Any non-sleep-only command — `_SLEEP_ONLY_BG` fails to match; `block_unauthorized_background.py` handles these
- Parse errors (fail-open)

**Smoke:** `dev/hook_smoke/test_rewrite_background_sleep.py` (11 cases: 5 positive rewrite, 6 negative no-op).

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

### block_broad_find.py (130 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks `find` invocations over broad/unbounded search roots when no `-maxdepth N` predicate is present and output is not immediately `| head`-bounded. Broad roots: `~`, `~/`, `$HOME`, `/`, and the `.claude` subtree (`~/.claude` or any path under it). A `find ~/.claude -type d -iname '*searxng*'` without depth or head limits traverses hundreds of session/worktree dirs and floods context (~80 results — the trigger incident). Exits 2 + stderr with three escapes. Exits 0 on any parse/internal error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with fix options) on violation only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (same-dir import via `sys.path` insert); `_fire_log.log_fire`; stdlib (`json`, `os`, `re`, `sys`).

**Blocked patterns:**
- `find ~/.claude -type d -iname '*searxng*'` — `.claude` subtree, no maxdepth, no head
- `find ~ -name foo` — home dir root, unbounded
- `find ~/ -type f` — trailing-slash form normalised via `os.path.normpath`
- `find $HOME -type f` — `$HOME` resolved to home dir
- `find / -name bar` — filesystem root
- `find ~/.claude/projects -type d` — any subpath under `.claude`

**Allowed patterns:**
- `find ~/.claude -type d ... | head -20` — output immediately piped to `head` (bounded)
- `find ~ -maxdepth 2 -name foo` — `-maxdepth` limits traversal depth
- `find src/ -name '*.py'` — non-broad root (project subdirectory)
- `find . -type f` — `.` is not a broad root
- `find /Users/x/Documents/ai/monitor-cc -name '*.py'` — specific project path
- `echo "find ~ -name foo"` — quoted: blanked by `_strip_non_shell_active`, no match

**Head-bounded exemption.** `_find_segment()` returns `(segment, after_segment)`. `_is_head_bounded(after)` checks `^\s*\|\s*head\b` — true only when `head` is the DIRECT next pipe after the find segment.

**Root extraction.** After `\bfind\b` (word boundary excludes `mdfind`, `findmnt`), leading global options (`-H`, `-L`, `-P`, `-O<level>`, `-D debugopts`) are skipped token-by-token. Tokens are collected as roots until the first predicate (token starting with `-`, `(`, `!`, `,`). Each root is normalised: `$HOME`/`${HOME}` prefix replaced with `~` first, then `os.path.expanduser` + `os.path.normpath` — covers all subpath forms (`$HOME/.claude`, `${HOME}/foo`) uniformly.

**Quote/heredoc stripping.** Before segment extraction, `_strip_non_shell_active()` (from `_shell_strip.py`) removes heredoc bodies and quoted regions. Prevents false-positives when `find ~/.claude ...` appears as literal text inside a `worker-cli send` message.

---

### block_gh_cli_chained.py (71 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks any of the 7 gh-cli search/research tools (`search_repos`, `search_code`, `get_repo_tree`, `get_file_content`, `index_issues`, `index_discussions`, `index_releases`) chained with any non-search command. These tools must run standalone so their full output reaches context — piping through grep/head/tail/sed/awk/wc forces Opus to reconstruct files from fragments instead of reading the complete result. Multiple gh-cli search/research calls combined in one Bash are allowed. The 5 issue-management commands (`list_issues`, `get_issue`, `create_issue`, `update_issue`, `delete_issue`) are fully exempt. Exits 2 + stderr on violation. Exits 0 on any parse/internal error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_input: {command}}`).
**Writes:** stderr (block message) on violation only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active`, `_fire_log.log_fire`; stdlib (`json`, `re`).

**Blocked patterns:**
- `gh-cli search_repos "q" | grep foo` — piped to a non-search command
- `gh-cli index_issues "q" o/r && rag-cli index docs` — chained with rag-cli
- `gh-cli search_code "q" o/r && echo done` — chained with echo
- `gh-cli get_file_content o/r path | head -10` — piped to head

**Allowed patterns:**
- `gh-cli index_issues "q" o/r --limit 30 --offset 0` — standalone with tool-native args
- `gh-cli index_issues "a" o/r && gh-cli index_discussions "b" o/r` — multiple search/research calls combined
- `gh-cli get_file_content o/r path > /tmp/out.txt` — redirect is not a separator
- `gh-cli list_issues o/r | grep open` — issue command, exempt
- any command with none of the 7 search/research calls — not policed

**Segment split.** `_SEPARATOR_RE` splits the (quote-stripped) command on `&&` `||` `;` `|` newline and space-bounded `&`; `>&`/`2>&1` redirects survive intact (no whitespace before `&`). Every non-empty segment must start with one of the 7 gh-cli search/research tools, else block.

**Smoke:** `dev/hook_smoke/test_block_gh_cli_chained.py` (18 cases: 9 block, 6 pass-standalone/two-chained/redirect, 2 exempt-issue-command, 1 single-quote strip, 1 heredoc strip).

---

### block_rag_cli_chained.py (71 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks any rag-cli call when a non-rag-cli segment follows it in the same Bash invocation. **Trailing-only rule:** segments BEFORE the first `rag-cli` are unrestricted (leading `cd` / file-guards stay legal); every segment AFTER the first `rag-cli` segment must also start with `rag-cli`, else block. Redirects (`>`, `2>&1`) are NOT separators and survive as part of their segment — `rag-cli index ... > /tmp/x.txt` is one segment with no trailing non-rag-cli. Exits 2 + stderr on violation. Exits 0 on any parse/internal error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_input: {command}}`).
**Writes:** stderr (block message) on violation only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active`, `_fire_log.log_fire`; stdlib (`json`, `re`).

**Blocked patterns:**
- `rag-cli index --collection x ; tail /tmp/x.txt` — rag-cli followed by tail via `;`
- `rag-cli index --collection x && echo done` — rag-cli followed by echo via `&&`
- `rag-cli search_hybrid "q" coll | grep foo` — rag-cli followed by grep via `|`
- `rag-cli list_documents coll | head` — rag-cli followed by head via `|`

**Allowed patterns:**
- `rag-cli index --collection x > /tmp/x.txt` — redirect is not a separator, one segment
- `[ -f .rag-docs.json ] && rag-cli update_docs .` — guard before first rag-cli, nothing after
- `cd /some/path && rag-cli index --collection x` — cd before first rag-cli, nothing after
- `rag-cli delete --collection x && rag-cli index --collection x` — both segments are rag-cli
- any command with no `rag-cli` — not policed (anchor exits early)
- `rag-cli` inside single-quoted string / heredoc body — blanked by `_strip_non_shell_active`, anchor fails

**Segment split.** Same `_SEPARATOR_RE` as `block_gh_cli_chained.py`: splits on `&&` `||` `;` `|` newline and space-bounded `&`; `>&`/`2>&1` redirects survive intact. `_find_first_rag_segment()` returns the index of the first segment whose stripped form `.startswith('rag-cli')`.

**Smoke:** `dev/hook_smoke/test_block_rag_cli_chained.py` (11 cases: 4 block, 7 allow including redirect/guard/cd/two-rag-cli/no-rag-cli/single-quote/heredoc).

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

**Purpose:** PreToolUse hook (Bash) — blocks destructive git operations: `git commit --amend`, `git push --force`/`-f`/`--force-with-lease`, `git commit/push --no-verify`, `git commit --allow-empty`, and `git config` modifications (read-only config variants allowed). Pattern connectors use `[^|;&\n]*` — matches cannot span across newlines in multi-line commands (closes cross-line FP: `git push` on line N + `[ -f file ]` on a later line). Enforces the Git Safety Protocol from `tool-use.md`. Exits 2 + stderr with the specific violation and a suggestion. Exits 0 on any parse error (fail-open).
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

### block_worker_spawn_placement.py (89 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks `worker-cli spawn` calls that either (a) target a different project than the current session or (b) pass `--no-worktree`. Spawns always land in a worktree of the current project; cross-project or worktree-less spawns are a mis-dispatch. Exits 2 + stderr. Exits 0 when the session itself runs from inside a worktree (worker sessions don't spawn workers) or on any parse/resolution error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`); `os.getcwd()` (session CWD for project-root resolution).
**Writes:** stderr (one-line block message) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (same-dir import via `sys.path` insert); `_fire_log.log_fire`.

**Blocked patterns:**
- `worker-cli spawn <name> <prompt> <path> ...` where `<path>` resolves to a different git-root than the current session's project
- `worker-cli spawn ... --no-worktree` — flag present anywhere after the `spawn` subcommand

**Allowed patterns:** `project_path` of `c` or `.` (resolve to current project by definition); same-project absolute/relative paths; non-spawn commands; spawn from inside a worktree CWD (skipped); parse or path-resolution errors (fail-open).

**Project-root resolution** (mirrors worker-cli's `resolve_project_path`):
1. `os.path.abspath(expanduser(path))` → absolute form
2. Strip `/.claude/worktrees/<name>` suffix (find `/.claude/worktrees/`, keep prefix)
3. `os.path.realpath()` — normalises symlink components (`/Users` vs `/System/Volumes/Data/Users`)
4. Walk parent dirs until a `.git` directory is found → that dir is the project root; `None` if filesystem root reached

Comparison is **case-insensitive** (`.lower()` on both roots) — macOS FS is case-insensitive; established convention from `session_finder.py`.

**Quote/heredoc stripping.** Before regex matching, `_strip_non_shell_active()` (from `_shell_strip.py`) removes heredoc bodies and quoted regions. Prevents matches when `worker-cli spawn` appears as literal text inside a `worker-cli send` message.

---

### block_worker_send_background.py (54 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks `worker-cli send` commands dispatched with `run_in_background=true`. `worker-cli send` is a fire-once, must-confirm action; backgrounding risks SIGTERM-kill before delivery (exit 143, silent message loss) or the orchestrator's next action running before the send completes. Canonical pattern: send in a standalone foreground Bash call; any timer dispatched as a separate `sleep 600 && echo done` call. Exits 2 + stderr. Exits 0 when `run_in_background` is absent or false, or on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command, run_in_background}}`).
**Writes:** stderr (block message with fix) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (same-dir import via `sys.path` insert); `_fire_log.log_fire`.

**Blocked patterns:** any `worker-cli send <name> <message>` with `run_in_background=true`.

**Allowed patterns:** `worker-cli send` with `run_in_background=false` or field absent; commands without `worker-cli send`; `worker-cli send` appearing inside a quoted string (blanked by `_strip_non_shell_active`); parse errors (fail-open).

---

### block_worker_kill_while_working.py (87 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks `worker-cli kill <name>` when the named worker is currently `working`. Double-gate: (1) regex `\bworker-cli\s+kill\s+([\w.-]+)` on shell-stripped command captures name token(s); (2) runs `worker-cli status <name>` subprocess (timeout 3s) and blocks only when the first output token is exactly `working`. Quoted/heredoc kill commands inside `worker-cli send` messages are stripped by `_strip_non_shell_active` → no match → guaranteed allow. All non-working statuses (idle, idle force-stopped, exited, unknown), subprocess errors, timeouts, and all exceptions → allow. Exits 2 + stderr with a message instructing the user to stop the worker first (ESC / `send 'stop'`) then kill.
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`); `worker-cli status <name>` output (subprocess).
**Writes:** stderr (block message naming the worker) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (same-dir import via `sys.path` insert); `_fire_log.log_fire`; `subprocess` (`worker-cli status` by absolute path via `_resolve_worker_cli()`: `shutil.which` first, then glob `~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/*/bin/worker-cli` newest — CC hook env PATH does not include plugin-cache bins); `shutil`, `glob` (stdlib).

**Double-gate rationale:** pure regex alone would block a `kill` dispatched right after a worker finishes (race). The live status check ensures block iff the worker is verifiably `working` at hook-fire time — zero false positives for idle/finished/nonexistent workers.

**Known accepted residual:** a shell comment containing the literal kill + a live-working-worker-name blocks (e.g. `echo hi # worker-cli kill foo`). Consistent with the whole hook family — none of the 31 hooks strip comments. The double-gate makes this unlikely in practice.

**Smoke:** `dev/hook_smoke/test_block_worker_kill_while_working.py` (13 cases: 3 block, 9 allow, 1 accepted-residual block).

---

### block_manual_worker_cleanup.py (54 LOC)

**Purpose:** PreToolUse hook (Bash) — blocks raw manual worker-cleanup commands that bypass `worker-cli kill <name>` and leave orphaned state. Two patterns: (1) `tmux kill-session -t worker-*` — kills the tmux session without removing the worktree, registry entry, or branch; (2) `git worktree remove .claude/worktrees/*` — removes the worktree without stopping the session or clearing the registry. Both patterns use `[^;&|\n]*` (not `.*`) to prevent bridging across shell separators — `tmux kill-session -t main ; cmd -t worker-x` does not trigger. `git branch -D` is deliberately excluded (worker branches have no distinguishing prefix; blocking would FP on normal feature-branch deletes). Exits 2 + stderr with `worker-cli kill <name>` as the fix. Exits 0 on any parse error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with worker-cli kill alternative) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** `_shell_strip._strip_non_shell_active` (same-dir import via `sys.path` insert); `_fire_log.log_fire`.

**Blocked patterns:**
- `tmux kill-session -t worker-*` — direct session kill (any `-t` form including `-tNAME` no-space)
- `git worktree remove .claude/worktrees/*` — direct worktree remove (handles `-C path`, `--force`, absolute paths)

**Allowed patterns:** `worker-cli kill <name>`; `tmux kill-session -t non-worker-session`; `tmux kill-session` (no -t); `git worktree remove /non-claude/path`; `git worktree list`/`add`; `git branch -D`; quoted patterns inside `worker-cli send` messages (stripped); cross-separator patterns (separator guard); parse errors (fail-open).

**Smoke:** `dev/hook_smoke/test_block_manual_worker_cleanup.py` (21 cases: 8 block, 13 allow including 2 separator-guard cases and 2 quoted-string cases).

---

### hook_setup.py (148 LOC)

**Purpose:** Idempotent installer with two defense layers. **Layer 1 — Worktree Guard:** `_guard_not_worktree()` checks `Path(__file__).resolve().parts` for consecutive `.claude`/`worktrees` components; exits 2 with a clear error message (stderr) if running from a worktree — preventing dead-path registration. **Layer 2 — Stale-hook Sweep:** `_sweep_stale_hooks()` iterates ALL event keys in `settings["hooks"]` (not only `PreToolUse`), checks every `python3 <path>` entry, and removes any whose script path fails `os.path.exists()`; drops now-empty groups, saves atomically, then runs the normal add-loop. Re-running heals stale entries from any source (worktree accident, repo move, etc.). Runs completely silent on success — no stdout output; stderr only for error conditions (worktree guard, JSON parse failure).
**Reads:** `~/.claude/settings.json`.
**Writes:** `~/.claude/settings.json` (atomic via temp + `os.replace()`; up to two saves per run — one after sweep if stale entries found, one after add-loop if new entries installed).
**Called by:** User manually (`python3 src/hooks/hook_setup.py` from Monitor_CC root). Never imported.
**Calls out:** stdlib only (`json`, `os`, `pathlib`, `sys`).

**Usage:** `python3 src/hooks/hook_setup.py` — run once after clone or reinstall. Re-run any time to heal stale hook entries. Hooks are active immediately (no CC restart needed).

**Note:** Must be run from the MAIN REPO root, not a worktree. The guard enforces this — attempting to run from a worktree exits with exit code 2 and a stderr message before touching settings.json.

---

## Gotchas

- **Hooks are the single source of truth for mechanical command rules — do NOT also state the rule in a skill or rule file.** A skill/rule loads its full text into every session (context cost + a maintenance surface that drifts) and carries that text whether or not it is relevant; a hook fires surgically only on the actual violation and costs nothing idle. Failure-case rules can therefore be added freely as hooks without bloating any always-loaded surface. When a rule can be a hook, make it a hook and keep skills/rules lean — never duplicate a hook-enforced rule as prose.
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
- **Seventeen hooks share a shell-region stripper (`_shell_strip.py`).** Before regex matching, `_strip_non_shell_active()` replaces heredoc bodies, single/double-quoted strings, and ANSI-C `$'...'` quotes with spaces of the same length (position-preserving). Command substitutions `$(...)` and backtick expressions are kept shell-active. Hooks using this: `block_broad_find.py`, `block_broad_grep.py`, `block_dangerous_kill.py`, `block_gh_cli_chained.py`, `block_manual_worker_cleanup.py`, `block_rag_cli_chained.py`, `block_search_subreddits_limit.py`, `block_venv_no_redirect.py`, `block_worker_kill_while_working.py`, `block_worker_send_background.py`, `block_worker_spawn_opus.py`, `block_worker_spawn_placement.py`, `rewrite_chained_sleep.py`, `rewrite_rag_cli_search_noise.py`, `rewrite_searxng_scrape_noise.py`, `rewrite_worker_cli_capture_noise.py`, `rewrite_worker_cli_response_noise.py`. Fail-open: any parse error returns the original string unchanged — a malformed command is never incorrectly allowed by the stripper.
- **Cache-bust on settings.json edit.** Editing `~/.claude/settings.json` busts CC's prompt cache — full message rebuild on the next request. Hooks are active immediately after settings.json is written; no CC restart needed.
- **PreToolUse exit codes.** Exit 0 = allow, exit 2 = block (CC shows stderr to user as the block reason), exit 1 = hook error (CC logs but does not block). This hook uses exit 2 on block, exit 0 on allow and on hook-internal errors.
- **Subprocess hooks must resolve plugin CLIs by absolute path.** CC's hook execution environment has a stripped PATH that does NOT include `~/.local/bin` or the plugin-cache `bin/` directories. A subprocess-hook invoking a plugin CLI by bare name (e.g. `subprocess.run(['worker-cli', ...])`) receives `FileNotFoundError` → catches it → returns the fail-open default → hook silently never fires. This was a confirmed live bug in `block_worker_kill_while_working`: the kill-guard let working-worker kills through until `_resolve_worker_cli()` was added (`shutil.which` + glob `~/.claude/plugins/cache/.../bin/worker-cli`). **Pattern for any future subprocess-hook:** resolve the binary via `shutil.which` first, then a hardcoded plugin-cache glob fallback; return `None` if unresolvable and fail-open. Never rely on bare PATH.
- **All 36 hooks log fires via `_fire_log.log_fire()`.** Called at the decision-point only — NOT at hook start and NOT on passthroughs. The shared log `src/logs/hook_firing.jsonl` is append-forever; fail-silent on write errors so logging never breaks hook behavior. New hooks must add a `log_fire()` call at their decision-point as part of the implementation. Use `MONITOR_CC_HOOK_FIRING_LOG` env var in smoke tests to redirect to a temp file and avoid polluting the real log.
