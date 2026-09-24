# reqs --gap restricted to gaps within one turn (2026-09-23)

## Problem

`_bracket_gap_positions` compared every chronological neighbor pair of the entry list. That paired
the last REQ of turn N with the first REQ of turn N+1, so the reported gap was just the idle time
between two prompts. Under `--merged` it also paired REQs of two different sessions.

Observed case, canvas project, `duallog reqs canvas --worker --since 2026-09-23 --gap 2`
(session `api_requests_worker_5dd99b09_trending_1790187573`):

```
── turn 1  20:19:35  0s ──   REQ 1   20:19:35
── turn 2  20:37:26  0s ──   REQ 2   20:37:26
```
An 18 minute cross-turn pair with no informational value. It must not print.

## Rule now

A gap counts only between two consecutive REQs of the same session AND the same turn, with or
without `--merged`. Implementation: iterate the (chronological) entry list, remember the last entry
index per `(stem, turn)`, compare each REQ against that one only. Both bracket REQs are kept when
elapsed whole minutes >= threshold. Output format is unchanged.

Consequence under `--merged`: a REQ of another session sitting chronologically between two
same-turn REQs of session A no longer hides A's gap. The old test
`test_merged_gap_bridged_by_another_session_does_not_qualify` asserted the opposite and was removed.

## REQs without a turn

Entry turn is `None` only for a session with no turn opener at all (a REQ before the first opener is
clamped into turn 1 by `timeline_grouping._group_markers_by_turn`). Decision: such REQs never form a
gap, because they are not "within one turn". A session without openers prints only its header under
`--gap`. Alternative not chosen: treat all REQs of an opener-less session as one implicit turn.

## Filter order

`--turn` still narrows first, then `--gap` runs on the narrowed entries, then `--rebuild`/`--drop`.
Positions are indices into the narrowed list.

## Tests (dev/dual_log_cli/tests)

The old gap and merged fixtures had no turn openers and would all drop under the new rule. Fixtures
now pass `turns_by_stem` with a DENSE row list: `_session_entries_and_separators` indexes
`turns[opener]` by msg index, so a sparse list raises IndexError. Openers are `user` rows with a
`text` block, all other indices `assistant` rows. Message counts map to turns via
`bisect_right(openers, message_count - 1)`: with openers `[0, 7]`, counts 2 and 5 are turn 1, 9 and
11 are turn 2.

Cases: cross-turn gap dropped; within-turn gap kept next to a cross-turn neighbor (turn 1 separator
disappears, turn 2 remains); no-turn REQs dropped; merged cross-session neighbor dropped; merged
same-turn gap interleaved by another session kept; merged cross-turn gap dropped.

## Verification (same command, worktree code)

- trending session: header only, the turn 1 -> turn 2 pair is gone.
- sidebar turn 6: REQ 4 21:38:45 -> REQ 5 22:13:27 still printed, REQ 6 22:39:16 too (REQ 5 -> 6 is
  a 26 minute within-turn gap).
- statusbar `..._1790169860` turn 1: REQ 1 15:24:21 -> REQ 2 15:58:37 (34 minutes) printed.

## Help text

`--gap` help and `_REQS_DESCRIPTION` in `cli_args.py` say "within one turn".
