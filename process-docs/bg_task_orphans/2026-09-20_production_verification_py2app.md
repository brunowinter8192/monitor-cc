# Production verification of the orphan killer, and the build step that almost hid it

Written by the orchestrator session, same day as the detection/kill entry in this area. That
entry covers how the mechanism works. This one covers only what happened when it was put into
production, because that part was not visible from inside the worktree.

## The failing first attempt

After merging the worker branch into `integration`, the menubar was restarted with
`launchctl kickstart -k gui/<uid>/com.brunowinter.monitor-cc-menubar`. It came back up and kept
writing its usual `[latency] bg_refresh` lines, so it was plainly alive.

Then a synthetic orphan was created to prove the new path in the real service:

```
D="/tmp/claude-$(id -u)/-verify-orphan-probe/00000000-0000-0000-0000-000000000000/tasks"
mkdir -p "$D"
( sleep 600 > "$D/verifyprobe.output" 2>&1 & )
```

The subshell exits immediately, so the `sleep` is adopted by launchd. Confirmed live:
pid 23308, ppid 1, holding the file on fd 1 and 2. That is structurally the same shape as the
real incident (pid 79018, a Python process holding a worker's task output file with ppid 1).

Forty seconds later pid 23308 was still alive and `menubar.log` carried no new `[bg_orphan]`
line. The mechanism looked broken.

## Why it looked broken

It was not broken. The launchd service does not run the source tree.

`~/Library/LaunchAgents/com.brunowinter.monitor-cc-menubar.plist` names exactly one program:

```
/Users/brunowinter2000/Applications/monitor-cc-menubar.app/Contents/MacOS/monitor-cc-menubar
```

That is a py2app bundle with its own embedded copy of the package. Merging into the checkout
changes nothing about it, and `launchctl kickstart` restarts the same stale bundle. The running
process confirmed it directly — `ps -A -o pid=,args=` showed pid 16127 running the bundle binary,
not a `python3 .../src/menubar/...` command line.

So the sequence for anything touching `src/menubar/` is three steps, not two:

1. merge into the checkout
2. `./venv/bin/python setup_py2app.py py2app` from the project root
3. the build script installs to `~/Applications`, codesigns, rewrites the plist and re-bootstraps
   the service itself — no separate `launchctl` call is needed afterwards

Step 2 must use the project venv. The build prunes most of `src/` out of the bundle and keeps
only what the menubar package needs; that pruning list is printed at the end of the build.

## The passing second attempt

Same synthetic orphan, still alive from the first attempt (pid 23308, ppid 1). After the rebuild
the freshly bootstrapped service found and terminated it without any further intervention:

```
2026-09-20T20:20:36 [bg_orphan] orphan_detected pid=23308 file=/private/tmp/claude-501/-verify-orphan-probe/00000000-0000-0000-0000-000000000000/tasks/verifyprobe.output
2026-09-20T20:20:36 [bg_orphan] kill_action  pid=23308 file=/private/tmp/claude-501/-verify-orphan-probe/00000000-0000-0000-0000-000000000000/tasks/verifyprobe.output
```

`ps -p 23308` returned nothing afterwards. The probe directory under `/tmp/claude-<uid>/` was
removed by hand after the check.

The synthetic probe is a usable pattern for re-verifying this mechanism later: a one-line
subshell redirect into a fake session path under `/tmp/claude-<uid>/`, then wait through one
scan cycle. Detection is bounded by two independent 10 second throttles (the lsof cache refresh
in `proc_cache.py` and the orphan scan's own interval), so allow roughly 25 to 45 seconds before
concluding anything.

## The real incident, closed out

Pid 79018 was the process that caused the original symptom. It was terminated at 20:10:12,
during the worker's own milestone 2 verification. Reproducing the exact probe `worker-cli wait`
runs — an `lsof` scoped to the `pusher` worker's tasks directory — returned `no` afterwards,
where it had returned `yes` continuously since 18:27.

One thing could not be observed and should not be claimed: a `bg=no` line for `pusher` inside
`wait_trace.log` itself. `worker-cli`'s wait loop breaks out of its per-worker iteration on the
first worker reporting `working`, and the project's other worker `builder` was working through
the entire observation window, so the loop never reached `pusher` at all. That is existing
control flow in `worker-cli`, unrelated to this change.

## Known limit, not addressed on purpose

The kill uses SIGTERM. A process that ignores SIGTERM would be re-detected and re-signalled every
10 seconds, and every attempt writes its own `kill_action` line — unlike `orphan_detected`, that
line is not deduplicated. No such process has been observed, so no escalation to SIGKILL and no
attempt counter was built. If a `menubar.log` ever shows the same pid in repeating `kill_action`
lines, that is the case, and that is the point to revisit it.
