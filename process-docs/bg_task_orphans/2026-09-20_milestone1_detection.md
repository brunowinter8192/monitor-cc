# Orphaned bg-task handle holders — Milestone 1 (detection only)

## Problem this addresses

`worker-cli wait` (iterative-dev plugin, `bin/worker-cli`, `_wait_has_live_bg_task`) treats a
project as "busy" whenever ANY process holds an open handle on a `*.output` file under that
session's `tasks/` directory — handle-based, not PID-tree-based, on purpose (replaced a
grandchild-count check in 2026-08 that produced a live false positive from a persistent LSP
child; see `bin/worker-cli`'s own inline comment history). The mechanism is correct for its
job. The failure mode this milestone targets is orthogonal: a background process CAN outlive
its own launching shell (shell exits, launchd adopts the orphaned child at pid 1) while still
holding that file handle open forever. `wait` then reports `bg=yes` for that project
permanently — every future `wait` for the same project blocks to the 3300s ceiling, regardless
of whether the actual triggering worker is long gone.

Live incident (2026-09-20, project `rag-cli`): 7 consecutive `wait` invocations never exited on
their own, all ending on `bg=yes` for worker `pusher`. Root cause identified via `lsof`: pid
79018, a `Python` process holding a `.output` file open, parent pid 1 (launchd), state `S`,
running over an hour. Its launching shell was long gone.

## Discriminator (given, verified live before implementation)

Walk the parent chain of the handle-holding pid upward. If it reaches a live Claude process
within a bounded number of hops, the handle holder is a genuine in-flight background task
(shell -> ... -> claude). If it reaches launchd (pid 1) without finding a Claude process
anywhere in the chain, it is orphaned.

Two concrete cases observed live and used to validate the classifier, unchanged from the task
prompt:

- **Genuine** — pid 58209 (a `/bin/zsh -c source ...snapshot-zsh...`), parent pid 59391, which
  IS the `claude` binary itself (`.../claude/versions/2.1.258 --model claude-opus-5`). One hop
  from holder to parent lands on a live Claude process.
- **Orphan** — pid 79018 (`.../Python.framework/.../Python -`), parent pid 1 (launchd). Zero
  hops find anything Claude-shaped; the parent IS launchd.

## Where the code lives and why

`src/menubar/proc_cache.py` already ran a global `lsof +D /tmp/claude-<uid> -Fn` every 10s
(`_refresh_bg_task_cache`) and kept only the file paths (feeding `_has_active_bg`, the menubar's
own has-bg badge — a DIFFERENT concern from `worker-cli`'s own separate probe, they just happen
to check the same directory shape independently, confirmed by reading `_wait_has_live_bg_task`'s
own comment: "Mirrors monitor-cc's ... NOT reimported"). Same call, `-Fpn` instead of `-Fn`,
also returns the holding pid — one extra field, no extra process spawned. `_cc_proc_cache`
(same file) already holds the live-Claude-process set the classifier needs to test membership
against. Both pieces of data were already being collected in the same permanently-running
launchd agent (`com.brunowinter.monitor-cc-menubar`) for an unrelated purpose — this milestone
is purely correlating two caches that already exist, not adding new process-scanning infra.

New module: `src/menubar/bg_task_orphans.py`. Not folded into `proc_cache.py` itself — that file
is a pure cache/probe layer (no classification logic anywhere in it), and not folded into
`bg_timer.py` either, despite the superficial resemblance to `_resolve_ancestor_cwd` there — see
"Why not reuse `_resolve_ancestor_cwd` directly" below. Wired into
`discovery_worker.py:_worker_loop`, called once per ~1.5s discovery cycle but self-throttled
internally to run its own `ps`/classification work at most once per 10s
(`_ORPHAN_SCAN_INTERVAL`), independent of `proc_cache.py`'s own 10s cache-refresh cadence — two
separate throttles that happen to share a value, not a shared constant (each module owns its own
cadence policy).

## Why not reuse `_resolve_ancestor_cwd` (`bg_timer.py`) directly

Studied in full before writing anything new. It walks up to 5 hops checking `_cc_proc_cache`
membership before advancing — exactly the shape this milestone needs — but it is architecturally
unsuitable to import and reuse as-is: its return value collapses "found a live Claude ancestor"
and "ran out of chain to walk" into the SAME output (`''`, empty cwd string), because for its own
purpose (best-effort project attribution for a display badge) that conflation is harmless — an
unattributable bg timer just gets bucketed under `'unknown'`, cosmetic only. This milestone's
classification feeds a kill decision in Milestone 2 — the three outcomes ("found Claude" /
"reached pid 1, confirmed no Claude anywhere" / "chain unresolvable, can't tell") MUST stay
distinguishable, because only the middle one may ever become a kill target and the third one
must never be mistaken for the second. `bg_task_orphans.py:_classify_bg_task_holder` reuses the
IDEA (bounded 5-hop walk, cache-membership check before advancing, one `ps -A -o pid=,ppid=`
scan reused across all holders in a batch rather than one `ps` call per holder) but is its own
function with a genuine 3-way return (`'live'` / `'orphan'` / `'unknown'`), plus an explicit
terminal check for pid `'1'` (launchd) that `_resolve_ancestor_cwd` has no equivalent of — that
module never needed to distinguish "definitely reached the top of the tree" from "lookup
failed," this one does.

## Failure-direction decisions (every one of them defaults to "leave it alone")

- **`ps -A -o pid=,ppid=` itself fails or throws** (`_build_ppid_map`): returns `{}`. Every
  holder pid then fails the very first `ppid_map.get(ancestor_pid)` lookup inside the classifier
  loop -> `'unknown'` for everything in that scan cycle. No holder is ever flagged on a probe
  failure; the next scan cycle (10s later) gets a fresh chance.
- **A pid disappears mid-walk** (holder pid, or any ancestor, no longer in the `ps` snapshot):
  `ppid_map.get(...)` returns `None` for that hop -> `'unknown'` immediately, walk stops there.
  This is indistinguishable in the data from "the process legitimately just exited between the
  `lsof` scan and the `ps` scan" — both cases resolve to "we don't actually know," and both are
  therefore left alone, never flagged. A process that exited on its own between scans also isn't
  holding anything anymore by the next `lsof` refresh, so it silently drops out of
  `_bg_task_holder_pids` regardless of what this classifier decided about it.
- **Chain exceeds 5 hops without resolving either way**: `'unknown'`, not `'orphan'`. The 5-hop
  cap is reused from `_resolve_ancestor_cwd`'s own precedent (documented there as covering
  "intermediate shells"); nothing observed live so far needed more than 1 hop for the genuine
  case, so 5 is untested headroom, kept for parity with the existing precedent rather than newly
  invented.
- **`lsof` itself fails** (`proc_cache.py:_refresh_bg_task_cache`, unchanged behavior from before
  this milestone): the whole refresh is skipped for that cycle, previous cache contents persist
  until the next successful refresh. Pre-existing behavior, not modified here.

Net effect: the only path to a `'orphan'` classification is a FULLY resolved chain that
terminates at pid 1 with no Claude process anywhere along the way. Every other outcome —
probe error, disappeared pid, unresolved chain — is `'unknown'` and never surfaces as an orphan.

## Cross-module state-sharing pitfall hit (and avoided) while implementing this

`proc_cache.py`'s `_bg_task_open_paths` (pre-existing) and the new `_bg_task_holder_pids` are
REASSIGNED to a brand new object on every `_refresh_bg_task_cache` call (`_bg_task_open_paths =
{...}` / `open_paths, holder_pids = _parse_bg_task_lsof(...)`), unlike `_cc_proc_cache`, which is
mutated in place (`.update()` / `del`) and therefore stays the same object forever. `bg_timer.py`
gets away with `from .proc_cache import _cc_proc_cache` directly BECAUSE of that in-place-mutation
property — the imported name still points at the live object. Doing the equivalent `from
.proc_cache import _bg_task_holder_pids` in the new module would have bound to whatever dict
existed at import time and never seen a single subsequent refresh — a silent, permanent
staleness bug that would never surface as an exception, just as "detection stops finding
anything new after the first process start." Caught before it shipped by reasoning through the
reassignment-vs-mutation distinction, not by observing the bug live. Fixed by adding
`bg_task_holder_pids_snapshot()` (mirrors the existing `cc_proc_cache_snapshot()` pattern
already used for cross-thread reads of `_cc_proc_cache`) and reading through that function on
every scan instead of importing the dict by name. Flagged in `DOCS.md`'s Gotchas so a future
module doesn't reach for the direct import out of habit.

## De-duplication of the log line

`menubar.log` would otherwise get a `[bg_orphan]` line every ~10s for as long as an orphan
process sits there (potentially hours, per the observed pid 79018 case). `_logged_orphan_pids`
(module-level set, rebuilt every scan) logs a given pid exactly once while it continuously
classifies as orphan; the line reappears only if the pid drops out of the orphan set (handle
closed, or process exited) and later reappears as an orphan again — no separate "still orphaned"
heartbeat line exists in this milestone.

## Live verification (real system, real orphan, not a fixture)

Ran the classifier against the actual running machine (2026-09-20, ~20:04 local), pid 79018
still alive at the time exactly as described in the task prompt. `_cc_proc_cache` held 7 live
Claude pids (main sessions + worker orchestrators across 4 different projects: websearch,
monitor-cc, rag-cli, and this task's own `bgorphan` worktree). `_bg_task_holder_pids` held 6
occupied task files with 15 total holder pids across those same 4 projects. Classified all 15:
14 resolved to `'live'` (every one of them a genuine in-flight worker/orchestrator background
task, one hop from a real Claude ancestor — this is incidental corroborating evidence, not
something staged for the test) and exactly 1 resolved to `'orphan'` — pid 79018, the one named
in the task prompt, ancestry `79018 -> 1` confirmed via a live `ps -A -o pid=,ppid=` scan
(`ppid_map['79018'] == '1'`).

Ran `scan_bg_task_orphans` end-to-end three times in sequence: first call wrote exactly one
`[bg_orphan]` line to the real `menubar.log`
(`~/Library/Application Support/com.brunowinter.monitor-cc-menubar/menubar.log`); a second call
one second later was a no-op (10s throttle); a third call issued 11s after the first (past the
throttle) produced zero additional log growth (dedup — pid 79018 was already in
`_logged_orphan_pids` from the first call and was still classified `'orphan'`, so it was not
re-logged). Confirmed `ps -p 79018` alive and unchanged before and after every run in this
session — nothing in this milestone ever calls `os.kill` or any process-terminating syscall,
matching the "detection only, no kill" scope exactly.

Full `src.menubar` package import (`app`, `bg_timer`, `focus_controller`, `proc_cache`,
`discover`, `discovery_worker`, `bg_task_orphans`) verified clean via the project's real venv
(`./venv/bin/python3` — plain `python3` lacks `objc`/`rumps`, fails immediately on `import
objc` inside `app.py`; use the venv interpreter for any future check of this package).
`py_compile` clean on all three touched/added files. `DOCS.md` LOC figures
(`proc_cache.py` 184, `bg_task_orphans.py` 74, `discovery_worker.py` 63) cross-checked against
real `wc -l` after every edit, not estimated.

## Explicitly NOT done this session (Milestone 2, pending go-ahead)

No kill anywhere in this code path. `_classify_bg_task_holder` returning `'orphan'` currently
only feeds a log line, nothing else. Milestone 2 (kill + traceable log line with pid and file) is
scoped in the task prompt as a separate, explicitly gated follow-up — not started.

## What a future agent extending this into Milestone 2 needs to know

- The exact (pid, path) pairs currently classified as orphan are available from
  `_find_orphans(_collect_holder_pairs(), _build_ppid_map())` — this already IS the kill
  candidate list, no new data plumbing needed.
- Mirror `bg_timer.py:_abort_bg_sleep_timers`'s existing pattern for the kill+log shape (resolve
  the file BEFORE the kill — the open handle and `lsof`'s ability to see it disappear the instant
  the process exits, per that module's own documented lesson from the 2026-08-18 abort-stamp
  incident) rather than inventing a new one; this module already resolves the file first as a
  side effect of classification, so the ordering concern is already satisfied for free.
- Do not touch `worker-cli wait` itself, and do not add any mechanism that could kill a
  `worker-cli wait` process — the August auto-abort removal (`process-docs/timer-loop/`) was
  explicit that a push-mechanism fighting the pull-based `wait` design is actively wrong; this
  orphan-killer is a different mechanism (kills the actual leaked handle holder, never the wait
  process itself) but the constraint bears repeating because the two mechanisms sit in the same
  file area and a future reader could conflate them.
- The dedup set (`_logged_orphan_pids`) is detection-log dedup only, not a "don't kill twice"
  guard — Milestone 2 will need its own bookkeeping (or none, if the kill target simply vanishes
  from `_bg_task_holder_pids` the moment it's dead and there's nothing left to re-kill).

## Update 2026-09-20 (same session) — module-standards fix + Milestone 2 (kill)

### Orchestrator-standards fix (reviewer-flagged)

`scan_bg_task_orphans` sat under `# FUNCTIONS` and carried two pieces of actual logic: the
throttle comparison (`now - _last_scan_ts < _ORPHAN_SCAN_INTERVAL`) and the
`_logged_orphan_pids.clear()` branch for the no-holders case. Restructured: added a real
`# ORCHESTRATOR` section holding exactly `scan_bg_task_orphans`, which now only calls
`_scan_due(now)` / `_mark_scanned(now)` / `_collect_holder_pairs()` /
`_forget_all_logged_orphans()` / `_build_ppid_map()` / `_find_orphans(...)` /
`_log_new_orphans(...)` / `_kill_confirmed_orphans(...)` and branches on their return values —
no inline computation, no direct global mutation left in the orchestrator body. The throttle
comparison moved into `_scan_due`, the timestamp write into `_mark_scanned`, the empty-holders
cache-reset into `_forget_all_logged_orphans`. `# FUNCTIONS` below it lists every helper in call
order (stepdown rule).

### Milestone 2 — the kill, with the fresh-reconfirmation requirement

**The risk being closed:** `_bg_task_holder_pids` (the pid<-file map the orphan list is built
from) is refreshed at most every 10s (`proc_cache.py`'s own throttle). macOS pid numbers get
reused. A pid that held a task file 9 seconds ago and has since exited could, in principle, have
its number reassigned to an unrelated process before the kill fires — sending SIGTERM to a
completely different, innocent process.

**The fix — one function, called immediately before every kill, never before:**
`_pid_still_holds_file(pid, expected_path)` runs a scoped `lsof -p <pid> -Fn` (not the batch
`+D <tasks_dir>` scan the detection side uses) and checks whether that pid's CURRENT open-file
list still contains that exact path. Modeled on `bg_timer.py:_resolve_pid_output_file`'s
ordering lesson (resolve/confirm before the kill, not after — the open handle and lsof's ability
to see it vanish the instant the process exits) but deliberately NOT the same call shape:
`_resolve_pid_output_file` scopes to fd 1/2 only (`-d 1,2`) because it's resolving a wait/sleep
process's OWN stdout/stderr redirect target; this reconfirmation instead checks ANY fd the pid
holds the expected path on (no `-d` restriction), because the original detection scan
(`lsof +D <tasks_dir> -Fpn`) that produced the candidate never restricted by fd either — the
reconfirmation has to be checking the identical thing the detection already found, not a
narrower one. `_kill_confirmed_orphans` calls this once per candidate; `True` -> `_kill_orphan`
(`os.kill(pid, SIGTERM)`, logs `kill_action`, or `kill_failed` on an `OSError`/lookup failure);
`False` -> no kill, logs `kill_skipped ... reason=reconfirm_failed`, moves to the next candidate.
No retry inside the same cycle — a genuinely-still-orphaned pid that failed reconfirmation for a
transient reason (`lsof` hiccup) gets picked up again on the next 10s scan, same as any other
`unknown`-classified holder.

**Why SIGTERM, not SIGKILL:** matches the only existing precedent in this codebase for killing a
process by pid from the menubar (`bg_timer.py:_abort_bg_sleep_timers`), and the live target
(pid 79018, state `S`, interruptible sleep, not `D`) had no structural reason to need SIGKILL —
confirmed live, SIGTERM alone terminated it.

**`worker-cli wait` cannot ever be a kill target through this path, structurally, not just by
convention:** `_wait_has_live_bg_task`'s own `lsof +D <tasks_dir> -Fn` call is a short-lived probe
subprocess that reads the directory and exits; the `wait` bash loop itself never opens a
persistent handle on any `.output` file. A `worker-cli wait` process can therefore never appear
in `_bg_task_holder_pids` in the first place — there is nothing to special-case in the kill path,
the constraint is satisfied by the shape of the data, not by an added guard. No redundant
defensive check was added for this; it would test something structurally unreachable.

### Live verification — real kill, real target, real before/after

**Baseline (before any code executed):** extracted `_wait_has_live_bg_task` verbatim from
`bin/worker-cli` via `sed`, sourced it in an isolated `bash -c` subshell alongside its real
`tmux_spawn.sh` dependency, called it against the real `pusher`/`rag-cli` session — returned
`yes`, confirming the poisoned state described in the task was still live at the start of this
update.

**Fresh-reconfirmation function tested in isolation first, no kill yet:** `_pid_still_holds_file`
against (real pid 79018, real path) -> `True`; against (real pid 79018, a deliberately wrong
path) -> `False`; against (a nonexistent pid `1234567`, the real path) -> `False`. `ps -p 79018`
re-checked alive after all three calls — nothing killed by the reconfirmation probe itself, as
expected (it only reads).

**The kill, via the real orchestrator entry point** (`scan_bg_task_orphans(time.time())`, not a
lower-level function call — the actual code path `discovery_worker.py` runs):
- `ps -p 79018` immediately after: no such process (exit code 1).
- `lsof` on the exact file path immediately after: no output, exit code 1 — handle confirmed
  gone, not just the process.
- `menubar.log`: `orphan_detected pid=79018 file=...bu4jcwahu.output` followed immediately by
  `kill_action pid=79018 file=...bu4jcwahu.output` — both lines present, pid and file traceable
  in both.

**Post-kill re-check of the exact mechanism `worker-cli wait` relies on:** same extracted
`_wait_has_live_bg_task` call, same session, now returns `no`. The handle-based signal
`worker-cli wait` polls every 5s for this project has flipped from permanently-stuck-busy to
correctly-idle.

**What was NOT captured live, and why, stated plainly:** the task asked to confirm via
`wait_trace.log` that a real `worker-cli wait` for `rag-cli` reaches a `bg=no` line for `pusher`.
Armed a real `worker-cli wait /path/to/rag-cli --timeout 15` (and separately observed a second,
already-running `wait` for the same project, pid 41166 — a pre-existing concurrent arm, not one
I started) and watched `wait_trace.log` live. Both arms polled continuously for over 3 minutes
(20:10:30 through 20:13:27) and `builder` (the OTHER worker in this project) was `status=working`
on every single poll in that entire window — genuine live work, not something I controlled or
should have interfered with. `worker-cli`'s own per-worker loop (`bin/worker-cli`, the `wait`
case) breaks out on the FIRST worker found `working` and never reaches the next name in the list
— by design (`SAW_WORKING=1; ... break`), not a bug and not something this change touches. Since
`builder` sorts before `pusher` in `worker_list`'s output and stayed busy throughout, `pusher`'s
own bg-check line never got emitted to the trace during the observation window — the loop
legitimately never got that far. This is pre-existing `worker-cli` behavior, confirmed by reading
the case statement, not a gap introduced or left by this change. The direct
`_wait_has_live_bg_task` before/after (`yes` -> `no`, same verbatim function, same live session,
same file) is the faithful substitute proof available within the observation window — it is the
exact function `wait`'s `idle` branch calls, not a reimplementation, and it is what will produce
a `bg=no` trace line for `pusher` the moment a future poll reaches that name in the list (i.e.
the moment `builder` itself goes idle or dead). Flagging this honestly rather than claiming a
trace line that was not actually observed.

### Files changed this update

`src/menubar/bg_task_orphans.py` restructured (74 -> 115 LOC): real `# ORCHESTRATOR` section
added, kill path added (`_pid_still_holds_file`, `_kill_orphan`, `_kill_confirmed_orphans`).
`src/menubar/DOCS.md` updated to match (LOC, Purpose, Reads, Writes, Calls out).
