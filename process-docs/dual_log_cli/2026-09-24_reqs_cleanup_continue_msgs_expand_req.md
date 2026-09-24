# reqs cleanup, continue msgs, expand --req (2026-09-24)

Covers three follow-ups after the pane-numbering cut (see this area's file on pane numbering). Goal of
the user: answer "which command ran in this gap?" with duallog commands only:
`reqs --gap` -> `expand <session> --req N` (or `msgs --req N` -> `expand <session> <msg>`).

## 1. reqs cleanup

- Empty sessions: `render_reqs` prints no `session <stem>` header (and no blank line) for a session whose
  entries are all filtered out. If no session prints, and under `--merged` if no entry survives, the
  output is the single line `no REQs to show` (the skipped-sessions note still follows). `no sessions
  found` for an empty scope is unchanged. Tests that expected a bare header now expect the line.
- REQ 97 of sidebar was missing. Observed data (UTC, `duallog`'s own session listing):

  | send | response end | kind | msgs | status | transcript |
  |---|---|---|---|---|---|
  | 20:13:26 | 20:13:27 | continue | 2 | 404 | none |
  | 20:13:27 | 20:19:08 | create | 290 | 200 | request id absent (unmapped) |
  | 20:19:08 | 20:19:16 | create | 290 | 200 | REQ 97, turn 6 |
  | 20:39:16 | 20:39:33 | create | 311 | 200 | REQ 104 |

  The request that vanished is the create sent 20:19:08 (REQ 97), not the one sent 20:13:27 (that one
  prints `REQ ?`). It shares `start_index` 290 with REQ 104 because it re-sent the same 290 msgs, so
  `request_markers` folded it into 104's refire group (owner: last mapped boundary = 104). Fix: the
  transcript path of `reqs` no longer goes through `request_markers`; every create and every continue is
  its own entry (`_request_marker`). `msgs` grouping keeps its own marker logic. Consequence: an unmapped
  create that shares a start_index with another one now also prints as `REQ ?` (before: folded).
  `reqs sidebar_1790187567 --gap 2` turn 6: REQ 96 21:52:10 -> 97 22:19:16 (27 min) -> 98 22:22:41 (3 min).

## 2. continue requests own msgs (`msgs --req`)

Unlocated continues used to own no msgs, so `msgs --req 96` failed. Now (transcript path only):

- `timeline_boundaries.continue_requests` also returns `tool_use_ids`: the `tool_use_id`s of the
  `tool_result` blocks in `_forwarded.messages_delta["0"]` (empty for a turn opener whose msg0 is text).
- `numbering._locate_msgs` (payload messages passed in from `commands`) writes `msg_start` on every request
  that is mapped in the transcript:
  - continue: the last assistant msg before its tool_result msg (found by `tool_use_id`), all ids must
    resolve, else unlocated;
  - create: the last assistant msg before its last sent msg (`message_count - 1`), replacing "count of
    the previous create" which was wrong once continues sit between creates; the first create starts at 0.
- Numbers for opus creates were identical to the old start_index on canvas 1790184565 (149/149) and
  1790157418 (340/340); opus_general_1790187918: one create starts at 35 instead of 38, one unmapped 404
  create owns no group.
- `request_markers` groups by `msg_start` when the key exists (else `start_index`); requests without a
  start are skipped. A REQ therefore owns the assistant reply it answers plus the msgs it sent, until the
  next located REQ starts. Msgs of unlocated requests (openers, trailing continues) sit under the
  preceding located REQ. Sidebar `msgs` now has 102 REQ separators (was 6). `msgs --req 104` shows 3 msgs
  (was 21: the continues 98..103 own the ones before it).
- `msgs --req F [T]` (`resolve_req_range_with_next`): groups F..T plus the next request's group, so the
  reply of the last requested REQ (the tool_use whose runtime is the gap) is included. Errors: REQ not in
  the log -> `REQ n not found`; an unlocated continue -> `REQ n is a continue request whose msgs could not
  be located (a turn opener, or newer than the last recorded payload); it owns no msgs`.
- Overlay "by REQ n" tails and the `expand` stripped/injected labels use the numbered requests
  (`data["requests"]`), so they carry pane numbers too.

Rejected: relabelling every group with its predecessor's number ("REQ x owns its own reply"). It would
have shifted all existing `msgs` separators and made every strip attribution ("by REQ n") say the next
request. Kept the "what this request added" meaning and extended `--req` instead.

## 3. expand --req N

`expand <session> --req N` replaces the msg argument and dumps, with all blocks, what REQ N produced: the
group of the next request (`resolve_req_output_range`), i.e. N's assistant reply (the tool_use) and the
tool_result that came back (the trailing system msg too). Header: `window    msgs 926-928 of 0-1081,
what REQ 309 produced, 2026-09-23`. `--before/--after/--only` still apply. Exactly one of msg / `--req`
(`expand takes exactly one of: a msg index, or --req N`). Needs the transcript path; otherwise
`expand --req needs the transcript numbering, which did not resolve for this session`. Errors: REQ not in
the log; `REQ n's reply is not recorded (no later request in the log)` (last request); `REQ n's reply
could not be located: the next request, REQ m, is a turn opener or newer than the last recorded payload`.

## Verification (2026-09-24, duallog only)

- statusbar_1790169860: `reqs --gap 4` shows REQ 309 16:41:43 -> REQ 310 16:46:22 (280 s);
  `expand ... --req 309` msgs 926..928: assistant tool_use[Bash] = `nohup npx vite ... for f in
  dev/box_status_bar/verify-box-status-bar-*.mjs; do ... node $f; ...`, the tool_result, the system msg.
- sidebar_1790187567: `reqs --gap 2` REQ 96 -> 97 -> 98; `expand --req 96` msgs 287..289: the `sed -i` +
  python patch + 40-run measure command, its tool_result (macOS `sed: ... extra characters at the end of
  d command`), the system msg. `msgs --req 96` printed the groups of REQ 96 (msgs 284..286) and REQ 97
  (287..289).
- statusbar REQ 121 -> 122 (8 min 26 s): the command was `rm node_modules reference && git status --short
  | head -20` (msg 362); a short command, so the gap was not its runtime (permission wait suspected; not
  visible in duallog).

## Tests (dev/dual_log_cli/tests)

`test_reqs_pane_numbering.py` 61/61: folded-create fixture (unmapped create + two creates sharing a
start_index), hidden empty sessions and the `no REQs to show` line (also `--merged`, skipped note), a
sidebar-modeled ownership fixture (creates c1/c2, continues k1..k5 with opener and 404, matching payload):
`msg_start` values 0,1,4,7,10 and None for the opener and the 404, ranges for `msgs --req` and `expand
--req`, error messages, the transcript-required refusal, argparse form, header label. Older tests changed
only where they asserted a bare `session s` / `merged N sessions` header. All 18 files pass.

## Not done / open

- Trailing continues newer than the last create (18 on sidebar) and turn-opener continues (msg0 text) still
  own no msgs; matching openers by prompt text stays parked.
- `expand --req` of the last located request errors (its reply is in no later request); the last create's
  own group shows under `msgs --req`.
- Parallel tool results of one continue in separate msgs use the minimum position; not observed.
