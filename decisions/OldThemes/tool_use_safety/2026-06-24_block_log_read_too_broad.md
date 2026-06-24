# block_log_read Too Broad — Narrow vs Kill (2026-06-24)

Design discussion. Status: OPEN (Pending — decide next session with fire-log evidence). Extends `2026-06-23_polling_foreground_structural.md`.

## Trigger — collateral block (call#187)
A legitimate short launch-and-verify command was blocked by `block_log_read` (Hook 33):
```
cd monitor-cc
nohup ./venv/bin/python dev/menubar_debug.py > /tmp/menubar_debug.log 2>&1 &
LAUNCH_PID=$!; sleep 6
ps -p $LAUNCH_PID ...; cat /tmp/menubar_debug.log; pgrep -fl "workflow.py --mode menubar"
```
It LAUNCHES a process and reads its `.log` ONCE for startup verification — not a poll. It ran in the foreground, took seconds, and was blocked uselessly (had to redirect to `.out` to proceed). `block_log_read` fired on the single `cat .log` with zero poll intent.

## User critique
`block_log_read` is too BROAD — it blocks ALL `.log` reads (except `logread`), catching one-shot launch-verification reads, not just polls. In its current form it does more harm than help.

## The two REAL pain cases (everything else is collateral)
Polling that actually burns budget happens on LONG background jobs whose only progress signal is a growing log:
1. **Indexing** — `rag-cli index` long-job; the anti-pattern is repeated `tail/cat <index>.log` (Docling 1h-poll history: `2026-05-25_block_polling_loop_design.md` § 2026-06-22).
2. **Searxng scraping** — the `searxng-cli-capture-and-index` skill launches scraping in the BACKGROUND; the poll is separate `.log` tailing. A chain-block (`block_rag_cli_chained`) does NOT catch a separate later `tail`; this is exactly what `block_log_read` covers. (Exact poll shape to be verified from the skill next session.)

## Why the log-read funnel is the lever (10-min premise, re-confirmed)
Foreground-forcing CANNOT structurally prevent long-job polling: CC Bash auto-backgrounds a foreground command after an UNVERIFIED threshold — NOT a kill (the earlier "CC kills foreground at 10min" was retracted, see `2026-06-23_polling_foreground_structural.md`). CC then reintroduces a pollable background handle for long jobs. So for jobs longer than the threshold the anti-poll property must come from the log-read funnel (or launch→idle→external-wake discipline), not from foreground occupation. → Indexing + scraping logs are precisely the long-job case where a `.log` block matters.

## Options
- **A — NARROW `block_log_read` (recommended, Pending evidence):** allow a launch-and-incidental-read form — a command that LAUNCHES a process (`nohup ... &` / trailing `&`) AND reads its `.log` once in the same command (the call#187 shape) — while keeping standalone repeated `tail/cat <x>.log` blocked. Removes the call#187 friction without losing the anti-poll funnel for the two long-job logs.
- **B — KILL `block_log_read` + cover the two pains otherwise:** indexing → use `rag-cli progress` / `status` as the check (not log-tail); scraping → the scrape-skill's "wait for background-done, read once" discipline + the bg-launch-ack text. Risk: long-job log-polling becomes DISCIPLINE-only, not hook-prevented — and history (Docling 1h, frequency hook fired 7×, worker kept polling) shows discipline alone is unreliable.

## Recommendation
A (narrow), not a naked kill. The collateral the user wants gone is the launch-and-incidental-read; the funnel for the two real pains stays. PENDING — decide next session with: (1) fire-log evidence on how often `block_log_read` blocks legitimate vs poll reads, (2) a precise look at how the searxng scrape skill actually polls.

## Open
- Verify the searxng scrape skill's exact poll shape (`searxng-cli: skills/searxng-cli-capture-and-index/SKILL.md`).
- Define the narrow exemption regex (launch + single read in one command) WITHOUT opening a poll-via-repeated-launch loophole.
- Fire-log audit: `src/logs/hook_firing.jsonl` — block_log_read legitimate-vs-poll ratio.
- Orchestrator self-poll residual stays rule-only (unchanged).

## Sources
- `decisions/OldThemes/tool_use_safety/2026-06-23_polling_foreground_structural.md`
- `decisions/OldThemes/tool_use_safety/2026-05-25_block_polling_loop_design.md`
- `decisions/pipe07_safety_hooks.md`, `src/hooks/DOCS.md` (hook IST)
- `searxng-cli: skills/searxng-cli-capture-and-index/SKILL.md`
