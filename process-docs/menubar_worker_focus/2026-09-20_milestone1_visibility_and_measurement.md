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
setup_py2app.py py2app` from that root using the project venv.

Build output ended with the same expected pattern the referenced entry documented (`bootstrap
retry in 1s (rc=5)... bootstrap com.brunowinter.monitor-cc-menubar: ok`), not a new failure
mode. Confirmed the service actually restarted, not just that the build command exited clean:

- pid before the build: `51048`; pid after: `94029` — different process, real restart, not a
  no-op bootstrap.
- `menubar.log` kept writing fresh `[latency]`/`[detection]` lines immediately after (real
  `bg_refresh`/`osc2_match`/`transition` activity, seconds-old at check time) — alive and doing
  real work, not just present in the process table.
- Grepped the INSTALLED bundle's own copy of the source (not the worktree, not the main
  checkout) directly: `Contents/Resources/lib/python3.14/src/menubar/system.py` contains
  `focus_worker_reprobe`/`_reprobe_single_tty` (4 matches); `ghostty.py` contains
  `_extract_term_id` (3 matches, the sleep-removal shape) while still carrying the batch
  refresh's own untouched `time.sleep(0.12)` at its original line — confirms the exact intended
  diff reached the bundle: the single-tty path lost its sleep, the batch path kept its own,
  deliberately un-remeasured, sleep.

## Update 2026-09-20 (same session) — app-level activate restored, combined with focus

### Problem this addresses

Two user-reported symptoms turned out to be one cause. Cmd+1..9 appeared not to react when
another app (e.g. Firefox) was in front. After switching to a Ghostty window the user had to
click into it before he could type. Root cause, measured by the reviewer against the live
Ghostty before this update (three osascript trials, frontmost checked before/after each): the
existing `focus terminal id "..."` command (used by both `_focus_session` and
`_focus_terminal_by_id`) never makes Ghostty the active app — `frontmost` stayed `false` before
AND after. Same for the window-level `activate window` command. Only app-level `activate` flips
`frontmost` to `true`, but alone it raises the LAST USED window, not the one just selected — so
it was never safe to use by itself.

### Why this was previously removed, and why that no longer applies

`process-docs/ghostty_foreground/cmd_n_ghostty_foreground.md` (2026-06) removed app-level
`activate` from `_focus_session` because it brought Ghostty forward on every desktop
unconditionally — a real, previously-confirmed regression. The user has now explicitly retracted
that constraint (his desktop layout is fixed; Ghostty coming forward on every desktop is fine)
and replaced it with a narrower one: a Ghostty window must never change ITS OWN desktop —
switching to a session on another desktop must move the user there, never drag the window over.
This task does not, and structurally cannot, verify that narrower constraint — see the
Verification section below for exactly what was and wasn't checked, and why.

### Approach

**Order:** `focus terminal id "..."` (or the cwd route's `focus (first terminal whose working
directory is "...")`) FIRST, `activate` SECOND, inside the same `tell application "Ghostty" ...
end tell` block. Matches the reviewer's own reasoning: select the target before asking the app
to come forward, so activation shows the just-selected window rather than whatever was last
used.

**One osascript invocation, not two:** both commands live in the same script string passed to
the same single `subprocess.run(['osascript', '-e', script], ...)` call that already existed —
no new subprocess, no added round trip. A second `osascript` call would have cost roughly 70ms
per focus (consistent with this session's own measured single-osascript-round-trip costs,
~75-105ms observed throughout this work) and the user was explicit that a noticeable slowdown is
unacceptable.

**Three call sites, one shared change pattern:**
- `_focus_session`'s id route: `activate` added as a second line inside the `tell` block, after
  `focus terminal id`.
- `_focus_session`'s working-directory fallback route (the `try`/`on error` block with the
  `MATCH`/`MISS:` sentinel): `activate` added INSIDE the `try`, between the `focus (first
  terminal whose ...)` call and `return "MATCH"` — reached only on a real match, never on the
  `on error` branch. The `MATCH`/`MISS:` return-value parsing in the Python side
  (`out.startswith('MISS:')`) was not touched at all; it still parses the exact same two
  sentinel shapes.
- `_focus_terminal_by_id` (the function `_focus_worker`'s first attempt AND the self-healing
  retry's second attempt both call — one code change covers both automatically): `activate`
  added after `focus terminal id`. No try/on-error wrapper exists here; if `focus terminal id`
  itself throws (the stale-id case this session's earlier work targeted), the unhandled
  AppleScript error halts the `tell` block before `activate` is ever reached — the same
  reach-activate-only-on-success guarantee as the cwd route, achieved for free by AppleScript's
  own error-propagation behavior, not by an explicit added check.

### A live-testing detour that did not become part of the implementation, recorded so it isn't repeated

Before settling on the above, tried to verify not just `frontmost` but WHICH specific window
came forward, using Ghostty's `front window` property and `focused terminal of (selected tab of
front window)`. Results were inconsistent between successive queries against the real, live,
actively-used machine (the same terminal kept appearing as "front" regardless of which target
was focused moments earlier, and calling `activate` mid-session visibly changed the REAL current
user's frontmost app during testing). Concluded this line of testing was entangled with the
live desktop/Space state of an actively-used machine in ways an automated script cannot isolate
or interpret — not a defect in the implementation, but a real limit of remote/scripted
verification on a shared live desktop. Deliberately stopped pursuing it rather than keep
disturbing the real screen. This is exactly the class of check the task itself named as the
user's job (whether windows stay on their own desktop), so no code decision was based on these
inconclusive readings — the implementation follows the reviewer's own specified order (focus,
then activate) and the change was verified the way the task actually asked for: `frontmost`
before/after.

### Verification — real osascript, real live Ghostty, all three paths and both `_focus_session` routes

Baseline before each check: `osascript -e 'tell application "Finder" to activate'` (deterministic
way to guarantee Ghostty starts backgrounded, confirmed via `frontmost` reading `false`).

1. **`_focus_session`, id route** (real cwd, real populated tty map):
   `frontmost` false -> true. `/tmp/monitor-cc-menubar_focus.log`:
   `OK id=A5F576B2-... lookup_ms=0.0 osascript_ms=102.9`.
2. **`_focus_session`, working-directory MATCH route** (deliberately ran in a fresh process with
   an EMPTY tty map, so `get_ghostty_terminal_id` returns `None` and the fallback is forced):
   `frontmost` false -> true. Log: `OK cwd=/Users/.../monitor-cc lookup_ms=0.0
   osascript_ms=101.0` — `MATCH` parsed correctly as `OK`, same as before this change.
3. **`_focus_session`, working-directory MISS route** (a cwd with no matching live terminal):
   log: `MISS cwd=/tmp/definitely-not-a-real-ghostty-cwd-xyz123 reason=-1719:...Ungültiger
   Index....` — `MISS:` sentinel parsing still intact, unchanged shape, no crash, no false
   activation (nothing to check for frontmost here since nothing should have changed — and nothing
   did, by construction, since `activate` sits after the line that threw).
4. **`_focus_worker`, first-attempt success** (real worker session, real populated tty map):
   `frontmost` false -> true. `menubar.log`:
   `focus_worker session=worker-rag-cli-builder ... status=OK attempt=1`.
5. **`_focus_worker`, self-healing second attempt** (reproduced the stale-id bug shape from this
   session's earlier work, forcing attempt 1 to fail and the reprobe-then-retry path to run):
   `frontmost` false -> true. `menubar.log`, one call, three lines in order:
   `status=ERR rc=1 ...(-1728) attempt=1` -> `focus_worker_reprobe ... result=E052F8AB-...` ->
   `status=OK attempt=2` — confirms the activation reaches the retry path too, since it's the
   same shared `_focus_terminal_by_id` function, not a separate implementation.

### What was not, and could not be, verified by me

Whether a Ghostty window ever changes its own macOS desktop/Space as a side effect of `activate`.
This requires watching the actual screen across an actual desktop switch, which is not available
to an automated agent — explicitly named as the user's own verification job in the task. **What
the user should watch for:** click a worker or session row whose window currently sits on a
DIFFERENT virtual desktop than the one he's viewing, and confirm two things — his own view
switches TO that desktop (expected, and new: this used to not happen since `activate` was
absent), and the WINDOW ITSELF stays exactly where it was (not moved to his current desktop).
The second one is the one hard requirement and the one this session's automated checks cannot
touch at all.

### Production rebuild

Same procedure as the earlier update in this file: merged `bgorphan` into `integration` in the
main checkout, ran `./venv/bin/python setup_py2app.py py2app`. See the commit log for the exact
before/after pid and bundle-content confirmation captured alongside this entry.

### Files changed this update

`src/menubar/system.py` (223 -> 226 LOC): `activate` added to all three focus AppleScripts,
`_focus_terminal_by_id`'s and `_focus_session`'s working-directory route's parsing untouched.
`src/menubar/DOCS.md` updated (LOC, Purpose, one new Gotcha explaining the historical reversal
and the narrower constraint that replaced it).

### Files changed this update

`src/menubar/ghostty.py` (178 -> 182 LOC): `_reprobe_single_tty` rewritten to drop the fixed
sleep in favor of immediate-query-then-one-retry; new `_extract_term_id` helper.
`src/menubar/system.py` (205 -> 223 LOC): `_focus_worker` now tags its log line `attempt=1` and
triggers `_retry_focus_worker_after_reprobe` on any non-OK outcome; new
`_retry_focus_worker_after_reprobe`. `src/menubar/DOCS.md` updated to match (LOC, Purpose, Reads,
Writes, Called-by, plus two new Gotchas — the sleep-removal measurement scope and the
reprobe-only-on-real-failure trigger).
