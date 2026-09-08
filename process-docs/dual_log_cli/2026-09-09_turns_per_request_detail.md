# `turns <session> N` — per-request detail inside a turn, 2026-09-09

Continues this area's `turns` command (Milestone 1, `2026-09-08_turns_command.md`). The bare
listing names the slow turn but not which request inside it drove the time; the issue that
motivated the whole area asks for the concrete driver — the one shell command that ran for
minutes.

## Design: share the grouping, not just the rule

`build_turn_rows` (M1) and the new `build_turn_requests` both need the identical turn-assignment
walk (`bisect_right(openers, message_count - 1)` over `request_markers`, see M1's own entry) —
duplicating it risked the two silently drifting apart on some future edge case. Split into
`_group_markers_by_turn(turns, boundaries) -> (markers, openers, groups)`, a pure refactor of
`build_turn_rows`'s own body; re-verified byte-identical against both ground-truth sessions and
the full existing suite before adding anything new on top of it.

## Where a request's OWN reply actually lives

The M1 investigation already established that a request's msg-index range `[start_index,
message_count)` describes messages that arrived BETWEEN the previous request and this one — i.e.
the PREVIOUS request's reply, not this one's own. `build_turn_requests` needed the opposite
direction: given request R, what did R's OWN reply contain? Answer: the range bounded by the NEXT
request's own `message_count` — `[R.message_count, R_next.message_count)`. This needed to be the
NEXT request GLOBALLY (via the whole session's `request_markers`, not R's own turn's group), not
the next request within R's turn: a reply is produced regardless of which turn the following
request later gets assigned to — the same idle-reply-bundled-with-next-prompt scenario M1 found
means the "next request" for the turn's own last member can genuinely belong to the FOLLOWING
turn.

A regression fixture in `test_turns.py` deliberately swaps the two directions (attributes req1's
tool name to req2's slot) to prove this stays caught — both directions produce a valid-looking
non-empty tool name, so a naive "does it run" check would not have caught a reversal; only
asserting the SPECIFIC name per request does.

## Tool_use names, not tool_use previews

`build_turns`' own per-block `preview` field for a `tool_use` block is the tool's INPUT preview
(`message_summary.py` partitions `name + "\n" + json.dumps(input)` and previews the part AFTER the
newline) — not the tool's name. The name survives instead in the block's `label`
(`"tool_use[Name]"`, produced by `_block_label` from the block's OWN raw `preview` field before
`build_turns` overwrites it). `_tool_use_name_from_label` parses that label rather than
re-deriving the name a second way.

## The two meanings of "?" in the tool_seconds column, deliberately not distinguished

A request's tool_seconds is unresolved either because the join failed (missing stream-end time) or
because it is structurally not computable — this request is the turn's OWN last one, so there is
no "next request within the turn" to subtract against, even when a LATER turn's own first request
exists and technically supplies a timestamp. Both render as `"?"`. This was a considered choice,
not an oversight: a reader digging into a slow turn needs "there is no number here" more than which
of the two reasons produced it, and the corrective action is the same either way (look at what the
PREVIOUS request's own tool time was). Introducing a second symbol was judged not worth it against
that.

## Verification against the milestone's own ground truth

The orchestrator's own probe reported reldist-power turn 1 containing "two Bash calls of roughly
582s and 584s and one of about 68s." `turns reldist-power 1` reproduces exactly this:

- REQ 42, `22:43:38`, tool `9m42s` (582s), `tool_names = ["Bash"]`
- REQ 59, `22:56:00`, tool `9m44s` (584s), `tool_names = ["Bash"]`
- REQ 26, `22:40:17`, tool `1m08s` (68s), `tool_names = ["Bash"]`

All three identified by REQ number AND correctly attributed to `Bash` as the tool_use name of that
same request's own reply. REQ 77 (turn 1's own last request, the idle text reply that closes the
turn) shows `tool_names = []` and `tool_seconds = "?"` — exactly the structural case above, not a
join failure (its model_seconds and tokens both resolve fine).

## What stayed untouched

The bare `turns <session>` listing (no `N` given) takes the exact pre-existing code path in
`_run_turns` (`args.turn is None`) — confirmed byte-identical before/after via `git stash` on both
ground-truth sessions, alongside `sessions`/`search`/`reqs`/`msgs`/`expand` on one real invocation
each. All 12 suites under `dev/dual_log_cli/tests/` pass (233 checks total, 18 new in
`test_turns.py`'s per-request section).

## Relevant Symbols / Paths

- `timeline._group_markers_by_turn`, `build_turn_requests`, `_tool_use_names`,
  `_tool_use_name_from_label`, `UnknownTurnNumberError` (`src/dual_log_cli/timeline.py`)
- `render.render_turn_detail`, `_turn_detail_line` (`src/dual_log_cli/render.py`)
- `_run_turns` (`src/dual_log_cli/__main__.py`)
- Ground truth: same two sessions as M1's own entry
- Area: this same area's `2026-09-08_turns_command.md` — the turn-assignment rule this milestone
  reuses via the shared `_group_markers_by_turn` split
