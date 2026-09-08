# `reqs` M6 — one fixed line form, every flag a pure filter, 2026-09-16

Continues this area's `reqs` line (2026-09-04 command + `--gap`/`--merged`/`--rebuild`/`--drop`,
2026-09-10 `--turns` grouping). This entry records a redesign, not an extension: every prior
`reqs` iteration ADDED its own tail to the line — `--gap`'s `+Nm`, `--turns`' `+<elapsed>`,
`--rebuild`/`--drop`'s `CR c  CC c[  −N]` — so a reader had to know which flag combination was
active to know what a given tail even meant, and no two flags' tails could combine into one
coherent picture. M6 removes every one of those tails in favor of ONE line form, always the same,
with every flag reduced to deciding which lines of it print.

## The fixed form

```
session <stem>
── turn n  HH:MM:SS  SPAN  <preview> ──
REQ n   HH:MM:SS  CR c  CC c
```

Turn grouping (send-time-only spans, no transcript join — see the 2026-09-10 pivot entry) is now
the UNCONDITIONAL default shape, not opt-in behind `--turns`. CR/CC (via `usage.build_usage_by_flow`,
the same per-request join `msgs` has always used) is now UNCONDITIONAL per-line output, not a
`--rebuild`/`--drop`-only extra — `CR ?  CC ?` when a flow's usage never resolves, so the column
never disappears, it degrades. A session with no turn opener at all falls back to a flat,
separator-free REQ list — the one shape variation the fixed form still allows, and it falls out of
`_grouped_lines` never finding a separator to print for a `turn_number=None` entry, not a special
case.

## Every flag becomes a filter or a selector, never a renderer

- `--turn N` (new, replaces the boolean `--turns`): keeps only turn N of each session in scope.
  Filtering, not toggling a display mode — turn grouping itself is now always on, so "select turn
  N" is a well-defined operation whether or not `--turn` is given at all.
- `--gap MINUTES`: keeps only the REQs bracketing a qualifying pause — SAME pairing rule as
  before (`_bracket_gap_positions`, inclusive `>=`, floored whole minutes), just no more `+Nm` tail
  on the survivor.
- `--rebuild`/`--drop`: SAME predicates as before (`_rebuild_drop_qualifies`, now returning a
  plain `bool` — no shortfall figure left to compute), just no more `CR/CC[+−N]` tail — CR/CC
  prints on every line regardless, filter or not, so there is nothing left for these flags to add.
- `--merged`: unchanged in what it does (flattens every session into one chronological chain,
  tags every line) — only WHERE the tag lands moves, since a turn separator now exists to tag too.

**All flags compose via one pipeline, `render._apply_filters`, applied in a fixed order:** `--turn`
narrows first, then `--gap`, then `--rebuild`/`--drop`. This ordering was named explicitly in the
milestone ("`--turn` narrows first, then filters apply within it") rather than left to chance —
`--turn 1 --gap 5`, for instance, means "find qualifying gaps WITHIN turn 1's own REQs", not
"find qualifying gaps anywhere, then check whether either end happens to be in turn 1". Verified
directly: `dev/dual_log_cli/tests/test_reqs.py`'s `test_turn_narrows_before_gap_applies` builds a
fixture where a REQ from a DIFFERENT turn would otherwise bracket a qualifying gap with turn 1's
last REQ, and confirms it never leaks into a `--turn 1 --gap` result.

## The separator-survival rule, and why its content is invariant

"A separator prints only when at least one of its own REQ lines survives filtering" was the one
rule from the milestone that needed real design, because a turn separator's OWN clock/span/preview
are properties of the WHOLE turn (every REQ it groups, whether or not a filter keeps it), never of
whichever subset a filter happened to keep. Verified against real ground truth before writing any
render code: `reqs k-ratio --gap 60` (pre-M6 shape) selects REQ 46/47/393/394; cross-checked
against `reqs k-ratio --turns` (also pre-M6), REQ 46 is turn 4's LAST request and REQ 47 is turn
5's FIRST — i.e. each surviving REQ sits alone under its own turn separator, and that separator's
span is the turn's real span (turn 4: 50s, most of it spent on REQs that did NOT survive `--gap`),
not "0s" or some function of the one surviving line. This is why `_session_entries_and_separators`
precomputes `separators` as `{(stem, turn_number): text}` up front, entirely independent of
filtering, and `_grouped_lines` only ever decides whether to EMIT an already-fixed string, never to
recompute one.

## Data model: one entry tuple threaded through every mode

`(dt, stem, marker, tag, turn_number, usage, prev_usage)` replaces the pre-M6 `(dt, marker, tag,
usage, prev_usage)` shape — `stem` is new (needed as half of the separator-survival grouping key,
and to look up a session's own CR-padding width even inside a `--merged` chain's interleaved
lines), and `turn_number` is new (what `--turn` filters on, and the other half of that key).
`_entries_for_session`/`_merged_entries` keep their pre-M6 names and their pre-M6 guarantee —
`prev_usage` is precomputed while still walking ONE session, before any cross-session merge/sort,
so `--drop`'s predecessor stays same-session under `--merged` exactly as it always has — extended
to also carry `turn_number`, computed by the SAME `_group_markers_by_turn` walk `--turns` already
used, just no longer gated behind a flag.

## CR/CC column alignment — worked out from the milestone's own example, not guessed

The milestone's fixed-form example showed CR values padded to a column (`CR 7,771    CC 5,496` /
`CR 13,267   CC 7,006`) without stating the rule in words. Reverse-engineered from the literal
spacing: CR is left-justified to the WIDEST CR string actually being printed (a session with a
7-char CR value pads a 5-char one with 2 extra spaces), followed by a FIXED 2-space gap, then `CC
<value>` unpadded (the last column — no trailing whitespace, matching this area's own
`render_sessions` convention). Padding is computed from exactly the entries about to print
(`_cr_width_by_stem`, post every filter) — so a narrowed `--turn N` or `--gap` listing reads as its
own tight table rather than carrying padding sized for lines it no longer shows. Under `--merged`,
padding stays PER SESSION (the milestone's own wording), so two interleaved sessions' REQ lines can
carry different CR widths even though they're printed one after another — an accepted, literal
reading of "per session", not a bug.

## The amendment: span survives, per-REQ elapsed tail does not

The milestone's own first cut proposed dropping the turn separator's SPAN figure along with every
other tail ("derivable from the clocks already on screen"). An amendment superseded that one
line before implementation began: SPAN stays (`_fmt_duration`, unchanged), placed exactly where it
already sat pre-M6, with `--merged`'s tag now sliding in AFTER it rather than after the clock. Only
the PER-REQUEST elapsed tail (`+<elapsed>` since the previous REQ of the same turn, `--turns`' own
addition from 2026-09-10) was actually removed — it duplicated information the reader could already
get from two adjacent REQ lines' clocks, which SPAN (a single number for the whole turn) does not.

## Verification

- All five of the milestone's own ground-truth checks reproduced exactly against real corpus data
  (`MONITOR_CC_ROOT` pointed at the main checkout): `reqs reldist-power` (2 turn separators, 79 REQ
  lines, every one carrying CR/CC — REQ 1/2's own CR/CC figures match the milestone's illustrative
  numbers exactly, confirming they were drawn from this session, not invented); `reqs reldist-power
  --turn 2` (exactly the turn-2 separator plus REQ 78/79); `reqs k-ratio --gap 60` (REQ 46/47/393/394,
  each under its own turn 4/5/15/16 separator, matching the 2026-09-10 `--turns` entry's own turn
  count exactly); `reqs k-ratio --drop` (REQ 47 and 394, no shortfall figure); `reqs trading --since
  2026-09-06 --until 2026-09-06 --worker --merged` (k-ratio and reldist-power interleaved
  chronologically, tags on every REQ line and every turn separator, clean boundary between the two
  sessions' own blocks of turns).
- `--turn` composed with `--gap`/`--rebuild` and combined with `--merged` spot-checked directly
  against the corpus (`reqs reldist-power --turn 1 --gap 5`, `reqs k-ratio --gap 60 --rebuild`), no
  leakage across the `--turn` boundary observed.
- `sessions`/`search`/`msgs`/`expand` proven byte-identical before/after via `git stash` on real
  invocations against `trading`/`k-ratio` — none of the four's own code was touched by this
  milestone, and the CLI-level check confirms nothing shared with `reqs` (e.g. `render.py`'s msg
  rendering, `usage.py`) drifted incidentally.
- `dev/dual_log_cli/tests/test_reqs.py` and `test_turns.py` rewritten for the new form (31 and 27
  checks respectively, both new counts — every check from before M6 either ported with its tail
  expectation removed, or replaced by an equivalent covering the same behavior in the new shape);
  all other 11 suites under `dev/dual_log_cli/tests/` re-run unchanged and passing (230 checks
  total across all 13 suites).

## What was removed

`render.py`: `_turn_grouped_lines`, `_elapsed_req_lines`, `_gap_lines`, `_bracket_gap_lines`,
`_usage_tail`, `_rebuild_drop_lines`, `_rebuild_drop_gap_lines` — all superseded by the single
`_apply_filters`/`_grouped_lines` pipeline. `__main__.py`: the `--turns` boolean flag and its
`--merged`/`--gap`/`--rebuild`/`--drop` mutual-exclusion validation (no longer needed — every flag
composes now). `_fmt_duration` was NOT removed (see the amendment above) — still used, now only for
the turn separator's own SPAN.

## What was kept, and why

`_group_markers_by_turn`, `turn_openers`, `_is_turn_opener`, `_turn_preview`, `request_markers`'
`message_count` field (`timeline.py`, entirely untouched by this milestone — the turn CONCEPT and
its assignment rule did not change, only how many `reqs` modes read it, from "one, opt-in" to
"every one"). `_bracket_gap_positions` (kept, its per-position gap-tail value dropped — now a pure
candidate-position selector). `_rebuild_drop_qualifies` (kept, return type narrowed from a 3-tuple
to a `bool`). `_entries_for_session`/`_merged_entries` (kept by name, entry shape extended with
`stem`/`turn_number`).

## Relevant Symbols / Paths

- `render._session_entries_and_separators`, `_apply_filters`, `_grouped_lines`,
  `_cr_width_by_stem`, `_req_line`, `_usage_part`, `render_reqs`, `render_reqs_merged`
  (`src/dual_log_cli/render.py`)
- `_run_reqs`'s always-on `turns_by_stem`/`usage_by_stem` construction, the `--turn` argparse flag
  (`src/dual_log_cli/__main__.py`)
- `timeline._group_markers_by_turn`/`turn_openers`/`_turn_preview` — read, not modified, by this
  milestone (`src/dual_log_cli/timeline.py`)
- Ground truth: `api_requests_worker_1dda1c81_reldist-power_1788726467`,
  `api_requests_worker_1dda1c81_k-ratio_1788698865` (same two sessions the 2026-09-08/09/10 `turns`
  entries used)
- Area: this same area's `2026-09-04_reqs_command.md`, `2026-09-04_reqs_gap_flag.md`,
  `2026-09-04_reqs_merged_flag.md`, `2026-09-04_reqs_rebuild_and_drop_flags.md`, and
  `2026-09-10_turns_pivot_to_reqs_grouping.md` — every prior `reqs` design decision this entry
  builds directly on top of, tail removal aside
