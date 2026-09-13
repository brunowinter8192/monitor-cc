# Env-context system-reminder strips again — CC dropped currentDate for gitStatus (2026-09-13)

**Topic:** `_ENV_CONTEXT_RE` in `src/proxy/strip_sr.py` widened again — the current CC build
replaced the `# currentDate` section with a `# gitStatus` section in the same bundled
`# userEmail` + date/status env-context block, and stopped emitting `# currentDate` at all.

## Problem

Same failure class as the 2026-09 CC 2.1.258 entry in this area, different shape. The regex
still hard-required a `# currentDate` section with a date line right after `# userEmail`. The
current CC build instead emits, after the (already-widened) `# userEmail` sentence:

```
# gitStatus
This is the git status at the start of the conversation. Note that this status is a snapshot in
time, and will not update during the conversation.

Current branch: main

Main branch (you will usually use this for PRs): main

Git user: Bruno Winter

Status:
(clean)

Recent commits:
19f939e docs: phase 4 section in main session entry
...

IMPORTANT: this context may or may not be relevant to your tasks. You should not respond to this
context unless it is highly relevant to your task.
```

No `# currentDate` anywhere, still exactly one `IMPORTANT:` footer. `fullmatch` failed, the block
fell through to `_PRESERVE_PREAMBLE` (same preamble as CLAUDE.md context blocks, same ordering
problem as every entry in this area), and reached the API unstripped in message 0 of every
session.

## Measurement

Scanned every `src/logs/dual_log/*_original.jsonl` in the main checkout at task time (9 files,
2218 request entries — the corpus has grown since the 7-file/1946-entry snapshot quoted in the
task prompt) for top-level standalone `<system-reminder>` blocks, using the same traversal
`_strip_system_reminders` actually uses (top-level `str`/`list[type=='text']` only, never
`tool_result`), deduplicated by (file, exact inner text):

- **gitStatus form:** 800 raw occurrences, 3 distinct blocks, 973-1045 chars each, from 3 sessions
  (`opus_monitor_cc`, `opus_monitor_cc` a second session, `opus_trading`). None carries
  `# currentDate`, none carries a second `IMPORTANT:`. All 3 have `Current branch:` either `main`
  or `integration`, `Status:` always `(clean)` in this corpus window (no dirty-status occurrence
  observed — T47's dirty-status fixture is synthetic, built from real `git status --short` output
  shape, not corpus-derived).
- **Pure currentDate form** (no `# claudeMd`): 416 raw, 3 distinct blocks — unchanged shape from
  the prior entry, still strips correctly.
- **Bundled `# claudeMd` + gitStatus form:** 0 occurrences in this corpus window. T49 in
  `test_strip_fix.py` is a synthetic fixture for this (structurally identical to T44's bundled
  `# claudeMd` + currentDate case) — added preemptively since the bundling behavior is known to
  happen for the currentDate form and there is no reason to expect CC's bundling logic
  distinguishes between the two date/status section kinds.

## The fix

Widened the alternation after the (already CC-2.1.258-tolerant) userEmail line to accept EITHER
the pre-existing `# currentDate\n...` branch OR a new `# gitStatus\n...` branch:

```python
_ENV_CONTEXT_RE = re.compile(
    r"As you answer the user's questions, you can use the following context:\n"
    r"# userEmail\n"
    r"The user's email address is brunowinter7934@gmail\.com\.[^\n]*\n"
    r"(?:"
    r"# currentDate\n"
    r"Today's date is \d{4}-\d{2}-\d{2}\.\s+"
    r"|"
    r"# gitStatus\n"
    r"This is the git status at the start of the conversation\. Note that this status is a "
    r"snapshot in time, and will not update during the conversation\.\n\n"
    r"Current branch: [^\n]*\n\n"
    r"Main branch \(you will usually use this for PRs\): [^\n]*\n\n"
    r"Git user: [^\n]*\n\n"
    r"Status:\n.*?\n\n"
    r"Recent commits:\n.*?\n\n"
    r")"
    r"IMPORTANT: this context may or may not be relevant to your tasks\. "
    r"You should not respond to this context unless it is highly relevant to your task\.",
    re.DOTALL,
)
```

Design notes:
- The gitStatus header sentence, and the `Current branch:` / `Main branch (...)`: / `Git user:` /
  `Status:` / `Recent commits:` labels are matched literally — per the task's cited CC issue
  reports, these labels are stable across CC versions; only their VALUES vary.
- `[^\n]*` after `Current branch:` / `Main branch (...):` / `Git user:` tolerates any single-line
  value, including the literal `HEAD` (detached-head state) for the branch — T48 pins this.
- `Status:\n.*?\n\n` (non-greedy, `re.DOTALL` newly added to the compiled flags for this reason)
  tolerates both `(clean)` and a multi-line `git status --short` listing with leading-column
  spaces (` M foo.py`, `?? bar.py`) — T47 pins the dirty variant. `re.DOTALL` is new on this
  compile call; every other branch in the alternation is unaffected because none of their own
  sub-patterns relied on `.` NOT matching newlines.
- `Recent commits:\n.*?\n\n` is the same non-greedy shape for the variable-length commit list.
- Both non-greedy `.*?` groups are safely bounded because the corpus guarantees exactly one
  `IMPORTANT:` per block (verified in the measurement above) — a second `IMPORTANT:` occurring
  inside a commit message subject line would make the `.*?` stop early and the fullmatch fail,
  correctly falling through to `_PRESERVE_PREAMBLE` (fails safe, not stripped, not corrupted).

**No other branch, guard, or template was touched.** `_PRESERVE_PREAMBLE` and its position, the
`_ENV_CONTEXT_RE` pre-guard position (checked before `_PRESERVE_PREAMBLE`), every other
`_SR_TEMPLATES` entry, and `strip_vocab.py` are all unchanged — this task's scope was explicitly
limited to widening the one regex.

## Tests added

`dev/proxy/test_strip_fix.py` T45-T49 (255 -> 260 checks, all pre-existing 255 confirmed passing
unmodified both before writing the new tests and after):
- T45, T46 — the two `main`/`integration`-branch real corpus blocks, copied verbatim, both strip.
- T47 — synthetic dirty-status variant (`git status --short`-shaped lines with leading-column
  spaces), strips.
- T48 — synthetic `Current branch: HEAD` variant, strips.
- T49 — synthetic bundled `# claudeMd` + gitStatus block (unobserved in corpus, added by analogy
  to T44's bundled currentDate case), preserved whole.

## Replay

`dev/proxy/replay_env_context_strip.py` widened: buckets are now split by FORM (`currentDate` vs
`gitStatus`) in addition to the existing stripped/left-pure/left-bundled/claudemd-preserved
dimension, and `_ENV_CONTEXT_RE_OLD` now quotes the regex immediately BEFORE this task's change
(i.e. already carries the CC 2.1.258 trailing-sentences tolerance, but still hard-requires
`# currentDate`) rather than the much older pre-2026-05-30 shape, so the before/after comparison
isolates exactly this task's effect. As of this task, over the 9-file/2218-entry corpus described
above:

| Bucket | Form | Before | After |
|---|---|---|---|
| stripped | currentDate | 3 | 3 |
| stripped | gitStatus | 0 | 3 |
| left — PURE | currentDate | 0 | 0 |
| left — PURE | gitStatus | 3 | 0 |
| left — BUNDLED | currentDate | 3 | 3 |
| left — BUNDLED | gitStatus | 0 | 0 |
| CLAUDE.md-preserved | other | 0 | 0 |

All 3 gitStatus-form blocks move from left-PURE (the bug) to stripped; the currentDate-form
stripped/left-BUNDLED counts are byte-identical before/after, confirming the fix is additive only.
The gitStatus-form BUNDLED count is 0/0 (unobserved in this corpus window, not asserted to never
happen — see T49 above for the synthetic guard).

## What the next reader should know

- The corpus this task measured against (9 files, 2218 entries) is LARGER than the 7-file/1946-
  entry corpus quoted in the task prompt — `dual_log/` is a live, growing/rotating directory in
  the main checkout, not a frozen fixture. Any future re-measurement will see different raw counts
  and possibly a different file count; the DISTINCT-block counts (3 and 3) are the numbers likely
  to stay stable, since they reflect the number of live sessions, not requests.
- If CC changes the gitStatus section's own structure again (e.g. drops the `Main branch (...):`
  line, or reorders sections), the fix here follows the same pattern as this task and the 2026-09
  CC 2.1.258 entry: widen the specific literal/label that broke, keep everything else anchored,
  re-verify against `dev/proxy/replay_env_context_strip.py`'s left-PURE bucket for that form before
  declaring victory.
