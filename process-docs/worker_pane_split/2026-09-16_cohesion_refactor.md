# Cohesion refactor of dev/worker_pane_split/ (2026-09-16)

## Task

Split `attach_worker_stats_cost_probe.py` (206 LOC, `run_probe_workflow` 92 LOC) to satisfy the
50-LOC-function threshold. No behaviour change allowed. Full task text lives in the issue that
spawned this session, not repeated here.

## Scope: single file, no multi-file split needed

The file was 206 LOC — well under the 400-LOC file threshold. Only the function threshold was
violated, and only by one function: `run_probe_workflow` itself, the ORCHESTRATOR. Extracted 9
helper functions from its body, all inside the same file (matching the pattern already used this
batch for `bg_wakeup_id_line/p1_scan_launch_ack_wordings.py`, which had the same shape: one file
under 400 LOC, one function over 50). Final file: 250 LOC, longest function 24 lines
(`_stress_test_lines`).

## The ORCHESTRATOR itself was the offending function — worth noting for future splits

Unlike every other file split this batch, here the 50-LOC violation was the WORKFLOW/ORCHESTRATOR
function itself, not a helper. The original `run_probe_workflow` didn't just call other functions —
it inlined the entire report-line-building logic (table construction, conditional warning lines,
extrapolation math) directly in the body. This also violated the project standard's OTHER
orchestrator rule independently of the LOC count: "Sie ruft nur andere Funktionen auf und enthält
null funktionale Logik" (an orchestrator calls only other functions and contains zero functional
logic) — `run_probe_workflow` had plenty of functional logic (string formatting, conditionals,
arithmetic). Fixed both problems with one extraction: introduced `_build_report(all_worktree_files)`
as a FUNCTIONS-section function that does all the report assembly (calling 7 further sub-helpers,
one per report section — header, no-files-found, files-found, typical-set table, cold/warm
summary, extrapolation, stress test), leaving `run_probe_workflow` as exactly 3 lines: find files,
build report, write report. This is now a genuinely pure orchestrator, not just a shorter one.

**Lesson for the next split where the hit list names the `_workflow`/orchestrator function
itself:** check whether the violation is "this orchestrator got too long" (extract a `_build_x`
function that absorbs ALL the inline logic, leaving the orchestrator as pure sequential calls) as
opposed to the usual case (a non-orchestrator helper function got too long, extract sub-helpers
from IT specifically). The fix shape differs: here the entire body moved out under one new
function name, not several peer extractions each replacing a chunk of the original body in place.

## Hazard classification

`attach_worker_stats_cost_probe.py` is READ-ONLY. Verified by reading both this file and the
`attach_worker_stats`/`find_worker_jsonl` functions it calls in `src/workers/worker_tmux.py` in
full: `find_worker_jsonl` normally shells out to `tmux display-message` against a real session,
but this probe MONKEYPATCHES it (`mod_worker_tmux.find_worker_jsonl = lambda session:
path_by_session.get(session)`) before ever calling `attach_worker_stats`, so the real tmux call
never fires for this probe's synthetic `sess-N` worker dicts. `attach_worker_stats` itself only
calls `find_worker_jsonl` (patched away) and `parse_worker_stats_delta` (pure file read, no
subprocess). The probe's only side effect is writing its own timestamped report under `md/`. No
desktop/window/Space/hotkey/monitor interaction anywhere in the call path. Safe to run — did run
it directly against real production data (`~/.claude/projects/*--claude-worktrees-*/`) multiple
times this session, each time deleting the generated report before commit.

## Behaviour-unchanged proof

Two layers, both passed:

1. **Real-data run, before and after**, structural comparison (exact wall-clock timing numbers
   are inherently non-reproducible between two separate real runs — this is a live cost
   measurement tool, not a pure function — so the meaningful invariant is which files got
   selected and in what shape the report renders, not the literal millisecond values). Ran the
   untouched pre-split script for real: `Found 223 ... Typical 5-worker set: 8.48 MB total ...
   COLD over the single largest file (196.1 MB)`. Ran the fully-split script for real
   afterward: identical file count (223), identical typical-set total (8.48 MB), identical
   largest-file size (196.1 MB) — the file-selection logic (`_find_worktree_jsonls`,
   `_select_typical_set`) is untouched in substance (only lifted into named functions), so this
   match was expected and confirms no selection-logic regression. Deleted both generated reports
   from the tracked `md/` dir before commit (git status confirmed clean both times).
2. **Frozen-fixture run, before and after, full text diff with only the timing-derived numbers
   masked.** Since exact wall-clock numbers can never match between two runs even with identical
   inputs, and a purely qualitative real-data comparison (above) doesn't exercise every code path
   deterministically (e.g. the >POLL_INTERVAL warning branches never fire against real data,
   since real per-tick costs are all sub-second) — built a frozen fixture: copied the 6 smallest
   real worker-worktree JSONL files on disk into `/tmp/wps_verify/fixture_projects/fakeproj--
   claude-worktrees-fixture/` (preserving real bytes, so `parse_worker_stats_delta` still parses
   genuine JSONL content, not synthetic placeholder text). Loaded the pre-split backup via
   `importlib.util.spec_from_file_location`, monkeypatched `PROJECTS_DIR` on both the pre-split
   and post-split module objects to point at the frozen fixture, ran `run_probe_workflow()` with
   stdout captured via `contextlib.redirect_stdout`, then read+deleted the generated report.
   Masked all timing-derived numbers (`\d+\.\d+ ms`, `\d+x` speedup, percentages, the `Run:`
   timestamp, the `Report written to:` absolute path) via regex before diffing — the masked
   stdout and masked report text were BYTE-IDENTICAL between pre- and post-split (`diff` exit 0
   both times).

**Verification-harness bug caught mid-session, worth flagging:** the first frozen-fixture attempt
computed the report's output directory as a hardcoded worktree path for BOTH the pre-split and
post-split loaded modules. `_write_report` actually uses `Path(__file__).resolve().parent / 'md'`
— since the pre-split module is loaded from `/tmp/wps_verify/probe_pre_split.py` via
`spec_from_file_location`, ITS `__file__` resolves to `/tmp/wps_verify/`, not the worktree. The
hardcoded-path harness silently picked up a STALE, unrelated report file left over in the
worktree's real `md/` dir from an earlier verification step, deleted it (matching the harness's
own "read then unlink" cleanup step), and reported a false mismatch (223 real files vs. 6 fixture
files) that had nothing to do with the actual code split. Fixed by computing the report directory
the same way the module itself does: `Path(mod.__file__).resolve().parent / "md"`. No production
file was lost — the deleted file was itself a `md/attach_worker_stats_cost_probe_<today>.md`
verification artifact from earlier in this exact session, already correctly scheduled for
deletion before commit, just deleted a few steps earlier than planned. Confirmed via `git status`
and `git log` that both PRE-EXISTING tracked reports (`*_20260915_213048.md`,
`*_20260915_213651.md`) were untouched throughout. **Lesson: when a verification harness loads a
`/tmp/`-backup copy of a script via `spec_from_file_location`, any output path the script computes
from ITS OWN `__file__` must be re-derived per-module in the harness, never assumed to be the
worktree path — this is the same class of mistake as the `MAIN_PROJECT`-resolves-to-`/tmp` bug
hit in the `tool_use_errors` session earlier this batch, but on the WRITE side instead of the
import side.**

Verification artifacts (`/tmp/wps_verify/`, including the frozen fixture and both real-data
verification reports) were deleted or left outside the worktree, never staged.

## Files NOT touched

`dev/worker_pane_split/md/*.md` (the two pre-existing tracked reports) were left untouched —
confirmed via `git log`/`md5` before and after.
