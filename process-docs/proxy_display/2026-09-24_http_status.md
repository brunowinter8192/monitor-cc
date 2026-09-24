# Proxy panes show the HTTP status of every request (2026-09-24)

## Why

Expanding a `REQ #?` row in the worker proxy pane showed no HTTP status. `_accumulate_request_ids` read the
`_response` stream but kept only `flow_id -> request_id` and dropped `status_code`. The reason the rows exist
(rejected requests) was invisible in the pane.

## What was built

- `proxy_pane_shared._accumulate_request_ids(path, pos, request_id_by_flow, status_by_flow=None)` also fills
  `flow_id -> status_code`; `_attach_http_status(entries, status_by_flow)` writes `entry['http_status']` on every
  entry each poll, but only once the status map is non-empty. Both panes (`pane.py`, `worker_proxy_pane.py`)
  own a `_..._status_by_flow` dict reset together with the request-id map, on session/worker change and on the
  hourly reparse.
- Value of `entry['http_status']`: an int for a request with a `_response` line, `None` for a request without
  one yet (in flight), key absent when no response information was read at all.
- `render_turn._status_marker`: header row ends with ` [404]` (red) for any non-200 status, ` [pending]` (dim)
  for `None`, nothing for 200 or an absent key. `render_turn._status_line`: the first line of an expanded REQ is
  `status: 404` / `status: 200` (dim for 200 and pending, red otherwise) or `status: pending (no _response line
  yet)`. The time column (right-aligned time, copy symbol) is unaffected; the marker sits inside the row content.
- REQ numbers and times are untouched: the marker and status line do not enter the join
  (`request_id_by_flow`, `time_by_flow`), and Test 8 (same time per REQ in both panes) stays green.

## Verification (gapturn session, width 110)

Turn 3 collapsed shows `▶ REQ #? sonnet 2msg eff:hig think:64k [404]` above `▶ REQ #10 ... 🧠  11:40:04`; expanded
on the rejected row it shows `▼ REQ #? ... [404]`, then `status: 404`, `beta`, `ctx`, `diag`, `sys`, the msgs.
The pane entry list of the session has exactly seven entries with status 404 and none pending
(09:40:02, 09:58:41, 10:52:53, 11:05:35, 11:22:37, 13:05:50, 13:40:21 UTC). The 404 finding itself is in the
dual_log_cli area's process-docs.

## Tests

`dev/proxy_display/test_req_prefix_turn_headers.py` 55/55, Test 10: `_accumulate_request_ids` keeps both maps;
entries get their status, unanswered ones stay `None`; the `[404]` marker is on the collapsed header row; 200
rows have no marker; `status: 404`, `status: 200` and `status: pending` lines; the pending marker; without any
response info nothing changes; REQ numbers 1..4 unchanged. `render_byte_identity.py` (proxy_display) does not set
`http_status`, so its output is unaffected by this change.

## Notes for a successor

`[pending]` also shows on an old entry whose `_response` line never arrived (2 worker entries in the whole log
directory had none on 2026-09-24); that is accurate, not a bug. The status marker is not part of the search
matching text beyond the expanded `status:` line (search renders the expanded section).
