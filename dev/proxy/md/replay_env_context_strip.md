# strip_sr.py — env-context `_ENV_CONTEXT_RE` replay (gitStatus widening fix)

Corpus: `/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log` — 9 `*_original.jsonl` files, 2260 request entries. Counts below are UNIQUE (file, exact inner text) — dual-logs are cumulative snapshots, the same block reappears in every later request of the same session.

## Before / after, by bucket and form

"Before" is the live regex immediately prior to this task (already carries the CC 2.1.258 trailing-sentences fix, but still hard-requires `# currentDate`). "After" is the live regex with the `# gitStatus` alternation this task adds.

| Bucket | Form | Before | After |
|---|---|---|---|
| env-context, stripped | currentDate | 3 | 3 |
| env-context, stripped | gitStatus | 0 | 3 |
| env-context, left — PURE (no `# claudeMd`, genuinely broken) | currentDate | 0 | 0 |
| env-context, left — PURE (no `# claudeMd`, genuinely broken) | gitStatus | 3 | 0 |
| env-context, left — BUNDLED (`# claudeMd` + `# userEmail` in one block, preserved by design) | currentDate | 3 | 3 |
| env-context, left — BUNDLED (`# claudeMd` + `# userEmail` in one block, preserved by design) | gitStatus | 0 | 0 |
| CLAUDE.md context, preserved (no userEmail hint at all) | other | 0 | 0 |

## Totals across both forms

| Bucket | Before | After |
|---|---|---|
| env-context, stripped | 3 | 6 |
| env-context, left — PURE | 3 | 0 |
| env-context, left — BUNDLED | 3 | 3 |
| CLAUDE.md context, preserved | 0 | 0 |

Newly stripped by this fix (present in "after" stripped, absent from "before"): 3 distinct blocks — all are the gitStatus-form PURE-left bucket moving to stripped (the bug this task fixes; the current CC build emits `# gitStatus` and no `# currentDate` at all, so the pre-fix regex never matched it). The currentDate-form stripped count is unchanged before/after (this task only adds an alternation branch, it does not touch the pre-existing currentDate branch). The BUNDLED bucket is unchanged before/after for both forms because `_ENV_CONTEXT_RE.fullmatch` correctly never matches a block that also carries real `# claudeMd` project content — that block must stay preserved whole, losing the CLAUDE.md content would be worse than leaving the unstripped env-context noise inside it.

CLAUDE.md-context-preserved (no userEmail hint) count is IDENTICAL before/after by construction — the fix only widens `_ENV_CONTEXT_RE`, it does not touch `_PRESERVE_PREAMBLE` or its position; the count in this corpus window is a property of which sessions happen to be in the current rotating `dual_log/` window, not evidence the guard never fires (see `process-docs/strip_efficacy_audit/2026-07-28_template_catalog_efficacy_cc205.md`, which measured 2 pure CLAUDE.md-preserved occurrences in a different corpus window).
