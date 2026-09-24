# reqs undercount: `thread: continue` requests are dropped as sidecars (2026-09-24)

Findings only, no code changed in dual_log_cli for this. A plan was reported and parked by the user.

## Symptom

`duallog reqs` for sidebar (`api_requests_worker_5dd99b09_sidebar_1790187567`) prints 6 REQs, `msgs`
shows msgs 0-310; spans are mostly 0s; msgs #113 and #116 share the timestamp 20:56:12.

## Cause (measured on the raw logs)

The logs are complete: 131 lines in `_original` and `_forwarded`, 130 in `_response`. They split into
7 `thread: create` requests (tools, 15 tool defs, full history), 122 `thread: continue` requests and
2 haiku. A continue request has `counts.tools == 0`, 1 system block (billing header only), exactly 2
msgs (the new tool_result or prompt plus a system reminder), `diagnostics.previous_message_id` set;
the server holds the rest of the history. `timeline_boundaries._is_sidecar` (`counts.tools == 0`)
drops all 122. The 7 creates give 7 boundaries; the two at msgs 290 share a `start_index`, so 6 REQs.
The create at 18:56:12 UTC (149 msgs, start_index 38) absorbs msgs 38..148 that 37 dropped continues
added, so all get its timestamp (local 20:56:12).

Spread: 817 continue requests in 19 sessions, only in worker sessions (all 6 opus sessions use
`thread` none, all with tools). Not checkable for older dates: the dual_log directory only holds
2026-09-23 and 2026-09-24 sessions.

## Discriminator

In `_forwarded`: family not haiku, `counts.tools == 0`, non-empty `diagnostics.previous_message_id`
(817 of 817 sonnet tools==0 entries; no counterexample). A real sonnet sidecar (tools 0 without a
previous id) was never observed in these logs; the 2026-09-03 sidecar tests use synthetic entries.

## Plan sketch (not implemented)

- Boundaries: continue becomes a boundary `kind="continue"`, not touching `prev_count`/restart/sys/tool
  hashes.
- Msgs: `_forwarded.messages_delta["0"]` holds msg0, either a `tool_result` block with
  `tool_use_id` or a plain-string prompt. Match `tool_use_id` against the last full payload:
  sidebar 99 of 122 resolve (stride 3 msgs per round: assistant, user tool_result, system). 5 are
  prompt-text continues (turn openers, match by text, untested), 18 lie after the last create (not in
  the payload; REQ line with time and CR/CC only), a few duplicates (parallel results, refire
  semantics).
- Effects: REQ numbers shift everywhere (`msgs --req`, "by REQ n" tails), `--gap` becomes meaningful,
  `--drop` compares consecutive real requests, `discovery` request counts and
  `test_sidecar_exclusion.py` change. CR/CC join by `flow_id` should work unchanged.
