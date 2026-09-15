# 2026-09-15 — Bash file-content-modification classification and extraction

## Task

Build one authoritative classification of "which shell forms change the content of a file",
living in `src/constants.py` because a later hook in `src/hooks/` will import the same list
(a hook cannot import from `dev/`). Alongside it, build a dev script that persists every Bash
tool call in the recorded dual-log corpus matching that classification, verbatim, before
`src/logs/dual_log/` rotates the sessions away. See `process-docs/cache/2026-09-13_tool_cost_measurement.md`
and `process-docs/cache/2026-09-14_main_session_edit_addressing.md` for the prior reasoning this
continues — the cost-per-call measurement that got Edit/Write removed from the model's toolset,
and the follow-up finding that a Bash edit still needs to be weighed against its own addressing
cost, not assumed free.

## Classification arrived at

`src.constants.BASH_FILE_MODIFICATION_FORMS`, 13 entries, each tagged with a determinacy:
`edit` (the command errors out if the target does not already exist — determinately modifies
existing content), `from_scratch` (the command errors out if the target already exists —
determinately creates new content), `undetermined` (ambiguous from the command text alone,
because the same syntax creates-or-overwrites depending on runtime state not visible in a log
line).

| label | determinacy |
|---|---|
| `sed -i` | edit |
| `perl -pi`/`-ni` | edit |
| `gawk -i inplace` | edit |
| `python open() mode r+` | edit |
| `python open() mode x` | from_scratch |
| truncating redirect `>` | undetermined |
| force-clobber redirect `>\|` | undetermined |
| appending redirect `>>` | undetermined |
| read-write redirect `<>` | undetermined |
| `tee -a` | undetermined |
| `tee` (default) | undetermined |
| `python open() mode w` | undetermined |
| `python open() mode a` | undetermined |

The task's starting set (`sed -i`, `cat >`, `cat >>`, `python3 -c`/heredoc with a write mode,
`tee -a`, `perl -pi`) is subsumed rather than listed literally: `cat >` and `cat >>` are one
instance each of the generic `>`/`>>` redirect operators, which also catch `echo >`, `printf >>`,
and any other command using the same shell syntax. The main session confirmed this generalization
was the right call and explicitly said not to go further than one addition.

**The one addition made**: the excluded family — `cp`, `install`, `dd`, `patch`, `git apply`,
`truncate`, `mv`, `rsync`, `curl -o`, `tar -x`, `unzip -o`, `git checkout --` — is named explicitly
in `dev/cache/DOCS.md`'s Gotchas section, with the line-draw reasoning (their content-mutation is
incidental to a different primary purpose, and "can overwrite a file as a side effect" has no
natural stopping point as an inclusion bar). It is NOT in `BASH_FILE_MODIFICATION_FORMS` — the
main session was explicit that this addition is documentation only, not a tenth-plus classification
entry, because a later hook consuming this list needs a completeness *decision* record, not a
report that could be mistaken for exhaustive coverage.

## Determinacy is per matched-form, not per record

A record's `matched_forms` is a list — one Bash command can trigger more than one form (e.g.
`sed -i 's/a/b/' f && cat > log`). The extraction script does not collapse this to one
determinacy per record. Of 207 persisted records: 16 matched only edit-determinate forms, 0
matched only the from-scratch-determinate form (`python open() mode x` had zero corpus hits — see
below), 185 matched only undetermined forms, and 6 matched a mix of an edit form and an
undetermined form within the same chained command.

## Calibration against the real corpus, before committing to the regex shapes

Before writing the final script, 1,333 deduplicated unique Bash commands (from the 13-14-session
corpus as it stood mid-session) were extracted to `/tmp/unique_bash_commands.jsonl` and every
candidate pattern was tested against them by hand before being written into `src/constants.py`.
This surfaced two things worth recording:

1. **A naive generic `>` pattern is unusable.** `(?<!>)>(?!>|\|)` alone matched 363 of 1333
   commands, dominated by `2>/dev/null` and `2>&1` — stderr redirection, not file-content writes.
   Excluding `/dev/null`/`/dev/stdout`/`/dev/stderr` targets and fd-duplication (`>&`) via
   negative lookahead brought that down to 125-127 genuine hits. This exclusion is baked directly
   into the `truncating redirect >` and `appending redirect >>` patterns in `src/constants.py`,
   not left to callers.

2. **Text-pattern matching cannot tell a real invocation from a quoted mention of one, and this
   is real in this exact corpus, not hypothetical.** The task's own claim that `tee -a` and
   `perl -pi` return zero real hits was verified precisely: both DO match in the raw corpus (2
   hits each), and both are quoting, not invocation — one is a `duallog search "tee -a" --only
   tool_use` / `duallog search "perl -pi" --only tool_use` call (searching logs for the term), the
   other is this exact task prompt's own bulleted description of the starting set, resent as
   ordinary conversation history on every later request of this session (the same
   self-discussion mechanism `dev/proxy_instrumentation/DOCS.md` already documents for
   `post_restart_verification.py`). The final corpus run surfaced the same effect for `sed -i`
   (a `duallog search "sed -i"` call), and for `<>`, `>|`, `gawk -i inplace`, and `tee` (default):
   this worker's own exploratory Bash calls, which construct or print those exact regex
   substrings as Python string literals while building this classification, get extracted as
   "matches" of their own subject matter. This is not a bug to fix here — building a real shell
   parser to eliminate it is out of scope and was not requested — but a successor must not read
   `matched_forms: ["tee -a"]` as proof that `tee -a` was actually run. The `command` field is
   carried in full specifically so this can be checked by hand.

## Extraction run against the real corpus

`dev/cache/extract_bash_file_mods.py`, run against the main checkout's `src/logs/dual_log/`
(15 `*_original.jsonl` files at run time — 13 stated at task-authoring time, 14 by the time
investigation started because this worker's own `editops` session had begun logging, 15 by the
time the script actually ran because a new `api_requests_opus_websearch_*` main session started
mid-task; the script globs at run time and hardcodes no session count for exactly this reason).

Raw `Bash` `tool_use` block occurrences before any deduplication: ~139,000 across the corpus (the
cumulative-payload duplication the task warned about — the same `tool_use` id reappears in every
later request of its session). After deduplication by `tool_use` id, scoped per session: 1,333
unique Bash calls in the calibration snapshot, growing to ~1,400+ by the time of the final run
(live corpus growth during this task, including this worker's own session). Of the deduplicated
calls, 207 matched at least one classification form and were persisted to
`dev/cache/jsonl/bash_file_mods.jsonl`, drawn from 13 of the 15 sessions present (two sessions —
one brand new — had zero matching calls). Restricting the raw-vs-deduplicated count to only the
tool_use occurrences that end up matching a form (rather than every Bash call in the corpus): a
snapshot taken seconds before the final run measured 16,600 raw matching occurrences collapsing
to 208 unique records, a ~80x deduplication factor; the delta against the script's own 207 is
corpus growth between the two runs, not a counting discrepancy — see the gitignored-runtime-data
gotcha `dev/proxy_instrumentation/DOCS.md` already documents.

## What a successor building the hook should know

- `BASH_FILE_MODIFICATION_FORMS` in `src/constants.py` is data only — patterns and determinacy
  tags, no matching function. The matching function (`_matching_forms` in
  `dev/cache/extract_bash_file_mods.py`) is NOT importable by a hook (it lives in `dev/`) and was
  deliberately kept there rather than promoted to `src/` — this task's scope was the classification
  and the extraction script, not the hook. A hook needs its own matching function importing only
  the constants, following the same tee-overlap resolution shown in
  `extract_bash_file_mods.py._matching_forms` (a `tee -a` match suppresses the redundant
  `tee (truncating)` match on the same command, since `tee -a` is more specific).
- The excluded family in `dev/cache/DOCS.md` is a decision to re-litigate, not a settled fence.
  Each excluded command should be judged on its own merits against whatever the hook actually
  needs to guarantee, since a hook's completeness bar differs from this task's.
- `python open() mode x` (the one from-scratch-determinate form besides the edit-only in-place
  editors) has zero hits in this corpus as of 2026-09-15. That is an absence-in-this-corpus fact,
  not evidence the pattern is wrong — same caveat the task gave for `tee -a`/`perl -pi` up front.

## Recap — 2026-09-15, later same session

Main review found one structural defect: in both touched files, imports sat ABOVE the
`# INFRASTRUCTURE` marker instead of below it. Code Standards says the marker is `Imports und
Konstanten` — the marker comes first, imports follow it. `src/hooks/block_po_read.py` is the
compliant shape in this repo (`# INFRASTRUCTURE` on line 1, every import under it);
`src/proxy/strip_sr.py` is the drifted one and was named explicitly as the anti-pattern, not the
model.

Fixed in `9bda8c8f`: moved `import re` below the marker in `src/constants.py`, and moved
`json`/`sys`/`from pathlib import Path` plus the `sys.path.insert`/`from src.constants import`
bootstrap below the marker in `dev/cache/extract_bash_file_mods.py`. Nothing else changed — same
LOC in both files (50 and 98), no regex touched, no re-run of the extraction, `dev/cache/DOCS.md`
needed no update since its `(98 LOC)` heading was already correct and no documented behavior
changed.

**Lesson for a successor**: when writing a new module in this repo, put `# INFRASTRUCTURE` on
line 1 before writing a single import. This worker wrote the import bootstrap first out of habit
(get `sys.path` working, then structure it), which put the marker in the wrong place relative to
the imports it's supposed to head. Write the marker first instead, every time.
