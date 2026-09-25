---
name: sysload
description: Free the Mac before a heavy job (for example a MinerU convert). Snapshots the load of the whole machine, terminates the unambiguous leftovers by exact PID or exact tmux session name, presents the doubtful processes to the user for a decision, and re-measures. Use when the machine is overloaded (beachball, slow menubar, aborting converts) or before a memory-hungry job.
---

# sysload

Draft skill. `SYSLOAD` below means: `PYTHONPATH=<directory that contains the sysload package> python3 -m sysload`. The final location of the package is not decided yet, so resolve that directory before the first call and reuse it.

The tool only measures and classifies. It never terminates anything. Every termination in this flow is a separate command that you issue yourself, by exact target, after the checks below.

## Hard rules

- Terminate only by `kill -TERM <numeric pid>` or `tmux kill-session -t <exact session name>`. Never `pkill`, never `killall`, never a pattern, never a loop over a `ps | grep` result. (`pkill -f` matched worker prompt text and killed unrelated workers before.)
- Only targets that appear in the latest snapshot JSON may be terminated. Never from memory, never from an older snapshot.
- Never terminate an ESSENTIAL row. macOS system processes (launchd, WindowServer, kernel_task, mds, mdworker_shared, and similar) respawn immediately and are not a fix. If one is hot, say so in the report and point at the trigger instead (for example the Spotlight privacy list for a constantly written folder).
- Never terminate your own chain or your own tmux session. The tool already marks both essential; do not override it.
- SIGTERM only. If a target survives, report it. Do not escalate to SIGKILL on your own.
- Doubtful rows are terminated only after the user picked them explicitly.

## Flow

1. **Baseline.** Ask what the user wants to free the machine for. If a job is already running or about to start, note how it appears in `ps` and add `--protect-pid <pid>` (or `--protect-root <dir>` for a repo whose `workflow.py convert` must stay). A MinerU convert (`workflow.py convert` with cwd `~/Documents/ai/Mineru`, its `venv/bin/mineru` child and the fast_api server) is protected by default.
   Run `SYSLOAD snapshot --out /tmp/sysload/before.json` and read the whole output.
2. **Tell the user the picture in two sentences**: load average, memory free, swap, and which owner kinds hold the CPU (the summary line "CPU now by owner kind"). Say plainly if most of the load is ESSENTIAL system load that no kill fixes.
3. **Terminate the KILLABLE actions**, one action at a time, from the `KILLABLE actions` block:
   - pid action: `SYSLOAD confirm pid <pid> "<lstart>"`, and only on `ok`: `kill -TERM <pid>`.
   - session action: `SYSLOAD confirm session <name> <created>`, and only on `ok`: `tmux kill-session -t <name>`.
   - On `changed` the target is not the process that was measured any more (pid reuse or a recreated session). Skip it and say so.
   - Say in one line what each action was (rule, what it covered).
4. **Settle and re-measure once**: wait about 5 seconds, run `SYSLOAD snapshot --out /tmp/sysload/mid.json`, run `SYSLOAD diff /tmp/sysload/before.json /tmp/sysload/mid.json`. Anything under "STILL RUNNING", "STILL PRESENT" or "new killable actions" is a respawn or a survivor. Report it; a respawn means something keeps recreating it and killing again is pointless.
5. **Interpret the DOUBTFUL rows.** For every row give the user: what it is (owner, chain, cwd, task file facts), what stops if it is terminated, and a recommendation (terminate or keep) with the reason. Guidance:
   - Claude Code sessions (`D_claude`): a main session on a tty is the user's conversation, keep unless the user says otherwise. A worker whose work is finished, a session with no tty and no tmux ancestor, or one burning CPU while idle are candidates. Only the user knows whether a session is needed, so ask.
   - Old silent background shells (`D_stale_bgshell`): look at the task file size and last write. A shell running over an hour with an empty task file and no writes is very likely stuck; a shell with a recent write is working.
   - `llama-server` (embedding and reranker for rag-cli) and OrbStack: large but real dependencies. Terminating llama-server breaks RAG search until it is restarted; OrbStack stops every container. Recommend keeping them unless the user needs the memory more than those services, and say what breaks.
   - Other user processes over a load threshold (`D_cpu_now`, `D_rss`, `D_burn`): identify the program from the chain and command; use the test "what breaks if this stops?".
   Present them as a numbered list and ask which numbers to terminate. Wait for the answer.
6. **Terminate the chosen doubtful rows** with the same confirm-then-kill procedure. For a Claude session, terminate the `claude.exe` pid; do not touch its tmux server.
7. **Final measure**: `SYSLOAD snapshot --out /tmp/sysload/after.json`, then `SYSLOAD diff /tmp/sysload/before.json /tmp/sysload/after.json`. Report the deltas of load, memory free, swap and the group totals, list what was terminated, what survived or respawned, and what was left running by decision.

## Reading the snapshot

- Groups: `killable` (unambiguous, you may terminate), `doubtful` (interpret, ask), `essential` (never).
- Killable rules: `K1_monitor_session` (monitor tmux session), `K2_firefox` (Firefox tree), `K3_dead_worker_session` (worker session without a Claude process), `K4_stale_proxy` (mitmdump of a gone worker with no client), `K5_bg_orphan` (task-file holder with no Claude ancestor).
- Rows whose evidence was unreadable (tmux, lsof) never become killable; they show up as doubtful with a `*_unverified` or `*_unresolved` rule.
- The tmux server process is essential even when it burns CPU: kill its monitor sessions instead, that is what lowers its load.
