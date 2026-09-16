# dev/hook_error_correlation/

## Role

Overlays `src/logs/tool_errors.jsonl` (hook-caused tool-result errors) against the current
`src/hooks/` config to classify which errors are still reachable under the CURRENT hook set
(false-positive candidates) vs. stale (can't recur — hook disabled, removed, or its trigger
pattern narrowed since). Touch this directory when auditing hook false-positive reports.

## Modules

### analyze.py (190 LOC)

**Purpose:** For each `tool_errors.jsonl` entry, resolves the exact triggering command via
`proxy_file + tool_use_id → raw_payload.messages` (direct lookup, no fire-log join needed —
session join yields 0 results since errors predate `_fire_log.py` or come from a cross-project
RAG session), replays the currently-active hook against that command, and classifies each entry
as `disabled` (`.py.disabled` exists), `removed` (no `.py` or `.disabled`), `pattern-narrowed`
(hook exists but the replay now exits 0), or current-config-relevant.
**Reads:** `src/logs/tool_errors.jsonl`, `src/logs/hook_firing.jsonl`,
`src/logs/<proxy_file>.jsonl` (`raw_payload.messages[assistant][type=tool_use][id=tuid]["input"]`).
**Writes:** `md/<date>.md` (hook-error counts, `error_full` examples per hook, exact triggering
command + error per current-config-relevant entry). Also runs hook scripts under `src/hooks/` as
subprocesses to replay past commands — a hook that blocks calls its own `log_fire()`, which
appends to the real `src/logs/hook_firing.jsonl`.
**Called by:** none — run manually.
**Calls out:** `analyze_report.py` (`format_report`).

---

### analyze_report.py (205 LOC)

**Purpose:** Pure markdown rendering for the Hook Error Correlation report — builds the Q1
summary table, join-analysis prose, Q2 error examples, Stufe-1 event list, and Stufe-2
reachability filter (stale/unverified/Q3-current-config-relevant) sections from the data
`analyze.py` already collected.
**Reads:** nothing — takes `stufe1`/`stufe2`/`fires`/`raw_counts`/`report_date` as arguments.
**Writes:** nothing — returns a markdown string.
**Called by:** `analyze.py` (`format_report`).

---

## Gotchas

**Hook replay must run with `cwd=MAIN_PROJECT`, not the worktree** — `block_cd_drift` exits 0
(passes) whenever `os.getcwd()` contains `.claude/worktrees/`, which would silently make every
replay look non-blocking regardless of the hook's real logic.
