# reqs: HTTP status on the REQ line, and what the `REQ ?` rows are (2026-09-24)

## The finding: the seven `REQ ?` rows of gapturn_1790242219 are all 404 continues

Hypothesis before the check: the `REQ ?` rows are continue requests rejected by the server after >= 5 min idle.
Checked against `_forwarded` and `_response` of `api_requests_worker_25c51a2e_gapturn_1790242219` (UTC; local is +2 h):

| REQ ? row (local) | 404 continue sent / answered (UTC) | previous request ended | idle | next request | status |
|---|---|---|---|---|---|
| turn 3, 11:40:02 | 09:40:02 / 09:40:02 | 09:31:57 | 485 s | create sent 09:40:02, 29 msgs | 200 |
| turn 6, 11:58:41 | 09:58:41 / 09:58:41 | 09:45:10 | 811 s | create sent 09:58:41, 89 msgs | 200 |
| turn 10, 12:52:53 | 10:52:53 / 10:52:53 | 10:10:23 | 2550 s | create sent 10:52:53, 248 msgs | 200 |
| turn 13, 13:05:35 | 11:05:35 / 11:05:35 | 10:59:58 | 337 s | create sent 11:05:35, 320 msgs | 200 |
| turn 16, 13:22:37 | 11:22:37 / 11:22:37 | 11:16:20 | 377 s | create sent 11:22:37, 410 msgs | 200 |
| turn 20, 15:05:50 | 13:05:50 / 13:05:50 | 11:36:16 | 5374 s | create sent 13:05:50, 521 msgs | 200 |
| turn 22, 15:40:21 | 13:40:21 / 13:40:21 | 13:08:14 | 1926 s | create sent 13:40:21, 548 msgs | 200 |

Every row: a `continue` (no tools, `previous_message_id` set) answered with HTTP 404 in the same second it was sent,
after an idle gap of at least 337 s; immediately followed by a full `create` (tools, full history) sent in the same
second and answered 200. The five rows before turns 3, 6, 10, 13, 16 were the ones the user asked about; turns 20
and 22 appeared later in the same session. The sidebar evidence matches: continue 20:13:26 UTC answered 404,
create 20:13:27 answered 200 (that create still has no transcript call and prints as an unmapped `REQ ?` without
status text because it returned 200).

Reading: CC keeps a server-side thread and continues it with `previous_message_id`; after a longer idle the server
no longer knows that thread (404) and CC re-sends the whole conversation as a create. The transcript has no call for
the 404, so duallog and the panes print it as `REQ ?`. Not verified: the server-side reason or the exact idle
threshold (the shortest idle before a 404 here was 337 s; no 200 continue after a comparable idle was checked).

## What was built (duallog part)

- `usage.flow_status_ids` (was the private `_flow_status_ids`) is used by `numbering._annotate_status`, which
  writes `http_status` on every create and continue from the `_response` stream, in both numbering paths (the
  transcript need not resolve). It has no fallback: a broken `_response` log fails the command loudly (review
  decision per § Fallback und Tripwire; a first version wrapped it in a silent `except Exception`).
- `timeline_markers.request_markers` carries `http_status`; `render_reqs._request_marker` too. `_req_line` prints
  `  <status>` after the time for any status that is not `None` and not 200, before `CR`/`CC`:
  `REQ ?   11:40:02  404  CR ?        CC ?`. 200 rows and rows without a `_response` line are unchanged.
  `--gap` semantics are unchanged (a `REQ ?` never forms a pair).

## Verification

`duallog reqs gapturn_1790242219`: all seven `REQ ?` rows print `404` (turns 3, 6, 10, 13, 16, 20, 22).
`duallog reqs sidebar_1790187567 --turn 6`: `REQ ?   21:38:44  404`, `REQ ?   22:13:26  404` (the rejected
continue) and `REQ ?   22:39:15  404`; `REQ ?   21:56:46` and `REQ ?   22:13:27` print without status (200 without a
transcript call).

## Tests

`dev/dual_log_cli/tests/test_reqs_pane_numbering.py` 70/70; new check on the fixture with two 404 continues each
followed by a 200 create: status after the time and before CR/CC on the rejected rows, numbered rows unchanged,
`--gap 2` output unchanged, every main-thread request carries its status. All 18 files pass.
