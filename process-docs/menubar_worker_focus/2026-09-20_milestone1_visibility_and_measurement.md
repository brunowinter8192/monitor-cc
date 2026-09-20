# Stale worker-focus id — Milestone 1 (visibility + single-tty reprobe cost)

## Problem this addresses

Clicking a worker row in the menubar panel resolves a Ghostty terminal UUID from
`ghostty.py:_ghostty_tty_to_id[tty]` and asks Ghostty to focus it. That map is populated once
per tty by `_refresh_ghostty_tty_to_id`'s OSC2-marker probe and never re-probed for a tty that
stays continuously present — only a tty that disappears entirely from Ghostty's child-tty list
gets dropped and re-added. Worker viewer windows close and reopen on every spawn/kill, and macOS
reuses tty numbers, so the SAME tty path (e.g. `ttys013`) commonly ends up attached to a NEW
Ghostty window while the map still holds the OLD window's UUID — permanently, until that tty
number happens to vanish from Ghostty's process tree entirely. `system.py:_focus_worker` sent
that stale id to Ghostty and logged `id=<term_id>` unconditionally, with no check of the
`osascript` result — a hard AppleScript failure (`-1728`, "can't get terminal id ...") was
recorded in `menubar.log` identically to a genuine success.

## Approach

**Visibility fix (`system.py`):** `_focus_worker`'s osascript call is factored out into
`_focus_terminal_by_id(term_id)`, which now inspects the real `subprocess.run` result instead of
discarding it — returns `('status=OK', ms)` on `returncode==0`, `('status=ERR rc=<n>
stderr=<text>', ms)` on a nonzero return, `('status=TIMEOUT', ms)` on `subprocess.TimeoutExpired`.
`_focus_worker` appends that outcome token to its existing `menubar.log` `[latency] focus_worker
...` line — same line shape as before (`session=... lookup_ms=... osascript_ms=... id=...`),
one token added at the end, so nothing that already parses that line breaks. Mirrors the INTENT
of `_focus_session`'s rc/MISS/TIMEOUT handling, not its literal shape (`_focus_session` has a
second, try/on-error AppleScript path for the no-id case with a `MISS:` sentinel baked into the
script; the worker path only ever sends a bare `focus terminal id "..."`, so there is no `MISS:`
text to parse — a nonzero `returncode` alone is the complete and correct failure signal for this
script shape, confirmed live below).

**Single-tty reprobe primitive (`ghostty.py`):** two new functions, `_query_single_terminal_id`
(scoped AppleScript, `id of (first terminal whose name is "<marker>")` wrapped in a
`try/on error -> ""`, one live terminal instead of iterating all of them) and
`_reprobe_single_tty(tty)` (writes ONE marker via the pre-existing `_write_markers([tty])`,
sleeps the same 120ms the batch refresh already uses, queries, clears via the pre-existing
`_clear_markers`, and updates `_ghostty_tty_to_id[tty]` in place on success). Reuses the existing
marker-write/clear helpers rather than duplicating them — only the query is genuinely new,
because the batch query (`_query_terminal_names`) fundamentally does more work (returns every
terminal's id+name pair) than a single-tty repair needs.

**Not done in this milestone, on purpose:** nothing calls `_reprobe_single_tty` yet. Wiring it
into `_focus_worker` as an automatic retry-on-failure, and deciding what happens if the retried
focus attempt also fails, is Milestone 2 — gated, per the task, on reporting this milestone's
measurement first.

## Milestone 1 measurement (live system, not an estimate)

Target tty: `ttys013` (`worker-rag-cli-builder`'s viewer), the same one the task's own evidence
used. Re-derived live rather than trusted from the prompt — confirmed `E052F8AB-5F84-40E1-
8B60-BB70E7932F81`, matching the prompt's stated value, still current at measurement time.

Five back-to-back live trials of the full `_reprobe_single_tty` sequence (marker write -> 120ms
sleep -> scoped osascript query -> marker clear) against this real tty, real Ghostty:

| trial | write_ms | query_ms | total_ms |
|---|---|---|---|
| 0 | 0.3 | 83.3 | 208.6 |
| 1 | 0.1 | 80.2 | 204.9 |
| 2 | 0.1 | 90.1 | 215.4 |
| 3 | 0.1 | 82.4 | 205.1 |
| 4 | 0.1 | 82.6 | 208.0 |

**~205-215ms per single-tty reprobe**, all five trials returning the correct, real, live UUID.
Breakdown: marker write is negligible (~0.1-0.3ms), the fixed 120ms sleep dominates the floor,
the scoped osascript round trip itself is ~80-90ms.

**Comparison point, same live system, immediately after:** the EXISTING batch query
(`_query_terminal_names`, iterates every Ghostty terminal) over the 11 terminals live on this
machine at measurement time: 265.5ms / 275.1ms / 274.8ms for the osascript call alone (before
even adding its own 120ms sleep) — confirms a scoped single-tty query is not just simpler but
measurably cheaper than reusing the batch path for a one-tty repair, and that reusing the batch
refresh for this purpose would cost noticeably more per repair than the ~205ms figure above.

## Visibility fix verified live (real osascript, real ttys, not mocked)

`_focus_terminal_by_id` called directly against the real, currently-correct id for `ttys013`:

```
outcome: status=OK ms: 78.8
```

Same function against a deliberately dead uuid (`00000000-...`):

```
outcome: status=ERR rc=1 stderr=25:86: execution error: „Ghostty" hat einen Fehler erhalten:
„terminal id "00000000-0000-0000-0000-000000000000"" kann nicht gelesen werden. (-1728)
```

Same `-1728` error class the task's own manual reproduction hit against the real stale id. Then
the full `_focus_worker` path, end to end, against the live process table:

1. Poisoned `_ghostty_tty_to_id['ttys013']` with the same dead uuid (reproducing the exact
   reported bug shape — a stale id sitting in the map for a tty that never disappeared) and
   called `_focus_worker('worker-rag-cli-builder')`. New `menubar.log` line:
   `focus_worker session=worker-rag-cli-builder lookup_ms=74.5 osascript_ms=84.8
   id=00000000-0000-0000-0000-000000000000 status=ERR rc=1 stderr=...(-1728)`.
2. Attempted to "fix" it the way the existing refresh mechanism would — called
   `_refresh_ghostty_tty_to_id` again. The poisoned entry was NOT corrected: `ttys013` never
   disappeared from Ghostty's child-tty list during the test, so the refresh's own
   `if tty not in all_ttys: del ...` / `new_ttys = [t for t in all_ttys if t not in
   _ghostty_tty_to_id]` logic never re-probes it. This is a second, independent live
   confirmation of the root cause described in the task (a continuously-present tty keeps its
   first id forever) — observed by deliberately trying the existing repair path and watching it
   fail to repair anything, not just read from the code.
3. Manually restored the correct id and called `_focus_worker` again. New `menubar.log` line:
   `focus_worker session=worker-rag-cli-builder lookup_ms=95.4 osascript_ms=95.1
   id=E052F8AB-5F84-40E1-8B60-BB70E7932F81 status=OK`.

OK and ERR are now unambiguously distinguishable in `menubar.log` by the trailing `status=`
token, with the full AppleScript error text preserved on failure.

## Verification method note

Per the task's own constraint ("You cannot click the panel yourself... verify by hand, with real
osascript calls, on real ttys"), every check above used real `osascript` invocations against the
live, running Ghostty application and real tty numbers from the live process table — no mocked
subprocess, no synthetic AppleScript responses. `py_compile` and a full `src.menubar` package
import (via the project venv — `objc`/`rumps` unavailable under plain `python3`) verified clean
after every edit. `DOCS.md` LOC figures (`system.py` 205, `ghostty.py` 178) cross-checked against
real `wc -l`.

## Production-bundle reminder (does not apply to this verification)

Per `process-docs/bg_task_orphans/2026-09-20_production_verification_py2app.md`: the installed
menubar runs a frozen py2app bundle, not the source tree — a merge alone changes nothing there.
All verification in this milestone was done by importing the worktree's `src.menubar` modules
directly in a real Python process against the real live system (ttys, Ghostty, osascript), which
is unaffected by the bundle-staleness issue — it exercises the actual code under test, just not
through the installed launchd service. The bundle rebuild step only matters once this reaches
Milestone 2 and needs to be confirmed live in the actual running panel.

## What a future agent extending this into Milestone 2 needs to know

- `_reprobe_single_tty(tty)` already updates `_ghostty_tty_to_id[tty]` in place on success and
  returns the fresh id (or `None` on any failure) — it's a drop-in call, no new plumbing needed
  to get from "focus failed" to "have a fresh id to retry with."
- `_focus_terminal_by_id(term_id)` already returns `('status=OK'|..., osascript_ms)` — the second
  attempt after a successful reprobe can call this exact same function again; no new osascript
  string needs writing.
- The user's hard requirement: the re-probe may ONLY run when the first attempt actually failed
  (`status` starts with `ERR` or is `TIMEOUT`) — never as a pre-check, never on the healthy path.
  The ~205-215ms measured cost above is the number to weigh against whatever "what if the second
  attempt also fails" decision gets made.
- Do not add a second route via working directory — the task is explicit that the user considers
  it unnecessary once the map itself is correct.
- Do not reintroduce app-level `activate` in any new AppleScript — see
  `process-docs/ghostty_foreground/cmd_n_ghostty_foreground.md`, read again before writing the
  retry's focus script if it's not a literal reuse of `_focus_terminal_by_id`.

## Update 2026-09-20 (same session) — sleep-removal measurement + Milestone 2 (self-heal)

### Measurement: is the fixed 120ms sleep in the single-tty reprobe actually needed?

Reviewer's hypothesis: the scoped query itself (measured at 80-90ms in Milestone 1) might already
give Ghostty enough time to have processed the OSC2 write, making the fixed 120ms sleep pure
waste for this specific call shape (one marker, one immediately-following query — NOT the batch
refresh's shape of writing several markers before one shared query, which was not re-measured or
touched).

**Test shape, exactly as specified:** write the marker, query immediately with no sleep; if the
marker isn't found yet, query once more (also immediately, no added sleep between the two
queries — the first query's own ~80ms round trip is the only gap between them).

**60 live trials total, two independent batches of 30, rotated across 7 real ttys** (both main
and worker viewers, so the result isn't an artifact of one specific window):

| batch | first-query success | final success (after ≤1 retry) | double-miss | avg total cost |
|---|---|---|---|---|
| 1 | 26/30 (87%) | 30/30 | 0 | 93.1ms |
| 2 | 27/30 (90%) | 30/30 | 0 | 90.9ms |

Every miss across all 60 trials was recovered by exactly one immediate retry — zero double-misses
observed. Average total cost ~91-93ms, against ~205-215ms for the sleep-based shape measured in
Milestone 1 — roughly the "cut it roughly in half" the reviewer predicted, confirmed by
measurement rather than assumed.

**Decision: the fixed sleep is not needed for this call shape, removed.**
`_reprobe_single_tty` now queries immediately after the marker write, retries once immediately on
a miss, and gives up (returns `None`) only if both queries miss — a double-miss was never
observed in 60 trials, so no third attempt was built for a case with zero measured evidence of
occurring; if `menubar.log` ever shows a `focus_worker_reprobe ... result=miss` line, that is the
double-miss case and the place to revisit this decision with fresh data.

### Milestone 2 — self-healing retry

**Trigger condition, exactly as specified — only a real Ghostty-reported failure, never a
pre-check:** `_focus_worker` runs its first `_focus_terminal_by_id` attempt exactly as before
(now logged with a trailing `attempt=1` token). Only if that outcome is not the literal string
`'status=OK'` (i.e. `status=ERR ...` or `status=TIMEOUT` — both cases where Ghostty, or the
`osascript` call to it, actually reported a failure) does `_retry_focus_worker_after_reprobe` run.
No validation pass, no pre-flight check, nothing added to the success path — a click that
resolves on the first attempt executes the identical sequence of calls it did before this
change, confirmed by direct measurement below.

**What happens on the retry (`_retry_focus_worker_after_reprobe`):** calls the now-sleep-free
`_reprobe_single_tty(tty)` (imported from `ghostty.py`), timed and logged as its own
`focus_worker_reprobe session=... tty=... reprobe_ms=... result=<id>|miss` line regardless of
outcome. If a fresh id came back, one more `_focus_terminal_by_id(fresh_id)` call runs — the
exact same function the first attempt used, no new AppleScript written — logged as a second
`focus_worker ... attempt=2` line.

**What happens if the second attempt also fails, and why (the reviewer's "your call"):** nothing
further — no third attempt, no fallback route. Logged exactly like any other failed attempt
(`status=ERR .../status=TIMEOUT ... attempt=2`), then `_focus_worker` returns. Reasoning: the
reprobe already queried Ghostty for the CURRENT truth about that tty; if focusing that
current-truth id still fails, the failure is not a stale-map problem anymore (the map is now
correct) — it's something else (window genuinely gone, Ghostty in a bad state, a real AppleScript
error unrelated to id staleness), and no additional retry has new information to act on. A bounded
single retry also keeps the added cost predictable and matches the one failure mode actually
observed and diagnosed (one stale entry, fixed by one fresh reprobe). The task is explicit that a
second route via working directory is not wanted once the map itself is correct, and this design
doesn't need one — the map IS corrected by the reprobe regardless of whether the immediately
following retry happens to succeed.

### Live verification — real stale entry, real focus path, real self-heal

Reproduced the exact bug shape again: poisoned `_ghostty_tty_to_id['ttys013']` with a dead uuid
(the tty stays live in Ghostty's child list throughout, matching the real incident), then called
the real `system._focus_worker('worker-rag-cli-builder')` — the same function a panel click
invokes. Three new `menubar.log` lines, in order, one call:

```
focus_worker session=worker-rag-cli-builder lookup_ms=61.0 osascript_ms=81.7
  id=00000000-0000-0000-0000-000000000000 status=ERR rc=1 stderr=...(-1728) attempt=1
focus_worker_reprobe session=worker-rag-cli-builder tty=ttys013 reprobe_ms=147.7
  result=E052F8AB-5F84-40E1-8B60-BB70E7932F81
focus_worker session=worker-rag-cli-builder osascript_ms=77.1
  id=E052F8AB-5F84-40E1-8B60-BB70E7932F81 status=OK attempt=2
```

First attempt fails with the real `-1728` error against the poisoned id, the reprobe runs and
finds the real current id, the second attempt succeeds against the real window. Confirmed
`_ghostty_tty_to_id['ttys013']` held the corrected id afterward — a SUBSEQUENT click would now
succeed on the first attempt with no reprobe at all, i.e. the map is durably repaired, not just
patched for one call.

**Healthy-path cost check (the hard requirement):** with the map left in its now-correct state,
called `_focus_worker('worker-rag-cli-builder')` three more times. All three logged a single
`focus_worker ... status=OK attempt=1` line each, no `focus_worker_reprobe` line at all, total
wall time 136-156ms per call — the same lookup_ms (~60-73ms) + osascript_ms (~74-83ms) ranges
measured for a successful call in Milestone 1, before any of this session's changes existed.
Confirms the reprobe path adds literally zero calls, not just "low cost," on a click that
succeeds today.

### Production rebuild

Per `process-docs/bg_task_orphans/2026-09-20_production_verification_py2app.md`: merged
`bgorphan` into `integration` in the main checkout (`/Users/brunowinter2000/Documents/ai/
monitor-cc`, not the worktree — the build reads from there), then ran `./venv/bin/python
setup_py2app.py py2app` from that root using the project venv. See the git/process log for the
exact build output and post-restart PID/status confirmation captured alongside this entry.

### Files changed this update

`src/menubar/ghostty.py` (178 -> 182 LOC): `_reprobe_single_tty` rewritten to drop the fixed
sleep in favor of immediate-query-then-one-retry; new `_extract_term_id` helper.
`src/menubar/system.py` (205 -> 223 LOC): `_focus_worker` now tags its log line `attempt=1` and
triggers `_retry_focus_worker_after_reprobe` on any non-OK outcome; new
`_retry_focus_worker_after_reprobe`. `src/menubar/DOCS.md` updated to match (LOC, Purpose, Reads,
Writes, Called-by, plus two new Gotchas — the sleep-removal measurement scope and the
reprobe-only-on-real-failure trigger).
