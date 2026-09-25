# system_load — scope, user decisions and the Spotlight finding (2026-09-25)

Orchestrator-side record of the session chat. The tool itself (sysload), its tests and the menubar latency measurement are recorded by the implementing worker in this same area.

## Trigger

The user reported, on 2026-09-25: beachball cursor, large CPU peaks in Activity Monitor, the menubar reacting slowly or not at all, and MinerU converts aborting. Screenshot values: kernel_task 20.7%, WindowServer 19.0%, OrbStack Helper 15.9% (7:17h CPU time), several single-thread Python processes at ~10% with ~1.5h CPU time each, mds_stores 10.2%, tmux 9.8% (2:08h). A worker background shell (`python3 - <<'E' ...` heredoc in worktree mcdev) had run 1h26m without output.

The user split the complaints into four topics. This cycle covered two of them together: menubar lag under load, and general machine overload before a heavy job. The other two are separate and were NOT worked on:
- Focus after Cmd+digit desktop switch: the Ghostty pane needs an extra click before keystrokes land in it (worked on before, see area menubar_worker_focus / ghostty_foreground).
- Worker background commands that never end (hours). The main-session timer correctly does not abort while a worker has background commands running, so a stuck command keeps the worker alive indefinitely. The user wants first to KNOW which commands these are (dual-log investigation), before deciding on any timeout mechanism. The user rejected both a blanket 30-minute kill and a "wake the worker after x minutes and let it decide" approach as unsatisfying.

## User decisions

- Diagnose first, then act.
- MinerU watchdog floor (system available memory) lowered from 10 GB to 5 GB. Done in the MinerU repo (`mem_watchdog.py` default; `decisions/watchdog.md` there).
- Killing load must be interpreted by an AGENT (skill), not a script or a menubar button. Rationale from the user: some processes are always safe to kill (example named: the monitor instances, Firefox), others are doubtful and need interpretation.
- Dead worker sessions and stale worker mitmdumps count as killable (orchestrator decision, leaks of our own tooling).
- llama-server and OrbStack are always doubtful, never auto-killed.
- Final location of tool and skill: OPEN as of 2026-09-25. Recommendation given to the user: own CLI under `Meta/ClaudeCode/cli/sysload` plus a user-level skill. Until decided, everything lives in `dev/system_load/`.

## Spotlight finding (observed, not hypothesis)

`ps` on 2026-09-25 afternoon: `mds` at 71.7% CPU, ~20 `mdworker_shared` processes alive at once. Sampling `lsof -c mdworker -Fn` once per second for 8 s, grouped by directory:

| open files | directory |
|---|---|
| 48 | `monitor-cc/src/logs/dual_log` |
| 40 | `Meta/ClaudeCode/cli/websearch/src` (narrowed: `src/logs`) |
| 17 | `monitor-cc/src/logs` |
| 16 | Firefox profile |

`monitor-cc/src/logs` was 511 MB, written continuously by the proxy, so Spotlight re-indexes it without end.

Excluding a folder from Spotlight, per external sources (indexed in `monitor-cc-reference`: procxray.com mds_stores guide, eclecticlight.co 2025-06-16):
- `.metadata_never_index` inside the folder no longer works in recent macOS. Do not use it.
- Working: System Settings > Spotlight privacy list; a `.noindex` suffix on the folder name; a leading dot on the folder name.
- Killing `mds_stores` is harmless but it respawns within seconds; it does not remove the trigger.

Action handed to the user (manual, no code): add `monitor-cc/src/logs` and `websearch/src/logs` to the Spotlight privacy list. Not yet re-measured as of writing.

## "Safe to kill" research result

No authoritative list exists. Consensus of all sources read: never kill macOS system processes (launchd, WindowServer, kernel_task, mDNSResponder); launchd respawns them, so killing brings no relief anyway. User-installed application processes are generally terminable; the test is "what breaks if this stops?". This is why the triage is agent-driven and why the lever is our own processes (monitor sessions, stale workers, proxies, background shells) plus user apps.

## Memory observation

Memory free was 49% while ten `worker-general-dsia-*` sessions were alive, and 84% after they ended (same afternoon). Parallel worker fleets in other projects are a main memory consumer during a convert.
