# Data-Dependent Re-Evaluations — Consolidated Tracker (2026-05-25)

**Topic:** as of 2026-05-25, three separate hook/strip topics all waited on accumulation of
live data in `src/logs/hook_firing.jsonl` and/or `src/logs/tool_errors.jsonl` before
follow-up decisions were meaningful. Consolidated into one tracker because the shared
trigger condition — "log accumulation is sufficient for empirical evaluation" — was
identical across all three.

---

## Re-Eval 1 — CC Noise Prefix Strip

**Status: COMPLETE 2026-05-30** — ran early (5 days of data; ~1 week accumulated).

**Result:** No new strippable patterns found. `strip_hook_prefix.py` is sufficient.
495 entries clustered across 6 buckets; all non-hook-prefixed content is agent-relevant (KEEP).
Cross-check confirmed strip reaches Anthropic (2,970 requests in 65 available proxy logs).

**Script:** `dev/tool_use_errors/A_error_cluster_audit.py`
**Report:** `dev/tool_use_errors/reports/2026-05-30_error_cluster_audit.md`

---

## Re-Eval 2 — rewrite_chained_sleep Audit

**Verdict at time of writing:** MONITOR — data too young to decide.

**Question:** was the narrow trivial-sync allow-list (`echo`, `true` as `cmd_before`)
the right scope for the hook? Are there load-bearing patterns wrongly stripped, or
trivial-sync patterns wrongly passed through?

**Data source:** `src/logs/hook_firing.jsonl` filtered on
`hook=rewrite_chained_sleep AND decision=rewrite`.

**Trigger date:** planned from ~2026-06-01 (≥ 7 days of live data).

**Eval method:**
1. Grep `hook_firing.jsonl` for all `rewrite_chained_sleep` fires.
2. Per fire: compare original command vs rewritten command.
3. False positives: rewritten command leads to unexpected behavior (verify via
   cross-reference with the session JSONL of the same session).
4. Missed cases: grep `tool_errors.jsonl` for sleep-related errors that would NOT
   have been caught by the allow-list.
5. If FP rate is unacceptable: tighten the allow-list OR revert to block-with-hint.
6. If coverage is too low: expand the allow-list with mixed tokens (`rag-cli search`,
   `bd` without `dolt-start`, etc.) via subcommand inspection.

---

## Re-Eval 3 — block_polling_loop Hook Audit

**Design note at time of writing:** built on attack surface A (single-call signature),
chosen with the explicit caveat that other polling variants could slip through.

**Question:** does the single-call signature (`ps -p` + `tail -N` in the same command)
catch the bulk of real-world polling loops? Or are there recurring other variants
(`while sleep; do tail; done`, plain repeated `tail` without a `ps` check, Python/jq
polling pipelines) that slip through?

**Data source:** `src/logs/hook_firing.jsonl` (filtered on
`hook=block_polling_loop AND decision=block` for caught cases) PLUS a counter-check
against raw session JSONLs (`~/.claude/projects/*/*.jsonl`) for uncaught cases with a
similar repetition pattern.

**Trigger date:** planned from ~2026-06-07 (≥ 2 weeks of live data).

**Eval method:**
1. Count `block_polling_loop` fires — how often did it trigger?
2. Forensics on polling anti-patterns in session JSONLs of the same period:
   - grep for `tail -N /tmp/` with monotonically incrementing N (≥ 5 calls in 60s)
   - grep for `while ... sleep ... done`
   - grep for `for ... do sleep ... done`
   - other repetitive Bash patterns
3. False negatives: patterns visible in session JSONLs but NOT caught by the hook.
4. If the false-negative rate is substantial:
   - attack surface B (cross-call repetition detection via a per-session state file)
   - OR attack surface C (session-JSONL frequency analysis on each Bash call)
   - re-run the trade-off analysis with the data then available.

---

## Combined Action at Trigger Date

A single session in ~2 weeks could work through all three re-evals at once — all three
data sources would be sufficiently grown by then, and all three share the same analytical
shape (grep the log, pattern detection, FP/FN assessment, decide the follow-up action).
Consolidating into one session saves setup overhead.

**Proposal:** at the re-eval trigger, run one session per topic in consolidation mode,
each producing a CHANGE-block update with the empirical findings and the decided
follow-up action. If a follow-up action needs substantial implementation: dispatch a
worker per topic.

---

## Sources

- `src/logs/hook_firing.jsonl` (data source 1)
- `src/logs/tool_errors.jsonl` (data source 2)
