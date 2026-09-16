# dual_log_cli comment/docstring salvage — 2026-09-16

## Context

Module-standards conformance pass over `dev/dual_log_cli/` (18 `.py` files: one probe plus
17 regression-suite files under `tests/`). The project standard allows exactly three comment
lines per module — `# INFRASTRUCTURE`, `# ORCHESTRATOR`, `# FUNCTIONS` — and no docstrings
anywhere. Every other comment and every docstring found in this directory is captured verbatim
below, then was deleted from the code. The three section markers were left untouched in the
code and are NOT repeated here — nothing was lost for them.

## Load-bearing docstring check

Grepped the whole directory for `__doc__` and `argparse` before deleting anything: zero hits.
No script in this directory uses `ArgumentParser(description=...)`, `epilog=`, `help()`, or
any other runtime read of `__doc__`. Every one of the 14 module docstrings found (all
module-level; zero function- or class-level docstrings exist in this directory) was pure
documentation prose, never consumed by running code. All 14 were deleted outright, not
rewired to a constant — there is nothing rewiring them TO.

## Script classification

All 18 scripts are read-only regression tests or a corpus-measurement probe. None import
`pyautogui`, `AppKit`, `Quartz`, or anything that drives the real macOS desktop, switches
Spaces, sends hotkeys, or restarts the monitor. All 18 were safe to run directly for
behaviour verification. `probe_sys_tool_original_chars.py` reads the real dual-log directory
(if present) and writes its own dated report under `dev/dual_log_cli/md/` — this is its
normal, pre-existing behaviour (see the sibling `2026-09-04` report already committed there),
not something this pass introduced.

## How the strip was done

Comments/docstrings were extracted with a small `ast` + `tokenize` script (module docstrings
via `ast.get_docstring` on `Module`/`FunctionDef`/`AsyncFunctionDef`/`ClassDef` nodes;
comments via `tokenize.COMMENT` tokens), salvaged into this file grouped by source file in
source order, then physically deleted from the source — full-line comments and docstring line
ranges removed entirely, trailing inline comments trimmed off their code line, three or more
consecutive resulting blank lines collapsed to one blank line, and a single stray leading
blank line (left behind where a module docstring used to open the file) stripped from the top
of 14 files. This was NOT done by hand — hand-editing 354 comments across 18 files invites
transcription slips; a token-position-based script that only ever deletes exactly what
`tokenize`/`ast` identified as a comment or docstring cannot accidentally touch a string
literal or a code line.

## Verification

Baseline stdout was captured for all 18 scripts BEFORE stripping
(`./venv/bin/python <script> > baseline.out`), then the identical command was re-run AFTER
stripping and diffed byte-for-byte against the baseline. All 18 are byte-identical, all still
exit 0. Post-strip, a second pass confirmed zero remaining comment tokens outside
`{# INFRASTRUCTURE, # ORCHESTRATOR, # FUNCTIONS}` and zero remaining docstrings anywhere in
the directory (checked with the same `ast`/`tokenize` script used to extract them, run
again post-strip).

## DOCS.md rewrite

The previous DOCS.md used a Purpose/Reads/Writes/Called by/Calls out shape per module already,
but every field ran well past the 25-word Purpose limit and the file carried a Role paragraph,
a Flow paragraph and a whole Gotchas section not in the mandated format. Rather than diff
paragraph-by-paragraph against the new, heavily-reworded/compressed version, the FULL previous
DOCS.md is salvaged verbatim below in one block — safer than guessing which exact sentences
counted as "cut" when nearly every sentence was reworded to fit the word limits. The new
DOCS.md's LOC figures were measured with `wc -l` AFTER the comment/docstring strip (not
before) — module-level LOC changed for every file that carried comments, e.g.
`probe_sys_tool_original_chars.py` 296 -> 230, `test_turns.py` 324 -> 251.

## For the next agent

- The comment-stripping script lived in `/tmp/` for this session and was never staged —
  it is not part of this repo. If another comment-standards pass is needed elsewhere, rebuild
  it: `ast.get_docstring` for docstrings, `tokenize.COMMENT` for comments, both keyed by
  `(lineno, col)` so a trailing inline comment is trimmed rather than deleting its whole code
  line.
- Every one of these 18 files independently duplicates its own `check()`/`_boundaries()`/
  `_delta_entry()`/`_local_clock()` helpers rather than importing a shared fixture module —
  this was already true before this pass (see the old DOCS.md's Gotchas section, salvaged
  below) and this pass did not change it; do not "fix" the duplication without checking
  whether that convention is intentional first.
- `dev/dual_log_cli/tests/test_reqs_gap.py`, `test_reqs_merged.py`, `test_reqs_rebuild_drop.py`
  and `test_reqs_turn_and_family.py` never had a module docstring to begin with (split out of
  `test_reqs.py` on 2026-09-16 per the old DOCS.md) — their comment counts are lower than the
  other 14 files for that reason, not because anything was missed here.

## Salvaged comments and docstrings, by file

Verbatim comments and docstrings removed from `dev/dual_log_cli/` during the module-standards
conformance pass. One heading per source file, content in source order. Section markers
(`# INFRASTRUCTURE`, `# ORCHESTRATOR`, `# FUNCTIONS`) are excluded — they remain in the code
unchanged, nothing was lost for them.

## Salvage from dev/dual_log_cli/probe_sys_tool_original_chars.py

Docstring (module, lines 1-32):
```

Corpus probe backing the design decision behind `duallog msgs`' sys/tool delta-tail feature
(src/dual_log_cli/overlay.py's `build_sys_tool_overlay`, src/dual_log_cli/render.py's
`_req_delta_lines`): is the LAST `_original` request's own `system`/`tools` lists a reliable source
for the ORIGINAL (pre-strip) size of any earlier request's sys/tool line, and is there a write-side
lag for system/tools the way there is for a trailing-msg total_tokens strip?

Measures, over every session on disk under the resolved dual_log directory:
  1. Whole-stripped tool coverage: every tool name the `_stripped` stream ever records with
     {"whole": True} must appear in the LAST `_original` request's own `tools` list, or its original
     size is unresolvable.
  2. Tool content stability: any earlier request's own tool-by-name content hash vs. the last
     request's, for every session with >=2 requests.
  3. System block stability, scoped to the indices that ever get a recorded strip (1, 2, 3 in every
     session observed) — the conversation family's FIRST real request vs. its LAST.
  4. Recording pattern: how many distinct stripped-stream lines ever carry a whole-tool strip or a
     system_delta entry for the rendered family, and whether the first such line is `is_first`.

Self-contained by convention (dev/ scripts do not import from src/): `_infer_family`, `_delta_hash`
and "last non-haiku line" below are deliberately simplified re-implementations for THIS probe's own
internal consistency, not the production helpers (`src/dual_log_cli/reader.infer_family`,
`src/proxy/logging._delta_hash`) — a stable-enough comparison within one probe run needs no more.

This is a measurement report, not a pass/fail test — see dev/dual_log_cli/tests/ for the regression
suite. Requires the real dual_log directory (MONITOR_CC_ROOT or the repo's own src/logs/dual_log/);
writes "no sessions found" and exits 0 if none exists, rather than failing.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/probe_sys_tool_original_chars.py

Writes its report to dev/dual_log_cli/md/probe_sys_tool_original_chars_<date>.md

```

Comment (lines 53-55):
```
# Resolve the dual_log directory the same way duallog_cli.discovery.resolve_dual_log_dir does,
# simplified: MONITOR_CC_ROOT, else this tree's own src/logs/dual_log, else — when run from inside
# a worktree, where the gitignored log directory never exists — the main checkout's copy.
```

Comment (lines 63-64):
```
# _HERE is already the dev/dual_log_cli DIRECTORY, one level shallower than a __file__ path —
# index 4 (not 5) lands on <main> for a worktree at <main>/.claude/worktrees/<name>/...
```

Comment (lines 73-74):
```
# Family bucket for a model string — haiku vs. sonnet vs. everything else ("opus"), matching the
# production three-way split closely enough for this probe's own internal comparisons.
```

Comment (lines 83-84):
```
# Stable content hash for a system block or tool dict — cache_control stripped, since it is a
# proxy bookkeeping key never present at the source and would otherwise mask identical content.
```

Comment (line 91):
```
# JSON-serialised size of a tool dict, matching what the wire actually carries
```

Comment (lines 96-97):
```
# The last non-haiku line of an _original stream, parsed; None if every line is haiku or the file
# is empty. Good enough for a probe — no sidecar/model-sniff fast path, just a straight parse.
```

Comment (lines 114-115):
```
# Every tool name the _stripped stream ever records with {"whole": True} for this stem, across all
# families/requests in the file.
```

Comment (line 132):
```
# Measurement 1: whole-stripped tool names vs. the last _original request's own tools list
```

Comment (lines 162-163):
```
# Measurement 2: tool content stability across a whole session (any earlier request's tool-by-name
# hash vs. the last request's)
```

Comment (lines 194-195):
```
# Measurement 3: system block stability, scoped to indices 1-3 (where a strip is ever recorded),
# family-first vs. family-last request
```

Comment (lines 230-231):
```
# Measurement 4: recording pattern — how many distinct stripped-stream lines ever carry a
# conversation-family whole-tool strip or system_delta entry, and whether the first is is_first
```

---

## Salvage from dev/dual_log_cli/tests/test_local_time.py

Docstring (module, lines 1-24):
```

Regression suite for the UTC-to-LOCAL timestamp conversion this area introduced 2026-09-04
(src/dual_log_cli/reader.py's `local_datetime`, and every renderer/filter built on it:
render.py's `fmt_timestamp`/`_clock`/`_window_date`, discovery.py's `filter_sessions` day
window, usage.py's `_epoch_from_iso`).

Covers: a Z timestamp renders as this machine's LOCAL wall clock (independently cross-checked
against a fresh `datetime.fromisoformat(...).astimezone()` computation, not just re-calling
`local_datetime` on itself); a day-boundary-crossing case built DYNAMICALLY from the machine's own
current UTC offset (never hardcoded, since the crossing direction depends on which side of UTC
this machine is on) proves `filter_sessions` lists a session under its LOCAL day, not the UTC day
its timestamp string happens to carry; `render._clock`/`fmt_timestamp`/`_window_date` all agree
with `local_datetime`; and `usage._epoch_from_iso` returns the TRUE UTC epoch of a Z timestamp,
regardless of the machine's own timezone (an epoch is timezone-independent by definition, unlike a
wall-clock string).

No dual-log directory or MONITOR_CC_ROOT required — every case is built from a literal ISO string
plus this machine's own timezone.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_local_time.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).

```

Comment (lines 54-56):
```
# A Z timestamp renders as this machine's LOCAL wall clock — cross-checked against a FRESH
# datetime computation (not just re-calling local_datetime on itself, which would only prove
# self-consistency, not correctness).
```

Comment (lines 69-70):
```
# render._clock / fmt_timestamp / _window_date all agree with local_datetime — the SAME
# conversion, not three independent (and possibly diverging) implementations.
```

Comment (lines 83-87):
```
# A day-boundary-crossing case built from THIS machine's own current UTC offset — never a
# hardcoded "23:30Z", since whether that crosses a local day boundary depends on which side of
# UTC the test machine is on. Anchored at local midnight +/- 30 minutes so the UTC calendar day
# and the LOCAL calendar day provably differ whenever the offset is nonzero (the common case; a
# UTC-zero machine makes this check vacuously trivial, not wrong).
```

Comment (line 92):
```
# East of UTC: local time just after midnight is still the PREVIOUS day in UTC.
```

Comment (line 95):
```
# West of UTC: local time just before midnight is already the NEXT day in UTC.
```

Comment (lines 116-117):
```
# usage._epoch_from_iso returns the TRUE UTC epoch of a Z timestamp — an epoch is timezone-
# independent by definition, so this must hold on ANY machine, unlike a rendered wall-clock string.
```

Comment (line 123):
```
# The rarer "...+00:00Z" shape (offset with "Z" appended) must resolve to the same epoch.
```

---

## Salvage from dev/dual_log_cli/tests/test_msgs_blocks.py

Docstring (module, lines 1-17):
```

Regression suite for `duallog msgs`' block sub-lines (src/dual_log_cli/render.py).

Covers: a multi-block msg renders one indented sub-line per block (type, chars, alignment),
a single-block msg stays byte-identical to the pre-sub-line format, tool_use sub-lines carry
the tool name and an is_error tool_result renders `tool_result!err` (both via the real
timeline.build_turns pipeline, not hand-built labels), and REQ separators are untouched.

All fixtures are synthetic and hand-built or fed through the real `message_summary` /
`timeline` pipeline — no dual-log directory or MONITOR_CC_ROOT is required, so this suite
depends only on the code under test.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_msgs_blocks.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).

```

Comment (lines 45-47):
```
# The LOCAL "HH:MM:SS" a UTC "...Z" timestamp renders as — computed the same way production code
# does (reader.local_datetime), so an expected string built from this is correct on ANY machine's
# timezone, not just the one this suite happened to be written on.
```

Comment (lines 52-53):
```
# A msg row shaped like timeline.build_turns' output, without going through it — used where the
# test wants to pin exact block chars rather than derive them from real block text.
```

Comment (lines 62-64):
```
# 25 msg-adding boundaries ending with one that opens msg index 70 — reproduces the exact
# `── REQ 25  14:49:03 ──` separator this feature's spec sample uses, via the real
# timeline.request_markers machinery (imported indirectly through render_msgs).
```

Comment (lines 78-79):
```
# Reproduces this feature's own spec sample byte-for-byte: a 3-block assistant msg (thinking,
# thinking, tool_use[Bash]) followed by a single-block tool_result msg, under a REQ 25 separator.
```

Comment (lines 100-103):
```
# render_msgs slices data["turns"] by LIST POSITION, not by msg["index"] — the two happen to
# coincide in production (build_turns enumerates in order) but this fixture only carries the
# two msgs it needs, at positions 0 and 1, while their "index" fields stay 70/71 for display
# and for the REQ-25 marker lookup.
```

Comment (lines 108-109):
```
# A single-block msg must render exactly the one line it rendered before this feature — no
# trailing sub-line, and the same `[idx] role type chars` column widths.
```

Comment (lines 121-122):
```
# A msg with N blocks must produce exactly 1 + N lines (parent + one sub-line per block), in
# block order, each sub-line carrying that block's own chars, not the msg total.
```

Comment (lines 137-141):
```
# Sub-line chars must right-align to the SAME column the parent line's chars use, regardless of
# label length — checked by column position, not by a fixed string, so it survives width tuning.
# Both labels here stay inside the block label field's width, same as the spec-sample fixture
# above; a label or chars value wide enough to overflow its own field is a documented, expected
# one-character (or more) jog — see the module's fixed-width Gotcha — not covered here.
```

Comment (lines 155-157):
```
# tool_use and is_error tool_result labels come from timeline._block_label via the real
# message_summary → build_turns pipeline, not from a hand-built dict — this proves the label
# grammar (`tool_use[Bash]`, `tool_result!err`) survives end to end into the msgs sub-line.
```

Comment (line 175):
```
# Force the error tool_result into a multi-block msg to exercise its sub-line label
```

Comment (lines 183-184):
```
# REQ separators must be untouched — same line for the same marker, whether the group's msgs are
# single- or multi-block.
```

---

## Salvage from dev/dual_log_cli/tests/test_msgs_overlay.py

Docstring (module, lines 1-21):
```

Regression suite for `duallog msgs`' strip/inject delta tail (src/dual_log_cli/render.py's
`_delta_tail` / `_msg_delta_tail` / `_block_overlay_totals`, fed by overlay.build_overlay).

Covers: an untouched msg or block line stays byte-identical to the pre-feature output (no tail at
all); a transformed line appends `  −N +M → Wc` (real minus sign, digit-grouped, wire size =
chars − stripped + injected) computed against THAT line's own chars value; a multi-block msg's
parent line carries the SUM over its blocks while untouched sub-lines stay bare; ` by REQ n` is
appended only when the transforming request differs from the group's own, and omitted on the
parent line when a msg's touched blocks disagree on which request touched them (never observed in
the corpus, but the omission is intentional, not an oversight).

All fixtures are hand-built dicts shaped like `render_msgs` expects (`boundaries`, `turns`, and an
`overlay` in the exact `{(msg_idx, blk_idx): {stripped, injected, req}}` shape `build_overlay`
returns) — no dual-log directory or MONITOR_CC_ROOT required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_msgs_overlay.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).

```

Comment (lines 60-61):
```
# A single-block, untouched msg renders exactly the pre-feature line — no tail at all, even when
# an overlay dict is supplied but has nothing for this coordinate.
```

Comment (line 68):
```
# The spec's own example: a single-block msg entirely stripped down to one injected char.
```

Comment (line 81):
```
# A transformed block whose owning request differs from the group's own gets " by REQ n" appended.
```

Comment (line 93):
```
# The SAME request performing the transform as the one that owns the group: no "by REQ" suffix.
```

Comment (lines 105-106):
```
# Multi-block msg: parent line sums stripped/injected over ALL blocks, a transformed sub-line
# carries its own figures, and an untouched sub-line in the SAME msg stays bare.
```

Comment (line 126):
```
# An untouched sub-line inside an otherwise-transformed multi-block msg stays exactly as before.
```

Comment (lines 140-142):
```
# A msg whose touched blocks were transformed by TWO DIFFERENT requests never appears in the
# corpus (measured: 0 of 1949), but if it did, the parent's aggregate line must not guess a single
# REQ — only the sub-lines, which each know their own, carry "by REQ".
```

Comment (line 161):
```
# A default (missing) overlay renders exactly the pre-feature output — additive parameter.
```

---

## Salvage from dev/dual_log_cli/tests/test_msgs_req_range.py

Docstring (module, lines 1-21):
```

Regression suite for `duallog msgs --req F [T]` (src/dual_log_cli/timeline.py's
`request_msg_range`/`resolve_req_range`) — translating a REQ number range into the msg-index
range `render_msgs` already knows how to handle, the way the FROM/TO positionals do today.

Covers: a single REQ number resolves to exactly its own group's msg range; a REQ range (F T)
spans from F's start to T's end; the LAST REQ of a session runs to the session's last msg index
(not to whatever its own group's natural end would otherwise be); an unknown REQ number raises
UnknownRequestNumberError; a REQ number that TWO different msg indices both carry — proven
possible even without a restart, via a trailing re-fire that adds no new msg — raises
AmbiguousRequestNumberError rather than silently picking either.

`request_boundaries` is exercised end to end against a real temp `_forwarded.jsonl`-shaped file,
matching this area's existing style (`test_msgs_sys_delta.py`) — no dual-log directory or
MONITOR_CC_ROOT required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_msgs_req_range.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).

```

Comment (line 56):
```
# One forwarded_delta line as addon.py's dual-log writer would shape it
```

Comment (line 71):
```
# Writes entries to a temp _forwarded.jsonl and runs the real request_boundaries over it
```

Comment (lines 83-84):
```
# Three ordinary, non-overlapping request groups: REQ 1 opens msg 0 (2 msgs), REQ 2 opens msg 2
# (3 msgs), REQ 3 opens msg 5 (4 msgs) — session has 9 msgs total, last index 8.
```

Comment (line 93):
```
# A single REQ number resolves to exactly its own group's msg range.
```

Comment (line 100):
```
# A REQ range (F T) spans from F's own start to T's own end.
```

Comment (lines 107-108):
```
# The LAST REQ of a session runs all the way to the session's last msg index, not to a
# next-marker boundary that does not exist.
```

Comment (line 115):
```
# An unknown REQ number raises UnknownRequestNumberError rather than an empty listing.
```

Comment (lines 126-130):
```
# A REQ number that TWO different msg indices both carry raises AmbiguousRequestNumberError.
# Reproduced WITHOUT a restart: a re-fire that adds no NEW msg (message_count does not exceed its
# own start_index) opens its own group at a start_index no earlier group used, but the running
# REQ-number counter does not advance for a non-adding boundary — so that group's owner is
# assigned the SAME number as the group before it.
```

Comment (lines 133-134):
```
# opens msg 0, adds, REQ 1
# start=2, count=2: re-fire, no add, stays REQ 1
```

---

## Salvage from dev/dual_log_cli/tests/test_msgs_sys_delta.py

Docstring (module, lines 1-22):
```

Regression suite for `duallog msgs`' sys/tool delta lines (src/dual_log_cli/timeline.py's
`_sys_lines`/`_tool_lines`/`request_boundaries`/`request_markers`, rendered by
src/dual_log_cli/render.py's `_req_delta_lines`). Name-based tool removal/rename coverage lives in
test_tool_name_comparison.py — this file's tool fixtures never shift a tool's index.

Covers: the family's first request lists every system block and every tool, no tag; a later
request lists only what its `system_delta`/`tools_delta` names, tagged `changed` for an index that
existed before and `new` for one beyond the previous request's count; a request whose only delta
is the excluded billing header (system index 0) prints no sys/tool lines at all; a re-fire group
shows the OWNER boundary's lines only; and an untouched separator (no `boundaries`, or a marker
with no delta) stays byte-identical to the pre-feature separator.

`request_boundaries` is exercised end to end against a real temp `_forwarded.jsonl`-shaped file
(`forwarded_delta` entries), so this suite depends only on that fixture and the code under test —
no dual-log directory or MONITOR_CC_ROOT required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_msgs_sys_delta.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).

```

Comment (lines 53-55):
```
# The LOCAL "HH:MM:SS" a UTC "...Z" timestamp renders as — computed the same way production code
# does (reader.local_datetime), so an expected string built from this is correct on ANY machine's
# timezone, not just the one this suite happened to be written on.
```

Comment (line 60):
```
# One forwarded_delta line as addon.py's dual-log writer would shape it
```

Comment (line 84):
```
# Writes entries to a temp _forwarded.jsonl and runs the real request_boundaries over it
```

Comment (lines 96-97):
```
# The family's first request: every system block and every tool listed, no tag at all — including
# the billing header (system index 0), which is excluded only on LATER requests.
```

Comment (lines 118-122):
```
# A later request: system index 0 is excluded even though it is present in system_delta (it
# changes on every request by construction and never invalidates the cache); an index seen before
# whose CONTENT actually differs is tagged "changed", an index never seen before is tagged "new",
# and an index seen before whose content is IDENTICAL (Edit here — carried in the delta but never
# actually touched, the write-side artifact this fix targets) is dropped, not tagged, not shown.
```

Comment (lines 147-150):
```
# A request whose delta is ONLY the billing header prints no sys/tool line at all — the common
# case, since the header changes on every request. tools=1 (not 0) throughout — a zero-tool entry
# is the UNRELATED sidecar shape `timeline._is_sidecar` excludes entirely (see
# test_sidecar_exclusion.py), which would swallow both boundaries here and defeat this fixture.
```

Comment (lines 164-166):
```
# render_msgs: a marker with no sys/tool lines prints the plain separator untouched (byte-
# identical to the pre-feature output); a marker WITH lines prints them directly under the
# separator, before the first msg line, in the block sub-line's indent/column layout.
```

Comment (line 190):
```
# A marker with no delta lines at all reproduces the exact pre-feature separator+msg pair.
```

Comment (lines 198-200):
```
# A re-fire group (two boundaries opening the same msg index) shows the OWNER boundary's sys/tool
# lines only — the same one whose timestamp the separator already carries — never the earlier
# member's.
```

Comment (line 206):
```
# re-fire: same start_index (0 messages added), OWNS index 0 because it is last in the group
```

---

## Salvage from dev/dual_log_cli/tests/test_msgs_sys_tool_overlay.py

Docstring (module, lines 1-32):
```

Regression suite for `duallog msgs`' sys/tool strip-inject delta tail
(src/dual_log_cli/overlay.py's `build_sys_tool_overlay`, rendered by
src/dual_log_cli/render.py's `_req_delta_lines`/`_delta_line`). Sibling to test_msgs_sys_delta.py
(the wire-based label/chars/tag lines this feature enhances) and test_msgs_overlay.py (the
message-level strip/inject tail this feature mirrors for sys/tool lines).

Covers: an untouched sys/tool line stays byte-identical when a sys_tool_overlay is supplied but
carries nothing for that coordinate; a transformed system line switches its leading chars from the
wire size to the ORIGINAL size (looked up in `data["payload"]["system"]`) and appends the same
`_delta_tail` a msg/block line carries; a description-stripped tool line does the same, looked up
in `data["payload"]["tools"]` by name, with its tail's wire figure the MEASURED wire chars
(`item["chars"]`) rather than derived from the recorded stripped TEXT length — the two are NOT
commensurable for a tool (JSON-encoded chars vs. raw description characters), a corrected defect
this suite pins with a fixture where they deliberately disagree; system index 0 (the per-request
billing header) is left completely untouched — wire chars, no tail — since it changes every request
by construction, so the last request's own copy is not a valid "original" for it; a tool the proxy
stripped WHOLE (absent from the wire tools_delta entirely, hence no line today) is synthesized as
its own standalone line with full strip and wire 0, attached to the marker whose own flow_id the
overlay recorded; a whole-stripped tool whose name cannot be resolved in `orig_tools` is skipped
rather than guessed; and a default (missing) sys_tool_overlay argument renders exactly the
pre-feature output.

All fixtures are hand-built dicts shaped like `render_msgs` expects, with `data["payload"]` added
for the original-size lookups this feature reads — no dual-log directory or MONITOR_CC_ROOT
required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_msgs_sys_tool_overlay.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).

```

Comment (lines 80-81):
```
# An untouched system line stays exactly as the pre-feature output when the overlay carries
# nothing for that coordinate — even with a payload and a (non-matching) sys_tool_overlay present.
```

Comment (lines 96-98):
```
# A transformed system line: leading chars becomes the ORIGINAL size (907, from data["payload"]),
# not the wire size (39307, the item's own "chars") — reproducing the real corpus example
# (opus_monitor_cc_1788464543 sys[2]: stripped 907, injected 39307, wire 39307).
```

Comment (lines 114-122):
```
# A description-stripped tool line: leading chars becomes the tool's FULL original size (name +
# full description, JSON-encoded), the tail's WIRE figure is the MEASURED wire chars
# (`item["chars"]`, exactly what `_tool_lines` computed before this feature) — never derived from
# the recorded stripped TEXT length, which is deliberately set here to a DIFFERENT number (raw
# description characters removed vs. the tool's JSON-encoded size delta are not the same unit,
# e.g. escaping) to prove the tail does not silently fall back to the wrong arithmetic. Reproduces
# the corrected defect: `tool[Bash]` on `opus_monitor_cc_1788464543`'s REQ 1 must show wire `517c`
# (the measured figure `_tool_lines` always computed), not a value derived from the 1,356-char raw
# stripped description text.
```

Comment (line 126):
```
# deliberately NOT original_chars - 50 (the raw stripped-text length below)
```

Comment (lines 133-134):
```
# Raw stripped description text is 50 characters — if the tail derived S from summing this
# (the pre-correction bug), the displayed wire would be original_chars - 50, not measured_wire.
```

Comment (lines 147-150):
```
# System index 0 (the billing header) changes on EVERY request by construction, so it is left
# completely untouched — wire chars, no tail — even when the overlay carries data for it (which
# would be wrong to apply: that data reflects THIS request's own strip, but the last request's
# system[0] is a DIFFERENT billing header entirely, not a valid "original" for this one).
```

Comment (line 156):
```
# last request's OWN sys[0]
```

Comment (lines 166-168):
```
# A tool the proxy stripped WHOLE never appears in the wire tools_delta (absent both before and
# after), so `marker["tool_lines"]` has no entry for it at all today — the overlay synthesizes a
# standalone line instead, full strip, wire 0.
```

Comment (line 173):
```
# no wire tool_lines at all
```

Comment (lines 188-189):
```
# A whole-stripped tool recorded under a DIFFERENT flow_id than the current marker is not shown
# here at all — it belongs under its own marker, never guessed onto this one.
```

Comment (lines 202-203):
```
# A whole-stripped tool whose name cannot be resolved in `orig_tools` (e.g. a stale/renamed entry)
# is skipped silently — showing nothing is preferred over guessing a size.
```

Comment (line 208):
```
# "GhostTool" absent
```

Comment (lines 215-216):
```
# A default (missing) sys_tool_overlay argument renders exactly the pre-feature output — additive
# parameter, matching test_msgs_overlay.py's own `test_default_overlay_unchanged` precedent.
```

---

## Salvage from dev/dual_log_cli/tests/test_msgs_usage.py

Docstring (module, lines 1-17):
```

Regression suite for `duallog msgs`' CR/CC prompt-cache separator (src/dual_log_cli/usage.py
and the usage-aware half of src/dual_log_cli/render.py).

Covers: `_req_separator`/`render_msgs` render `CR c  CC c` between the clock and the closing
`──` when a marker's flow_id resolves in the usage map (digit-grouped, no `c` suffix, re-fire
suffix staying OUTSIDE the `──` exactly as before), and render the pre-feature plain separator
when it does not — never a placeholder. `usage.build_usage_by_flow` is exercised end to end
against a FIXTURE `~/.claude/projects/`-shaped tree (a temp dir passed via `projects_root`, for
both a main-stem label match and a worker-stem sid8 match), so the suite depends only on those
fixtures — a plain Python file read, never a subprocess or the real, live-growing store.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_msgs_usage.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).

```

Comment (lines 48-50):
```
# The LOCAL "HH:MM:SS" a UTC "...Z" timestamp renders as — computed the same way production code
# does (reader.local_datetime), so an expected string built from this is correct on ANY machine's
# timezone, not just the one this suite happened to be written on.
```

Comment (lines 68-71):
```
# One fake `~/.claude/projects/<dir>/<uuid>.jsonl` transcript: a leading line carrying "cwd" (what
# project_map._first_cwd scans for) followed by one assistant record per (request_id, cr, cc)
# triple, all compact JSON (no space after ":") to match CC's own transcripts exactly — the
# literal fragment `_find_transcript` searches for has none either.
```

Comment (lines 87-88):
```
# render_msgs with a resolved usage map renders "CR 9,096  CC 1,928" between the clock and the
# closing "──", digit-grouped exactly like the msg lines' chars, with no "c" suffix.
```

Comment (lines 99-100):
```
# A marker whose flow_id is absent from usage_by_flow renders the plain pre-feature separator —
# no placeholder of any kind.
```

Comment (lines 112-113):
```
# A None usage_by_flow (the default) must render byte-identical to the pre-feature separator —
# proves the parameter is additive, not a behavior change for existing callers.
```

Comment (lines 124-125):
```
# The re-fire suffix stays OUTSIDE the closing "──", after any CR/CC — same position as before
# usage existed.
```

Comment (lines 139-140):
```
# _find_transcript scans plain Python file content — a hit inside `directories`, none outside
# them, and mtime filtering drops a file that predates the session's start.
```

Comment (line 155):
```
# an mtime cutoff no fixture file (written just now) can meet
```

Comment (lines 161-164):
```
# usage.build_usage_by_flow end to end for a MAIN stem: the stem's label ("fakeproject") is
# matched against a fixture project's cwd, its transcript resolves the right CR/CC, an owner
# with a non-200 status is dropped even though its request id would otherwise resolve, and the
# whole thing runs through a fixture projects_root — never the real store.
```

Comment (lines 190-191):
```
# The worker-stem path: sid8 is the real md5(cwd)[:8] hash, resolved to the project's cwd, and the
# worker's OWN transcript directory is that cwd plus the worktree layout every worker runs under.
```

Comment (line 203):
```
# The MAIN project's own directory — only its cwd is needed, to resolve sid8 -> cwd
```

Comment (line 205):
```
# The WORKTREE's directory — this is where the worker's own transcript actually lives
```

Comment (line 217):
```
# No boundaries, or no _response stream, degrades to {} rather than raising
```

---

## Salvage from dev/dual_log_cli/tests/test_project_display.py

Docstring (module, lines 1-24):
```

Regression suite for the PROJECT-over-CONTEXT rework (2026-09-10): `src/dual_log_cli/discovery.py`'s
`project_for_stem`/`display_stem`/`resolve_stem`/`filter_sessions`/`filter_by_family`, and
`src/dual_log_cli/render.py`'s `render_sessions`/`render_expand_full`'s new PROJECT column/header.

Covers: `project_for_stem` resolves a worker's sid8 to the PROJECT's own cwd (never the worker's
own worktree cwd) via a fixture `project_index`, resolves a main stem's label to a matching cwd,
and falls back to the sid8 (worker) / the label (main) / the raw stem (unparseable) when nothing
resolves; `display_stem` strips a worker's sid8 segment while preserving the trailing epoch, and
leaves a main stem (and an unparseable one) unchanged; `resolve_stem` accepts a substring of
either the full on-disk stem OR its displayed form against a real temp directory of empty
stem-shaped files, and raises ambiguity across the UNION of both match sets; `filter_sessions`
matches its `context`/`scope` needle against the PROJECT path OR the stem (case-insensitive),
identically for both parameters now that the CONTEXT string they used to differ over is gone;
`filter_by_family` reads the stem via `stem_identity` directly; `render_sessions` prints a
PROJECT column (widened to the longest path, no truncation) and a SESSION column using the
DISPLAYED stem; `render_expand_full`'s header prints `project   <path>` instead of the old
`context   <string>` line.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_project_display.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).

```

Comment (lines 61-62):
```
# A fixture project_index shaped exactly like project_map.build_project_index's own return value —
# no filesystem involved, so this suite never touches the real ~/.claude/projects/.
```

Comment (line 71):
```
# --- project_for_stem -------------------------------------------------------------------------
```

Comment (lines 100-102):
```
# No "_" at all -> stem_identity's own partition finds no tail -> returns None (see its
# Purpose) -- the one genuinely unparseable shape, unlike a body with several underscores
# (which always parses as SOME "main" identity, however meaningless the label).
```

Comment (line 114):
```
# --- display_stem ------------------------------------------------------------------------------
```

Comment (line 133):
```
# --- resolve_stem: matches the full stem OR the displayed form --------------------------------
```

Comment (lines 163-164):
```
# stem A's raw form and stem B's DISPLAYED form both contain "reldist-power" — the
# ambiguity check must consider the union of both match kinds, not just one.
```

Comment (line 176):
```
# --- filter_sessions: context and scope both match PROJECT path OR stem -----------------------
```

Comment (line 196):
```
# --- render_sessions: PROJECT column widened, SESSION uses the displayed stem ------------------
```

Comment (line 217):
```
# --- render_expand_full: the header's second line is "project", not "context" ------------------
```

---

## Salvage from dev/dual_log_cli/tests/test_reqs.py

Docstring (module, lines 1-34):
```

Regression suite for `duallog reqs` (src/dual_log_cli/render.py's `render_reqs`/`render_reqs_merged`,
and src/dual_log_cli/discovery.py's `filter_by_family`) — rewritten 2026-09-16 for the M6 redesign:
one fixed REQ line form (`REQ n   HH:MM:SS  CR c  CC c`, always, no elapsed/gap/shortfall tail
anywhere), every flag a pure filter/selector over it. Turn-grouping/separator coverage
(`_session_entries_and_separators`, `--turn`, the separator-survival rule) lives in
`test_turns.py`; this file covers the flat-listing shape and every filter/predicate/merge behavior
that does not need a turn concept — most fixtures here pass no `turns_by_stem`, which reproduces
the pre-M5 flat listing exactly (an empty `turns` list yields no openers, so `_grouped_lines` never
finds a separator to print).

Covers: the fixed CR/CC line form (resolved usage digit-grouped, unresolved usage as `CR ?  CC ?`,
CR padded to the widest value actually printed for that session so CC lines up); a session's REQ
lines match `msgs`' own numbers/timestamps exactly (re-fires collapsed, a restart handled
identically — built via the real `request_boundaries`/`request_markers`, matching this area's
established fixture style); multiple sessions blank-line separated, newest-first order preserved;
a session with zero requests still gets its `session <stem>` header and no REQ lines; the trailing
skipped-sessions note; an empty result set; `--gap MINUTES` (pairing rule and the "prints once"
rule for a REQ bracketing two adjacent qualifying gaps, no tail of any kind); `--merged` (two
sessions interleave in strict chronological order under one `merged <N> sessions` header, each
line tagged with its own session, combined with `--gap` using cross-session neighbors); `--rebuild`/
`--drop` (the CC>CR and CR(n)<CR(n-1)+CC(n-1) predicates, the strict-inequality boundary, REQ 1
never qualifying for `--drop`, the same-session predecessor rule holding under `--merged`, AND
combination, unresolved usage failing either flag outright); `--turn` narrowing precedence ahead of
`--gap`/`--rebuild`/`--drop`; and `filter_by_family`.

`request_boundaries` is exercised end to end against a real temp `_forwarded.jsonl`-shaped file —
no dual-log directory or MONITOR_CC_ROOT required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_reqs.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).

```

Comment (lines 62-64):
```
# The LOCAL "HH:MM:SS" a UTC "...Z" timestamp renders as — computed the same way production code
# does (reader.local_datetime), so an expected string built from this is correct on ANY machine's
# timezone, not just the one this suite happened to be written on.
```

Comment (line 69):
```
# One forwarded_delta line as addon.py's dual-log writer would shape it
```

Comment (line 84):
```
# Writes entries to a temp _forwarded.jsonl and runs the real request_boundaries over it
```

Comment (lines 96-98):
```
# A session dict carrying only what render_reqs/render_reqs_merged actually read — `_session_tag`
# derives the --merged tag straight from the STEM via `discovery.stem_identity`, so a realistic
# stem is what a fixture needs, not a fake context string.
```

Comment (lines 124-125):
```
# A session's REQ lines carry exactly the numbers, clock times and CR/CC `msgs` would show for the
# same flows, no separators (no turns_by_stem given -> flat listing, matching the pre-M5 shape).
```

Comment (line 142):
```
# A flow absent from the usage map renders "CR ?  CC ?" — never omitted, never a guess.
```

Comment (lines 151-153):
```
# A re-fire (adds no new msg) opens the SAME group as the boundary that eventually completes it
# and is collapsed into that group's number/timestamp, exactly as `msgs`' own separator does — no
# extra REQ line for the re-fire itself.
```

Comment (lines 157-158):
```
# start_index=2, re-fire (2<2 is False)
# start_index=2 too — same group, adds, owns it
```

Comment (lines 168-169):
```
# Multiple sessions stay in LISTING order (newest-first is the caller's responsibility, unchanged
# here) and are blank-line separated.
```

Comment (line 186):
```
# A session with zero requests still prints its own header, with no REQ lines beneath it.
```

Comment (line 193):
```
# The trailing skipped-sessions note, reused from `search`.
```

Comment (line 202):
```
# An empty result set renders "no sessions found", with the skipped note still appended if nonzero.
```

---

## Salvage from dev/dual_log_cli/tests/test_reqs_gap.py

Comment (lines 27-29):
```
# The LOCAL "HH:MM:SS" a UTC "...Z" timestamp renders as — computed the same way production code
# does (reader.local_datetime), so an expected string built from this is correct on ANY machine's
# timezone, not just the one this suite happened to be written on.
```

Comment (line 34):
```
# One forwarded_delta line as addon.py's dual-log writer would shape it
```

Comment (line 49):
```
# Writes entries to a temp _forwarded.jsonl and runs the real request_boundaries over it
```

Comment (lines 61-63):
```
# A session dict carrying only what render_reqs/render_reqs_merged actually read — `_session_tag`
# derives the --merged tag straight from the STEM via `discovery.stem_identity`, so a realistic
# stem is what a fixture needs, not a fake context string.
```

Comment (lines 86-87):
```
# --gap: one qualifying pair. REQ1->REQ2 is exactly the threshold (qualifies, prints both, NO tail
# of any kind); REQ2->REQ3 is a small gap (does not qualify) — REQ3 must not appear at all.
```

Comment (lines 91-92):
```
# +90m
# +5m
```

Comment (line 104):
```
# --gap: two adjacent qualifying gaps sharing REQ 2 — it prints exactly ONCE.
```

Comment (lines 108-110):
```
# +90m from f0 — qualifies
# +120m from f1 — qualifies
# +5m from f2 — does not qualify
```

Comment (line 120):
```
# --gap: no pair qualifies — the session prints ONLY its header line.
```

Comment (lines 132-133):
```
# --gap threshold is inclusive (>=): a gap of EXACTLY the threshold qualifies; one second short
# does not — floored to whole minutes, never rounded.
```

Comment (line 137):
```
# exactly +5400s = +90m
```

Comment (line 141):
```
# +5399s = 89m59s -> floors to 89m
```

---

## Salvage from dev/dual_log_cli/tests/test_reqs_merged.py

Comment (lines 27-29):
```
# The LOCAL "HH:MM:SS" a UTC "...Z" timestamp renders as — computed the same way production code
# does (reader.local_datetime), so an expected string built from this is correct on ANY machine's
# timezone, not just the one this suite happened to be written on.
```

Comment (line 34):
```
# One forwarded_delta line as addon.py's dual-log writer would shape it
```

Comment (line 49):
```
# Writes entries to a temp _forwarded.jsonl and runs the real request_boundaries over it
```

Comment (lines 61-63):
```
# A session dict carrying only what render_reqs/render_reqs_merged actually read — `_session_tag`
# derives the --merged tag straight from the STEM via `discovery.stem_identity`, so a realistic
# stem is what a fixture needs, not a fake context string.
```

Comment (lines 85-86):
```
# --merged: two sessions' REQs interleave in TIME, not in listing order, each line carrying its own
# session's tag (read straight off its stem).
```

Comment (lines 110-111):
```
# --merged --gap: a gap that exists WITHIN one session but is BRIDGED by another session's request
# must NOT qualify — the merged chain only ever compares GLOBAL chronological neighbors.
```

Comment (line 115):
```
# +95m from a0 — would qualify ALONE
```

Comment (line 118):
```
# +30m after a0, +65m before a1
```

Comment (line 127):
```
# --merged --gap: a gap that exists ACROSS sessions (nothing bridging it) DOES qualify.
```

Comment (line 130):
```
# +100m
```

---

## Salvage from dev/dual_log_cli/tests/test_reqs_rebuild_drop.py

Comment (lines 27-29):
```
# The LOCAL "HH:MM:SS" a UTC "...Z" timestamp renders as — computed the same way production code
# does (reader.local_datetime), so an expected string built from this is correct on ANY machine's
# timezone, not just the one this suite happened to be written on.
```

Comment (line 34):
```
# One forwarded_delta line as addon.py's dual-log writer would shape it
```

Comment (line 49):
```
# Writes entries to a temp _forwarded.jsonl and runs the real request_boundaries over it
```

Comment (lines 61-63):
```
# A session dict carrying only what render_reqs/render_reqs_merged actually read — `_session_tag`
# derives the --merged tag straight from the STEM via `discovery.stem_identity`, so a realistic
# stem is what a fixture needs, not a fake context string.
```

Comment (lines 89-90):
```
# --rebuild: only REQs where CC > CR. REQ 3 has no entry in the usage map at all and must be
# skipped, not shown with a "?" tail — an unresolved REQ fails the predicate outright.
```

Comment (line 98):
```
# f2 (REQ 3) unresolved
```

Comment (lines 108-110):
```
# --drop: REQ n qualifies when CR(n) < CR(n-1) + CC(n-1). REQ 2's CR (300) is exactly REQ 1's
# CR+CC (300) — the boundary, does NOT qualify (strict <). REQ 3's CR (250) is less than REQ 2's
# CR+CC (350) — qualifies, no shortfall figure printed anywhere.
```

Comment (line 128):
```
# --drop: REQ 1 of a chain never qualifies (no predecessor), even when its own usage resolves.
```

Comment (lines 138-139):
```
# --drop --merged: the predecessor is ALWAYS the previous request of the SAME session, never the
# merged chain's chronological neighbor.
```

Comment (line 164):
```
# A REQ whose own usage never resolves is skipped under EITHER flag.
```

Comment (line 179):
```
# --rebuild AND --drop combine with AND: a REQ must satisfy both.
```

Comment (line 192):
```
# Neither --rebuild nor --drop set: CR/CC still print (baseline behavior, not an opt-in tail).
```

---

## Salvage from dev/dual_log_cli/tests/test_reqs_turn_and_family.py

Comment (lines 28-30):
```
# The LOCAL "HH:MM:SS" a UTC "...Z" timestamp renders as — computed the same way production code
# does (reader.local_datetime), so an expected string built from this is correct on ANY machine's
# timezone, not just the one this suite happened to be written on.
```

Comment (line 35):
```
# One forwarded_delta line as addon.py's dual-log writer would shape it
```

Comment (line 50):
```
# Writes entries to a temp _forwarded.jsonl and runs the real request_boundaries over it
```

Comment (lines 62-64):
```
# A session dict carrying only what render_reqs/render_reqs_merged actually read — `_session_tag`
# derives the --merged tag straight from the STEM via `discovery.stem_identity`, so a realistic
# stem is what a fixture needs, not a fake context string.
```

Comment (lines 86-88):
```
# --turn combined with --gap: --turn narrows the candidate REQ sequence FIRST, so --gap's pairing
# walk only ever sees the turn's own REQs — a qualifying gap straddling the turn boundary (not
# inside the kept turn) must not leak a REQ from the OTHER turn into the output.
```

Comment (lines 109-111):
```
# turn 1
# turn 1, +5m from f0
# turn 2 (start=2<5, count=6>=5)
```

Comment (line 122):
```
# --turn N missing from a session prints only its header line.
```

Comment (lines 131-132):
```
# filter_by_family: --main keeps only opus-identifying stems, --worker keeps only
# worker-identifying stems, neither flag returns the list unchanged.
```

---

## Salvage from dev/dual_log_cli/tests/test_search_chars.py

Docstring (module, lines 1-19):
```

Regression suite for `duallog search`'s hit-line format (src/dual_log_cli/search.py's
`find_matches`, src/dual_log_cli/render.py's `render_search`).

Covers: a hit reports the block's original-payload chars (the same value `msgs`/`expand` show for
that block) instead of an occurrence count and a text snippet; a block with several occurrences of
the term still stays exactly ONE hit; a small genuine artifact and a larger prose hit are
distinguishable by their chars column at a glance; the `no match` case and the per-session
`session <stem>` header stay unchanged; and hit-line column alignment holds across sessions with
different label/chars widths.

All fixtures are hand-built payloads run through the real `find_matches`/`render_search` pipeline
— no dual-log directory or MONITOR_CC_ROOT required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_search_chars.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).

```

Comment (lines 46-47):
```
# A hit carries the block's chars, not an occurrence count or a snippet — and a block the term
# appears in twice still yields exactly one hit.
```

Comment (line 71):
```
# The rendered hit line: msg index, role, block label, right-aligned chars — no `×N`, no snippet.
```

Comment (lines 84-85):
```
# A genuine 9-char artifact and a larger prose hit are distinguishable by chars alone — the
# use-case this feature exists for.
```

Comment (line 99):
```
# no match stays exactly "no match", untouched by this change.
```

Comment (lines 106-107):
```
# Hit-line columns (label, chars) align across TWO sessions with different label/chars widths —
# both widths are computed over the combined result set, not per session.
```

Comment (line 116):
```
# the chars column ends at the same offset on both lines regardless of label/chars width
```

---

## Salvage from dev/dual_log_cli/tests/test_sidecar_exclusion.py

Docstring (module, lines 1-20):
```

Regression suite for excluding the zero-tool sidecar call from request boundaries
(src/dual_log_cli/timeline.py's `_is_sidecar`/`request_boundaries`), the session inventory
(src/dual_log_cli/discovery.py's `build_session`) and the last-conversation-request loader
(src/dual_log_cli/reader.py's `load_last_request`).

Covers: a sidecar `forwarded_delta` entry (`counts.tools == 0`, non-haiku) between two real
conversation requests seeds no boundary, no restart, and does not pollute the sys/tool delta
comparison the NEXT real request is tagged against; `discovery.build_session`'s `requests`/
`requests_main`/`messages` figures skip the same entry; and `reader.load_last_request` walks past
a sidecar `_original` line exactly like a haiku one, never returning it as "the conversation".

All fixtures are temp JSONL files shaped like the real dual-log streams — no dual-log directory or
MONITOR_CC_ROOT required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_sidecar_exclusion.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).

```

Comment (lines 50-52):
```
# One forwarded_delta line. tools=0 with is_haiku=False reproduces the security-monitor sidecar
# shape (own short system prompt, no tools, one message) that shares the real conversation's
# model name.
```

Comment (lines 75-79):
```
# A sidecar between two real conversation requests seeds no boundary at all, and the request
# after it is judged against the LAST REAL request, not the sidecar's reduced counts — so a tool
# byte-identical to what the real conversation already sent stays untagged as far as this check
# goes (its presence/absence in tools_delta is the proxy's call; here only the count-based
# threshold is under test).
```

Comment (lines 103-104):
```
# discovery.build_session's requests/requests_main/messages figures skip the sidecar the same way
# timeline.request_boundaries does, so the inventory's request count means the same thing.
```

Comment (lines 124-125):
```
# One _original-shaped line, as addon.py writes it: top-level model plus a nested payload carrying
# the real "tools" list load_last_request checks after parsing.
```

Comment (lines 136-138):
```
# load_last_request must never return a sidecar line as "the conversation" — it walks past a
# zero-tool non-haiku line the same way it already walks past haiku, landing on the real
# conversation request further back.
```

Comment (lines 156-157):
```
# A session whose last non-haiku line genuinely carries tools is completely unaffected — the
# common case, and the one every session on disk matches today.
```

---

## Salvage from dev/dual_log_cli/tests/test_tool_name_comparison.py

Docstring (module, lines 1-21):
```

Regression suite for `duallog msgs`' NAME-based tool comparison (src/dual_log_cli/timeline.py's
`_tool_lines`), rendered by src/dual_log_cli/render.py's `_req_delta_lines`.

Covers: a tool that shifts INDEX with byte-identical content prints nothing at all (the exact
false-positive `skill-help_1788343931` REQ 196 showed under index-based comparison: removing one
tool renumbers every tool after it, and each renumbered slot used to print `changed`); a tool
removed from the list (present before, absent now) prints `tool[Name] removed` with no chars
column; a tool whose OWN content changes at its new position still prints `changed`; a brand new
tool name prints `new`; and the exact skill-help shape (6 tools -> 5, one removed from the middle)
end to end via `request_boundaries` reproduces `tool[SendFeedback] removed` and nothing else.

`request_boundaries` is exercised end to end against a real temp `_forwarded.jsonl`-shaped file, so
this suite depends only on that fixture and the code under test — no dual-log directory or
MONITOR_CC_ROOT required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_tool_name_comparison.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).

```

Comment (lines 80-82):
```
# A tool removed from the middle of the list renumbers everything after it — the proxy's own
# per-POSITION delta includes every renumbered slot, but NONE of them actually changed content, so
# none should print a line; only the genuinely absent name gets `removed`, with no chars at all.
```

Comment (line 88):
```
# Grep removed: Write shifts from index 3 to index 2, byte-identical content
```

Comment (lines 103-104):
```
# A tool whose OWN content changes (not just its position) still prints `changed`, even while other
# tools are also shifting around it in the same request.
```

Comment (line 109):
```
# Bash removed; Grep shifts 1->0 unchanged; Write shifts 2->1 WITH a real content edit
```

Comment (line 122):
```
# A brand new tool name (never seen before) is tagged `new`, same as index-based comparison.
```

Comment (lines 135-137):
```
# A name removed and later reintroduced (a different request re-adds a tool of the same name) is
# tagged `new` again — presence is judged against the IMMEDIATELY preceding request's active set,
# not the tool's own history.
```

Comment (line 143):
```
# Grep removed (tools 2->1, no delta needed: index 1 just drops out of range)
```

Comment (lines 154-155):
```
# End-to-end reproduction of the real corpus case: skill-help_1788343931 REQ 196, 6 tools -> 5,
# SendFeedback removed from the middle, Skill and Write renumbered into its wake.
```

Comment (lines 173-174):
```
# render.py's _req_delta_lines: a `chars: None` item ("removed") skips the numeric chars column
# entirely — never prints a size for content that no longer exists.
```

---

## Salvage from dev/dual_log_cli/tests/test_turns.py

Docstring (module, lines 1-29):
```

Regression suite for `reqs`' turn grouping — rewritten 2026-09-16 for the M6 redesign: turn
grouping is now the DEFAULT, always-on shape of `reqs` output (no more opt-in `--turns` flag), and
a turn's own separator carries no per-request elapsed tail any more (removed along with every other
ADD-output tail) — only the amendment-kept span figure. Covers: src/dual_log_cli/timeline.py's
`_is_turn_opener`/`turn_openers`/`_turn_preview`/`_group_markers_by_turn` (unchanged by this
milestone — still the turn CONCEPT and assignment rule `render.py` groups by),
src/dual_log_cli/render.py's `_session_entries_and_separators`/`_grouped_lines`/`_fmt_duration`/
`render_reqs`'s always-on turn-grouping branch, and `--turn N` selection.

Covers: turn-opener classification (unchanged); the preview is the LAST `text`-type block of the
opener, not the first (unchanged); the turn-ASSIGNMENT rule this area's investigation found and
`_group_markers_by_turn` still owns — a request whose msg-index KEY (`start_index`) sits before the
next opener but whose OWN `message_count` already reaches past it belongs to the NEXT turn
(unchanged); `_fmt_duration`'s three duration bands plus its "?" passthrough (unchanged);
`_session_entries_and_separators`' separator format (turn number, first-request clock, SPAN = last
send minus first send within the turn, preview) reproducing the milestone's own worked example
byte-for-byte, now ALWAYS on rather than gated by a flag; a session with no turn opener falling
back to a flat, separator-free REQ list; `--turn N` selecting exactly one turn's separator plus its
own REQ lines, and printing only the session header when the session has no turn N; and the
separator-survival rule — a turn's separator prints only when at least one of its own REQ lines
survives an active `--gap`/`--rebuild`/`--drop` filter, and its own clock/span/preview never change
because of that filtering.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_turns.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).

```

Comment (line 104):
```
# --- turn-opener classification (unchanged by this milestone) --------------------------------
```

Comment (line 125):
```
# --- preview: last text block wins, not first --------------------------------------------------
```

Comment (line 139):
```
# --- the turn-assignment rule: message_count decides, not the marker's msg-index key ---------
```

Comment (lines 142-143):
```
# opener1 at msg 0, opener2 at msg 5. req3's OWN start_index (4) sits before opener2 (5), but
# its message_count (7) already reaches past it -- it must land in turn 2, not turn 1.
```

Comment (lines 154-156):
```
# req1: start=0, count=1
# req2: start=1, count=4
# req3: start=4, count=7
```

Comment (line 167):
```
# no opener at all
```

Comment (line 174):
```
# --- _fmt_duration bands (unchanged; kept for the turn separator's SPAN figure) ------------------
```

Comment (line 183):
```
# --- render_reqs: turn grouping is now the DEFAULT, always-on shape -----------------------------
```

Comment (lines 185-187):
```
# The milestone's own worked example, byte-for-byte — no flag needed any more to get turn
# separators; every REQ line also carries CR/CC (always-on since M6), not just the elapsed tail
# turn grouping used to add.
```

Comment (line 190):
```
# turn 1 opener
```

Comment (line 195):
```
# turn 2 opener
```

Comment (lines 199-202):
```
# REQ 1, turn 1 opener
# REQ 2, +9s
# REQ 3 (start=4 < opener2=5,
# but message_count=7 -> turn 2)
```

Comment (lines 209-211):
```
# CR is padded to the widest value across every REQ this call prints — turn 1's own two REQs
# AND turn 2's (no --turn narrowing here) — so REQ 3's 7-char "323,412" widens REQ 1/2's own
# padding too; this reproduces the milestone's own worked example literally.
```

Comment (line 225):
```
# no opener anywhere
```

Comment (line 246):
```
# --- --turn N: select exactly one turn -----------------------------------------------------------
```

Comment (line 285):
```
# --- separator-survival rule: a turn's separator prints only when a REQ of its own survives -----
```

Comment (line 290):
```
# only REQ 3 passes --rebuild
```

---

## Salvage from dev/dual_log_cli/DOCS.md

Full previous content of dev/dual_log_cli/DOCS.md before the module-standards conformance
rewrite (Role/Flow prose reworded, Modules compressed to fit the word limits, and the
Gotchas section removed entirely since it is not part of the mandated DOCS.md format):

```markdown
# dev/dual_log_cli/

## Role

Regression suite plus one measurement probe for `src/dual_log_cli/`. The suite proves each
`msgs`/`reqs`/`search`/`sessions`/`expand` rendering rule byte-for-byte against hand-built or
temp-file fixtures, driving the real `src.dual_log_cli.*` functions directly rather than
re-implementing their logic. The probe measures a real corpus question that informed a design
decision (whether the last `_original` request's own `system`/`tools` lists are a reliable source
for an earlier request's pre-strip size) and writes a report rather than asserting pass/fail.
Touch this directory when changing any `src/dual_log_cli/` rendering, filtering, or boundary rule;
each test file targets one feature area and is runnable standalone. Do NOT add fixtures that
require a live `MONITOR_CC_ROOT` or real `~/.claude/projects/` tree — every test file here builds
its own synthetic or temp-file fixtures precisely so it needs neither.

## Flow

A test script builds synthetic dicts shaped like `render_msgs`/`render_reqs` expect, or writes a
temp `_forwarded.jsonl`-shaped file and runs the real `request_boundaries` over it, then calls the
`src.dual_log_cli` function under test and compares the string/dict result against an expected
value via a local `check()` helper; a failure list drives the exit code. The probe instead globs
the real dual-log directory for every `*_original.jsonl`/`*_stripped.jsonl` stem pair, runs four
corpus-wide measurements, and writes a dated Markdown report to `md/`.

## Modules

### probe_sys_tool_original_chars.py (296 LOC)

**Purpose:** Measures, across every session on disk, whether the last `_original` request's own
`system`/`tools` lists reliably recover an earlier request's pre-strip size, and whether
system/tools writes lag the way a trailing-msg token strip does — backing the design behind
`overlay.build_sys_tool_overlay` and `render._req_delta_lines`.
**Reads:** every `*_original.jsonl`/`*_stripped.jsonl` pair under the resolved dual-log directory
(`MONITOR_CC_ROOT`, else the repo's own `src/logs/dual_log`, else the main checkout's copy when run
from a worktree).
**Writes:** `dev/dual_log_cli/md/probe_sys_tool_original_chars_<date>.md`; "no sessions found" and
exit 0 if the directory has no sessions.
**Called by:** none — run manually.
**Calls out:** none — deliberately self-contained; its `_infer_family`/`_delta_hash` are simplified
re-implementations, not `src.dual_log_cli.reader.infer_family` / `src.proxy.logging._delta_hash`.

---

### tests/test_local_time.py (148 LOC)

**Purpose:** Proves the UTC-to-local conversion (`reader.local_datetime`) matches an independently
computed `datetime.astimezone()`, that every renderer built on it (`render_format._clock`/
`fmt_timestamp`/`_window_date`, `discovery.filter_sessions`, `usage._epoch_from_iso`) agrees with
it, and that a day-boundary-crossing timestamp is filed under its LOCAL calendar day — the crossing
case is built dynamically from the running machine's own UTC offset, never hardcoded.
**Reads:** nothing external — literal ISO strings plus the running machine's own timezone.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.reader`, `.render_format`, `.usage`.

---

### tests/test_msgs_blocks.py (215 LOC)

**Purpose:** Proves `msgs`' block sub-lines (one indented line per block under a multi-block msg,
untouched single-block format, `tool_use[Name]`/`tool_result!err` labels sourced through the real
`timeline_turns.build_turns` pipeline, unchanged REQ separators).
**Reads:** nothing external — hand-built `render_msgs` input dicts, one case via the real
`build_turns` pipeline.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_msgs`, `.timeline_turns`.

---

### tests/test_msgs_overlay.py (189 LOC)

**Purpose:** Proves `msgs`' strip/inject delta tail (`−N +M → Wc`, digit-grouped, real minus sign)
computed from `overlay.build_overlay`'s `{(msg_idx, blk_idx): {...}}` shape: untouched lines stay
byte-identical, a multi-block parent sums its blocks' figures, `by REQ n` appears only when the
touched request differs from the group's own and is omitted when a msg's blocks disagree on it.
**Reads:** nothing external — hand-built `render_msgs` input dicts and overlay fixtures.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.render_msgs`.

---

### tests/test_msgs_req_range.py (171 LOC)

**Purpose:** Proves `msgs --req F [T]` (`timeline_markers.request_msg_range`/`resolve_req_range`)
resolves a single REQ or a range to the correct msg-index span, runs the last REQ to the session's
last msg index, and raises `UnknownRequestNumberError`/`AmbiguousRequestNumberError` for an unknown
or duplicate REQ number (the duplicate case reproduced via a non-adding re-fire, without a restart).
**Reads:** a temp `_forwarded.jsonl`-shaped file, written and deleted per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.timeline_boundaries`, `.timeline_markers`.

---

### tests/test_msgs_sys_delta.py (237 LOC)

**Purpose:** Proves `msgs`' sys/tool delta lines (`timeline._sys_lines`/`_tool_lines`/
`request_boundaries`/`request_markers`, rendered by `render._req_delta_lines`): the family's first
request lists everything untagged, a later request tags `changed`/`new` and drops the excluded
billing header (system index 0) and any byte-identical carried entry, and a re-fire group shows
only the owning boundary's lines.
**Reads:** a temp `_forwarded.jsonl`-shaped file, written and deleted per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_msgs`, `.timeline_boundaries`, `.timeline_markers`.

---

### tests/test_msgs_sys_tool_overlay.py (253 LOC)

**Purpose:** Proves the sys/tool strip-inject delta tail (`overlay.build_sys_tool_overlay`,
rendered by `render._req_delta_lines`/`_delta_line`): a transformed system/tool line shows the
ORIGINAL size (looked up in `data["payload"]`) with the tail's wire figure being the MEASURED wire
chars, never derived from the raw stripped-text length; system index 0 stays untouched; a
whole-stripped tool (absent from the wire delta entirely) is synthesized as its own line scoped to
the owning flow_id; an unresolvable whole-stripped name is skipped, not guessed.
**Reads:** nothing external — hand-built `render_msgs` input dicts with a `data["payload"]` added.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.render_msgs`, `.timeline_boundaries`.

---

### tests/test_msgs_usage.py (245 LOC)

**Purpose:** Proves the `CR c  CC c` prompt-cache separator renders when a marker's flow_id
resolves in the usage map and stays plain otherwise (never a placeholder), that
`usage.build_usage_by_flow` resolves both a main-stem (label-matched) and a worker-stem (sid8 ->
cwd -> worktree cwd) session end to end against a fixture `~/.claude/projects/`-shaped tree, and
that a non-200-status flow is dropped.
**Reads:** a fixture `projects_root` tree (temp dir) and a temp `_response.jsonl`-shaped file.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_msgs`, `.usage`, `src.proxy_display.forwarded_parser`.

---

### tests/test_project_display.py (262 LOC)

**Purpose:** Proves the PROJECT-over-CONTEXT rework: `discovery.project_for_stem` resolves a
worker's sid8 to the PROJECT's own cwd (never the worker's worktree cwd) via a fixture
`project_index`, with sid8/label/raw-stem fallbacks when nothing resolves; `display_stem` strips a
worker's sid8 while preserving the epoch; `resolve_stem` matches either the full on-disk stem or
its displayed form and raises ambiguity across their union; `filter_sessions` matches the PROJECT
path OR the stem; `render_sessions`/`render_expand_full` print the new PROJECT column/header.
**Reads:** a real temp directory of empty stem-shaped files (for `resolve_stem`).
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.render_expand`, `.render_sessions`,
`src.proxy_display.forwarded_parser`.

---

### tests/test_reqs.py (212 LOC)

**Purpose:** Proves `reqs`' fixed `REQ n   HH:MM:SS  CR c  CC c` line form: CR padded to the widest
value per session, unresolved usage as `CR ?  CC ?`, re-fires collapsed, multi-session blank-line
separation, a zero-request session's bare header, the trailing skipped-sessions note, and empty
results. Split 2026-09-16 from a single 552-LOC file that covered every `reqs` filter/selector;
the other filter/selector areas now live in the sibling `test_reqs_*.py` files below, each
independently runnable, matching this directory's per-feature-area convention.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_reqs_gap.py (153 LOC)

**Purpose:** Proves `reqs --gap MINUTES`: the pairing rule, the inclusive (`>=`) threshold floored
to whole minutes, and the "prints once" rule for a REQ bracketing two adjacent qualifying gaps —
split out of `test_reqs.py` 2026-09-16.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_reqs_merged.py (143 LOC)

**Purpose:** Proves `reqs --merged`: two sessions' REQs interleave in strict chronological order
under one `merged <N> sessions` header, each line tagged with its own session, and a within-session
gap bridged by another session's request does not qualify for `--gap` — split out of `test_reqs.py`
2026-09-16.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_reqs_rebuild_drop.py (211 LOC)

**Purpose:** Proves `reqs --rebuild`/`--drop`: the CC>CR and CR(n)<CR(n-1)+CC(n-1) predicates, the
strict-inequality boundary, REQ 1 never qualifying for `--drop`, the same-session predecessor rule
holding under `--merged`, AND combination, unresolved usage failing either flag outright, and the
plain-listing baseline with neither flag set — split out of `test_reqs.py` 2026-09-16.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_reqs_turn_and_family.py (153 LOC)

**Purpose:** Proves `reqs --turn` narrows the candidate REQ sequence ahead of `--gap`/`--rebuild`/
`--drop` (a qualifying gap straddling the turn boundary must not leak a REQ from the other turn),
`--turn N` missing from a session prints header-only, and `filter_by_family` (`--main`/`--worker`)
— split out of `test_reqs.py` 2026-09-16.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_search_chars.py (138 LOC)

**Purpose:** Proves `search`'s hit-line format (`search.find_matches`, `render.render_search`)
reports a block's original-payload chars instead of an occurrence count or snippet — one hit per
matching block regardless of how many occurrences it contains — and that hit-line columns align
across sessions with different label/chars widths.
**Reads:** nothing external — hand-built payloads run through the real `find_matches`/
`render_search` pipeline.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.render_search`, `.search`.

---

### tests/test_sidecar_exclusion.py (192 LOC)

**Purpose:** Proves a zero-tool, non-haiku sidecar `forwarded_delta` entry seeds no boundary, no
restart, and does not pollute the sys/tool delta comparison of the request after it
(`timeline._is_sidecar`/`request_boundaries`); that `discovery.build_session`'s request/message
counts skip the same entry; and that `reader.load_last_request` walks past a trailing sidecar line
exactly like a haiku one.
**Reads:** temp JSONL files shaped like the real dual-log streams, written and deleted per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.reader`, `.timeline_boundaries`.

---

### tests/test_tool_name_comparison.py (214 LOC)

**Purpose:** Proves `msgs`' NAME-based tool comparison (`timeline._tool_lines`): a tool that shifts
INDEX with byte-identical content prints nothing (the `skill-help_1788343931` REQ 196
false-positive under index-based comparison), a removed name prints `tool[Name] removed` with no
chars column, a name's own content change at its new position still prints `changed`, and a
reintroduced name is tagged `new` again rather than silently dropped.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.render_msgs`, `.timeline_boundaries`.

---

### tests/test_turns.py (324 LOC)

**Purpose:** Proves `reqs`' always-on turn grouping: opener classification
(`timeline_grouping._is_turn_opener`/`turn_openers`), preview is the opener's LAST text block, the
turn-assignment rule (a request's `message_count` reaching past the next opener assigns it to the
NEXT turn even when its own `start_index` sits before that opener), `_fmt_duration`'s bands, the
turn separator's exact worked-example format, `--turn N` selecting one turn, and the
separator-survival rule under an active `--gap`/`--rebuild`/`--drop` filter.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_format`, `.render_reqs`, `.timeline_boundaries`,
`.timeline_grouping`.

---

## Gotchas

**`check()`/`_local_clock`/`_delta_entry`/`_boundaries`/`_session` are duplicated verbatim across
every `test_reqs_*.py` file** (and across most other files in this directory) — this is the
established convention here, not an oversight: each test file is independently runnable with zero
cross-file imports, so a shared fixture helper is copied into every file that needs it rather than
factored into a shared module.

**A real minus sign (U+2212), not an ASCII hyphen, appears in every delta-tail string** —
`test_msgs_overlay.py` asserts on it literally; grepping for a hyphen instead silently finds
nothing.

**A tool's wire chars and its raw stripped-description-text length are NOT the same unit**
(JSON-encoding vs. raw characters) — `test_msgs_sys_tool_overlay.py` deliberately sets them to
disagree to catch code that derives the tail's wire figure from the wrong one; the correct source
is always the measured `item["chars"]`.

**`probe_sys_tool_original_chars.py`'s `_infer_family`/`_delta_hash` are intentionally simplified,
NOT the production helpers** (`reader.infer_family`, `src.proxy.logging._delta_hash`) — good enough
for one probe run's own internal comparisons, not a byte-identical substitute; do not import them
elsewhere expecting production behavior.

**The probe resolves a worktree's dual-log directory by indexing `parents[4]`** off its own
`__file__` path, assuming the fixed `<main>/.claude/worktrees/<name>/...` layout — silently falls
back to the (nonexistent, in a worktree) direct path if that layout ever changes.

**Every day-boundary case in `test_local_time.py` is built from the machine's OWN current UTC
offset at run time, never hardcoded** — on a UTC+0 machine the crossing assertion is vacuously
true rather than wrong, so a green run there is not full coverage of the crossing logic.
```

