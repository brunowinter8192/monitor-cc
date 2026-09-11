# dev/hook_error_correlation/

## Role

Overlays `src/logs/tool_errors.jsonl` (hook-caused tool-result errors) against the current
`src/hooks/` config to classify which errors are still reachable under the CURRENT hook set
(false-positive candidates) vs. stale (can't recur — hook disabled, removed, or its trigger
pattern narrowed since). Touch this directory when auditing hook false-positive reports.

## Modules

### analyze.py (349 LOC)

**Purpose:** For each `tool_errors.jsonl` entry, resolves the exact triggering command via
`proxy_file + tool_use_id → raw_payload.messages` (direct lookup, no fire-log join needed —
session join yields 0 results since errors predate `_fire_log.py` or come from a cross-project
RAG session), replays the currently-active hook against that command, and classifies each entry
as `disabled` (`.py.disabled` exists), `removed` (no `.py` or `.disabled`), `pattern-narrowed`
(hook exists but the replay now exits 0), or current-config-relevant.
**Reads:** `src/logs/tool_errors.jsonl`, `src/logs/hook_firing.jsonl`,
`src/logs/<proxy_file>.jsonl` (`raw_payload.messages[assistant][type=tool_use][id=tuid]["input"]`).
**Writes:** `md/<date>.md` (hook-error counts, `error_full` examples per hook, exact triggering
command + error per current-config-relevant entry).
**Called by:** none — run manually.

---

## Gotchas

**Hook replay must run with `cwd=MAIN_PROJECT`, not the worktree** — `block_cd_drift` exits 0
(passes) whenever `os.getcwd()` contains `.claude/worktrees/`, which would silently make every
replay look non-blocking regardless of the hook's real logic.
