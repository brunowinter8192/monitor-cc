# Tool-Use Safety

## State as of this entry's audit

Tool-use discipline was enforced two ways:

1. **`~/.claude/shared-rules/global/tool-use.md`** — 16 hard rules + soft rules. Text-based, prompt-injected via `SessionStart` hooks in `~/.claude/scripts/session-start-rule-inject.sh`. Sent along on every REQ prefix (costs input tokens, cached). A mix of positive guidance ("use X") and negative prohibitions ("don't do Y").

2. **Persistent audit logs** (from 2026-05-24) — `src/logs/tool_errors.jsonl` (tool-use errors per session, appended by `warnings_persist.py`) + `src/logs/hook_firing.jsonl` (hook fire events via `_fire_log.py`). Superseded the deleted analyze.py scripts from `dev/tool_use_errors/` and `dev/hook_firing/`. **Detection/audit only, no prevention.**

3. **No PreToolUse hooks** active at the time. `~/.claude/settings.json` had `"hooks": {}` (empty). An earlier hook configuration in a backup file (`settings.json.hooks-backup`) showed a working format for PreToolUse/SubagentStop/SessionStart/InstructionsLoaded.

## Evidence

### Quantification of the `pkill -f` Antipattern (2026-05-12)

A run of `grep '"command":[^,]*pkill -f' src/logs/api_requests_*.jsonl` over 67 proxy logs (period 2026-05-06 18:20 — 2026-05-12 20:59, ≈6 days):

| Metric | Value |
|---|---|
| Total `pkill -f` calls | 267 |
| Top concentration, single session | 246 (searxng 2026-05-08) |
| Today's session (Monitor_CC) | 18 |
| Today's worker kills, same antipattern | 3 (menubarfix, mbarfix2, mbarlive) |

### Worker-Kill Mechanism (verified this session)

A worker process has the cmdline `claude.exe --model sonnet --dangerously-skip-permissions # Worker — <FULL PROMPT TEXT>`. If the prompt text contains strings like `workflow.py --mode menubar` (e.g. inside a smoke-test block), `pkill -f "workflow.py --mode menubar"` ALSO matches the worker process. SIGTERM → the worker dies with status 143.

Reproduced 3 times in one session, once directly AFTER self-explaining the antipattern → discipline alone is insufficient, structural prevention needed.

### rule_compliance.py Output (at the Time)

A run on that day's 4 sessions (224 tool_use blocks):
- 4 of 16 rules violated (Rule 3 grep scope, Rule 9 Read-before-Edit, Rule 12 sleep, Rule 13 .claire/ typo)
- 6 uncategorized failures
- Report: `dev/tool_use_analysis/20260512_rule_compliance.md`

Important: the `pkill -f` antipattern is NOT captured by Rule 3 (Rule 3 targets grep for source-code search, not process-kill pipes). The uncategorized bucket at the time would have contained it if logged as a failure (`is_error=True`) — but `pkill -f` typically SUCCEEDS (exit 0) and writes nothing to tool_result. So it's destructive-but-silent: no error trace, only a side effect.

## Recommendation (target state)

Pending — migration from a purely textual rule system to a hybrid system:

- **Hook-based prevention** for structurally-recognizable destructive patterns (`pkill -f`, `ps|grep|kill` chains). Block + point to an alternative.
- **tool-use.md** gets reduced to positive guidance ("use `pgrep -x <exact>`", "capture PID at launch in a PID file"). Negative rules out.
- **rule_compliance.py** stays for detecting patterns that CANNOT be mechanically blocked (behavioral, judgment-required).

Concretely, next session:
1. First hook implementation: a PreToolUse Bash matcher → script `~/.claude/scripts/block-dangerous-process-kill.py`. Block `pkill -f` + ps-grep-kill pipes. Allow `worker-cli kill`, allow a direct PID kill (`kill <numeric_pid>`).
2. Nuance design: distinguish an intentional kill (CLI wrapper, PID-direct) from an accident (textual pattern match).
3. Document the cache cost: every edit to `~/.claude/settings.json` invalidates the CC prefix cache → a one-time full rebuild per hook-migration wave.
4. Remove tool-use.md negative rules once the corresponding hook is live + verified.

## Open Questions

- How to distinguish "intentional kill via PID" from "textual pattern match"? Heuristic: block when the kill target was determined via a grep/awk pipe; allow when the PID is referenced directly (numeric or `$(cat pid-file)`).
- How many further antipatterns are migration candidates? Only assessable after phase-1 hook experience.
- Should hook blocks hard-block unconditionally, or have an optional "warning + confirm with Y" mode? — hard-block is more consistent, less discipline-dependent.

## Sources

- A tracker for the hook migration (closed at session end)
- The session-findings entry in this area — the discussion trail of that session
- `~/.claude/shared-rules/global/tool-use.md` — the source of the hard rules at the time
- `~/.claude/settings.json.hooks-backup` — a working hook-format reference
- `dev/tool_use_analysis/20260512_rule_compliance.md` — that day's compliance-run output
