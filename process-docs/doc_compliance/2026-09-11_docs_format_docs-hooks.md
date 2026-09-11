This file is the salvage of the format cut applied to `src/hooks/DOCS.md`, dated 2026-09-11. The prior DOCS.md had accreted into a changelog of every past worker's delta (dated iteration notes, "split out of X", "replaced the old Y", verification notes, function-by-function narratives, exhaustive blocked/allowed pattern lists). None of that is the module map the documentation rules define, so it was cut from DOCS.md and preserved here as-is, grouped by the module it came from. This file is write-once; later recap sessions append dated sections below, never edit what is already here.

## Salvage from src/hooks/DOCS.md

### Role (original, full text)

Global CC safety hooks — scripts that intercept Bash, Edit, and Read tool calls and either **block** known-destructive patterns, **silently rewrite** known-broken patterns before execution, or **feed an instruction back** after a call has already failed. Registered in `~/.claude/settings.json` (global, fires for ALL projects on this machine, not just Monitor_CC). Each hook script reads CC's JSON payload from stdin and either exits 0 (allow / silent-rewrite via `hookSpecificOutput.updatedInput` JSON to stdout) or 2 (block, stderr shown to user).

**Three hook classes:**

- **Block hooks** (`block_*.py`, PreToolUse) — exit 2 + stderr when detecting damage patterns (irreversible commands, context-flooding outputs). Damage-prevention only.
- **Rewrite hooks** (`rewrite_*.py` plus the recently-upgraded `block_path_typo.py`, PreToolUse) — exit 0 + JSON `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput.{command|file_path}` containing the corrected input. Pattern-class: a broken input has a unique computable corrected form. CC v2.1+ supports this for Bash + Read + Write under `acceptEdits` mode (Issue #47853 OP). Edit-Matcher exhibits an anomaly under investigation — see `process-docs/tool_use_safety/2026-05-22_block_path_typo_edit_no_fire.md`.
- **Feedback hooks** (`feedback_*.py`, PostToolUseFailure) — exit 0 + JSON `hookSpecificOutput.additionalContext`. The call already ran and already failed; nothing is blocked or modified, the model just receives an extra instruction alongside the error it already sees. Pattern-class: the failure itself is legitimate, but the model's *reaction* to it needs discipline. (No `feedback_*.py` module exists in the current tree — this class is design-documented but unimplemented as of 2026-09-11.)

Design rationale and statistics: `process-docs/tool_use_safety/2026-05-12_session_findings.md`. Hook API capabilities and auto-rewrite conversion: `process-docs/tool_use_safety/2026-05-22_hook_api_auto_rewrite_works.md`.

### _shell_strip.py

Full original Purpose text: Shared utility — provides `_strip_non_shell_active(command)`, the position-preserving shell-region stripper used by twenty-three Bash-scanning hooks. Replaces heredoc bodies, single/double-quoted strings, and ANSI-C `$'...'` quotes with spaces of the same length before pattern matching runs. Command substitutions `$(...)` and backtick expressions are kept shell-active. Fail-open: any parse error returns the original command unchanged (never silently allows a blocked pattern due to a strip failure). `_strip_impl` is decomposed into 6 private scan helpers (`_scan_heredoc`, `_scan_ansi_c_quote`, `_scan_cmd_subst`, `_scan_backtick`, `_scan_single_quote`, `_scan_double_quote`), each returning `(fragment, new_i)`.

### _known_cli.py

Full original heading included a LOC/history annotation: "(81 LOC, rewritten for `block_cli_chained.py` — 2026-09 chain-hook unification; interpreter-path-bypass fix + stale-subcommand-name fix — 2026-09-06)".

Full original Purpose text: Shared utility — `PROTECTED_SUBCOMMANDS`, a `{tool: set-of-subcommands-or-None}` table for the 8 CLIs `block_cli_chained.py` polices (`gh-cli`, `rag-cli`, `worker-cli`, `reddit-cli`, `websearch`, `linkedin`, `penny-cli`, `duallog`); `None` means every subcommand of that tool is protected (`linkedin`, `penny-cli`, `duallog` — no unprotected subset exists for any of the three). Plus `match_known_cli_segment(segment)` (matches by WRAPPER name only — returns the `re.Match` with named groups `tool`/`sub`, or `None`), `match_interpreter_cli_segment(segment, command_context)` (matches a bare `<python> cli.py <sub>` interpreter invocation, resolving WHICH tool via a project-directory marker found in `command_context`), `resolve_cli_segment(segment, command_context)` (tries the wrapper form first, falls back to the interpreter form — the one function `block_cli_chained.py` actually calls), `is_known_cli_segment(segment)` (wrapper-name only, currently unreferenced), `is_protected_segment(match)` (takes an already-resolved match object, not a string — protected subcommand, or a `None`-tool where every invocation counts), and `tool_sub_name(tool, sub)` (block-message naming, drops `sub` when it is actually a flag like `--help`). **Superseded the old `is_allowed_chain_segment`/`is_guard_segment`/`is_echo_segment`/`is_loop_scaffold_segment` predicates** (2026-08/2026-09 chained-CLI hook family) — those existed to decide whether a "foreign" chain segment was actually fine; the 2026-09 rule rewrite dropped the whole foreign-segment concept (chaining with `;`/`&&` is unconditionally fine for any CLI, with any other command — "no allowlist of chain segments"), so the predicates lost their only consumers and were deleted rather than kept unreachable.

**2026-09-06 fixes (two independent holes, both found by a real run, not by inspection):** (1) `PROTECTED_SUBCOMMANDS["websearch"]` named `scrape_url`, a subcommand that no longer exists in websearch's `cli.py` (renamed to `scrape_url_chromium` a while back) — the exact-match check in `is_protected_segment` silently never fired for the real subcommand; fixed by updating the table entry. All 7 other entries were audited the same way (resolving each wrapper to its actual `cli.py`/subcommand list) and found still accurate. (2) `_KNOWN_CLI_RE` (hence `match_known_cli_segment`) only recognizes the 8 WRAPPER names, but 5 of those wrappers (`gh-cli`, `rag-cli`, `reddit-cli`, `websearch`, `linkedin`) are 2-line bash shims that `exec <dir>/venv/bin/python <dir>/cli.py "$@"` — invoking that same `cli.py` through the interpreter directly (typically `cd <dir> && ./venv/bin/python cli.py <sub>`, so the python line itself carries no path at all) matched no rule; `match_interpreter_cli_segment`/`resolve_cli_segment` close this by recognizing the bare `cli.py` shape and resolving the tool from a project-directory marker (`_CLI_PY_DIR_TOOL`) found anywhere in the whole shell-stripped command. `worker-cli` (bash wrapper, no interpreter indirection), `penny-cli` (`-m src`, too generic an anchor), and `duallog` (`-m src.dual_log_cli`, no observed incident) are deliberately NOT covered by the interpreter-path fix — see the inline comment on `_CLI_PY_DIR_TOOL` and `process-docs/tool_use_safety/`.

### _fire_log.py

Full original Purpose text: Shared utility — provides `log_fire(hook_name, decision, tool_name, command, reason=None, rewritten=None, session_id=None)`, the single fire-event appender used by all active hooks. Appends one JSON line per fire to `src/logs/hook_firing.jsonl`. For `decision="block"` and `decision="feedback"`: includes `reason` field (the message text), omits `rewritten`. For `decision="rewrite"`: includes `rewritten` field (new command/path), omits `reason`. Fail-silent: any exception in the write path is swallowed so a logging failure never breaks the hook itself. Log path overridable via `MONITOR_CC_HOOK_FIRING_LOG` env var (used for test isolation in `dev/hook_smoke/`).

Original Called by note: Called at the decision-point only (immediately before `sys.exit(2)` for blocks; immediately before `print(json.dumps(output))` for rewrites). NOT called on passthroughs.

### block_dangerous_kill.py

**Blocked patterns:**
- `pkill -f <anything>` — cmdline-substring matching, kills worker prompts
- `ps ... | ... grep ... | ... kill ...` — same problem via pipe chain

**Allowed patterns (not blocked):** `pkill -x <name>` (exact), `pkill <name>` (name-only), `kill <numeric_pid>`, `kill -<signal> <numeric_pid>`, `worker-cli kill <name>`, `launchctl bootout/kickstart`.

**Allowlist (`_PKILL_F_ALLOWLIST`):** explicit literal strings for `pkill -f` arguments that are safe to pass through. Checked against original (un-stripped) command via `_PKILL_F_ARG_RE` (handles single-quoted, double-quoted, unquoted). Conservative: any non-allowlisted `pkill -f` in the same command still blocks. Current entries: `"dolt sql-server"` (bd Beads SQL backend — bd's orphan-cleanup SIGKILLs any process with this cmdline string, making it impossible for a worker to carry it).

**Quote/heredoc stripping.** Before regex matching, `_strip_non_shell_active()` (imported from `_shell_strip.py`) removes heredoc bodies, single-quoted, double-quoted, and ANSI-C `$'...'` regions from the command string. Command substitutions `$(...)` and backtick expressions are kept shell-active. Eliminates false-positives where `pkill -f` appears as literal text inside heredoc bodies (test scaffolding, `bd comments add` session notes, Python string literals).

### block_chained_sleep.py.disabled (entire entry, module no longer in scope)

**Disabled 2026-05-24** — superseded by `rewrite_chained_sleep.py`. Renamed via `git mv` (file still in repo for history). Previously blocked all non-canonical `sleep N` chains. Replaced by a rewrite hook that strips trivial-sync sleeps (`echo`, `true` cmd_before) and passes load-bearing patterns through. See `process-docs/hook_fp_audit/sleep_pattern_audit_2026-05-24.md` for audit rationale.

### rewrite_chained_sleep.py

**Allowlist:**
- `_TRIVIAL` (first token of preceding segment): `echo`, `true`, `grep`, `cat`, `ls`, `wc`, `head`, `tail`, `find`
- `_TRIVIAL_PAIRS` (`(tokens[0], tokens[1])` exact pair): `(git,status)`, `(git,log)`, `(git,diff)`, `(git,show)`, `(rag-cli,search)`, `(worker-cli,status)`, `(worker-cli,list)`, `(worker-cli,response)`

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

### block_search_subreddits_limit.py

**Blocked patterns:** `reddit-cli search_subreddits "query" --limit N`; `cli.py search_subreddits "query" --limit N` — `--limit` caps the result set before the caller can select from it.

**Allowed patterns:** `reddit-cli search_subreddits "query"` without `--limit`; commands not containing `search_subreddits`; parse errors (fail-open). `_LIMIT_RE` is searched only after `_SEARCH_RE` matches — non-matching commands exit at the first gate.

### block_unauthorized_background.py

Original heading annotation: "(59 LOC, Milestone 2 worker-cli wait exemption 2026-08)".

**Rewrite condition:** `run_in_background=true` AND command matches NEITHER `_SLEEP_ONLY_BG` (`^\s*sleep\s+\d+(?:\.\d+)?\s*(?:&&\s*echo\b[^;&|\n]*)?\s*$`) NOR `_WAIT_FORM` (`^\s*worker-cli\s+wait\b[^;&|\n]*$` — `\b` word-boundary after `wait` rejects `waitfoo`-shaped tokens; `[^;&|\n]*` tail-guard rejects a chained `worker-cli wait && other_cmd`).

**Passthrough (no output):**
- Any sleep-only command (`sleep N`, `sleep N && echo done`, `sleep N && echo "custom text"`) with `run_in_background=true`
- Any `worker-cli wait` form (bare, with `project_path`, with `--timeout N`, with both) with `run_in_background=true`
- Any command with `run_in_background=false` or field absent (foreground — no restriction)
- Parse errors (fail-open)

**No quote-stripping.** Checks the `run_in_background` bool field and the two canonical regexes only — no general command-text scanning.

**Smoke:** `dev/hook_smoke/test_block_unauthorized_background.py` (14 cases: 3 sleep-only ALLOW, 4 `worker-cli wait` ALLOW, 6 FORCE incl. chained-wait and word-boundary, 1 foreground PASS).

### rewrite_background_sleep.py

Original heading annotation: "(65 LOC, Milestone 2 rewrite target change 2026-08; orchestrator-only guard 2026-08 Milestone 3b)".

Full original Purpose text: PreToolUse hook (Bash) — **rewrites** ANY sleep-only background command to the canonical `worker-cli wait` (iterative-dev plugin — blocks in-process until all workers of the project go stably idle, or `--timeout`; its own exit IS the wake-up, replacing the old push-based raw-sleep + menubar-kill mechanism). Matches bare `sleep N` OR `sleep N && echo <anything>` (regex `_SLEEP_ONLY_BG`). No "already canonical" exemption needed: `_SLEEP_ONLY_BG` requires a literal `sleep` token, which can never match the target string `"worker-cli wait"` — every sleep-only match, including the OLD canonical `sleep 3300 && echo done`, is now a stale habit and gets rewritten. Pairs with `block_unauthorized_background.py`, which exempts both sleep-only commands AND `worker-cli wait` forms from foreground-forcing (that hook stays global — it only ever flips `run_in_background`, never the command text, so a worker's `sleep N` staying `sleep N` in the background is already harmless there). **Orchestrator-only (2026-08, live incident, `_in_worktree()`/`_WORKTREE_FRAGMENT`, same convention the removed `block_timer_*` hooks used):** skipped entirely when the hook's own cwd is inside a worktree — a worker's own background sleep (e.g. waiting on its own long test run) must never get promoted to `worker-cli wait`, since run from the worker's worktree cwd that command resolves the worktree path as the project, finds no workers there, and blocks up to the full default timeout; that stray wait becomes a live child under the worker's own `claude` process, which then makes the ORCHESTRATOR's own `worker-cli wait` see a live background task and refuse to finish too — one misfire cascading into two stuck waits. `_in_worktree()` fails open TOWARD "skip rewrite" on any `os.getcwd()` failure (deliberately the opposite fail-open direction from most hooks here — a missed rewrite for the orchestrator is harmless, rewriting a worker's sleep on an unreliable cwd read is the exact incident being prevented).

**Rewrite condition (ALL must hold):**
1. Hook cwd is NOT inside `.claude/worktrees/` — orchestrator-only guard
2. `run_in_background == True`
3. Command matches `_SLEEP_ONLY_BG`: `^\s*sleep\s+\d+(?:\.\d+)?\s*(?:&&\s*echo\b[^;&|\n]*)?\s*$`

**Passthrough (no output):**
- Hook cwd inside `.claude/worktrees/` — worker session, never rewritten regardless of command shape
- `run_in_background=false` or field absent — foreground, any sleep form allowed
- Any non-sleep-only command (including `worker-cli wait` itself, already canonical) — `_SLEEP_ONLY_BG` fails to match; `block_unauthorized_background.py` handles the allow/force decision for these
- Parse errors (fail-open)

**Smoke:** `dev/hook_smoke/test_rewrite_background_sleep.py` (14 cases: 6 positive rewrite incl. the old canonical target, 5 negative no-op incl. `worker-cli wait` passthrough, 3 worktree-cwd no-op cases proving the orchestrator-only guard actually fires — cwd forced explicitly per case via `subprocess.run(..., cwd=...)`, both a plain non-worktree tempdir and a `.claude/worktrees/`-shaped one, since this suite's own on-disk path contains that fragment and would otherwise leak into every case's inherited cwd).

### block_broad_grep.py

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

### block_broad_find.py

Full original Purpose text: PreToolUse hook (Bash) — blocks `find` invocations over broad/unbounded search roots when no `-maxdepth N` predicate is present and output is not immediately `| head`-bounded. Broad roots: `~`, `~/`, `$HOME`, `/`, and the `.claude` subtree (`~/.claude` or any path under it). A `find ~/.claude -type d -iname '*searxng*'` without depth or head limits traverses hundreds of session/worktree dirs and floods context (~80 results — the trigger incident).

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

### block_cli_chained.py

Original heading annotation: "(167 LOC, 2026-09 chain-hook unification; interpreter-path-bypass fix — 2026-09-06)".

Full original Purpose text: PreToolUse hook (Bash) — replaces the 7 per-CLI chained/isolated hooks this family used to carry (`block_gh_cli_chained.py`, `block_rag_cli_chained.py`, `block_worker_cli_read_chained.py`, `block_websearch_scrape_chained.py`, `block_duallog_chained.py`, `block_linkedin_cli_isolated.py`, `block_penny_cli_chained.py`) with one hook enforcing one rule set, driven by `_known_cli.py`'s `PROTECTED_SUBCOMMANDS` table, for all 8 CLIs. **The old hooks enforced MORE than the actual rule:** they blocked any "foreign" chain segment (an allowlist of known CLIs, cd guards, echo, loop scaffolding) even when nothing about that segment touched the CLI's output — measured on `src/logs/hook_firing.jsonl`, 115 historical blocks by the 7 old hooks, of which 66 turned out to be non-truncating chains under the actual rule (see the replay probe below). **The actual rule, exactly 3 conditions, nothing else:** chaining any CLI with `;`/`&&`/`||`/newline/background-`&` and ANY other command is always fine — there is no allowlist of chain segments. What blocks: (1) a known-CLI segment (any of the 8, any subcommand) piped into anything — pipes are checked structurally by splitting each chain segment into `|`-stages and requiring a CLI-matching stage to be the LAST stage of its pipe run; (2) a redirect (`>`, `>>`, `2>&1`, `&>`, `<`) on a segment invoking a PROTECTED subcommand (`is_protected_segment`) — deliberately excludes bare `2>` (stderr-only suppression, never touches the real output); (3) a same-Bash-call readback of a file ANY CLI segment (protected or not) redirected into, via `head`/`tail`/`cat`/`sed`/`awk`/`grep`/`less`/`more`/`wc` — tracked by extracting every CLI stage's own `>`/`>>`/`&>` target file, then checking every readback-tool stage's text for that target as a substring. Each rule fires its own single-sentence message naming the variant plus the offending segment (`"Blocked segment: <text>"`).

**2026-09-06 interpreter-path-bypass fix.** A real run found `cd <websearch-dir> && ./venv/bin/python cli.py scrape_url_chromium <url> > /tmp/out.txt 2>&1` (redirecting a protected scrape to a file, then reading it back with `head` in a later call) got a clean pass 3 times: the segment starts with `./venv/bin/python`, which matches none of the 8 wrapper names `_KNOWN_CLI_RE` anchors on, so `_segment_stages_with_cli` returned `False` at the very first gate and no rule was ever evaluated. `resolve_cli_segment` closes this — see `_known_cli.py`. **Deliberately not touched: `block_venv_no_redirect.py`.** That hook REQUIRES a redirect on any `./venv/bin/python <script>.py` call and fired on this exact command earlier in the same session (over the no-redirect form). Making the interpreter form "protected" here does not contradict that hook — it completes a pincer: the no-redirect form of a protected interpreter call is blocked BY `block_venv_no_redirect.py` (demands a redirect), and the redirected form is blocked BY this hook's rule 2 (protected + redirected) — no variant of that command, redirected or not, passes both hooks. That is exactly the desired outcome ("cannot escape the rule by taking the interpreter path"), reached without editing `block_venv_no_redirect.py` at all; its own redirect-discipline reasoning is unrelated to output-boundedness and stays correct on its own terms.

**Blocked patterns:**
- `rag-cli search "x" coll | head -40` — rule 1, protected subcommand piped
- `gh-cli get_file_content o r path | head -80` — rule 1, UNPROTECTED subcommand piped (rule 1 is universal across all 8 CLIs, any subcommand — not scoped to the protected set)
- `worker-cli kill name 2>&1 | tail -5` — rule 1, an unprotected `worker-cli` subcommand piped
- `linkedin --help 2>&1 | head -40` — rule 1 (every `linkedin` invocation is protected, but the pipe alone already blocks regardless)
- `rag-cli search "x" coll > /tmp/out.txt` — rule 2, protected subcommand redirected
- `gh-cli list_issues o r 2>&1` (no pipe) — rule 2, `2>&1` counts as a protected-subcommand redirect even standalone
- `duallog sessions > /tmp/out.txt` / `penny-cli --klasse "X" > out.txt` — rule 2, every subcommand of `duallog`/`penny-cli` is protected
- `rag-cli update_docs . > /tmp/ragsync.txt 2>&1; tail -12 /tmp/ragsync.txt` — rule 3, the milestone's canonical incident: `update_docs` is UNPROTECTED (redirect alone would pass), but reading its own redirected file back in the same call blocks

**Allowed patterns:**
- `mkdir -p x && rag-cli index --collection x` — chaining with `&&` is fine for any CLI, with any other command
- `ls; gh-cli get_issue o r 5` — chaining with `;` is fine, no allowlist of what `ls` is
- `gh-cli list_issues o r 2>/dev/null || true` — bare `2>` does not count as a redirect (rule 2 excludes it)
- `rag-cli index --collection x > /tmp/log 2>&1` — unprotected subcommand, redirect alone stays allowed (no same-call readback)
- `echo test && penny-cli --klasse "X"` — chaining with `&&` is fine even for `penny-cli` (the old hook's whole-invocation isolation is retired)
- `for n in 62 61 59; do echo "=== #$n ==="; gh-cli get_issue o r $n; done` — a for-loop with no pipe/redirect passes trivially, no loop-scaffold predicate needed
- `duallog-search-chars`/`iterative-dev-duallog` path substrings — never match a real CLI invocation (segment must literally start with the tool name)

**Segment mechanics.** `_build_chain_segments()` splits the shell-stripped command on `_CHAIN_SEPARATOR_RE` (`&&`/`||`/`;`/newline/space-bounded `&` — deliberately excludes `|`), then, WITHIN each chain segment, splits again on `_PIPE_SEPARATOR_RE` (bare `|`) into pipe stages — both splits are position-preserving (`_split_spans`/`_trim_span`) so block messages quote the real original text, not the quote-blanked stripped copy. Rule 1 walks every stage except the last in each pipe run; rule 2 checks only the LAST stage of each pipe run (a CLI stage piped further is already rule 1's territory); rule 3 does two passes — collect redirect targets from every last-stage CLI segment, then scan every stage (any position) for a readback-tool first token referencing one of those targets.

**Smoke:** `dev/hook_smoke/test_block_cli_chained.py` (42 cases: all 3 rule classes across all 8 CLIs, protected-vs-unprotected-redirect contrast, the bare-`2>`-exclusion, cross-CLI/no-allowlist passes, the for-loop-with-no-pipe pass, the duallog path-substring-FP pass, malformed-stdin fail-open, plus the 2026-09-06 additions). Replay probe (every historical `block` fire of the 7 replaced hooks from `src/logs/hook_firing.jsonl`, fed through this hook): `dev/hook_smoke/probe_replay_cli_chained.py`, report at `dev/hook_smoke/md/block_cli_chained_replay_report.md` — as of the 2026-09 rewrite, 49/115 still block, 66/115 now pass (the milestone's own pre-implementation estimate was "about 83/32"; the literal 3-rule text, verified message-for-message against the milestone's own 3 example messages, produces a larger non-truncating-pass share than that estimate anticipated — see the report for the full list of now-passing commands).

### block_gh_cli_local_path.py

Original heading annotation: "(90 LOC, 2026-08-07)".

Full original Purpose text: PreToolUse hook (Bash) — blocks `gh-cli get_file_content`/`gh-cli download_files` when a positional path argument (the one(s) after `owner`/`repo`) starts with `/` or `~` — a local filesystem path where a repo-relative path is required. Observed failure class: agents pass Claude Code tool-result paths (`~/.claude/projects/.../tool-results/...`) or other absolute/`~` paths as `get_file_content`'s `path`; the GitHub API then 404s/validation-errors. Same philosophy as `block_gh_cli_chained.py` — the skill prose that used to teach this is being removed, the hook teaches at block time instead. Tokenizes the matched segment via `shlex.split` (quote-preserved, sliced from the ORIGINAL command using indices computed against the `_strip_non_shell_active`-stripped copy — same position-preserving trick `block_rag_cli_document_repeat.py` uses), walks tokens classifying value-consuming flags vs positionals: `get_file_content`'s `--offset`/`--limit` and `download_files`'s `--dest` each consume their own value token, everything else is a positional. **False-positive trap solved:** `download_files --dest DIR` — `DIR` is a LOCAL directory by design (where downloaded files land), explicitly excluded from the positional-path check via the per-subcommand `_VALUE_FLAGS` set, regardless of whether `--dest` appears before or after the repo-path positionals. Only positions `[2:]` (after owner/repo) are checked.

**Smoke:** `dev/hook_smoke/test_block_gh_cli_local_path.py` (15 cases: 5 block — `/Users/...`, `~/...`, absolute `download_files` positional, `~/...` among multiple `download_files` positionals, local path with a preceding `--limit` flag; 4 pass — repo-relative path, the `--dest` trap case in both flag positions, `--metadata-only` flag present; 4 untouched — `get_repo_tree`/`index_issues`/`repo_freshness`/non-gh-cli; 2 shell-strip — single-quote, heredoc). Report: `dev/hook_smoke/md/block_gh_cli_local_path_smoke_report.md`.

### block_rag_cli_index_isolated.py

Full original Purpose text: PreToolUse hook (Bash) — blocks any `rag-cli index` call that shares the Bash invocation with anything other than shell variable assignments and a `cd`, or that carries any command/process substitution anywhere. `rag-cli index` runs for minutes; `block_rag_cli_chained.py`'s trailing-only rule misses noise placed BEFORE the index segment (e.g. `tail <log> \n echo ... \n cd ... && rag-cli index ...` — a poll-then-index pattern that grabs the collection lock mid-run). This hook enforces the tighter rule: any number of assignment-only segments, any number of `cd` segments, exactly one `rag-cli index` segment (optionally env-var-prefixed), nothing else — in any position, and no `$(...)`/backtick/`<(...)`/`>(...)` anywhere in the raw command. Backslash+newline line-continuations are collapsed before segment-splitting. Out of scope for all other rag-cli subcommands (`search`, `delete`, `list_documents`, etc.), which stay governed by `block_rag_cli_chained.py` (a hook that no longer exists in the tree as of 2026-09-11 — reference is stale).

**Blocked patterns:**
- `tail -20 /tmp/x.log \n echo ... \n cd ... && rag-cli index --collection x > /tmp/out.log 2>&1` — the observed incident: polling noise before a leading cd + index
- `tail -20 /tmp/x.log && rag-cli index --collection x` — noise before index
- `rag-cli index --collection x && echo done` — noise after index
- `rag-cli index --collection x ; tail /tmp/x.log` — noise after index via `;`
- `rag-cli delete --collection x && rag-cli index --collection x` — a second rag-cli command (even `rag-cli`) is not exempt
- `rag-cli index --collection x | tee /tmp/log` — piped
- `tail -20 /tmp/x.log && PYTHONUNBUFFERED=1 rag-cli index --collection x` — env-var-prefixed index does NOT exempt a preceding non-cd/non-assignment segment (2026-08-01 fix)
- `RAG_ROOT=/x \n tail /tmp/y.log \n cd "$RAG_ROOT" && PYTHONUNBUFFERED=1 rag-cli index --collection x` — the standalone assignment line is allowed, the `tail` line still blocks
- `X=$(tail /tmp/a.log) rag-cli index --collection x` / `` X=`tail /tmp/a.log` rag-cli index --collection x `` — command substitution smuggled through an assignment value (2026-08-02 fix)
- `rag-cli index --collection $(cat /tmp/name.txt)` / `rag-cli index --collection x > `pwd`/out.log` — substitution in an argument or redirect target
- `rag-cli index --collection x > >(tail -5)` / `< <(cat /tmp/y)` — process substitution
- `X=$((1+1)) rag-cli index --collection x` — arithmetic expansion (`$((` starts with `$(`, same gate)
- `cd "$(pwd)" && rag-cli index --collection x` — substitution nested inside a double-quoted `cd` target
- `rag-cli index --collection x &tail /tmp/y` / `rag-cli index --collection x&tail /tmp/y` — bare `&` smuggles a second command regardless of surrounding whitespace (2026-08-02 fix)

**Allowed patterns:**
- `rag-cli index --collection x` — bare, standalone
- `rag-cli index --collection x > /tmp/out.log 2>&1` — redirect is not a separator, stays in the segment
- `cd /some/path && rag-cli index --collection x` — cd + index, nothing else
- `cd /path && rag-cli index --collection x > /tmp/out.log 2>&1`
- `PYTHONUNBUFFERED=1 rag-cli index --collection x` — env-var prefix on the index segment itself
- `RAG_ROOT=~/path \n cd "$RAG_ROOT" && PYTHONUNBUFFERED=1 rag-cli index --collection x \\\n > /tmp/out.log 2>&1` — the canonical skill form: standalone assignment line, cd, env-prefixed index, backslash-continued redirect
- `X="a;b" rag-cli index --collection x` — quoted metacharacter in an assignment value, not command substitution
- `rag-cli index --collection x &> /tmp/out.log` — `&>` redirect, not the bare backgrounding `&` separator
- any command without `rag-cli index` — out of scope, anchor exits early (`rag-cli search`/`delete`/`list_documents` all pass)
- `rag-cli index` inside a quoted string / heredoc body — blanked by `_strip_non_shell_active`, anchor fails

**Segment split.** `_SEPARATOR_RE` splits on `&&` `||` `;` `|` newline and bare `&` (background) — the single-`&` alternative uses `(?<![&>])&(?![&>])` (lookaround, no whitespace requirement) so it excludes `&&`/`&>`/`N>&M` (`2>&1`) but still catches `&` with no surrounding spaces at all (`x&tail`); redirects (`>`, `2>&1`) survive intact as part of their segment. Before splitting, `_LINE_CONTINUATION_RE` (`\\\n`) is collapsed to a space so a backslash-continued line stays one logical segment. Fast-path anchor `_RAG_INDEX_RE` (`\brag-cli\s+index\b`) searched first; if absent, exit 0 immediately. `_SUBSHELL_RE` (`\$\(|`|<\(|>\(`) is then checked against the RAW (unstripped) command — a hard gate independent of segment classification, since `_strip_non_shell_active` keeps `$()`/backticks shell-active outside quotes but blanks them inside `"..."` even though real bash still evaluates them there. Every segment must then match one of three classifiers: `_RAG_INDEX_SEGMENT_RE` (`^(?:VAR=val\s+)*rag-cli\s+index\b` — env-assignment prefix optional), `_CD_SEGMENT_RE` (`^cd\b`), or `_ASSIGNMENT_ONLY_SEGMENT_RE` (`^(?:VAR=val\s*)+$` — one or more bare assignments, nothing else) — all position-independent; exactly one index segment is required, more than one blocks.

**Gotchas (original, module-scoped):**
- **2026-08-01 fix — env-var prefix bypass.** The original `_RAG_INDEX_SEGMENT_RE` was anchored `^rag-cli\s+index\b` with no assignment-prefix allowance. An env-prefixed segment (`PYTHONUNBUFFERED=1 rag-cli index ...`) matched neither the index regex nor the cd regex, so `index_segments` came back empty and the early-exit `if not index_segments: sys.exit(0)` treated the whole command as out-of-scope — silently ALLOWING any noise placed alongside an env-prefixed index call. Fixed by making the assignment prefix part of `_RAG_INDEX_SEGMENT_RE` itself, and adding `_ASSIGNMENT_ONLY_SEGMENT_RE` as a third allowed classifier (needed because a real skill invocation commonly declares `RAG_ROOT=...` on its own line before `cd "$RAG_ROOT"`).
- **Line continuation:** without the `_LINE_CONTINUATION_RE` collapse, `rag-cli index --collection x \` + newline + `> /tmp/x.log` split into two segments at the bare `\n`, and the second (`> /tmp/x.log`) matched neither classifier — a legitimate backslash-continued redirect blocked.
- **2026-08-02 fix — command-substitution and bare-`&` smuggling.** `_ASSIGN_TOKEN`'s value part (`\S*`) happily swallows `$(tail /tmp/a.log)`, so an assignment segment could carry an arbitrary command through a value that segment-classification alone never inspects — closed with the standalone `_SUBSHELL_RE` gate. Separately, the original single-`&` pattern required whitespace on both sides (`\s&(?=\s|$)`), so `x &tail` / `x&tail` (no space, or no trailing space) matched no separator at all and stayed glued into the index segment — real bash still tokenizes `&` as a background operator regardless of adjacent whitespace, so the lookaround was tightened to drop the whitespace requirement while still excluding `&&`/`&>`/`N>&M`.

**Smoke:** `dev/hook_smoke/test_block_rag_cli_index_isolated.py` (37 cases: 20 block covering the observed incident, the 2026-08-01 env-prefix/assignment-line holes, and the 2026-08-02 command-substitution/process-substitution/arithmetic-expansion/bare-`&` holes; 17 allow covering bare/redirect/cd/env-prefix/assignment-line/line-continuation/quoted-metacharacter/`&>`-redirect/out-of-scope-subcommand/no-rag-cli/single-quote/heredoc).

### block_rag_docs_layer.py

**Blocked patterns:**
- `rag-cli search "q" monitor-cc-docs` — no filter at all
- `cd /x && rag-cli search "q" foo-docs` — collection ends `-docs`, no filter, after a leading cd
- `rag-cli search "q" monitor-cc-docs --document 'src/search/%'` — filter present but value doesn't contain `process-docs` (known edge case, see Gotchas)

**Allowed patterns:**
- `rag-cli search "q" monitor-cc-docs --document 'process-docs/%'` — process-layer filter
- `rag-cli search "q" monitor-cc-docs --exclude 'process-docs/%'` — code-layer filter
- `rag-cli search "q" monitor-cc-docs --document='process-docs/%'` — `=`-form filter
- `rag-cli search "q" monitor-cc-reference` — collection doesn't end `-docs`, rule inapplicable
- `rag-cli list_documents monitor-cc-docs` — not `search`, out of scope
- `rag-cli search` token inside a quoted string — blanked by `_strip_non_shell_active`, anchor fails

**Segment extraction.** Same technique as `rewrite_rag_cli_search_noise.py` (a hook that no longer exists in the tree — reference is stale): `_RAG_RE` (`\brag-cli\s+search\b`) is matched against the shell-stripped command; the segment end is found via the same chain-operator/noise regexes. Because `_strip_non_shell_active` is position-preserving, the match indices are then sliced out of the **original** (unstripped) command — recovering real quoted argument values (e.g. `'process-docs/%'`) for `shlex.split` tokenization, rather than the blanked stripped form.

**Predicate.** `_segment_violates()`: `shlex.split` the original segment → find `collection` (2 tokens after the `search` literal) → if it doesn't end with `-docs`, no violation → else violation unless any `--document`/`--exclude` token (space-separated or `--flag=value` form) has a value containing the substring `process-docs`.

**Known edge case:** a code SUB-area search like `--document 'src/search/%'` does not contain `process-docs`, so it is blocked under this predicate — the correct form for scoped code search is `--exclude 'process-docs/%'` (broad code-layer exclusion), not a positive `--document` on a code subpath (note: `src/search/` does not exist in this repo — the example predates a rename/removal). A more permissive predicate (e.g. accepting any `--document` value NOT starting with `process-docs` as implicitly code-layer) was intentionally not implemented — deferred pending real usage data.

**Smoke:** `dev/hook_smoke/test_block_rag_docs_layer.py` (11 cases: 3 block, 8 allow).

### block_rag_corpus_read.py

Original heading annotation: "(81 LOC, 2026-08)".

Full original Purpose text extra: see `process-docs/tool_use_safety/2026-08-28_rag_cli_path_indirection_bypass.md`, which documents a worker routing around the (then-buggy) `block_rag_cli_chained.py` FP by reading the corpus through `cat`/interpreter indirection because the block message never named an allowed alternative. This hook's `_BLOCK_MESSAGE` explicitly names both sanctioned forms for that reason. File management and deletion over the corpus tree (`ls`, `rm`, `mv`, `mkdir`) are deliberately NOT policed — those are sanctioned operator actions, only bypassing rag-cli's own read path is blocked. Bash-only by design (no Read-tool matcher) — Read already has its own directory/oversize handling; this hook's scope is shell indirection specifically. `_CORPUS_PATH_RE` matches `rag-[^/\s]*` (not a literal `rag-cli`) so a renamed checkout or worktree (`rag-cli-eval`, `rag-cli-convert`) is still caught.

**Blocked patterns:**
- `cat /Users/x/cli/rag-cli/data/documents/github_issues/123.md` — direct read of a corpus document
- `grep -r foo /Users/x/cli/rag-cli/data/documents/` — recursive grep over the corpus tree
- `head -50 "/Users/x/cli/rag-cli/data/documents/x.md"` — quoted corpus path (path recovered from the ORIGINAL, unstripped segment — quoting alone does not evade the check)
- `cat /Users/x/cli/rag-cli-eval/data/documents/z.md` — renamed checkout (glob dodge via `rag-[^/\s]*`)
- `rag-cli index --collection x && cat /Users/x/cli/rag-cli/data/documents/z.md` — the corpus-read segment blocks regardless of what else is chained alongside it

**Allowed patterns:**
- `ls /Users/x/cli/rag-cli/data/documents/` — file management, not a content read
- `rm -rf /Users/x/cli/rag-cli/data/documents/old` / `mv ...` / `mkdir ...` — deletion and management stay sanctioned
- `cat /etc/hosts` — no corpus path involved
- `rag-cli search "q" coll` / `rag-cli read_document coll doc1` — the sanctioned forms themselves, untouched
- `echo "you could cat data/documents/x"` — quoted mention, not an actual read
- corpus path text inside a heredoc body — blanked before segment-start matching
- `cat data/documents/foo.md` (relative, no `rag-*` prefix visible) — known text-only-matching limitation, shared with the sibling rag-cli isolation hooks (none resolve paths against cwd)

**Segment split.** Same `_SEPARATOR_RE` as the chained-CLI hook family. `_split_segments()` walks `_SEPARATOR_RE.finditer()` over the STRIPPED command once, yielding `(stripped_segment, original_segment)` pairs at IDENTICAL index ranges in both copies — `_READ_CMD_RE.match()` runs against the stripped copy, `_CORPUS_PATH_RE.search()` runs against the ORIGINAL copy.

**Gotchas (original, module-scoped):**
- **Trim-boundary bug (caught in dev, not shipped):** the first `_trim_pair()` draft trimmed both copies using `stripped_seg.strip()`'s boundary. A quoted argument at the very END of a segment blanks to trailing SPACE characters in the stripped copy, indistinguishable from real trailing whitespace — `.strip()` removed them, and the identical index range then cut the real (quoted) path text out of the original copy too, silently under-matching `head -50 "/path/.../data/documents/x.md"`. Fixed by computing the trim range from the ORIGINAL segment's own whitespace boundary instead.
- **Argument-role blindness:** the hook does not distinguish a grep PATTERN argument from a file-path argument (no `shlex`-based flag/positional parsing, unlike `block_rag_docs_layer.py`) — `grep "rag-cli/data/documents" /tmp/notes.txt` searching FOR that literal string is not mistaken for a real corpus read only because `_CORPUS_PATH_RE`'s leading boundary fails to match a quote character; a differently-worded pattern could in principle still false-block. Accepted: the failure direction (blocking a rare crafted string) is the safe one for a policy hook.

**Smoke:** `dev/hook_smoke/test_block_rag_corpus_read.py` (24 cases incl. all 9 read commands blocked, glob-dodge renamed-checkout blocks, quoted-path block, mutation/management allows, no-corpus-path allows, sanctioned-form allows, echo/heredoc shell-strip allows, relative-path limitation, malformed-payload fail-open, block-message content checks).

### block_noop_edit.py

**Blocked patterns:** any Edit where `old_string` and `new_string` are identical non-None strings.

**Allowed patterns:** any Edit with different strings; missing/non-string fields (fail-open).

### block_read_directory.py

**Blocked patterns:** `file_path` resolves to an existing directory (`os.path.isdir`).

**Allowed patterns:** file paths, nonexistent paths, missing/non-string field (all fail-open).

### block_read_oversize.py.disabled (entire entry, module no longer in scope)

**Disabled 2026-07-22** — pre-empted CC's own >256KB Read rejection (redundant), pinned to a CC-internal size number that goes stale on CC updates, and its "grep the file first" advice contradicts the just-added `block_po_read.py` (which forbids partial shell-reads of persisted-output exports). Renamed via `git mv`. Not replaced by another hook.

### block_cd_drift.py

**Blocked patterns:** command contains a `cd .claude/worktrees/...` target AND that worktree path is the LAST `cd` target (no cd-back).

**Allowed patterns:** `cd <worktree> && ... && cd <main-repo>` (cd-back at end); commands with no worktree `cd`; calls from inside a worktree (workers live there — hook skips entirely); parse errors (fail-open).

### block_dev_imports_src.py

Original heading annotation: "(58 LOC, 2026-08 regression-suite exemption)".

Full original Purpose text extra: **2026-08 exemption:** a `dev/` file is NOT a probe — and is skipped entirely, imports allowed — when it sits under a `tests/` directory segment AND its filename matches pytest's own discovery convention (`test_*.py`, `*_test.py`, or `conftest.py`). A regression suite is the categorical opposite of a probe: it exists to import and exercise the live `src/` tree, and the exemption keys off pytest's own naming convention rather than any one project's directory layout (e.g. `websearch`'s `dev/tests/` — note: this path does not exist in this repo). Both conditions are required — a bare `tests/` dir doesn't exempt a stray probe someone drops there, and pytest-shaped naming alone doesn't exempt a renamed probe outside an actual test directory.

**Blocked patterns:** Write or Edit where `file_path` matches `/dev/` AND the written content contains `^from src\.` or `^import src\.` AND the file is NOT a pytest-shaped test file under a `tests/` directory.

**Allowed patterns:** files outside `dev/`; dev/ files without `src/` imports; a `dev/.../tests/test_*.py` (or `*_test.py`/`conftest.py`) file with `src/` imports — regression suite, not a probe; parse errors (fail-open).

### block_except_pass.py

**Blocked patterns:** `except [OptionalType]:\n    pass` — any bare exception-swallow block in written content.

**Allowed patterns:** `except ... : raise`; `except ... as e: logger...; raise`; `finally: resource.close()`; parse errors (fail-open).

### block_git_add_deps.py

**Blocked patterns:** `git add` (with optional `-C path`) where command also contains `venv/`, `.venv/`, or `node_modules/` as a target.

**Allowed patterns:** `git add` targeting specific files; `git add .` without a dependency directory in scope; parse errors (fail-open).

### block_git_destructive.py

Full original Purpose text extra: Pattern connectors use `[^|;&\n]*` — matches cannot span across newlines in multi-line commands (closes cross-line FP: `git push` on line N + `[ -f file ]` on a later line). Enforces the Git Safety Protocol from `tool-use.md`.

**Blocked patterns:**
- `git commit --amend`
- `git push --force` / `--force-with-lease` / `-f`
- `git commit|push --no-verify`
- `git commit --allow-empty`
- `git config` (modify — write operations); read-only flags (`--list`, `--get`, `--show-origin`, etc.) are exempt

**Allowed patterns:** `git commit` (without `--amend`/`--no-verify`/`--allow-empty`); `git push` (without force flags); `git config --list|--get|...` (read-only); parse errors (fail-open).

### block_path_typo.py

Full original Purpose text: PreToolUse hook (Bash + Read + Write + Edit) — detects path typos `.claire/` (tokenizer typo of `.claude/`) and `..letter` (double-dot immediately followed by lowercase letter, e.g. `..claude/`, `..src/`) and **auto-rewrites** them to `.claude/` and `../letter` respectively. Upgraded 2026-05-22 commit `ce8d220` from block-and-hint to auto-rewrite. File name preserved (`block_path_typo.py`) for settings.json compatibility; internal semantics are now rewrite.

**Detected patterns:**
- `.claire/` anywhere in command (Bash) or file_path (Read/Write/Edit), after quote-stripping
- `..letter` — two dots followed by lowercase letter in path context (boundary char `^`, `/`, whitespace, `=`)

**Rewrites:**
- `.claire/` → `.claude/` (literal `str.replace`)
- `..<letter>` → `../<letter>` (regex `(^|[/\s=])(\.\.)([a-z])` → `\1\2/\3`, preserves the boundary char and letter)

**Edit-specific:** `updatedInput` for Edit carries ALL 4 fields (`file_path`, `old_string`, `new_string`, `replace_all`) per Issue #47853 OP requirements — only `file_path` is rewritten, the other three are passed through unchanged from `tool_input`.

**Edit-Matcher anomaly:** the hook is registered for Edit but evidence suggests it doesn't fire on Edit tool calls (bash + Read confirmed working in same session). See `process-docs/tool_use_safety/2026-05-22_block_path_typo_edit_no_fire.md`. The auto-rewrite form is correct; the issue is on the CC-side firing pipeline for Edit.

**Allowed (passthrough):** `.claude/` (correct spelling); `../` (valid parent traversal); quoted strings containing typo patterns (stripped before matching); parse errors (fail-open).

### block_venv_no_redirect.py

**Blocked patterns:** `./venv/bin/python <anything>.py` (or `venv/bin/python ...`) without `> <file>` or `| tee` in the command.

**Allowed patterns:** command includes `> /tmp/file.md` or `| tee /tmp/file.md`; commands not matching the venv-python-script pattern; parse errors (fail-open).

**Quote/heredoc stripping.** Before pattern checks, `_strip_non_shell_active()` removes quoted regions. Prevents false-positives when `./venv/bin/python dev/...` appears as a literal example inside a `worker-cli send` message.

### block_worker_spawn_placement.py

**Blocked patterns:**
- `worker-cli spawn <name> <prompt> <path> ...` where `<path>` resolves to a different git-root than the current session's project — message points to `worker-cli worktree <name> <target_repo>` to create AND register the target-project worktree
- `worker-cli spawn ... --no-worktree` — flag present anywhere after the `spawn` subcommand

**Allowed patterns:** `project_path` of `c` or `.` (resolve to current project by definition); same-project absolute/relative paths; non-spawn commands; spawn from inside a worktree CWD (skipped); parse or path-resolution errors (fail-open).

**Project-root resolution** (mirrors worker-cli's `resolve_project_path`):
1. `os.path.abspath(expanduser(path))` → absolute form
2. Strip `/.claude/worktrees/<name>` suffix
3. `os.path.realpath()` — normalises symlink components (`/Users` vs `/System/Volumes/Data/Users`)
4. Walk parent dirs until a `.git` directory is found → that dir is the project root; `None` if filesystem root reached

Comparison is **case-insensitive** (`.lower()` on both roots) — macOS FS is case-insensitive; established convention from `session_finder.py`.

### block_worker_send_background.py

**Blocked patterns:** any `worker-cli send <name> <message>` with `run_in_background=true`.

**Allowed patterns:** `worker-cli send` with `run_in_background=false` or field absent; commands without `worker-cli send`; `worker-cli send` appearing inside a quoted string (blanked by `_strip_non_shell_active`); parse errors (fail-open).

### block_worker_kill_while_working.py

Original heading annotation: "(86 LOC, message text corrected 2026-09-04)".

Full original Purpose text extra: **2026-09-04:** `_BLOCK_MESSAGE` shortened to `"worker '{name}' is working — do not kill a working worker. Not possible.\n"` — the old text ("stop it first ... or: worker-cli send '{name}' 'stop'") suggested exactly the workaround the new sibling hook (`block_worker_send_while_working.py`) now forbids, so the message no longer names an alternative at all.

**Double-gate rationale:** pure regex alone would block a `kill` dispatched right after a worker finishes (race). The live status check ensures block iff the worker is verifiably `working` at hook-fire time — zero false positives for idle/finished/nonexistent workers.

**Known accepted residual:** a shell comment containing the literal kill + a live-working-worker-name blocks (e.g. `echo hi # worker-cli kill foo`). Consistent with the whole hook family — none of the 31 hooks strip comments. The double-gate makes this unlikely in practice.

**Smoke:** `dev/hook_smoke/test_block_worker_kill_while_working.py` (13 cases: 3 block, 9 allow, 1 accepted-residual block; asserts only on `decide()`'s `(block, name)` tuple, never the message text, so the 2026-09-04 wording change needed no test update).

### block_worker_send_while_working.py

Original heading annotation: "(86 LOC, new 2026-09-04)".

**Double-gate rationale, known accepted residual:** identical to `block_worker_kill_while_working.py`'s.

**Smoke:** `dev/hook_smoke/test_block_worker_send_while_working.py` (12 cases: `decide()`-level — 3 block, 7 allow; plus 2 subprocess-level checks against the real entrypoint: malformed stdin fails open, and a command naming an unresolvable real worker fails open).

### block_manual_worker_cleanup.py

Full original Purpose text extra: Both patterns use `[^;&|\n]*` (not `.*`) to prevent bridging across shell separators — `tmux kill-session -t main ; cmd -t worker-x` does not trigger. `git branch -D` is deliberately excluded (worker branches have no distinguishing prefix; blocking would FP on normal feature-branch deletes).

**Blocked patterns:**
- `tmux kill-session -t worker-*` — direct session kill (any `-t` form including `-tNAME` no-space)
- `git worktree remove .claude/worktrees/*` — direct worktree remove (handles `-C path`, `--force`, absolute paths)

**Allowed patterns:** `worker-cli kill <name>`; `tmux kill-session -t non-worker-session`; `tmux kill-session` (no -t); `git worktree remove /non-claude/path`; `git worktree list`/`add`; `git branch -D`; quoted patterns inside `worker-cli send` messages (stripped); cross-separator patterns (separator guard); parse errors (fail-open).

**Smoke:** `dev/hook_smoke/test_block_manual_worker_cleanup.py` (21 cases: 8 block, 13 allow including 2 separator-guard cases and 2 quoted-string cases).

### block_po_read.py

Full original Purpose text extra: Discriminator is path-schema only (`/.claude/` substring AND `.txt` suffix on the same token) — no size threshold, no Read-tool matcher (Read stays fully allowed). Direct structural clone of `block_log_read.py.disabled`'s Branch B (reader-tool + matching input-path segment → block) with no state file / no session counting.

**Blocked patterns:**
- `head`/`tail`/`grep`/`cat`/`sed`/`rg`/etc. on a Claude Code persisted-output export path (under a `.claude` dir, ending `.txt`)
- `cat <PO-export-path> | head -20` — reader + path co-occur in the same pipeline segment
- `split -l N <PO-export-path> /tmp/...`, `dd if=<PO-export-path> of=...` — partitions content for later partial consumption, same escape class as head/tail (live incident 2026-07: `split` bypassed the hook and fed a copy to `awk`)

**Allowed patterns:** any reader tool on a file NOT under `.claude/`; any reader tool on a `.claude/` path NOT ending `.txt`; a PO-export path as a redirect WRITE target (stripped before the input-path check); a PO-export path appearing only inside a quoted string; parse errors (fail-open).

**Segment split.** Same `_SEGMENT_SPLIT`/`_REDIRECT_STRIP` mechanic as `block_log_read.py.disabled`: split on `&&`/`||`/`|`/`;`/newline, strip redirect-write targets per segment before checking for a reader-tool + PO-path co-occurrence.

**Block message escalation.** States the verified-correct escape: read via the Read tool; when the total exceeds the per-call token cap, page with MULTIPLE Read calls via `offset`/`limit` (offset starts at 1); files with very long single lines need a small line-count limit per call.

**Smoke:** `dev/hook_smoke/test_block_po_read.py` (16 cases: 9 block including the piped `cat | head` case and the `split`/`dd` partitioning cases, 7 no-op including redirect-write, quoted-string, and parse-error fail-open).

### block_pipe_scraper_isolated.py

Full original Purpose text extra: Direct clone of `block_rag_cli_index_isolated.py` with the anchor swapped: CC auto-backgrounds a Bash call only when it stands ALONE in the invocation; a worker chaining a poll (`tail`, `&& echo done`) onto the scraper call in the same invocation defeats auto-backgrounding, and the worker sleeps until the multi-minute scrape finishes instead of staying awake to poll. Segment classifier `_SCRAPER_SEGMENT_RE` additionally tolerates an interpreter path prefix before `python`/`python3` since the scraper is always invoked via a venv interpreter, not a bare CLI name.

**Blocked patterns:**
- `python -m src.crawler.pipe_scraper --url-file /tmp/x.txt && tail /tmp/x_scrape.log` — poll chained after the scraper
- `tail /tmp/x_scrape.log && ./venv/bin/python -m src.crawler.pipe_scraper --url-file /tmp/x.txt` — poll chained before the scraper
- `./venv/bin/python -m src.crawler.pipe_scraper --url-file /tmp/x.txt | tee /tmp/log` — piped
- `X=$(tail /tmp/a.log) ./venv/bin/python -m src.crawler.pipe_scraper --url-file /tmp/x.txt` — command substitution smuggled through an assignment value
- `./venv/bin/python -m src.crawler.pipe_scraper --url-file $(cat /tmp/name.txt)` — substitution in an argument
- `./venv/bin/python -m src.crawler.pipe_scraper --url-file /tmp/x.txt &tail /tmp/y` — bare `&` smuggles a second command

**Allowed patterns:**
- `cd "$WEBSEARCH" && ./venv/bin/python -m src.crawler.pipe_scraper --url-file /tmp/x.txt --output-dir "$OUTPUT_DIR" > /tmp/x_scrape.log 2>&1` — the canonical form
- `./venv/bin/python -m src.crawler.pipe_scraper --url-file /tmp/x.txt` — bare, standalone
- `PYTHONUNBUFFERED=1 ./venv/bin/python -m src.crawler.pipe_scraper --url-file /tmp/x.txt` — env-var prefix on the scraper segment itself
- any command without `-m src.crawler.pipe_scraper` — out of scope, anchor exits early
- `src.crawler.pipe_scraper` inside a quoted string / heredoc body — blanked, anchor fails

**Segment split.** Identical `_SEPARATOR_RE`/`_LINE_CONTINUATION_RE`/`_SUBSHELL_RE` mechanic as `block_rag_cli_index_isolated.py`.

### block_rag_cli_document_repeat.py

Full original Purpose text: PreToolUse hook (Bash) — the first STATEFUL hook in this family. Blocks the 2nd (or later) single-document `rag-cli index --collection X --document Y` / `rag-cli delete --collection X --document Y` call to the SAME `(subcommand, collection)` within a 10-minute rolling window, across SEPARATE Bash invocations. `block_rag_cli_index_isolated.py` already forbids CHAINING (>1 `index` segment in one Bash call) but each individually-isolated `--document` call passes that hook fine — the gap it cannot see is REPETITION across calls: an observed incident issued ~40 consecutive `rag-cli index --document <file>` calls (and ~48 `rag-cli delete --document <file>` calls) instead of one collection-wide call, none of which individually run long enough to auto-background, so the worker stayed awake for dozens of turns instead of sleeping through one long run. State-persistence architecture is a direct clone of the disabled `block_polling_loop.py.disabled`'s pattern (append-only JSONL, self-pruned to the window on every write, count by session_id+target) — the only established stateful-hook precedent in this codebase; the alternative `last_cmd_state.jsonl`/adjacency-based "last command" pattern was deliberately NOT used (it was redesigned then fully removed in 2026-07-20/21 specifically because adjacency tracking false-positive-blocked legitimate interleaved commands — see `2026-07-20_timer_guard_concurrent_redesign.md`). Segment/argument extraction reuses `block_rag_docs_layer.py`'s technique. Threshold 2, not 3: a genuine single-document op is singular by definition — a SECOND `--document` call to the same collection+subcommand within the window is already the opening move of the per-file loop, not a second legitimate one-off. Window 600s, not the polling-loop's 30s: a full model turn sits between two rag-cli calls, so a short window would expire before a real repeat pattern registers.

**Blocked patterns:**
- `rag-cli index --collection monitor-cc-docs --document a.md` then (separate Bash call, same session, within 10 min) `rag-cli index --collection monitor-cc-docs --document b.md` — 2nd single-document index call to the same collection
- `rag-cli delete --collection monitor-cc-docs --document a.md` then `rag-cli delete --collection monitor-cc-docs --document b.md` (same session) — delete is covered identically to index

**Allowed patterns:**
- `rag-cli index --collection monitor-cc-docs --document a.md` — a single one-off `--document` call, alone, always passes
- `rag-cli index --collection monitor-cc-docs` (no `--document`, any number of times) — collection-wide call never touches the state file, out of scope by design
- a 2nd `--document` call from a DIFFERENT `session_id` — session-scoped counting, no cross-session leakage
- any command without `rag-cli index`/`delete` — anchor exits early
- a segment with `--collection` but no `--document` (or vice versa) — `_extract_target` returns `None`, not counted

**State mechanic.** `_STATE_FILE` (env-var override `MONITOR_CC_RAG_DOC_REPEAT_STATE` for test isolation) holds one JSON line per qualifying occurrence: `{ts, session_id, target}` where `target = "<subcommand>:<collection>"`. On every qualifying call: read entries with `ts >= now - 600s` (self-pruning), append the new occurrence, overwrite the file, then count entries matching `(session_id, target)`; block if count `>= 2`. Accepted trade-off: a legitimate collection-wide call interspersed between two `--document` calls does NOT reset the window — purely time-based.

**Smoke:** `dev/hook_smoke/test_block_rag_cli_document_repeat.py` (7 cases: single `--document` call allow, 2nd call block, 3x collection-wide always-allow, cross-session independence, delete-subcommand-also-counts, malformed-stdin fail-open).

### hook_setup.py

Full original Purpose text: Idempotent installer with three defense layers. **Layer 1 — Worktree Guard:** `_guard_not_worktree()` checks `Path(__file__).resolve().parts` for consecutive `.claude`/`worktrees` components; exits 2 with a clear error message (stderr) if running from a worktree — preventing dead-path registration. **Layer 2 — Stale-hook Sweep:** `_sweep_stale_hooks()` iterates ALL event keys in `settings["hooks"]` (not only `PreToolUse`), checks every `python3 <path>` entry, and removes any whose script path fails `os.path.exists()`; drops now-empty groups, saves atomically, then runs the normal add-loop. **Layer 3 — Two-Condition Install Gate:** `decide_entries()` (pure, injectable `git_query_fn` + `tree_query_fn`) partitions `_HOOK_SCRIPTS` into installable vs. skipped BEFORE the add-loop runs. A script installs only when BOTH: (a) `_script_on_main()` confirms it's committed on `main`; (b) `_script_in_worktree()` confirms it's present in the CURRENT working tree, at the exact path about to be registered. Condition (a) prevents the incident this layer was built for: a hook merged into `integration`, auto-registered via `.githooks/post-merge` using its absolute working-tree path, then orphaned machine-wide the moment the tree checked out `main` — every Bash call on every project failed with `[Errno 2] No such file or directory` until the entry was removed by hand. Condition (b) closes the mirror-image hole found in review: (a) alone lets a script that IS on `main` but was deleted/renamed in the CURRENT tree pass the gate and get registered as a dead path — same outage, entering from the other side; note `_sweep_stale_hooks()` runs BEFORE this gate, so without condition (b) the sweep would remove that exact dead entry and the install loop would immediately put it back. Decision is per-script (cached by filename, shared across a script's multiple matcher entries) — one unmergeable/deleted script never blocks the other 38 (stale count from an earlier module total). `_report_skipped()` prints one deduped stderr line per skipped script naming it and the reason. Runs completely silent on success — no stdout output; stderr only for error conditions.

**Fail-safe direction (git query unanswerable):** `_script_on_main()` returns `None` when `main` doesn't resolve, `git` is missing, or the subprocess errors/times out (5s timeout on both calls). `decide_entries()` treats `None` identically to a confirmed-absent `False` — SKIP, never install. Rationale: the incident this layer prevents is a machine-wide Bash outage from a dead absolute path; losing one hook's enforcement until the query can succeed again is categorically cheaper than risking that outage on an unverifiable script. Note: this `None` path is exercised only via stub in the smoke suite — not reproduced against a live git repo lacking a `main` ref.

**Event dimension (2026-08-29).** `_HOOK_SCRIPTS` entries are `(script, matcher)` — registering under `PreToolUse`, the `_DEFAULT_EVENT` — or `(script, matcher, event)` for any other hook event; `_unpack_entry()` normalises both shapes. The add-loop keys `hooks.setdefault(event, [])` and checks `_already_installed` within that event's list, so the same script may be registered under different events without collision. `decide_entries()` passes entries through in the SHAPE they arrived, keeping the install gate agnostic of an event dimension it does not judge — which is also why its smoke suite needed no change. `_sweep_stale_hooks()` already iterates every event key, not just `PreToolUse`.

**Usage:** `python3 src/hooks/hook_setup.py` — run once after clone or reinstall. Re-run any time to heal stale hook entries. Hooks are active immediately (no CC restart needed).

**Note:** Must be run from the MAIN REPO root, not a worktree. The guard enforces this — attempting to run from a worktree exits with exit code 2 and a stderr message before touching settings.json.

**Smoke:** `dev/hook_smoke/test_hook_setup_main_branch_gate.py` (10 cases, stub `git_query_fn` + `tree_query_fn`: all-present install, absent-from-main skip, git-query-fails skip, mixed set, multi-matcher script skips every entry, absent-from-tree-only skip, present-in-both install, absent-from-both reports the main-branch reason, skip-reason text distinguishes the two conditions).

### Top-level Gotchas (original, full text, everything cut or shortened)

- **Hooks are the single source of truth for mechanical command rules — do NOT also state the rule in a skill or rule file.** A skill/rule loads its full text into every session (context cost + a maintenance surface that drifts) and carries that text whether or not it is relevant; a hook fires surgically only on the actual violation and costs nothing idle. Failure-case rules can therefore be added freely as hooks without bloating any always-loaded surface. When a rule can be a hook, make it a hook and keep skills/rules lean — never duplicate a hook-enforced rule as prose.
- **Auto-deploy via `.githooks/` (per-clone setup required).** The repo ships `.githooks/post-merge` and `.githooks/post-commit` — both fire `python3 src/hooks/hook_setup.py` automatically when a commit (merge or direct) touches `src/hooks/*`. This keeps settings.json in sync with the filesystem, preventing the stale-hook disaster class. Each clone must activate the hooks once: `git config core.hooksPath .githooks` (local config, not committed). Workers committing from worktrees are unaffected — `hook_setup.py`'s worktree guard exits 2, which the hook script swallows silently; settings.json is only updated when the hook fires from the main repo context. Verification: after a commit touching `src/hooks/`, confirm settings.json (user-level file, not in repo) has mtime fresher than the commit timestamp.
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
- **A feature-branch-only script must never reach settings.json in the first place.** Confirmed incident: a hook merged into `integration` was auto-registered by `.githooks/post-merge` using its absolute working-tree path; the tree later checked out `main` (script absent there) → the registered path went dead → every Bash call on every project, every session, failed globally until removed by hand. The sweep only heals this AFTER `hook_setup.py` runs again — during the outage window Bash itself is dead, so nothing triggers a sweep. `hook_setup.py`'s Layer 3 closes this at registration time instead.
- **A shared shell-region stripper (`_shell_strip.py`) is used across most Bash-scanning hooks.** [list of hook names, now covered by _shell_strip.py's own Called-by field] Fail-open: any parse error returns the original string unchanged.
- **Cache-bust on settings.json edit.** Editing settings.json busts CC's prompt cache — full message rebuild on the next request. Hooks are active immediately after settings.json is written; no CC restart needed.
- **PreToolUse exit codes.** Exit 0 = allow, exit 2 = block (CC shows stderr to user as the block reason), exit 1 = hook error (CC logs but does not block).
- **A failed tool call does NOT reach `PostToolUse` — the event is `PostToolUseFailure` (measured 2026-08-29).** With a stdin-dumping probe on `PostToolUse`/Bash: 4 payloads for 4 successful calls, **zero** for 3 failing ones (`cat <missing>`, `false`, `exit 3`). The failure lands on the sibling event `PostToolUseFailure`, whose payload carries `error` (`"Exit code N\n<output>"`) and `is_interrupt`, and NO `tool_response` at all. `ToolUseFailure`, `PostToolUseError` and `ToolError` are not real event names — probes registered under them never fired. Consequence for any future post-hoc hook: "only react to errors" needs no condition, it is what registering on this event already means. Also measured: on a success, `tool_response.stderr` was empty and stderr text arrived inside `stdout`, so `tool_response.stderr` is not a usable error signal either. (No module in the current tree implements a `PostToolUseFailure` hook — this is forward-looking design knowledge, not tied to any current file.)
- **Feedback surfaces to the model through three channels; plain stdout is swallowed.** Measured on `PostToolUseFailure` (2026-08-29): exit 2 + stderr renders as a "blocking error" framing even though nothing was blocked; stdout `{"decision":"block","reason":MSG}` renders similarly; stdout `hookSpecificOutput.additionalContext` renders as plain additional context (the correct channel for post-hoc feedback); plain stdout produces nothing at all. All three arrive as a system-reminder after the error result. Note `strip_hook_prefix.py` (in the proxy, not in src/hooks/) strips the `PreToolUse:<Tool> hook error: [...]` prefix and does not cover these newer shapes.
- **Subprocess hooks must resolve plugin CLIs by absolute path.** CC's hook execution environment has a stripped PATH that does NOT include local bin or the plugin-cache bin directories. A subprocess-hook invoking a plugin CLI by bare name receives `FileNotFoundError` → catches it → returns the fail-open default → hook silently never fires. This was a confirmed live bug in `block_worker_kill_while_working`: the kill-guard let working-worker kills through until `_resolve_worker_cli()` was added.
- **All active hooks log fires via `_fire_log.log_fire()`.** Called at the decision-point only — NOT at hook start and NOT on passthroughs. New hooks must add a `log_fire()` call at their decision-point as part of the implementation. Use `MONITOR_CC_HOOK_FIRING_LOG` env var in smoke tests to redirect to a temp file and avoid polluting the real log.

## 2026-09-11 recap — format pass, method and verification

This section is the recap append for the docs-format task on `src/hooks/DOCS.md`; the salvage above was written in the same session as the format rewrite, before the first recap request, so this is the first dated append.

**Method used.** Every one of the 34 active `.py` files in `src/hooks/` was read in full (not grepped/sampled) before writing a module entry, plus the 6 `.py.disabled` files to confirm they carry no active registration. `hook_setup.py`'s `_HOOK_SCRIPTS` list was cross-checked against the 34 active filenames to confirm all 30 hook scripts (28 `block_*` + 2 `rewrite_*`; the 3 leading-underscore files are shared libraries, not hooks; `hook_setup.py` is the installer itself) are registered — zero DEAD CODE candidates. `Called by` for the 3 shared-library modules (`_shell_strip.py`, `_known_cli.py`, `_fire_log.py`) was derived from `grep -l "from _X import" src/hooks/*.py`, run three times (once per library), rather than trusted from the prior DOCS.md prose.

**Decision — `.disabled` files excluded from the Modules section.** The task scope named "34 modules" for `src/hooks/`, matching exactly the 34 non-`.disabled` `.py` files; the 6 `.py.disabled` files are not valid Python module names, are absent from `hook_setup.py`'s `_HOOK_SCRIPTS`, and are not loaded by anything. Their prior DOCS.md entries (`block_chained_sleep.py.disabled`, `block_read_oversize.py.disabled`) were pure changelog ("Disabled YYYY-MM-DD — superseded by X") with no LOC/Reads/Writes/Called-by shape to map to the target format, so they were dropped from Modules entirely and their text moved to salvage rather than kept as stub entries.

**Decision — dev/hook_smoke/ subprocess-test callers not counted as `Called by`.** Most `dev/hook_smoke/test_block_*.py` files invoke the hook under test as a subprocess (`HOOK = "src/hooks/block_x.py"`, then `subprocess.run(["python3", HOOK, ...])`), which is a test-harness invocation, not a code dependency in the sense `Called by` / dead-code detection cares about. Only the two modules whose test file does a direct Python `from block_x import decide` (`block_worker_kill_while_working.py`, `block_worker_send_while_working.py`) and `hook_setup.py` (`from hook_setup import decide_entries` in `test_hook_setup_main_branch_gate.py`) got that test file listed under `Called by`, in addition to the "Claude Code hook system, registered by hook_setup.py" line every hook script carries.

**Decision — Blocked/Allowed pattern lists, segment-mechanics prose, and Smoke references cut entirely, not summarized.** The target format has no per-module field for these (only Purpose/Reads/Writes/Called by/Calls out), and the rule "module-level only, no function-level documentation" reads them out categorically — an exhaustive regex-example list is a step below function-level, it's test-case-level. All of it went to the salvage file verbatim, grouped by module.

**Decision — top-level Gotchas trimmed to calibrated values a reader would hit in the code today.** Kept: fail-open convention, 5s hook timeout, the block/rewrite/ui-notice enum table, PreToolUse exit-code table, the stale-hook-blocks-all-Bash trap + recovery steps, the absolute-path-on-move trap, the per-clone `core.hooksPath` setup step, and the subprocess-PATH-resolution trap (still live in two current modules). Cut to salvage: the `PostToolUseFailure`/feedback-channel measurement bullets, because no `feedback_*.py` module exists in the tree — that content is forward-looking design knowledge about a hook class that isn't implemented, not a landmine tied to current code, and it carried explicit "measured 2026-08-29" dates besides. Also cut: the "hooks are the single source of truth, don't duplicate in skills" design-philosophy bullet, folded instead into the Role paragraph's "when to touch it" framing rather than kept as a Gotcha.

**Verification performed.** (1) A Python script read every `### <module>.py (<LOC> LOC)` heading via regex and compared against `wc -l` of the actual file — all 34 matched exactly, no drift. (2) `docs-drift-check` was run twice: first pass surfaced 3 backtick-flagged findings, all from backticking the runtime-only fragment `.claude/worktrees/` (a path that exists only inside a live worktree, never as a static repo path, so the checker's on-disk existence check can never pass for it) inside `rewrite_background_sleep.py`, `block_cd_drift.py`, and `block_manual_worker_cleanup.py`'s Purpose lines; reworded to plain prose ("a worktree path (contains the fragment .claude/worktrees/)") without backticks, second pass showed zero findings whose path starts with `src/hooks/DOCS.md`. (3) `git diff integration --name-only` confirmed only `src/hooks/DOCS.md` and the new process-docs file changed — no `.py`/`.sh` touched.

**Known drift not owned by this task.** The drift-check run surfaced unrelated findings in `dev/timer-loop/DOCS.md` (references `src/hooks/block_timer_pending_bg.py` and `src/proxy/pending_bg_state.py`, neither present in the current tree) and in many other `dev/`/`src/` DOCS.md files referencing a `src/logs/` tree that is gitignored and not present in a clean checkout. Both are pre-existing and out of this task's scope (only `src/hooks/DOCS.md` was in scope); noted here rather than touched, per the rule that another file's error is stated in this file, never fixed in the other one.
