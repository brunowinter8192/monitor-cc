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

## The fix — v1 (field-enumerated, REJECTED on review) and v2 (header-anchored, shipped)

**v1**, the first version, widened the alternation after the (already CC-2.1.258-tolerant)
userEmail line to a `# gitStatus` branch that enumerated all 5 fields the 3 corpus blocks
happened to carry, each with a fixed blank-line gap:

```python
r"# gitStatus\n"
r"This is the git status at the start of the conversation\. Note that this status is a "
r"snapshot in time, and will not update during the conversation\.\n\n"
r"Current branch: [^\n]*\n\n"
r"Main branch \(you will usually use this for PRs\): [^\n]*\n\n"
r"Git user: [^\n]*\n\n"
r"Status:\n.*?\n\n"
r"Recent commits:\n.*?\n\n"
```

**Review caught this as an unfalsified generalization.** Only the header sentence is stable per
the task's cited CC issue reports; the field list and blank-line structure were inferred from 3
corpus blocks, not from any stability guarantee. Two counter-examples from CC issue reports break
v1: **#86891** — a snapshot with only `Current branch` / `Main branch` / `Status`, no `Git user`
line and no `Recent commits` section at all; **#43250** — fields with NO blank lines between them
and `Status:` inline on one line (`Status: clean`). Neither would `fullmatch` against v1's rigid
5-field structure, so both would silently fall through to `_PRESERVE_PREAMBLE` again — the exact
failure this task exists to fix, just moved one CC-layout-change later. Worse: none of the 5
enumerated fields carries any protective value the fullmatch doesn't already get for free from the
preamble, the literal `brunowinter7934@gmail.com` email, and the `IMPORTANT:` footer — a block
that opens with the preamble, names that exact email, and closes with that exact footer IS the
env-context block regardless of what its gitStatus body contains.

**v2 (shipped)** anchors only the stable header sentence, then leaves the body free:

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
    r"snapshot in time, and will not update during the conversation\.\n"
    r".*?"
    r")"
    r"IMPORTANT: this context may or may not be relevant to your tasks\. "
    r"You should not respond to this context unless it is highly relevant to your task\.",
    re.DOTALL,
)
```

Design notes:
- Only the gitStatus header sentence is matched literally — the one piece of the section the
  task's cited CC issue reports actually describe as stable.
- The body after the header sentence is `.*?` (non-greedy, `re.DOTALL` newly added to the compiled
  flags for this reason) up to the literal `IMPORTANT:` footer — this accepts the 3 corpus shapes,
  both issue-report shapes (#86891's truncated field set, #43250's no-blank-lines/inline-status
  shape), the dirty `git status --short` variant, and a detached `HEAD` branch, all with the SAME
  pattern, because none of them are anchored at all.
- The non-greedy `.*?` is safely bounded because the corpus guarantees exactly one `IMPORTANT:`
  per block (verified in the measurement above) — a second `IMPORTANT:` occurring inside a commit
  message subject line would make the `.*?` stop early and the fullmatch fail, correctly falling
  through to `_PRESERVE_PREAMBLE` (fails safe: not stripped, not corrupted, just left whole like
  any other block the regex doesn't recognize).
- The tradeoff this widening accepts: a `# gitStatus` section that DOESN'T end right before an
  `IMPORTANT:` footer (e.g., if CC ever appends something after gitStatus but before the footer)
  would still `fullmatch` and strip, since the body itself is unconstrained. This is judged
  acceptable because the preamble + literal email + footer combination is not observed to occur
  outside the env-context/CLAUDE.md-context family at all (see `_PRESERVE_PREAMBLE`'s existing
  role for the sibling CLAUDE.md-context block), and a body-content check would reintroduce
  exactly the brittleness review rejected in v1.

**No other branch, guard, or template was touched.** `_PRESERVE_PREAMBLE` and its position, the
`_ENV_CONTEXT_RE` pre-guard position (checked before `_PRESERVE_PREAMBLE`), the pre-existing
`# currentDate` branch, every other `_SR_TEMPLATES` entry, and `strip_vocab.py` are all
unchanged — this task's scope was explicitly limited to widening the one regex.

## Tests added

`dev/proxy/test_strip_fix.py` T45-T51 (255 -> 262 checks, all pre-existing 255 confirmed passing
unmodified before writing any new test, again after v1, and again after the v2 correction):
- T45, T46 — the two `main`/`integration`-branch real corpus blocks, copied verbatim, both strip.
- T47 — synthetic dirty-status variant (`git status --short`-shaped lines with leading-column
  spaces), strips.
- T48 — synthetic `Current branch: HEAD` variant, strips.
- T49 — synthetic bundled `# claudeMd` + gitStatus block (unobserved in corpus, added by analogy
  to T44's bundled currentDate case), preserved whole.
- T50 — CC issue #86891 shape (only `Current branch`/`Main branch`/`Status`, no `Git user` line,
  no `Recent commits` section), strips. Added on review; would have FAILED against v1.
- T51 — CC issue #43250 shape (no blank lines between fields, inline `Status: clean`), strips.
  Added on review; would have FAILED against v1.

## Replay

`dev/proxy/replay_env_context_strip.py` widened: buckets are now split by FORM (`currentDate` vs
`gitStatus`) in addition to the existing stripped/left-pure/left-bundled/claudemd-preserved
dimension, and `_ENV_CONTEXT_RE_OLD` now quotes the regex immediately BEFORE this task's change
(i.e. already carries the CC 2.1.258 trailing-sentences tolerance, but still hard-requires
`# currentDate`) rather than the much older pre-2026-05-30 shape, so the before/after comparison
isolates exactly this task's effect. As of this task, over the 9-file/2218-entry corpus described
above (re-run after the v2 correction; the 9-file corpus grew from 2218 to 2252 entries between
the v1 and v2 replay runs — same 9 files, more requests logged in the meantime — the distinct
gitStatus-block count stayed at 3, as expected since it counts live sessions, not requests):

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
happen — see T49 above for the synthetic guard). The bucket counts are unchanged between the v1
and v2 regex shapes over this corpus — v1 and v2 agree on every occurrence actually seen so far;
v1's brittleness only shows up against the shapes it never saw (T50/T51's issue-report fixtures).

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
- **The v1/v2 rejection is the reusable lesson here, not just this task's outcome.** When a
  `fullmatch`-based strip already pins the block by preamble + a proxy-specific literal (this
  proxy's own hardcoded email) + a footer, do NOT additionally enumerate a variable body's
  internal field structure "for safety" — that enumeration adds no discriminating power (the
  three outer anchors already do the discrimination) and only adds guaranteed-to-break surface
  area against the NEXT CC layout change. Anchor the stable prose (a header sentence, a fixed
  literal), leave genuinely variable structure (a field list, a status listing, a commit log)
  fully free. Two live counter-examples (CC issues #86891, #43250) surfaced this on first review
  here, with real per-field variability, before this shipped — check any future SR-shape fix for
  the same generalize-from-N-samples mistake before calling it done.

## Recap 2026-09-13

Task closed. Both `_ENV_CONTEXT_RE` revisions (v1 field-enumerated, v2 header-anchored) and both
M1/M2 deliverables are complete on branch `envstrip`, worktree
`.claude/worktrees/envstrip/`, across two commits:
`417b7e3` (fix: widen env-context strip regex for gitStatus form — M1+M2, v1 regex) and
`343852f` (fix: anchor gitStatus strip on header only, not fields — the v2 review correction,
T50/T51 added).

**Self-audit** (`git diff integration --name-only`) — touched files, all inside this worktree:
`src/proxy/strip_sr.py`, `dev/proxy/test_strip_fix.py`, `dev/proxy/replay_env_context_strip.py`,
`dev/proxy/md/replay_env_context_strip.md`, `src/proxy/DOCS.md`, `dev/proxy/DOCS.md`, and this
process-docs file. No file outside this list was modified.

**Final state verified at recap time:** `python3 dev/proxy/test_strip_fix.py` — 262/262 passed.
`python3 dev/proxy/replay_env_context_strip.py` — runs clean, writes
`dev/proxy/md/replay_env_context_strip.md`. `src/proxy/DOCS.md` strip_sr.py LOC (161) and
`dev/proxy/DOCS.md` test_strip_fix.py LOC (1786) / replay_env_context_strip.py LOC (244) all match
`wc -l` on the files as left. No further DOCS.md drift found in either file for the modules
touched by this task.

**For whoever picks up the next env-context regex break:** read the "What the next reader should
know" section above in full before touching `_ENV_CONTEXT_RE` again — the v1/v2 rejection lesson
(anchor stable prose only, never enumerate a variable body's field structure) is the single most
valuable thing this task produced, more so than the fix itself.
