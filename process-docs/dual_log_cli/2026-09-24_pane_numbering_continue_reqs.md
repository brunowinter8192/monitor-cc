# reqs/msgs: continue requests as REQs, numbers and times identical to the panes (2026-09-24)

## Task

`duallog reqs <scope> --gap MIN` must show two consecutive REQs of one turn of one session that are MIN
or more minutes apart. It failed for worker sessions because `request_boundaries` dropped every
`thread: continue` request as a sidecar (see the finding in this area's earlier file about the
undercount). Decided scope: every main-thread request (create AND continue) is its own REQ with its
own time and CR/CC; haiku stays out; continues own no msgs; and duallog's REQ numbers, turn numbers
and times become the token pane's / proxy panes' own, because the user reads duallog next to them.

## Measurements that drove the design (2026-09-24)

- Turn of a continue by the latest create sent before it (no transcript) was wrong for 37 of 116
  (sidebar), 108 of 360 (statusbar_1790169860), 66 of 77 (textfx), 77 of 103 (gapturn), 37 of 56
  (p4scan); pushimg 0 of 27. Turn of a continue by the last transcript prompt timestamp <= its send
  time: 0 wrong out of about 770 continues in six worker sessions. Reason: a turn opener often
  arrives via a continue, not via a create. So the turn of a continue needs the transcript; duallog
  already resolves it for CR/CC.
- Numbers today versus panes on sidebar: duallog `msgs`/`reqs` showed REQ 1..6 for the creates, the
  panes 1, 13, 50, 87, none, 104 (one create with status 200 has no transcript call). Opus sessions were
  already identical (canvas 1790184565: 149 of 149).
- Time basis for `--gap`: send time and response-end time each give 24 pairs on sidebar with
  `--gap 1`, but not the same 24 ((52,53) and (57,58) only by send time, (11,12) and (51,52) only by
  response end). Both contain REQ 84 -> 85 (send 21:21:54 -> 21:23:32, response end 21:21:58 ->
  21:23:39). Only response end matches what the panes show.

## What was built

- `timeline_boundaries.continue_requests(forwarded_path, family)`: family match, `counts.tools == 0`,
  `diagnostics.previous_message_id` set. `boundaries` still holds creates only (`_is_sidecar` untouched),
  `load_timeline` adds `continues`. Continues own zero msgs, so `msgs`/`expand` ownership is
  unchanged and the parked `tool_use_id` matching stays parked.
- `numbering.build_session_numbering(session, boundaries, continues, projects_root=None)`: resolves
  the transcript once (`usage.resolve_transcript`, now public), builds usage
  (`usage.usage_from_transcript`) and the pane view (`build_cache_turns`, `token_format.call_numbers`,
  request_id -> (number, turn, last-assistant-entry time)), and writes `pane_number`, `pane_turn`,
  `pane_time` onto every create and continue (`None` when the request id is not in the transcript:
  HTTP 404, in flight, or a 200 that never reached it). Returns `{usage, pane_turns, path}`.
- `timeline_markers`: `_boundary_numbers` uses `pane_number` when the key exists, else the old running
  number. Owner of a refire group is the last MAPPED boundary (sidebar's 290-msg group: an unmapped
  refire may be last). Markers carry `clock_timestamp` (pane time, else send time) and `pane_turn`.
  `number None` prints `REQ ?` and is skipped by `request_msg_range`. Overlay "by REQ n" tails only get
  mapped numbers.
- `render_reqs`: with `pane_turns` the entries are all main-thread requests sorted by response-end
  time, turn = transcript turn, separators are rebuilt from those entries (span = real first-to-last
  time, preview = transcript prompt, 100 chars). `REQ ?` rows carry the send time and no turn, never
  form a gap, and do not repeat a separator (`_grouped_lines` leaves the current key alone for
  `turn None`). `prev_usage` for `--drop` is the chronologically previous request.
- `render_msgs`: separators print the pane number, `REQ ?` when unmapped, and the pane time.
- `commands`: one stderr line per run names the path, e.g. `numbering: 15 session(s) via transcript
  (pane REQ numbers, response-end times)` or, for the monitor-cc main session (transcript does not
  resolve): `numbering: 0 session(s) via transcript (...); 1 via boundaries fallback, transcript
  unresolved (create requests only, own numbers, send times): api_requests_opus_monitor_cc_1790241323`.
  `msgs --req N` on a continue number: `REQ N is a continue request: it owns no msgs (msgs belong to
  create requests only)`.

## Fallback

The only observed unresolved-transcript case is the monitor-cc main session (opus, no continues).
Without a transcript the code keeps the pre-change behaviour: create requests only, own running
numbers, send times, turns via `message_count`, no continues (they would have no turn and could
never form a gap). Chosen over chronological numbering of continues to keep the fallback identical to
the previous output.

## Verification (worktree code, 2026-09-24)

- `reqs sidebar_1790187567 --gap 1`: 122 mapped REQs, REQ 84 21:21:58 and REQ 85 21:23:39 present;
  turn numbers equal the token pane's (turns 1, 2, 3, 5, 6, 8, 9 have qualifying gaps).
- `reqs canvas --worker --since 2026-09-23 --gap 2`: 15 sessions via transcript, 101 lines.
- `msgs sidebar_1790187567 --req 104`: separator `── REQ 104  22:39:33  CR 324,769  CC 1,211 ──  (+1
  re-fire)`, msgs 290..310. Separators of the whole session: REQ 1, 13, 50, 87, `?`, 104. `--req 5` (a
  continue): the continue error text.

## Tests (dev/dual_log_cli/tests)

`test_reqs_pane_numbering.py` 27/27: fixture with 2 creates, 5 continues (one HTTP 404) and a haiku,
a fake worker transcript with two prompts; asserts continues found and haiku not, annotation
(numbers 1,2,3,4,5,6 and None, turns, response-end times), the `reqs` listing (6 numbered rows plus
`REQ ?`, two separators, no repeated separator), `--gap 2` (exactly REQ 2+3 and 5+6, the cross-turn
pair 4->5 dropped), `msgs` separators and `--req` (4 resolves, 3 is a continue), the owner rule, `REQ ?`
in `msgs`, the fallback path and its stderr line. All other tests needed no edits: they call the
renderers without pane data, which is the fallback path. All 18 files pass.

## Not done / open

- Msg attachment for continues (`tool_use_id` matching, prompt-text openers, trailing continues after
  the last create) stays parked. Consequence: a create's msg group spans the msgs added by the dropped
  continues, e.g. `msgs --req 13` lists 36 msgs.
- `reqs --gap` for a worker session without a resolvable transcript finds nothing.
- A `REQ ?` row (send time) can sit slightly out of order next to mapped rows (response-end times).
