# 2026-09-15 — The edit-addressing question, measured and then overturned (main session)

This is the main session's half of the work recorded from the worker's side in this same area and
in `process-docs/tool_use_safety/`. It holds two things the worker never had: the ad hoc
measurements taken directly on the extracted corpus, and the landscape check of other agent
harnesses that ended the whole line of work. The worker only ever received a summary of the
latter.

## Where this started

`process-docs/cache/`'s entries from 2026-09-13 and 2026-09-14 left an open question. The
2026-09-13 run measured the Edit tool against `sed -i` over 20 uniform one-line replacements and
found a 157-token-per-call gap, attributed structurally: Edit carries `old_string` verbatim to
locate its target, `sed -i '' '1s/.*/MARKER/'` addresses by line number and carries nothing. The
2026-09-14 entry then observed that the project, having removed Edit on the strength of that run,
was resending the old text anyway through `python3` heredocs that searched for a literal block. The
decision recorded there was to collect real usage data before changing the editing form.

That data collection is what the worker built this session (extraction script and classification,
recorded in this area's own worker entry). What follows is what the data then said.

## What the corpus actually contained

210 matched Bash calls, deduplicated, drawn from 13 sessions spanning 2026-09-14 and 2026-09-15.
A crude regex pass over the verbatim commands (throwaway script, `/tmp`, deliberately not kept)
classified them by shape. Categories overlap, one command can hit several:

| shape | count |
|---|---|
| none of the below | 118 |
| literal old/new via `.replace(` | 65 |
| an `assert` guarding the anchor | 53 |
| variables literally named `old` and `new` | 35 |
| `sed` addressed by a pattern | 17 |
| `sed` addressed by a line number | 5 |
| python addressing by line index | 2 |

The 118 with no shape are overwhelmingly heredocs creating new files, a large share of them worker
prompts written to `/tmp`. Among the calls that genuinely change an existing file, the Edit tool's
own shape dominates about nine to one over any form of line addressing. Thirty-five of them name
their variables `old` and `new`, which are the Edit tool's own parameter names.

This was the first concrete support for the hypothesis the user raised: the agent was not
improvising, it was reproducing a form it knows from training.

## How large the anchor actually was

Of the 210, 44 had a literal anchor that could be cut out cleanly by regex (triple-quoted `old =`
blocks, single-quoted `old =` assignments, and the first argument of `.replace(`). That 44 is a
lower bound on the real count, not a census — the extraction was crude by choice.

Across those 44 calls:

- 124,053 characters were sent in total.
- 32,080 of them were anchor, i.e. pure addressing. **25.9 percent.**
- Per call: minimum 2, median 285, mean 729, maximum 4,790 characters.

The mean sits far above the median because a handful of very large anchors pull it up.

**A caveat that was called out during the session and is worth repeating.** Converting those
32,080 characters into roughly 10,600 tokens used the 0.331 tokens-per-byte slope from the
2026-09-13 run. That slope was fitted on markdown prose cut from a statistics textbook. Applying
it to shell and Python with brackets, indentation and escapes is an extrapolation, and code
generally tokenizes worse than prose, so the figure is probably an underestimate — but it is an
estimate either way, not a measurement. Only the 32,080 characters are counted. The API's
`count_tokens` endpoint passes unmodified through this project's proxy and would give a real
number; that was offered and not taken.

## The measurement that killed the plan before the landscape check did

A canonical line-addressed form was designed and shipped as a hook (see
`process-docs/tool_use_safety/` for that hook's own history). Its fixed scaffolding — the heredoc
opener, the `path` and `edits` assignments, the read, the bottom-up loop, the fingerprint
comparison, the `SystemExit`, the slice assignment, the write-back and the closing delimiter —
measures **460 characters**, counted with `len()`, on every single call.

Against a median anchor of 285 characters, that is **175 characters more per typical edit, not
less**. The form only wins against anchors above 460 characters, which in this corpus means the
upper tail. The block message the hook emits on a violation is a further ~1,500 characters, about
five times the anchor of a single edit.

So the token argument — the entire original motivation, traceable to the 157-token figure from
2026-09-13 — inverted once measured against real main-session edits rather than 20 uniform
one-line replacements in a purpose-built corpus. The 2026-09-14 entry had explicitly warned that
those per-call numbers were not assumed to transfer. They did not.

## The landscape check

Four agent harnesses were examined through `gh-cli`, looking for how each addresses an edit. This
was one pass and it was decisive.

**Aider** (`Aider-AI/aider`) carries seven edit formats under `aider/coders/` — editblock,
editblock-fenced, udiff, udiff-simple, patch, wholefile and function-calling variants. **None of
them addresses by line number.** Its own write-up at `aider/website/docs/unified-diffs.md` states
that line-number-based formats were among the approaches explored and rejected, and lays out four
design principles, of which the second is: *"SIMPLE - Choose a simple format that avoids escaping,
syntactic overhead and brittle specifiers like line numbers or line counts."* That names both
halves of what had just been designed here — the line number and the total-line-count check.

The same document says outright: *"GPT is terrible at working with source code line numbers. This
is a general observation about *any* use of line"* numbers, and later, explaining why it prompts
for whole-block rather than surgical diffs: *"GPT can't reliably give us line numbers to specify
exactly where in the file to make changes."* A second, independent post,
`aider/website/_posts/2024-05-22-linting.md`, repeats it about linter output: *"LLMs are quite bad
at working with source code line numbers, often making off-by-one errors and other mistakes even
when provided with"* them. Its prompt files (`udiff_prompts.py`, `patch_prompts.py`) instruct the
model *"Don't include line numbers"* and *"Do not include line numbers."*

Aider's first principle is *"FAMILIAR - Choose an edit format that GPT is already familiar with."*
That is the same claim the user had made about why the agent reproduced the Edit tool's shape,
arrived at independently and backed by benchmark scores. Aider also carries
`aider/coders/search_replace.py` at 757 lines — a fuzzy-matching machine built to make string
anchors apply even when the model gets them slightly wrong. That is the cost they chose to pay
rather than use line numbers.

**Anthropic's own editor**, as reimplemented in SWE-agent under
`tools/edit_anthropic/bin/str_replace_editor`, is `str_replace` with `old_str`/`new_str`, plus
`insert` by line and an `undo_edit`.

**OpenHands' ACI** (`OpenHands/openhands-aci`, `openhands_aci/editor/`) exposes exactly the same
surface: `file_editor(command, path, file_text, view_range, old_str, new_str, insert_line,
enable_linting)`. Replacement is by string; only insertion takes a line number.

**SWE-agent** (`SWE-agent/SWE-agent`) is the one harness that does address replacements by line
range, with `edit <start_line>:<end_line>` followed by replacement text terminated by
`end_of_edit`. It ships that form in three variants under `tools/windowed_edit_*`. Two things it
pairs with the line range are exactly what was missing from the design here, read from
`tools/windowed_edit_linting/bin/edit`:

- It runs `flake8` before and after the edit. If the edit introduces a NEW syntax error, the edit
  is reverted with `wf.undo_edit()` and the agent is shown two numbered windows, captioned *"This
  is how your edit would have looked if applied"* and *"This is the original code before your
  edit"*, plus *"Your changes have NOT been applied... DO NOT re-run the same failed edit
  command."*
- On success it calls `wf.goto(start_line)` and `wf.print_window()` — it reprints the numbered
  window around the edit. **That is its answer to the stale-line-number problem: it does not ask
  the agent to do arithmetic and it uses no fingerprint, it simply hands back fresh numbers after
  every edit.** It also maintains a stateful "currently open file" with `open`, `goto`,
  `scroll_up`, `scroll_down`.

So of four harnesses, three address replacements by string, and the fourth pairs line ranges with a
linter-backed revert and an unconditional re-display. The design that had just been shipped here
had line ranges and neither safeguard.

## What was decided

The user's call, on seeing the above: restore `Edit` and `Write` and retire the hook. Done the same
session — `Edit` and `Write` came out of `TOOL_BLOCKLIST` (34 entries down to 32),
`block_non_canonical_edit.py` was moved to `.disabled` following the existing convention for
retired hooks, and its registration was removed from `hook_setup.py`. The live deregistration was
confirmed by grepping `~/.claude/settings.json` (zero hits) and by a `sed -i` on an existing file
running cleanly again.

`~/.claude/shared-rules/global/tool-use.md` and its English counterpart under `situational/` were
rewritten in the same session: a new file is still created with a quoted-delimiter heredoc
(the 2026-09-13 run measured that as cheaper per call than the `Write` tool, and much cheaper for
several files in one call), an existing file is changed with `Edit`, and an existing file is never
rewritten in full.

## Two things worth keeping from the dead end

**The form worked, it just cost more.** While the hook was live, the worker performed its entire
revert milestone — edits to `src/constants.py`, `src/hooks/hook_setup.py`, two `DOCS.md` files and
a test — through the canonical `LINEEDIT` form, because the hook blocked everything else. It
carried out the retirement of the very hook that was forcing it. So the form is usable in practice
by a current model. The objection to it is cost and the missing safety net, not that a model cannot
produce it.

**The classification and the corpus survive the reversal.** `BASH_FILE_MODIFICATION_FORMS` in
`src/constants.py` and the extraction under `dev/cache/` remain correct and are untouched. Any
future question about how this project writes files can be answered from
`dev/cache/jsonl/bash_file_mods_*.jsonl` without re-reading a gigabyte of proxy logs.

## The meta-lesson, stated plainly because it cost a whole session

The landscape check took ONE pass with `gh-cli` and overturned the premise. It was run AFTER the
classification, the extraction, the canonical form, the enforcing hook, its 19 smoke tests, its
corpus verification and its live activation were all built, reviewed, merged and shipped.

This project's own Phase 1 process has a step for exactly this. Its gap analysis requires naming
external channels — `gh`, `web`, `reddit` — for every gap, and states explicitly that one should
not weigh whether pulling in external sources is worth it. That step was skipped outright this
session. Nothing about the failure was subtle or required hindsight: the question "how do other
harnesses address an edit" was available from the first minute, the tooling to answer it was
installed, and the answer was one command away.

The trap worth naming for a successor is that this line of work looked purely internal. It was
framed as a cost measurement on our own corpus, and a cost measurement on one's own corpus feels
like the kind of question that has no outside literature. It had outside literature, with
benchmarks, from someone who had run the same experiment and published why it failed.
