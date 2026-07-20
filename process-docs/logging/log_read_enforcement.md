# Log-Read Enforcement — `logread` + `block_log_read` (2026-06-22)

Structural fix for worker log-polling: ONE sanctioned `.log` reader (`logread`), all other `.log` reads
blocked, `logread` itself capped. Replaces frequency detection for the `.log` case. Pipe07 Hook 33.

## Problem
Workers endlessly poll a growing `.log` (`tail -n +58 x.log | head`, repeated) and drain their own context.
The skill rule "go idle, don't poll" is not honored by naive workers — pure discipline gap.

## Why frequency detection failed (the dead end that led here)
`block_polling_loop` (Hook 8) is frequency-based: same target ≥3× within a time window → block. Investigated
its real behavior on the live Docling poll (fire-log forensics):
- The worker polled **18:26 → 19:29 — over an hour**. The frequency hook blocked it **7×** (18:26:59,
  18:27:23, 18:27:34, 18:33:26, 18:33:43, 18:50:16, 19:29:28) and the worker **kept polling regardless**.
- Two structural faults: (1) **timing is the wrong axis.** API latency (thinking blocks, variable streaming)
  spaces consecutive polls unpredictably — the blocks above had 6-to-39-min gaps. A fixed window (30 s, even
  5 min) catches only when polls happen to cluster; spaced polls slip. Widening the window trades FN for FP
  and never closes the gap (a poll spaced > window/2 always escapes). (2) **even when it fires it doesn't
  stop the loop** — it blocks one call; the worker spaces out or switches form and continues.
- A 5-min-window widening was investigated (`pollwindow` worker) and **dropped** — same axis, marginal gain.
- The real discriminator between a poll and a legit repeated read is NOT timing — it is whether the worker
  does real work between reads. No time-window can see that.

## Decision (user-driven): structural funnel, not frequency
Don't detect the bad pattern — make it impossible. ONE sanctioned `.log` reader; block all other `.log`
reads; cap the sanctioned reader cumulatively (no time window → timing fully irrelevant). Keep it simple,
scope `.log`-only (the observed failure was read-only on `.log`); extend later if other patterns appear.

## State (at the time) — two rules (Hook 33 `block_log_read.py`, per-segment)
**Rule A — cap `logread`:** `logread <file>` counted per (session, file), CUMULATIVE, no time window. 1st + 2nd
read pass, **3rd read of the same file in the session → hard block** with `"go idle immediately! stop
whatever you do, go idle!"`. State `src/logs/logread_state.jsonl` ({ts, session_id, file}), 24 h prune is
dead-session cleanup only (not a detection window). File = first arg (`logread x.log 50` → file `x.log`).

**Rule B — block non-`logread` `.log` reads:** content-output read tools (`tail cat head grep egrep fgrep sed
less more awk tac nl zcat`) with a `.log`/`.log.N`/`.log.gz` as an INPUT arg → block with "read .log only via
logread". Deliberately NOT `wc`/`ls`/`stat` (those don't drain context). Output redirects stripped first, so
WRITING a log (`> x.log`, `>> x.log`, `2>> x.log`, `tee x.log`) is NOT blocked; input redirect (`< x.log`) IS
(it reads). Per-segment precedence (evasion fix): a command mixing `logread` + a `tail x.log` still blocks the
tail segment (`tail x.log ; logread y` → BLOCK).

**Escape:** `~/.local/bin/logread <file> [N]` — cat-like (whole file) or last N lines. The only sanctioned
reader; orchestrator-created infra wrapper.

## Relation to `block_polling_loop` (Hook 8)
block_polling_loop STAYS, unchanged window (30 s), as the backstop for **`ps -p` process-polling** and
**non-`.log` file polling** (which block_log_read does not cover). Today's earlier block_polling_loop work
(pipe-fed-tail FP fix `48e1504`, long-form/offset tail extension `db789ad`) remains relevant for the non-`.log`
file case. So: `.log` polling → block_log_read (structural funnel); `ps -p` + other-file polling → frequency.

## Accepted trade-offs
- **Ergonomic cost:** ALL `.log` reads (every worker AND the orchestrator) now go through `logread`. Reflexive
  `tail`/`cat` on a `.log` is blocked — deliberate (breaks the reflexive poll; forces a conscious read).
- **Scope `.log`-only:** polls on `.jsonl`/`.out`/no-extension slip block_log_read (frequency hook is their
  only backstop). Accepted; extend the read-tool/extension scope if such a pattern appears live.

## Verification
22-case smoke (`dev/hook_smoke/test_block_log_read.py`) + 18 direct-invocation cases + live end-to-end:
`tail /tmp/x.log` blocked live with the message; `echo > x.log` + `logread x.log` + `rm x.log` all pass live;
`logread` 3rd-same-file blocks; `tail x.log ; logread y` evasion blocks. Commit `91c6ac5`.
