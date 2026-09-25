# sysload: Mac-wide load snapshot tool, skill draft and menubar latency measurement (2026-09-25)

## Why this exists

On 2026-09-25 the MacBook Pro M4 Pro (48 GB) was repeatedly overloaded: beachball cursor, slow menubar, MinerU converts aborting because the MinerU watchdog aborts when available memory drops below a floor. The user wants to free the machine before a heavy job by ending everything that costs load and is not needed. Some processes are always safe to end (monitor instances, Firefox), others need interpretation. Decision from the chat: a script collects facts and separates the unambiguous cases; an agent, driven by a skill, interprets the doubtful ones and asks the user. No blind kill script, no menubar button.

## What was built (all under `dev/system_load/`, location-independent)

Package `sysload/` (import root is the directory `dev/system_load`; imports read `from sysload.classify import ...`; run with `PYTHONPATH=<that dir> python3 -m sysload <command>`). Nothing in the package refers to `dev/system_load` or `src/`, so it can be moved as one directory. Note the deviation from the `from src.module...` convention: there is no `src` here on purpose.

- `snapshot`: collects `ps` (with full command and start time), `top -l 2` (second sample = instantaneous CPU), `tmux` sessions and panes, one `lsof +D /tmp/claude-<uid>` (Claude task output files and their holders), one `lsof -iTCP -sTCP:ESTABLISHED` (client connections per proxy port), `lsof -d cwd` for Claude and convert candidates, load average, `memory_pressure`, swap. Classifies every process, prints a report, writes `/tmp/sysload/<timestamp>.json`. Runtime about 2 s (the `top` sample dominates).
- `confirm pid <pid> "<lstart>"` / `confirm session <name> <created>`: read-only identity check, prints `ok` or `changed`, exit 0 or 1. It exists because pids are reused (see the orphan-killer lesson: the same guard is used there before a kill).
- `diff <before.json> <after.json>`: system deltas, group deltas, per-action outcome (`gone`, `STILL RUNNING`, `STILL PRESENT`) and killable actions that are new in the second file (respawn detection).
- `SKILL.md` (draft): the agent flow. Baseline, kill KILLABLE actions one by one (confirm, then `kill -TERM <pid>` or `tmux kill-session -t <name>`), re-measure, interpret and present DOUBTFUL rows, ask, kill chosen ones, final diff.

The tool contains no termination code at all. A test scans the package sources for `os.kill`, `signal`, `pkill`, `killall`, `kill-session`, `SIGTERM`, `SIGKILL` and fails if any appears.

## Classification (first matching rule wins)

Groups: `killable` (agent may terminate), `doubtful` (agent interprets, user decides), `essential` (never).

| Rule | Group | Meaning |
|---|---|---|
| `caller_chain`, `caller_session` | essential | ancestors of the tool's own pid and everything inside its own tmux session. The agent can never kill itself. |
| `protected` | essential | the heavy job tree, see below |
| `system_owner` / `system_path` / `core_app` / `tmux_server` | essential | uid other than the user, pid 1, `/System`, `/usr/libexec`, `/usr/sbin`, `/sbin`, `/Library/Apple`, Ghostty, the menubar bundle, the tmux server |
| `K2_firefox` | killable | every process whose command starts with `/Applications/Firefox.app/Contents/MacOS/`; the action is the exact pid of the top-most member |
| `K1_monitor_session` | killable | any process inside a `monitor_cc_*` tmux session; action is the session name |
| `K3_dead_worker_session` | killable | `worker-*` session with no Claude process in it; action is the session name |
| `K4_stale_proxy` | killable | `mitmdump` with ppid 1 whose addon file names a worker (`.proxy_addon_live_worker_<name>_...`), no `worker-*-<name>` session exists, and zero established connections on its `-p` port |
| `K5_bg_orphan` | killable | holds a `/tmp/claude-<uid>/.../*.output` file and its parent chain reaches pid 1 without a Claude process on the way (same three-way discipline as the menubar orphan killer: live / orphan / unknown) |
| `D_claude` | doubtful | every Claude Code process (worker, main, or without tty and tmux) |
| `D_stale_bgshell` | doubtful | Claude background shell holding a task file, alive for 15 minutes or more (facts: file size, last write) |
| `D_named_heavy` | doubtful | `llama-server`, anything under `/Applications/OrbStack.app/`. Never killable (user decision). |
| `D_cpu_now`, `D_rss`, `D_burn` | doubtful | user process at 5% CPU now, 500 MB resident, or an averaged 5% of a core over its life with at least 600 CPU seconds |
| `quiet` | essential | everything else |

Tripwires (nothing unobserved becomes killable): tmux unreadable makes all session rules and K4 inapplicable; unreadable connection list makes a stale proxy doubtful (`proxy_unverified`); an unresolved parent chain makes a task-file holder doubtful (`holder_unresolved`); a worker proxy whose worker is gone but which still has connections is doubtful (`proxy_clients_left`).

Main-session proxies (`.proxy_addon_live_<hash>_<launcher pid>_...`) have a live parent (ppid is the launcher) and are essential; without a live parent they are doubtful.

## The MinerU protection (observed facts, exact matching)

Facts given by the orchestrator: a convert runs as `<repo>/venv/bin/python workflow.py convert ...` with cwd `~/Documents/ai/Mineru`, spawns `<repo>/venv/bin/mineru` (or `venv3/bin/mineru`) in its own process group (`start_new_session=True`), and MinerU starts a `fast_api` server during the convert.

Observed on this machine: a process started as `<repo>/venv/bin/python` shows up in `ps` with the framework interpreter path, not the venv path. Reproduced with `~/Documents/ai/Mineru/venv/bin/python -c "import time; time.sleep(6)" convert`: `ps` showed `/opt/homebrew/Cellar/python@3.11/.../Python.app/Contents/MacOS/Python -c import time; time.sleep(6) convert`. So the interpreter path cannot be used for matching. Matching therefore is:

1. Root: an argv token `workflow.py` immediately followed by `convert`, where the script token is either `<root>/workflow.py` (absolute) or the bare `workflow.py` with the process cwd exactly equal to `<root>` (root list: `~/Documents/ai/Mineru`, extendable with `--protect-root`). Or one of the first four argv tokens is exactly `<root>/venv/bin/mineru` / `<root>/venv3/bin/mineru`, or is the token `mineru.cli.fast_api`. Or a pid given with `--protect-pid`.
2. Protected set = roots plus all descendants by ppid. `start_new_session` does not change the ppid, so the spawned mineru and the fast_api server stay in the tree.

Not protected on purpose (tested): the same `workflow.py convert` with another cwd (monitor-cc has its own `workflow.py`), a script merely named `Mineru-notes.py`.

Not verified live: no convert was running while this was built, so the protection is verified against fixtures shaped like the observed commands and against the interpreter-path observation above, not against a real convert tree. A real convert was not started (out of scope, heavy).

## Observed process shapes that drove the rules (2026-09-25)

- The tmux server (`tmux new-session -d -s monitor_cc_5dd99b09 ...`, pid 72039, 141 min CPU) is the parent of every pane process, and its command line names only its first session. It is classified essential (`tmux_server`) with the hint that ending the monitor sessions is what lowers its load.
- Worker Claude processes run as `.../cc-cache-fix-280/node_modules/@anthropic-ai/claude-code/bin/claude.exe` inside `worker-*` panes; each worker has its own `mitmdump -p <port> -s .../.proxy_addon_live_worker_<name>_<ts>_<pid>.py` with ppid 1. Session `worker-general-dsia-k07` maps to addon name `dsia-k07`, session `worker-monitor-cc-mineru-floor` to `mineru-floor`; matching is `session.startswith("worker-") and session.endswith("-" + name)`.
- Main sessions: `claude.exe` on a `ttysNNN`, parent chain `bash < zsh < login < ghostty`, their mitmdump has ppid = the launcher shell.
- Firefox: main `firefox` (ppid 1), `crashhelper` (ppid 1, detached, separate pid), GPU helper and `plugin-container` children. The crash helper gets its own exact-pid action.
- `mitmdump` established connections show as `[::1]:<port>->[::1]:<client port>` in `lsof -Fn`; the server side is the one that starts with the proxy port.
- `/System/Applications/Preview.app` (700 MB) sits under `/System`: it is a user app, so `/System/Applications/` is excluded from the system-path rule and goes through the normal load thresholds (doubtful by memory).

## Live verification (real Mac, 2026-09-25)

Snapshot of 887 processes compared with an independent `ps` dump taken seconds later (`verify_against_ps.py`, report in `md/verify_against_ps.md`):

- pid sets: 887 vs 885, 5 only in the snapshot, 3 only in `ps` (churn); parent links equal for 882 shared pids, 0 mismatches.
- Firefox: 16 members in `ps`, 16 in the snapshot, 0 differing.
- Monitor sessions: the killable session actions equal `tmux list-sessions` filtered to `monitor_cc_*` exactly.
- Group counts add up to the row count (43 killable, 9 doubtful, 835 essential in that run).
- Top-10 CPU overlap between `top` (instantaneous) and `ps` (decaying average): 6 of 10. Reported as info only; the two measure different things.
- The tool changed nothing: `tmux ls` and the process list before and after were identical apart from churn.

Termination flow rehearsed only on sacrificial targets I created myself: tmux session `monitor_cc_sysloadtest` running `sleep 900`, and a `sleep` orphan (subshell exit, ppid 1) holding `/tmp/claude-501/-verify-sysload-probe/.../tasks/*.output`. Both appeared as `K1_monitor_session` and `K5_bg_orphan`. Then `confirm` returned `ok`, `kill -TERM <pid>` and `tmux kill-session -t monitor_cc_sysloadtest` were issued, a second snapshot and `diff` reported both `gone`; the three real `monitor_cc_*` sessions were reported `STILL PRESENT` (untouched, as intended) and `tmux ls` confirmed them. The probe directory was removed afterwards.

Racing detail worth knowing: the first sacrificial orphan (`sleep 901`) was terminated by the menubar's own orphan killer about 30 s after creation, before my confirm step. `confirm pid` then printed `ok` for a vanished pid because the empty `ps` output equalled my empty `lstart`. That was a real bug found by this rehearsal; fixed (empty output never confirms) and covered by a test. If you rehearse the K5 path, create the orphan and run snapshot, confirm and kill within a few seconds.

Not verified live: K3 (dead worker session) and K4 (stale worker proxy). The ten `dsia-k*` workers whose mitmdumps I saw earlier had finished by the time the tool existed, so no dead-worker leak was present. Both rules are verified against fixtures built from the observed shapes only (hypothesis: leaks appear when a worker session ends without its mitmdump, which is what the user described as leaks of our own tooling). The skill was not run end to end by an agent; only its command sequence was rehearsed by hand.

## Tests

`dev/system_load/tests/test_classify.py` (9 strands) and `test_parsers_and_guards.py` (6 strands), fixtures only, run through the shared strand runner. Both pass (9/9, 6/6). The tests found two real bugs before verification: `ancestors()` returned parent pids that were missing from the process table (KeyError when building the chain of a process whose parent had exited), and the fixture builder turned `established=None` into an empty list, hiding the unreadable-connections tripwire.

## M5: menubar responsiveness under load (measurement only, no `src/` change)

`dev/hotkey_latency/analyze_latency.py` was run on the live 50 MB `menubar.log` (report `dev/hotkey_latency/md/latency_report_20260925T164619Z.md`, whole retained window since 2026-08-19; 0.9 s) and on a copy of only the 2026-09-25 lines (`latency_report_20260925T164632Z.md`). Log times are local (UTC+2). Only cycles over the 200 ms threshold are logged, so counts are over-threshold counts.

Findings for 2026-09-25:

- Main thread: 71 over-threshold ticks all day, every one of them `panel_rebuild_update` (AppKit panel work), none from discovery. Worst 3041 ms at 12:17:28, then 1914 ms at 15:37, 1625 ms at 12:46, 1433 ms at 00:17. The main thread is not blocked by process scanning any more (discovery lives on the background thread since 2026-08-19); what remains is panel rebuild time that grows when WindowServer is contended (WindowServer was at 19 to 31 percent CPU in the screenshot and in a live sample).
- Background discovery worker: this is where load shows. Hourly median of a cycle overnight with the machine idle: 2.7 to 3.4 s, driven by `desktop_detection` at about 2.4 to 2.7 s per cycle. During the load hours 12:00 to 15:59 the p95 cycle is 3.4 to 8.0 s and single cycles reach 15.7 to 25.8 s with every phase (ps, lsof, tmux, ghostty) inflated 10 to 30 times (12:17:49: `per_project_loop` 12575 ms, `ghostty` 2883 ms, `tmux_state` 1987 ms). Cycles over 5 s per hour: 37 at 12:00, 18 at 13:00, 6 at 14:00, 9 at 15:00, versus 0 between 04:00 and 09:00. Consequence: under load the menubar shows data up to 25 s old, which matches "reacts slowly or not at all".
- The bg cycle cost changes sharply after the menubar process restart at about 16:03: hourly median 678 ms at 17:00 against 2.0 to 3.4 s before. Not investigated (which build changed this is outside this task); worth noting because the 12:00 to 15:00 numbers come from the earlier build. At 18:00 the median is back to 1278 ms with 4 cycles over 5 s.
- Hotkey queue delay: 424 presses today. In the load hour 12 there were outliers (100 to 214 ms for `cmd+2`/`cmd+k` at 12:30, and a maximum of 2394.8 ms for `cmd+k` in the whole window); all other hours have a maximum of about 1 ms. So the Carbon-timestamp metric is not fully blind (it did register the 100+ ms delays under load), but its near-zero values still do not prove responsiveness: only 424 presses, the metric measures dispatch after the event was created, and the user's slow-menubar perception is mostly the stale data plus the panel rebuild, not hotkey dispatch.
- Focus path: `osascript_ms` median 103 ms, p95 130 ms, max 3796 ms over the whole window.

Reading: the menubar suffers from load through its subprocess-based discovery (many `ps`/`lsof`/`tmux` calls that slow down 10 to 30 times under load), not through the hotkey path. Reducing the load on the machine (this tool) reduces the staleness; no `src/` change was made.

## Where things should live (open, decided by the orchestrator/user)

Everything is in `dev/system_load/` for now. Recommendation given to the orchestrator: package as a standalone CLI next to the other Mac-wide CLIs (source under `Meta/ClaudeCode/cli/`, symlink in `~/.local/bin`, same pattern as `poread`), skill as a user-level skill. Moving is a copy of the `sysload/` directory; nothing else depends on the location. Update the `SYSLOAD` definition in `SKILL.md` when it moves.

## Open points for a successor

- Thresholds in `sysload/config.py` (5% CPU, 500 MB, burn ratio) were set against one live snapshot; tune them after a few real runs.
- Claude main sessions are always doubtful. If the user wants idle-burning `claude.exe` sessions surfaced more sharply, add the hook state (`hooks.json` in the menubar app support directory) as a fact; not done to keep the tool Mac-wide and independent of the menubar.
- `D_named_heavy` lists every OrbStack process, including tiny idle ones. Cosmetic.
- The skill is a draft: it has never been executed by an agent in a real session.
