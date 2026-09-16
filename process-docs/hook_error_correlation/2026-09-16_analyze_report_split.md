# 2026-09-16 — dev/hook_error_correlation/ cohesion split

## What happened

`dev/hook_error_correlation/analyze.py` was 349 LOC with one function over the
50-line threshold: `format_report` at 141 lines. The file itself was under the
400-LOC file-split threshold — only the function-length rule was actually
violated. Split anyway into two files along the existing concern boundary
(data-loading/hook-replay vs. markdown rendering), rather than just chopping
`format_report` into same-file helpers, per the milestone's own framing that a
cosmetic in-file shrink is not a split:

- `analyze.py` (190 LOC) — entry script, unchanged filename. Keeps bootstrap
  (`_resolve_main_project`, path constants), the orchestrator
  (`analyze_workflow`), and every data-loading/hook-replay function
  (`load_raw_counts`, `load_hook_errors`, `load_fires`, `classify_hook_status`,
  `build_stufe1`, `lookup_command`, `build_stufe2`, `build_replay_payload`,
  `replay_hook`, `write_report`) byte-for-byte unchanged. The only edits: one
  new import line (`from analyze_report import format_report`) and the
  `format_report(...)` call site now passes `REPORT_DATE` explicitly instead of
  the callee reading it off the module global.
- `analyze_report.py` (205 LOC) — new sibling module, pure markdown rendering,
  no I/O, no subprocess. `format_report` is now a 14-line composer calling
  `_compute_hook_stats`, `_build_hook_errors`, and one render function per
  report section (`_render_q1_section`, `_render_join_analysis_section`,
  `_render_q2_section`, `_render_stufe1_section`, `_render_stufe2_section` —
  the last composing `_render_stale_table`/`_render_unverified_list`/
  `_render_q3_section`), plus `_fmt_cmd`. Longest function after the split:
  `_compute_hook_stats` at 25 lines.

Naming note: Main explicitly rejected my first-response proposal of
`report.py` — a bare `report.py` sitting at a dev-area root is a `sys.path`
collision risk because these scripts run with their own directory on
`sys.path` (any other dev area's script doing `import report` would silently
grab the wrong module if both areas ever end up on `sys.path` in the same
process, e.g. under a test runner that imports multiple dev scripts). Named it
`analyze_report.py` instead — prefixed with the owning entry script's name,
matching the `probe01_bridge.py`/`probe01_report.py` naming convention already
used in `dev/desktop_detection/`. **Generalize this for any future split in
this codebase: never name a new dev/ sibling module a bare noun like
`report.py`, `utils.py`, `helpers.py` — prefix it with the owning script's
name.**

## Why REPORT_DATE became a parameter, not a cross-module import

The original `format_report` read `REPORT_DATE` as a module global inside
`analyze.py`. Two ways to preserve that after the split: (a) have
`analyze_report.py` do `from analyze import REPORT_DATE`, or (b) pass it as a
parameter. (a) creates a circular import — `analyze.py` already does
`from analyze_report import format_report` for the orchestrator to call it, so
`analyze_report.py` importing back from `analyze.py` would deadlock the import
graph (Python raises on the partially-initialized module). Went with (b):
`format_report(stufe1, stufe2, fires, raw_counts, report_date)`. This is a
call-signature change but not a behavior change — the value passed is the
exact same `REPORT_DATE` global, still computed once at `analyze.py` import
time via `datetime.now(timezone.utc)`, just handed over explicitly instead of
read implicitly. Watch for this exact shape (a helper function reads a
module-level global that isn't a pure constant registry) whenever splitting a
file that has one — that's the tell for "this needs to become a parameter,
not a re-import," to avoid a circular import.

## Hazard classification and why verification used zero real I/O

`analyze_workflow()` end-to-end is **mutating**, and not in the way the
milestone's stock hazard wording (macOS desktop/windows/Spaces/hotkeys/monitor)
anticipates: `build_stufe2` → `replay_hook` executes real hook scripts under
`src/hooks/*.py` via `subprocess.run(cwd=MAIN_PROJECT)` with `session_id:
"replay"`. Reading `block_cd_drift.py` confirmed hooks call their own
`log_fire()` on block, which **appends a real line to the production
`src/logs/hook_firing.jsonl`** — a permanent write to a shared live log, not
just an in-memory side effect. `src/logs/tool_errors.jsonl` itself is old and
static (dated Jun 8, not live-growing like the dual-log corpus from the
`strip_fp_tool_result` split), but `hook_firing.jsonl` IS live (grows during
normal proxy/hook usage) and replay pollutes it with fake "replay" session
entries every time `analyze_workflow()` runs for real.

The split only touches `format_report`/`_fmt_cmd`, both pure functions with
zero I/O and zero subprocess calls — so verification never needed to run
`analyze_workflow()`, touch `replay_hook`, or read any real log file at all.
Built one small synthetic `stufe1`/`stufe2`/`fires`/`raw_counts` fixture in
memory (4 stufe1 entries covering `active`/`disabled`/`removed` hook status,
`current`/`stale:pattern-narrowed`/`stale:<reason>`/`unverified:proxy_missing`
classifications, and all four `_fmt_cmd` branches — `Bash`, `Write`, `Read`,
`Edit`/None), then compared `backup.format_report(...)` (pre-split, loaded via
`importlib.util.spec_from_file_location`) against
`analyze_report.format_report(...)` (post-split) on that identical fixture.
Result: `OLD LEN 2995 NEW LEN 2995`, string equality `True`.

Gotcha hit during this: `importlib.util.spec_from_file_location` on a backup
copied to `/tmp/` makes `__file__` resolve to `/tmp/analyze_orig_backup.py`,
so `analyze.py`'s own `SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))`
→ `_resolve_main_project()` walks up from `/tmp` and never finds a `.git`,
raising `RuntimeError: Cannot find main project root` at module-exec time —
this happens before any test code gets a chance to patch anything, because
`_resolve_main_project()` runs as top-level module code, not inside a function
call the test controls. There is no clean monkeypatch fix for this shape
(unlike the `strip_fp_tool_result` split, where `os.environ.setdefault` could
be pre-set before `exec_module`). Fix used here: copy the backup into the real
`dev/hook_error_correlation/` directory under a throwaway filename
(`_verify_backup_analyze.py`) so `__file__`'s directory is the real one and
`.git` traversal resolves correctly, run the comparison, then delete the
throwaway file before committing. **If a future split's pre-split file does
path-resolution work at import time (not inside a function), load the backup
copy from inside the real directory, not from `/tmp`.**

## Pointers

- The `_MC`/`_PO`-style "old corpus, frozen finding, don't fix it against
  today's data" caveat does not apply here — `analyze.py`/`analyze_report.py`
  carry no hardcoded historical filenames or manual verdict tables, everything
  is computed fresh from whatever `tool_errors.jsonl`/`hook_firing.jsonl`
  contain at run time. The hardcoded `"Alle 59 rohen Errors..."` and
  `"17/21 unique Events..."` sentences inside
  `_render_join_analysis_section()` ARE frozen historical prose (copied
  verbatim, unchanged by this split) — they describe a specific past finding
  and will silently go stale if the underlying logs change; not something
  this milestone was scoped to fix.
- `DOCS.md` already documented a `REPORTS_DIR`/`md/` path mismatch before this
  split (code writes to `SCRIPT_DIR/reports/`, the two committed report files
  in the repo live under `SCRIPT_DIR/md/`) — pre-existing, out of this
  milestone's scope, left untouched.
