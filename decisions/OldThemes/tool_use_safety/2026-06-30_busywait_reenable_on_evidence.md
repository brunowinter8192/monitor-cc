# Re-enable block_busywait_loop on evidence (2026-06-30)

Triggers the revisit condition left explicit in `2026-06-24_background_foreground_simplification.md`:
"an agent could shell-background a work job and poll it unguarded … revisit with a targeted hook only
if fire-log shows it." Evidence now observed → block_busywait_loop re-enabled.

## Evidence (the accepted-residual materialised)

A worker (trading project, edge-drift probe) ran a long compute and polled it:
- Launched the compute via shell-`&` (`python p2_…py > /tmp/p2_run.log 2>&1 &`, PID 7692) — a DETACHED
  launch, invisible to CC, so `block_unauthorized_background` (flag-only) correctly did not catch it.
- Then polled with busy-wait loops, 3×:
  `until ! ps -p 7692 >/dev/null 2>&1; do sleep 10; done; tail -40 /tmp/p2_run.log`
  `until grep -q "Stage 2 gate" /tmp/p2_run.log || ! ps -p 7692; do sleep 8; done; tail -50 …`
- The "Do NOT check, poll" launch-ack injection did NOT deter it (instruction-only is insufficient).

The shell-`&` launch is unhookable (detached, no CC ack) — but the busy-wait LOOPS are ordinary Bash and
ARE hookable. block_busywait_loop catches the loops regardless of how the job was launched.

## What was re-enabled

`block_busywait_loop.py` (renamed from `.disabled`, added to `hook_setup.py` `_HOOK_SCRIPTS`, registered).
Unchanged logic — fires ONLY on the precise signature: a `while|until` loop whose body is exactly
`sleep N` AND whose condition is a status-check (`ps|pgrep|grep|tail|cat|test|ls|wc|…`). Universal (all
sessions); safe for the orchestrator because the sleep-timer (`sleep 600 && echo done`) is not a loop.

Smoke (manual, stdin payloads):
- busy-wait poll loop (`until ! ps -p …; do sleep …; done`) → BLOCK (exit 2, "stop polling, go idle").
- orchestrator sleep-timer (`sleep 600 && echo done`) → PASS (exit 0).
- legit retry loop (`until curl -sf …; do sleep 2; done`) → PASS (exit 0, body not sleep-only).

## Deferred — block_polling_loop + cwd worker-detection (RECOMMENDED, pending user)

For the OTHER polling manifestation: repeated SEPARATE status-check calls across turns (slow polling —
a few calls over ~10 min, each below any 30s-window threshold, still context-burning). NOT observed this
session (only busy-wait loops were), so not built — block-on-evidence principle.

Recommended design (user sign-off + smoke tests first):
- Discriminate by caller via `os.getcwd()` — `'.claude/worktrees/'` fragment = worker session
  (the same detector `block_cd_drift.py` already uses).
- Worker session → aggressive frequency block: threshold ~2, window ~600s, broadened target signature
  (`ps -p`, `tail <logfile>`, `cat <logfile>`, `worker-cli status`). Workers have NO legit reason to poll.
- Orchestrator (cwd not in a worktree) → exempt / lax: its ~10-min timer-loop status cadence is legit, so
  a wide window must NOT apply to it. cwd-scoping is what dissolves the "30s misses slow polling vs 10min
  false-positives the orchestrator" tension — the wide window applies ONLY where polling is never legit.
- cwd-scoping bounds the blast radius to worker sessions; cannot lock out the orchestrator.

Reverses more of the 2026-06-24 slim decision than the busy-wait re-enable → deserves the user's review.
