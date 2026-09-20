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
