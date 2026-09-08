# `turns` removed; `reqs --turns` replaces it — the REQ list grouped, not a transcript-joined split, 2026-09-10

Continues this area's `turns`/`reqs` lines (`2026-09-08_turns_command.md`,
`2026-09-09_turns_per_request_detail.md`). This entry records a PIVOT, not an extension: the
`turns` subcommand answered a different question than the one the user actually asked, and was
removed rather than patched.

## What `turns` was, and why it was the wrong shape

`turns <session>` (M1) and `turns <session> N` (M2) computed, per turn, a duration split into
model time (summed per-request stream time, via a SECOND transcript join reading CC's own
assistant-record timestamps) and tool time (the gaps between them), plus per-request tool_use
names. It was technically correct — verified against an independent orchestrator probe down to
the exact request count and output-token totals on two real sessions — but the actual ask,
restated directly in this milestone's own problem statement, was simpler and different: "the REQ
listing itself grouped into turns, with the elapsed time between consecutive requests visible, so
that a slow stretch can be located by reading the list — no transcript join, no model/tool split,
no token column." `turns` built a NEW view instead of grouping the view that already existed
(`reqs`), and required a transcript join the user never asked for.

## The replacement: `reqs --turns`, an additive flag on the existing command

Rather than a new subcommand, `--turns` groups `reqs`' own REQ lines under turn separators. The
key simplification this pivot enabled: a turn's SPAN is now just its last request's send minus its
first (`request_markers`' own `timestamp`) — no transcript join, no stream-end time, nothing CC's
own store needs to supply. The elapsed tail on each REQ line (`  +<elapsed>`) is the SAME
send-to-send gap, computed within the group instead of across it, and reset at each turn's own
first request (which therefore never carries a tail — visible directly in the milestone's own
worked example: REQ 78, turn 2's first request, carries none, even though REQ 77 immediately
precedes it in the whole session).

## What was reused unchanged, and why it still applied

The turn-assignment rule itself — a request belongs to the turn whose opener is the LATEST one
already contained in that request's own `message_count`, not the msg-index key `request_markers`
groups it under — did not change at all. It was never specific to the transcript-joined duration
`turns` computed; it is purely about which requests belong to which turn, a question `--turns`
asks just as much. `_group_markers_by_turn`, `turn_openers`, `_is_turn_opener`, `_turn_preview`,
and `request_markers`' `message_count` field all carried over untouched. `_fmt_duration` also
survived, repurposed from formatting transcript-joined durations to formatting send-time gaps —
the one function that turned out to be genuinely reusable across both designs.

## What was removed, and confirmed dead

`timeline.py`: `build_turn_rows`, `build_turn_requests`, `_tool_use_names`,
`_tool_use_name_from_label`, `UnknownTurnNumberError` (plus the now-unused `local_datetime` import
— both removed functions were its only callers in this module). `usage.py`:
`build_request_times_by_flow`, `_transcript_stream_ends` (`_resolve_session_transcript` — the
shared preamble both this and `build_usage_by_flow` used — stayed, since `build_usage_by_flow`
still needs it). `render.py`: `render_turns`, `_turn_line`, `render_turn_detail`,
`_turn_detail_line`, `_fmt_tokens`, `_TURN_NUMBER_WIDTH`, `_TURN_DURATION_WIDTH` (the last two
dead once their only callers went — the milestone's own worked example confirmed neither the turn
number nor the elapsed/span figures are padded in the new output, so neither constant had a
replacement use). `__main__.py`: the `turns` subparser, `_run_turns`, and the
`args.command == "turns"` dispatch line. Confirmed dead by grep across the whole package after
removal — no lingering references outside historical Gotcha/process-docs prose.

## Design of the replacement

`_run_reqs` validates `--turns` against `--merged`/`--gap`/`--rebuild`/`--drop` FIRST, before
`list_sessions` ever runs (two usage errors: one naming `--merged` specifically, since "turns are
computed per session" is a distinct reason from the other three, which are rejected together).
When accepted, the per-session load loop additionally retains `data["turns"]` (already built by
`load_timeline` for every `reqs` mode — this is genuinely free, not a new cost) into a
`turns_by_stem` map, mirroring exactly how `usage_by_stem` is already conditionally built for
`--rebuild`/`--drop`. `render_reqs` gets one new optional parameter, `turns_by_stem`, and an
entirely separate branch ahead of its existing `filtering` logic — the pre-existing branch is
untouched line for line, which is what keeps plain `reqs` (and `--gap`/`--merged`/`--rebuild`/
`--drop`) byte-identical.

## Verification against the milestone's own ground truth

`reqs reldist-power --turns`: 2 turns. Turn 1: 77 REQ lines, REQ 43 at `+9m46s`, REQ 60 at
`+9m48s` (the two long-running study-script runs the milestone named), turn 2: REQ 78 (no tail)
and REQ 79 at `+8s`. `reqs k-ratio --turns`: 20 turn separators, matching the milestone's own
count exactly.

## What stayed untouched

Plain `reqs`, `reqs --gap`, `reqs --merged`, `sessions`, `search`, `msgs`, `expand` confirmed
byte-identical before/after via `git stash` on real invocations of each. All 13 suites under
`dev/dual_log_cli/tests/` pass (232 checks total) — `test_turns.py` was pruned of every test
exercising a removed function (18 of its original functions), keeping opener classification,
preview extraction, the message_count assignment rule (rewritten against
`_group_markers_by_turn`'s own return shape instead of `build_turn_rows`'s rows), and
`_fmt_duration`'s bands, then extended with the milestone's own worked example rendered
byte-for-byte, the per-turn elapsed-tail reset, the no-opener fallback, and `_run_reqs`'s four
usage-error paths (called directly with a hand-built `argparse.Namespace`, since the validation
runs before any filesystem access — no subprocess needed).

## Relevant Symbols / Paths

- `timeline._group_markers_by_turn`, `turn_openers`, `_is_turn_opener`, `_turn_preview` (still
  live, `src/dual_log_cli/timeline.py`)
- `render._turn_grouped_lines`, `_elapsed_req_lines`, `_fmt_duration`, `render_reqs`'
  `turns_by_stem` parameter (`src/dual_log_cli/render.py`)
- `_run_reqs`'s `--turns` validation and `turns_by_stem` collection (`src/dual_log_cli/__main__.py`)
- Ground truth: same two sessions as the M1/M2 entries
- Area: this same area's `2026-09-08_turns_command.md` and `2026-09-09_turns_per_request_detail.md`
  — the removed command's own design and verification record, kept as-is (write-once) even though
  the code they describe is gone
