# 2026-09-15 — the canonical line-edit form and its hook, reverted

## What happened and why, in order

Earlier this same session: `BASH_FILE_MODIFICATION_FORMS` was built in `src/constants.py`
(process-docs/cache), then `src/hooks/block_non_canonical_edit.py` was built on top of it — a
canonical, fingerprinted, line-numbered edit form for Bash, plus a hook enforcing it and blocking
every other form of modifying an existing file's content. `Edit`/`Write` had already been removed
from the model's toolset the day before (`process-docs/cache/2026-09-13_tool_cost_measurement.md`),
so this was meant to be the replacement path for editing.

**The hook went live in the real environment before its premise was checked against how other
agent harnesses actually approach this problem.** That check happened only afterward, took a
single pass, and reversed the decision outright:

- Aider explicitly evaluated line-number-based edit formats and rejected them — its own stated
  design principle is to avoid brittle specifiers like line numbers or line counts, its docs say
  models are terrible at working with source-code line numbers and make off-by-one errors even
  when GIVEN the numbers, its prompts instruct the model not to emit line numbers at all, and it
  carries roughly 750 lines of fuzzy search/replace matching specifically to avoid needing them.
- Anthropic's own editor and OpenHands' ACI editor both use `old_str`/`new_str` plus an
  insert-by-line command — neither addresses a REPLACEMENT by line range, which is exactly what
  this hook's canonical form did.
- SWE-agent is the one harness that does use line ranges, but it pairs that with two things this
  build had neither of: a linter that reverts the edit if it introduces a new syntax error, and a
  re-printed numbered window after every successful edit so the agent never works from stale
  numbers. This build had a fingerprint-on-first-line check instead of a linter, and no re-window
  step at all — a fingerprint mismatch aborts loudly, but nothing corrects the agent's mental model
  of the file afterward, and nothing catches a syntactically-valid-but-wrong edit that a linter
  would have caught.
- Separately, the token case had already collapsed on its own measurement, independent of any of
  the above: the canonical form's fixed boilerplate came out to 460 characters per call against a
  median literal-anchor of 285 characters in the same corpus this whole thread started from — the
  typical edit got MORE expensive under the new form, not cheaper. The original premise
  (`process-docs/cache/2026-09-13_tool_cost_measurement.md`'s Edit-vs-sed gap) was about a
  20-file, one-line-replacement-per-file synthetic corpus; the real corpus's edits were smaller
  and more varied than that synthetic benchmark assumed, and the fixed cost of the canonical
  form's own boilerplate ate the saving.

**The lesson for a successor, stated plainly because it is the part most worth carrying forward:**
a design premise was built, tested against a real corpus, activated in the live environment, and
enforced against real work — all before anyone checked what the field already knew about the same
question. The landscape check that overturned it was cheap and could have run first. Test against
reality (this session did that thoroughly, and the corpus-replay work stands on its own merits)
is not a substitute for checking whether the problem has already been studied elsewhere; both are
needed, and the order matters when one is much cheaper than the other.

## What was reverted, exactly

- `Edit`/`Write` taken back out of `TOOL_BLOCKLIST` in `src/constants.py` (32 entries now, was 34
  before this pair was added, 32 again — nothing else in the frozenset touched).
- `src/hooks/block_non_canonical_edit.py` retired via `git mv` to
  `src/hooks/block_non_canonical_edit.py.disabled`, following this repo's own established
  convention (`block_read_oversize.py.disabled`, `block_chained_sleep.py.disabled`, four others).
- Its entry removed from `_HOOK_SCRIPTS` in `src/hooks/hook_setup.py` (35 entries now, was 36).
- Its module entry and its four dedicated Gotchas removed entirely from `src/hooks/DOCS.md` —
  matching the established convention there: none of the other six `.disabled` hooks have any
  entry or Gotcha in that file either. The genuinely reusable insights from those four Gotchas
  (the two-pass heredoc-body recognition technique, the cross-package-import justification, the
  corpus-replay confounds, the unquoted-delimiter gap) are not lost — they live in this session's
  own process-docs entries (`2026-09-15_block_non_canonical_edit_hook.md`), which is where DOCS.md
  itself says implementation reasoning belongs, not in DOCS.md describing a module that no longer
  runs.

## What stays, unconditionally

`BASH_FILE_MODIFICATION_FORMS` in `src/constants.py` — untouched. `dev/cache/extract_bash_file_mods.py`
and `dev/cache/jsonl/` — untouched. Both are real measurements independent of what consumed them;
the classification of which Bash forms modify a file's content did not become less true because
the ONE canonical form built on top of it turned out to be the wrong ask. If a future hook wants
a different enforcement shape, this classification is still the correct starting point.

## The two dev/hook_smoke test files — decisions and the asymmetry between them

**`test_block_non_canonical_edit.py`: kept, and fixed to stay genuinely runnable.** Its `HOOK`
constant now points at `src/hooks/block_non_canonical_edit.py.disabled` — `python3 <path>` runs a
file regardless of extension, so this one-line reference update (the same class of change as
fixing `hook_setup.py`'s registration) keeps all 18 subprocess-driven cases passing for real, not
just nominally. Verified: 18/18 pass against the disabled file.

Its 19th case (added in the review round right before this reversal — a direct-import monkeypatch
forcing `_decide` to raise, to test the audible-fail-open diagnostic) was REMOVED, not left
broken. It required `import block_non_canonical_edit` by module name, which a `.disabled`-suffixed
file cannot satisfy — left in place, the whole script would crash with an uncaught
`ModuleNotFoundError` instead of reporting a clean pass/fail count, which is a worse failure mode
than any individual case failing. Removing it was judged the necessary consequence of the
retirement, not new scope, for the same reason fixing the `HOOK` path wasn't new scope either.

**`verify_block_non_canonical_edit_corpus.py`: kept, unmodified, documented as non-runnable.** It
imports the hook as a Python module (`from block_non_canonical_edit import _decide`), not via
subprocess — a plain `import` statement needs a `.py`-suffixed, importable name, which the
`.disabled` file no longer provides. Fixing this would mean adding
`importlib.util.spec_from_file_location`-style dynamic loading, machinery the script never needed
while the hook was live — that crosses from "necessary reference update" into "new capability for
a script whose target will never run live again," which the negative scope for this milestone
ruled out. Left as-is; `dev/hook_smoke/DOCS.md` now states plainly that it can't run and why. Its
value going forward is the corpus-replay methodology and the already-committed findings (the
confound categories, the anchoring-bug discovery), not re-execution — and the committed report
(`dev/hook_smoke/md/block_non_canonical_edit_corpus_report.md`) stays for the same reason,
traceable to the script that produced it.

**The asymmetry is deliberate, not an inconsistency:** one file needed a trivial, in-scope
reference fix to stay functional; the other needed genuinely new machinery that would have been
scope creep for code whose target is retired. Treating them the same either way (both fixed, or
both left broken) would have been the wrong call in one direction or the other.

## A real defect found as a side effect of this retirement, in a THIRD, unrelated file

While deciding what to do with `test_block_non_canonical_edit.py`, checked how the ONE other
`.disabled` hook with a surviving test (`block_chained_sleep.py.disabled` /
`test_block_chained_sleep.py`) handles the same situation, to see if there was an established
pattern to follow. There wasn't a functioning one: `test_block_chained_sleep.py`'s `HOOK` constant
still points at `src/hooks/block_chained_sleep.py`, the pre-disable path, which has not existed
since that hook was retired at some point before this session. Running it now: `python3` itself
reports "can't open file ... No such file or directory" and exits with status 2 for every single
case regardless of the case's actual command — and 2 also happens to be this hook family's own
BLOCK exit code, purely by coincidence. The result: the 5 cases that expect BLOCK (`chained before
sleep`, `non-echo-done cont`, `real sleep after quoted`, `cmd-subst sleep`, `backtick sleep`) all
report OK, having tested nothing about the actual (nonexistent) hook; the 8 cases that expect PASS
report FAIL, since `python3`'s own file-not-found code is never 0. The script's summary line
("FAILED: 8 case(s)") is honest about there being a problem, but reading only the per-case output
for the 5 BLOCK-expecting cases — a completely plausible thing to do when skimming — shows five
confident "OK"s that mean nothing at all. A test that reports PASS while never executing its
target is worse than no test, because it buys false confidence rather than none.

**Not fixed here.** Retiring `block_non_canonical_edit.py` is not licence to fix an unrelated,
pre-existing defect in a different hook's test, discovered only incidentally while looking for
precedent. Documented in `dev/hook_smoke/DOCS.md`'s Gotchas with the exact mechanism (stale
`HOOK` path, the exit-code-2 coincidence, and which specific cases flip to false PASS versus false
FAIL) so whoever picks it up next does not have to re-derive it from scratch. The fix, if someone
takes it on, is the same one-line `HOOK`-path update this session just gave
`test_block_non_canonical_edit.py` on its own retirement.

## Recap — 2026-09-15, session close

Self-check (`git diff integration --name-only`) confirms this milestone's full touched set:
`src/constants.py`, `src/hooks/hook_setup.py`, `src/hooks/DOCS.md`,
`src/hooks/block_non_canonical_edit.py.disabled` (renamed), `dev/hook_smoke/DOCS.md`,
`dev/hook_smoke/test_block_non_canonical_edit.py`, and this file.

DOCS.md staleness check found one real miss from the retirement commit itself, fixed during this
recap: `dev/hook_smoke/DOCS.md`'s corpus-replay-confound Gotcha ended with "see its own Gotcha in
`src/hooks/DOCS.md`" — a dangling reference, since that exact Gotcha was one of the four removed
from `src/hooks/DOCS.md` in the same commit that added this cross-reference's neighbor text. Fixed
by pointing it at `process-docs/tool_use_safety/` instead, which still holds the material. Lesson
for a successor: when a retirement removes documentation in one file, grep the REST of the repo's
DOCS.md files for cross-references into the part just removed, not only the file being edited —
this one was missed in the original commit and only caught here because the recap step checks
DOCS.md accuracy as a matter of course, not because anything flagged it directly.

Every other LOC heading re-checked against real `wc -l` after the fixes: `hook_setup.py` (211),
`test_block_non_canonical_edit.py` (131), `verify_block_non_canonical_edit_corpus.py` (115,
unchanged) — all correct. Smoke suite re-run clean: 18/18.

This closes out the `tool_use_safety` area for this worker's session. Three process-docs files
now exist for this one area from this session, each a closed, dated snapshot per the write-once
rule: `2026-09-15_block_non_canonical_edit_hook.md` (the build), and this file (the reversal). The
`cache`-area file from earlier the same session
(`process-docs/cache/2026-09-15_bash_file_modification_classification.md`) is a separate area,
untouched from here.
