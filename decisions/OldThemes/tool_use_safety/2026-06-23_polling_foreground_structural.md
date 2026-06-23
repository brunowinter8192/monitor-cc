# Polling — Structural Prevention (foreground-forcing) + Findings, 2026-06-23

Design discussion. Status: OPEN (design not converged). No code this session beyond `block_broad_find` (separate, merged — see `hook_design_principles/`).

## Existing polling/wait hook stack (IST recap)
- `block_polling_loop` (Hook 8): stateful frequency — same target ≥3×/30s/session → block. Timing-axis; known weak (spaced polls escape; firing doesn't stop a determined loop).
- `block_busywait_loop` (Hook 21): single-call `while`/`until` loop whose body is exactly `sleep N` and whose condition is a passive status-check → block.
- `block_log_read` (Hook 33) + `logread`: structural — `logread` is the only sanctioned `.log` reader, all other `.log` reads blocked, `logread` capped at 3×/(session,file). Replaced frequency for the `.log` case.
- `block_unauthorized_background` (Hook 3): `run_in_background=true` non-canonical → rewritten to foreground; only `sleep N && echo done` passes as background.
- `rewrite_chained_sleep` / `rewrite_background_sleep`: strip trivial-sync chained sleeps / normalize timer N→600.

## Real polling pattern observed (trading session)
Launch Convert in background → self-wake timer (`sleep 90 && echo done`, then `sleep 900 ...`, self-labeled "progress check"/"completion check") → on wake probe the buffer files: log (tail, then logread), engine-map JSON (`ls -l`/`wc` byte-size as the imagined done-signal), output dir (`ls -lt` for new mds) → not done → next timer → repeat. The TIMER was the poll engine; all probes were null-informative mid-run (output buffering: 0 bytes ≠ done).

## Key findings
- `block_log_read` caught only the `.log` probe (→ logread → cap). The JSON byte-size check (`ls -l`/`wc` = metadata, not content) and the dir-listing were NOT caught — and extending `block_log_read` to `.json`/`.jsonl` would NOT catch them either (metadata/listing, not content reads).
- → `.json`/`.jsonl` extension of `block_log_read` = WRONG lever for this pattern. `.json` is overwhelmingly config/data (huge FP surface). `.jsonl` real polling targets exist (session/proxy logs) but the right tools (jq/python) aren't caught anyway; defer unless fire-log evidence shows real `.jsonl` polling.
- The poll engine is the TIMER, which is mechanically identical to the sanctioned orchestrator timer (wakes to check a WORKING WORKER's status). Intent differs (worker-status vs process-buffer-poll) but is not in the hook payload → not cleanly hookable.

## foreground-forcing idea (user) + objections
Idea: force every process to foreground with an auto-timeout (30/60min); only sleeps pass as background ⇒ no parallel background ⇒ polling structurally impossible (the process occupies the agent until done).
- ~80% already live: `block_unauthorized_background` already forces non-sleep background → foreground (for the CC FLAG).
- Gap 1 (actionable): shell-`&` backgrounding (`convert ... &`) bypasses the flag-hook. Closing it (detect trailing single `&`, force foreground) makes foreground-forcing airtight for short jobs.
- Gap 2 (blocker for long jobs): CC Bash foreground does NOT hard-cap-and-kill at a timeout — it MOVES the command to BACKGROUND after a timeout (user-observed; exact threshold/mechanism UNVERIFIED). CC itself then reintroduces a pollable background handle for long jobs ⇒ foreground-forcing cannot structurally prevent polling for jobs longer than the timeout.
- Retraction: the earlier "CC kills foreground at 10min" was a config-derived ASSUMPTION presented as fact — wrong. Real behavior = auto-background. Verify exact threshold + mechanism (BashOutput-pollable handle?) from CC docs/session-logs before building.

## SOLL direction (NOT yet evidence-converged — Pending)
- Short jobs (≤ CC fg timeout): foreground-forcing works; close the shell-`&` gap in `block_unauthorized_background`.
- Long jobs: foreground impossible (auto-background); anti-poll property must come from launch → truly-idle → external-wake discipline, not occupation. Harder, partly discipline-only.
- Prerequisite: verify the actual CC Bash auto-background threshold + whether the resulting handle is BashOutput-pollable (and thus itself hookable).

## Sleep-only foreground-forcing was too aggressive — fixed (2026-06-23, later same session)

The IST in "Existing polling/wait hook stack" above (`block_unauthorized_background`: "only `sleep N && echo done` passes as background") was a bug, not the design. Both `block_unauthorized_background._CANONICAL` and `rewrite_background_sleep._CANONICAL_BG` matched ONLY the exact literal `sleep N && echo done`; any deviation fell through.

### Symptom
A background timer in any non-exact form was silently foreground-forced — it ran in the foreground and returned its output immediately, defeating the "launch timer → go idle" mechanism. Concretely: `sleep 45 && echo "bg-ack-probe done"` (custom echo text) and bare `sleep 300` (no echo) both failed the exact regex.

### Evidence
fire-log `src/logs/hook_firing.jsonl`: `sleep 45 && echo "bg-ack-probe done"` rewritten by `block_unauthorized_background` (run_in_background true→false) at ts `2026-06-23T00:33:02Z`, while canonical `sleep N && echo done` forms went to `rewrite_background_sleep` → `sleep 600`.

### Fix — committed `9b49869` on dev
Both hooks broadened to a shared sleep-only pattern `_SLEEP_ONLY_BG = ^\s*sleep\s+\d+(?:\.\d+)?\s*(?:&&\s*echo\b[^;&|\n]*)?\s*$` (bare `sleep N` OR `sleep N && echo <anything>`; `[^;&|\n]*` stops at separators so `sleep N && echo x && realcmd` is NOT exempt).
- `rewrite_background_sleep`: normalizes any sleep-only bg command → `sleep 600 && echo done`; guard switched from `float(group(1))==600` to `command.strip()==_TARGET` (broadened regex dropped the capture group).
- `block_unauthorized_background`: `_CANONICAL` broadened to the same pattern → sleep-only is never foreground-forced; exempts both raw and normalized forms (hook-order independent). Non-sleep background commands are STILL foreground-forced (the actual #30 lever — preserved; smoke FORCE1/FORCE2).

### Verification
Smokes: `test_rewrite_background_sleep.py` 11/11, new `test_block_unauthorized_background.py` 9/9. Hooks live post-merge (`hook_setup.py` re-registers from `src/hooks/`).

### Relation to #30
Fixes the legitimate timer (the "go idle" tool) that foreground-forcing was breaking — makes the sanctioned launch→idle→external-wake path actually usable. Does NOT resolve the broader #30 goal: the shell-`&` gap (Gap 1) and long-job auto-background (Gap 2) above remain Pending.
