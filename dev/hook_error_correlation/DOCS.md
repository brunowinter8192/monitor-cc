# dev/hook_error_correlation/

## Problem

Tool-result errors in `src/logs/tool_errors.jsonl` contain `PreToolUse:<Tool> hook error:` messages. Goal: identify which hook-caused errors are still reachable under the **current** hook config (False-Positive candidates) vs stale (can't recur).

## Data Sources

| File | Role | Schema |
|------|------|--------|
| `src/logs/tool_errors.jsonl` | Tool-use errors from proxy | `ts, session_id (8-char), worker, tool_name, tool_use_id, error_full, proxy_file, request_id` |
| `src/logs/hook_firing.jsonl` | Hook fire events | `ts, hook, decision, tool, command, reason/rewritten, session (full UUID)` |
| `src/logs/<proxy_file>.jsonl` | Full API request payloads | `raw_payload.messages[assistant][type=tool_use][id=tuid]["input"]` → exact triggering command |

**Command source**: `proxy_file + tool_use_id → raw_payload.messages` — direct per-error lookup, no fire-log join needed. Session join yields 0 results (errors predate `_fire_log.py` or come from cross-project RAG session).

## Scripts

### analyze.py

Overlay `tool_errors.jsonl` (hook errors) against proxy logs to extract exact triggering commands; replay active hooks against those inputs; classify as current-config-relevant or stale.

```bash
./venv/bin/python dev/hook_error_correlation/analyze.py
# Output: dev/hook_error_correlation/md/YYYY-MM-DD.md
```

**Output report answers three questions:**
1. Hook-error counts: historisch (raw/unique) vs current-config-relevant vs stale
2. `error_full` text examples per hook
3. Exact triggering command + error per current-config-relevant entry (legit/FP basis)

**Stale classification (three mechanisms):**
- `disabled` — `.py.disabled` exists; hook registered but file missing → every Bash call fails with "can't open file"
- `removed` — no `.py` or `.disabled`; same error type
- `pattern-narrowed` — hook `.py` exists; replay with exact original command returns exit 0 (hook logic has since narrowed its trigger criteria)

**Replay cwd**: `MAIN_PROJECT` (not worktree) — required for `block_cd_drift` which exits 0 when hook's `os.getcwd()` contains `.claude/worktrees/`.

## Reports

`reports/YYYY-MM-DD.md` — one report per run, named by UTC date.
