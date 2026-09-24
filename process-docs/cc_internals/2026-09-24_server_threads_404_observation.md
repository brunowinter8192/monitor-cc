# Server-side threads and the 404 after idle (observation, 2026-09-24)

Status: observed and noted, no action taken. The user decided to watch it rather than change anything.

## What Claude Code 2.1.280 sends

- Worker sessions (claude-sonnet-5) send most main-thread requests as thread continuations: `thread: {"type": "continue"}`, `counts.tools == 0`, `diagnostics.previous_message_id` set, and exactly 2 messages in the body (newest tool_result plus a system reminder).
  - Counted on sidebar_1790187567: 7 full requests, 122 continuations, 2 haiku.
  - Across 19 sessions on 2026-09-23/24: 817 continuations, all sonnet.
- Main sessions (claude-opus-5-5) never send a continuation. Every request carries the full history.
- Main and workers run the same binary (`~/cc-cache-fix-280/.../claude.exe`, version 2.1.280, file dated 2026-09-23 11:30, every process started 2026-09-24). The difference is the model, not the version.
- The server rebuilds the full context from the thread. The token pane therefore shows the full history as cache read (for example CR 436,752, D 2) while the proxy pane shows `2msg` for the same request. Both are correct: one is what goes over the wire, the other is what the model processes.

## The 404 after idle

Every continuation sent after >= 5 minutes of idle is answered with HTTP 404, and Claude Code immediately resends the turn as a full request. Observed on gapturn_1790242219 (`duallog reqs gapturn_1790242219`, status column added the same day):

| Turn | Idle before | 404 at | Full resend |
|---|---|---|---|
| 3 | 8 min | 11:40:02 | REQ 10, 11:40:04, 29 msgs |
| 6 | 13.5 min | 11:58:41 | REQ 30 |
| 10 | 42.5 min | 12:52:53 | REQ 83 |
| 13 | 5.5 min | 13:05:35 | REQ 107 |
| 16 | 6 min | 13:22:37 | REQ 137 |
| 20 | 89 min | 15:05:50 | REQ 174, 521 msgs, CR 9,005 / CC 512,745 |
| 22 | 32 min | 15:40:21 | REQ 183, CR 540,260 |

- After a 30 s pause (turn 4) there was no 404.
- sidebar_1790187567 shows the same pair: continuation 404 at 22:13:26 local, full request 200 at 22:13:27.
- The prompt cache outlives the thread: after 32 min the resend read 540k from cache, after 89 min it rebuilt 512k. So the 404 costs 1 to 8 seconds while the cache is warm; the expensive case is the cache expiring after roughly an hour, not the 404.

## Cause: hypothesis only

- Most likely the server keeps a thread for about 5 minutes and answers `thread_not_found` after that. Supported by the Bifrost v2.2.1 changelog (docs.getbifrost.ai/changelogs/v2.2.1): Claude Code's server-side threads are bound to the creating account, a missing thread fails with `thread_not_found`, the client then resends the turn in full; the error code `thread_unsupported_request` instead makes the client stop sending threads for the rest of the session.
- The 5-minute figure comes only from our timestamps; no source states it.
- Why only sonnet uses threads is unexplained. A lead from anthropics/claude-code#75607: Claude Code is enrolled in server-side experiments via the `x-cc-atis` header, and an experiment there was scoped to one model. Unverified for threads.
- The `_response` log stores no error body, so the 404 reason text was never seen.
- anthropics/claude-code issues on `previous_message_id` (#59520, #58427, #76008, #96033) are a different bug: 400 caused by a client-fabricated UUID id, session stays broken. Ours is a 404 and the session continues normally.

## Consequence for the logs

- A continuation carries no assistant message. Assistant replies reach the proxy log only inside the next full request. After the last full request of a session, the model's replies (and its tool_use commands) are absent from the proxy log; they exist only in the Claude Code transcript. This is why `duallog expand --req` cannot resolve REQs near a session's end (sidebar REQ 107 and 120).

## If this is picked up again

- Store the response body for non-200 answers in the proxy to read the real 404 reason.
- Spawn one worker on claude-opus-5-5 to see whether threads depend on the model.
- Check whether requests carry `x-cc-atis`.
- Fill missing assistant replies in duallog from the transcript.
