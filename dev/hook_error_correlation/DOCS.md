# dev/hook_error_correlation/

## Role
Overlays `src/logs/tool_errors.jsonl` (hook-caused tool-result errors) against the current `src/hooks/` config to classify which errors are still reachable (false-positive candidates) vs. stale (hook disabled, removed, or its trigger pattern narrowed since). Touch when auditing hook false-positive reports.

## Public Interface
No `__init__.py` in this directory. Entry point is direct invocation: `python3 dev/hook_error_correlation/analyze.py`.

## Flow
`analyze.py` loads `tool_errors.jsonl` and `hook_firing.jsonl`, resolves each error's exact triggering command via `proxy_file + tool_use_id` lookup into the matching proxy JSONL, replays the currently-active hook as a subprocess against that command, classifies each entry, and hands the result to `analyze_report.py` to render a Markdown report.

## Modules

### analyze.py (175 LOC)

**Purpose:** For each `tool_errors.jsonl` entry, resolves the triggering command via proxy lookup, replays the active hook, and classifies reachability.
**Reads:** `src/logs/tool_errors.jsonl`, `src/logs/hook_firing.jsonl`, `src/logs/<proxy_file>.jsonl`.
**Writes:** `reports/<date>.md`. Also runs `src/hooks/<name>.py` as a subprocess to replay past commands.
**Called by:** none — run manually.
**Calls out:** `analyze_report.py` (`format_report`).

---

### analyze_report.py (202 LOC)

**Purpose:** Pure markdown rendering for the Hook Error Correlation report — builds the Q1/Q2/Q3 and Stufe-1/Stufe-2 sections from data `analyze.py` collected.
**Reads:** nothing — takes `stufe1`/`stufe2`/`fires`/`raw_counts`/`report_date` as arguments.
**Writes:** nothing — returns a markdown string.
**Called by:** `analyze.py` (`format_report`).
**Calls out:** none.

---

## State
`analyze.py` owns all state in this directory: `MAIN_PROJECT`/`HOOKS_DIR`/`LOGS_DIR` are resolved once at import time from `.git` traversal and read-only afterward. `replay_hook()` runs a real hook script from `src/hooks/` as a subprocess with `cwd=MAIN_PROJECT` — if that hook blocks, the hook itself calls `log_fire()`, which appends to the production `src/logs/hook_firing.jsonl`. This is a live side effect on shared production state, not sandboxed; do not invoke `analyze_workflow()`/`main()` casually. Hook replay must run with `cwd=MAIN_PROJECT`, not the worktree — `block_cd_drift` exits 0 whenever `os.getcwd()` contains `.claude/worktrees/`, which would make every replay look non-blocking regardless of the hook's real logic.
