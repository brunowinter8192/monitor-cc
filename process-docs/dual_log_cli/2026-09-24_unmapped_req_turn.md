# reqs: a REQ without a transcript match belongs to a turn (2026-09-24)

## Observed

`duallog reqs gapturn_1790242219` printed `REQ ?` (a first attempt to send a new prompt) outside the turn:

```
REQ 9   11:31:57  CR 43,667   CC 613
REQ ?   11:40:02  CR ?        CC ?
── turn 3  11:40:04  21s  recap — area dual_log_cli ──
REQ 10  11:40:04  CR 44,280   CC 1,741
```

The worker proxy pane showed the same request inside turn 3, with the turn header time at the prompt
time (11:40:02). The `REQ ?` is a continue sent after >= 5 min idle that never reached the transcript
(rejected), REQ 10 the full resend. Same pattern 5 times in that session (before turns 3, 6, 10, 13, 16).

## Rule (user decision: duallog assigns turns exactly like the proxy pane)

- A REQ without a transcript match (`pane_turn` None) gets its turn from its send time against the
  transcript turn start times, by calling the proxy pane's own `proxy_display.format._assign_turns_to_entries`
  (latest turn whose start <= send time, entries before the first turn go to turn 1). Mapped REQs keep
  the transcript's turn; both rules agreed on every mappable row measured earlier.
- The turn separator time is the turn's prompt time (`pane_turns[n-1]["timestamp"]`), the same time the
  token/proxy pane turn header carries; if a turn has no prompt timestamp it falls back to the first REQ.
  The span is still first to last REQ of the turn, now including the unmapped one (the example turn 3
  reads `23s`).
- `--gap`: a `REQ ?` sits inside its turn but never takes part in a pair. A pair member must be a numbered
  REQ because the chain continues with `expand --req N`, which a `REQ ?` cannot serve. It is still
  printed in the normal listing and kept by `--turn N`.
- `msgs --req` / `expand --req` use pane numbers, not turns: unaffected. The request after an unmapped one
  resolves its reply as before.

## Verification (2026-09-24)

`duallog reqs gapturn_1790242219 --turn 3` prints `── turn 3  11:40:02  23s  recap — area dual_log_cli ──`,
then `REQ ?  11:40:02`, `REQ 10  11:40:04`, 11, 12. The full listing shows the same pattern for turns 6
(11:58:41), 10 (12:52:53), 13 (13:05:35), 16 (13:22:37) and 20 (15:05:50). `reqs canvas --worker --gap 2`:
16 sessions, no `REQ ?` line, no empty header; against the run before the change only the separator times
moved to the prompt time (e.g. textfx turn 4 20:56:18 -> 20:56:12) and two new sessions from other workers
appeared.

## Tests

`dev/dual_log_cli/tests/test_reqs_pane_numbering.py` 66/66: fixture with two turns, two rejected continues
(HTTP 404, request ids absent from the transcript) and four numbered REQs; asserts both `REQ ?` rows inside
turn 2 in order, the separator at the prompt time (10:20:00, not the first REQ's 10:20:01), the 5m14s span,
`--turn 2` keeping both, and `--gap 2` listing only REQ 3 and REQ 4. All 18 files in
`dev/dual_log_cli/tests` pass.
