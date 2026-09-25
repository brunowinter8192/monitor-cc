# system_load — full session record: scope, research, decisions, build, first cleanup (2026-09-25)

Orchestrator-side record of the whole session of 2026-09-25. The implementing worker's own record (tool internals, tests, menubar latency measurement in detail) lives in this same area. This file covers everything else: what the user reported, what was decided and why, what was researched, what was built where, what was verified, and what is still open.

## 1. Trigger — what the user reported

The user reported, with two screenshots:
- Beachball cursor, big CPU peaks in Activity Monitor, "the Mac is brought to its limit".
- The menubar reacts slowly, sometimes not at all, especially under load.
- MinerU converts keep aborting (watchdog).
- After Cmd+digit switches to a Ghostty desktop, a click into the pane is needed before typing lands there.
- Worker background shells that never end.

Activity Monitor screenshot (CPU tab): kernel_task 20.7% (8:43h CPU time, 675 threads), WindowServer 19.0% (7:13h), OrbStack Helper 15.9% (7:17h), claude.exe 10.7%, Python 10.4% (1:33h, 1 thread), Python 10.3% (1:37h, 1 thread), mds_stores 10.2% (1:48h), Ghostty 9.9%, tmux 9.8% (2:08h), monitor-cc-menubar 5.8%, spotlightknowledged.updater 5.8%, sysmond 5.5%, Python 3.1% and 2.9% (1 thread each). System 13.55%, user 14.42%, idle 72.03%, with two broad peaks in the load graph.

Claude Code shell-details screenshot: status running, runtime 1h 26m 53s, command `cd .../monitor-cc/.claude/worktrees/mcdev && python3 - <<'E'` followed by a string-replace script on `dev/refactoring/layout_scan.py`, output "No output available".

## 2. Scope

The user split the report into four topics and grouped them himself: menubar lag (2) and machine overload (4) belong together and form this cycle, because he wanted to re-run a MinerU convert. Focus after desktop switch (1) and endless worker background commands (3) are independent topics, not worked on in this session.

User statements that define the scope:
- Diagnose first, then act.
- Wanted: a way to "kill everything that is not vital" before a heavy job. Some processes are always safe to kill (named: the monitor instances, Firefox); others are doubtful. The doubtful ones must be judged by an AGENT that can interpret, not by a blind script or a menubar button.
- MinerU watchdog floor: lower it from 10 GB to 5 GB (confirmed explicitly).
- On topic 3 (for the record, not worked on): the main-session timer correctly does not abort while a worker has background commands running, so a stuck command keeps a worker alive for hours. A blanket timeout (e.g. 30 min) is not acceptable because indexing and scraping legitimately run long; waking the worker after x minutes to decide was also rejected as unsatisfying. The user first wants to KNOW which commands these are, via the dual-log reading skill.

## 3. Process history consulted (areas)

- hotkey_latency: menubar discovery was moved off the main thread in 2026-08; desktop detection (~700 ms per 10 s) and osascript focus (~90 ms) stayed. Never measured under system load before this session.
- monitor_lifecycle: the same overload picture (a dozen single-thread Python processes with 30 min to 1 h CPU each) happened before; cause were monitor tmux sessions (nine pane processes each) that outlive their Ghostty window. A 24 h sweep exists; younger monitors keep running.
- bg_task_orphans: the menubar terminates background-task holders whose ancestry reaches pid 1 without a Claude process. Hung shells of a LIVE worker are not covered.
- pipeline: `pkill -f` once matched worker prompt text and killed three unrelated workers; kills must use exact PID or exact tmux session name.
- MinerU repo (`decisions/watchdog.md`, `decisions/OldThemes/memory_pressure_crash/`): the watchdog aborts on MinerU tree footprint > 30 GB or system available < floor (10 GB before this session). The floor depends on everything else running on the machine.

## 4. Live measurements

`ps` snapshot, afternoon: `mds` 71.7% CPU; `mds_stores` 114 min CPU over 5 days; about 20 `mdworker_shared` processes alive at once (3-17% each); OrbStack Helper 476 min CPU over 5 days, ~1 GB RSS; tmux server 140 min CPU over ~2 days; 3 `monitor_cc_*` and 10 `worker-general-dsia-*` tmux sessions; memory free 49%, swap 537 MB used.

Later the same afternoon, after the ten dsia workers had ended: memory free 84%. Parallel worker fleets in other projects are a main memory consumer during a convert.

## 5. Gaps and how they were closed

| Gap | Result |
|---|---|
| 1 Spotlight load and what it indexes | Closed by measurement and web research (section 6) |
| 2 OrbStack idle load | Not researched; OrbStack is classified as doubtful, the agent decides per case |
| 3 Which macOS processes are safe to kill | Closed by web research (section 7) |
| 4 claude.exe idle CPU | Partly closed from RAG: anthropics/claude-code #19393 (idle CPU on macOS) and #92393 (background-agent path, ~2.1.231+) |
| 5 kernel_task high | Not researched |
| 6 tmux server load | Not researched; the tool marks the tmux server essential and recommends killing its sessions instead |
| 7 Menubar under load | Closed by the worker's measurement (section 9) |

The user agreed to leave 2, 5 and 6 to per-case agent judgement.

## 6. Spotlight finding (observed)

Sampling `lsof -c mdworker -Fn` once per second for 8 s, grouped by directory: 48 open files under `monitor-cc/src/logs/dual_log`, 40 under `Meta/ClaudeCode/cli/websearch/src` (narrowed to `src/logs`), 17 under `monitor-cc/src/logs`, 16 in the Firefox profile. `monitor-cc/src/logs` was 511 MB and is written continuously by the proxy, so Spotlight re-indexes it without end. `mdutil -s /` reported indexing enabled; no `.metadata_never_index` existed.

External facts (both pages indexed into `monitor-cc-reference`: procxray.com mds_stores guide, eclecticlight.co 2025-06-16):
- `.metadata_never_index` no longer works in recent macOS. Do not use it.
- Working exclusions: System Settings > Spotlight privacy list; a `.noindex` suffix on the folder name; a leading dot on the folder name.
- Killing `mds_stores` is harmless but it respawns within seconds and does not remove the trigger.
- Developer folders with many constantly changing small files are the typical cause.

Action handed to the user (manual, no code): add `/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs` and `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch/src/logs` to the Spotlight privacy list. As of the end of the session this was NOT applied: a re-sample after the cleanup still showed 42 open files under `dual_log` and 12 under the Mineru repo.

## 7. "Safe to kill" research result

No authoritative list exists (superuser 1792027, theodorehq.com, setapp, macbookjournal). Consensus: never kill macOS system processes (launchd, WindowServer, kernel_task, mDNSResponder); launchd respawns them, so killing brings no relief anyway. User-installed application processes are generally terminable; the test is "what breaks if this stops?". Consequence: the lever is our own processes (monitor sessions, stale workers, proxies, background shells) plus user apps, and doubtful cases need interpretation, which is why the triage is agent-driven.

## 8. Milestones and decisions

- M1 Spotlight exclusion of the two log folders: user action, not done yet (section 6).
- M2 Mac-wide load snapshot tool `sysload`, M3 agent skill draft, M5 menubar measurement: one worker (`sysload`) in monitor-cc.
- M4 MinerU floor 10 -> 5 GB: one worker (`mineru-floor`) spawned in monitor-cc, working in a MinerU worktree.
- Final verification: a real MinerU convert after a cleanup. Not done in this session.

Decisions given to the sysload worker after its plan:
- Build everything location-independent in `dev/system_load/`; skill draft as `dev/system_load/SKILL.md`.
- Dead worker sessions (no Claude process inside) and stale worker mitmdumps (worker session gone, no client connection) are KILLABLE, as leaks of our own tooling.
- The running MinerU convert is protected as a whole tree: `workflow.py convert` with cwd `~/Documents/ai/Mineru`, the exact `venv/bin/mineru` or `venv3/bin/mineru` path, the `mineru.cli.fast_api` server, and all descendants.
- llama-server and OrbStack are always doubtful, never auto-killed.
- Final location of tool and skill: OPEN. Recommendation given to the user: own CLI under `Meta/ClaudeCode/cli/sysload` plus a user-level skill; alternative: inside monitor-cc. The user has not decided.

## 9. What was built and verified

MinerU repo (branch mineru-floor, commits `9ada8cb` fix + `a670603` docs date correction, merged `73492b2`, pushed to main):
- `mem_watchdog.py` default `WATCHDOG_FLOOR_GB` from 10 to 5; `WATCHDOG_PROC_GB` stays 30; env overrides still win.
- `decisions/watchdog.md` updated (trigger conditions, recommendation, evidence, open question about reduced headroom for Firefox, llama-server and OrbStack).
- New `test_mem_watchdog.py`: three cases in parallel subprocesses (default 5.0/30.0, floor override 7, proc override 12); passes with the venv interpreter (pytest is not installed there).

monitor-cc (branch sysload, commits `c0a21483` feat + `360f077e` recap, merged `23981de0`, pushed to main):
- `dev/system_load/sysload/` package (config, collect, classify, render, snapshot, confirm, diff, cli, __main__), stdlib only. Commands: `snapshot` (report + JSON under `/tmp/sysload/`), `confirm pid <pid> <lstart>` / `confirm session <name> <created>` (read-only identity check, prints `ok` or `changed`), `diff <before> <after>`. The package contains no termination code; a test guards that.
- Killable rules: K1 monitor tmux session, K2 Firefox tree, K3 worker session without Claude, K4 stale worker mitmdump, K5 task-file holder without Claude ancestor. Unreadable evidence never becomes killable. The caller's own chain and tmux session are essential.
- Tests: 9/9 and 6/6 strands on fixtures. Live check against an independent `ps` dump matched. Kill flow rehearsed only on the worker's own throwaway targets. That rehearsal found a real bug: `confirm` said `ok` for a vanished pid; fixed.
- Review by the orchestrator: code read in full; a live snapshot run classified plausibly. Verified that main Claude sessions do NOT run inside `monitor_cc_*` sessions (the eight monitor panes are only `workflow.py --mode ...`), so K1 cannot hit a main session.
- M5 menubar measurement (details in the worker's record): under load the background discovery cycle reached 15-26 s instead of ~3.3 s, so the menubar showed data up to ~25 s old; main-thread ticks and hotkey dispatch were not the bottleneck. Conclusion: less machine load helps the menubar directly.

## 10. First real cleanup run (orchestrator, by hand along the skill draft)

- `before` snapshot: killable = three `monitor_cc_*` sessions and two Firefox pids (~2.8 GB, ~10% CPU); doubtful = two main claude.exe sessions (general, websearch), OrbStack (2 processes), two llama-server (~8.1 GB and ~4.3 GB), Preview (1.2 GB); `mds_stores` 40.8% CPU.
- `confirm` returned `ok` for four targets; the second Firefox pid returned `changed` because it had already exited with its parent. `diff`: killable 37 -> 0 processes, all five actions `gone`, no respawn.
- Shell gotcha: in zsh, `S="env PYTHONPATH=... python3 -m sysload"; $S confirm ...` fails (no word splitting); every confirm printed nothing and no kill ran, so the guard held. Use `export PYTHONPATH=<dir>` and call `python3 -m sysload` directly.
- llama-server: both instances had exited during the session and were running again 80 s after a `rag-cli update_docs` call (observed once). Terminating them before a convert costs only a restart on the next RAG call.
- The skill draft is not installed as a skill, so no agent can invoke it yet. The cleanup above was done by the orchestrator following the draft step by step.

## 11. State at end of session (2026-09-25)

- monitor-cc and MinerU: `integration` merged into `main`, pushed; docs synced to RAG.
- Both workers killed, their worktrees and branches removed.
- Open: final location and installation of tool and skill; a full skill run by an agent; a real MinerU convert under the 5 GB floor; the Spotlight privacy exclusion and a re-measure; threshold tuning after several real runs; live observation of the dead-worker and stale-proxy rules.
- Separate open topics, not started: keyboard focus after Cmd+digit (area menubar_worker_focus) and endless worker background commands (area bg_command_runtime).
