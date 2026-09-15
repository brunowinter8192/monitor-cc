# Suspicion about `worker-cli wait` hanging, recorded before it was lost (2026-09-15)

Written by an orchestrator session in monitor-cc. The code discussed here does NOT live in this
repo — `worker-cli` is at `Meta/iterative-dev/bin/worker-cli`, and that repo carries its own
`process-docs/worker_wait/` area with five entries. This note exists because the observation was
made from here, the issue that prompted it was closed here, and nothing on disk would otherwise
carry it.

## Why the issue was closed

The monitor-cc issue "Waitloop" (closed 2026-09-15) asked that `worker-cli wait` terminate
reliably when a project's workers go idle, with no manual abort. It carried no reproduction case
and no trace. The user's instruction was to close it unless the symptom could be mapped onto an
obvious code fault.

Reading `bin/worker-cli`'s `wait` case end to end turned up no obvious fault. The loop is
carefully built: a trace log per poll, an explicit fail-toward-waiting contract where only a
verbatim `idle` counts as idle, a closed status vocabulary, and a bg-task probe that holds an idle
worker still coordinating a background child.

## The one place that would explain the symptom

A transition gate was added on 2026-09-02, after the newest entry in that repo's own
`worker_wait/` area (2026-08-19). Its shape, quoted from the source as read on 2026-09-15:

```
SAW_WORKING=0
...
    working)
        SAW_WORKING=1
```

and the exit paths for `workers idle` / `worker terminal` are gated on it. The comment states the
intent plainly: a level-triggered exit on a bare state, such as arming `wait` on an
already-idle worker or on zero workers, was waking the orchestrator for nothing, so only an actual
working-to-non-blocking edge may end the wait.

The consequence is the part that matches the reported symptom. If `wait` is armed at a moment when
the worker is ALREADY past its working phase, this invocation never observes a `working` poll, so
`SAW_WORKING` stays 0 and no exit path opens. The loop then runs to `--timeout`, whose default is
3300 seconds. From the orchestrator's chair that is indistinguishable from a hang, and the only
way out is a manual abort — which is exactly the wording the closed issue used.

This is a race between arming and the worker's own transition, not a logic error. The gate does
what its author intended; whether the price is worth it is a different question, and one nobody
has measured.

## What is NOT known

Whether this actually happened to the user. No trace was captured for any of the hangs that
prompted the issue. The trace log written by `wait` carries `event=exit reason=timeout
elapsed=... saw_working=...` on every timeout, so a real occurrence is directly checkable after
the fact: a timeout line with `saw_working=0` is this race, and a timeout line with
`saw_working=1` is something else entirely.

Nothing in the observed data says the gate's own trade-off was chosen wrongly. The 2026-09-02
comment names a real failure it fixed — spurious wakeups — and that failure was presumably as
annoying as this one.

## What a next session should do

Do not change the gate on the strength of this note. Pull the trace log first
(`$WORKER_LOGGER_DIR/wait_trace.log`, default under `Meta/blank/src/logs/`), count the
`reason=timeout` lines, and split them by `saw_working=`. That single split decides whether this
suspicion is the user's problem or a distraction, and it costs one grep against data that is
already being written on every run.

If it turns out to be real, the fix direction worth weighing is arming the gate from the
orchestrator side rather than from inside `wait` — the orchestrator knows it just dispatched work,
which is the fact the gate is trying to infer from polling.
