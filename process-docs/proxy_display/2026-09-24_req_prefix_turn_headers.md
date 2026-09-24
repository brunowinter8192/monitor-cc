# Proxy panes: `REQ #n` prefix, turn headers, continue-safe parser (2026-09-24)

## Task

The proxy panes (`pane.py` main, `worker_proxy_pane.py` worker) must look like the token pane:
every REQ header row starts with `REQ #<n>`, turn boundaries are their own `Turn n [..]` rows, and
the number n of a request is the SAME in both panes (users read them side by side).

## Root cause of the number mismatch (measured 2026-09-24)

Token pane: one REQ per CC transcript `api_call`, running across turns (`request_requestId`
merges consecutive duplicates). Proxy pane before this change: `#n` fresh only when
`diff_from_prev.messages_added > 0`, else `#n.m`.

- Opus sessions were already equal: opus_canvas_1790184565 149/149, opus_canvas_1790157418 340/340,
  opus_general_1790187918 18/19 (one retry).
- Worker sessions were not: sidebar 1/122, statusbar_1790169860 1/366, gapturn 1/44. Labels read
  `#1, #1.1 ... #1.12, #2, #2.1 ...` because most worker requests are `continue` requests (see
  below) with 2 msgs, which land in the `#n.m` branch.
- Plain counting of non-haiku entries fails as well: sidebar has 129 non-haiku entries against 122
  transcript calls (5 HTTP 404 responses among the 7 unmapped). Only a join is exact.

## The join

`forwarded.request_id` is empty in ALL 1,505 checked forwarded entries. The path is
forwarded `flow_id` -> `_response` line (`flow_id`, `request_id`) -> transcript call `requestId`
(`api_calls[].request_id`). 1,499 of 1,505 entries have a `_response` line. Both panes now read the
`_response` log incrementally (`proxy_pane_shared._accumulate_request_ids`, path from
`parser._find_response_log_path`, state reset with the other positions) and pass
`request_id_by_flow` to `format_proxy_block`.

Labels (`render_turn._req_label`): `REQ #n`; a second entry mapped to the same n (refire) `REQ #n.1`,
`REQ #n.2`; unmapped non-standalone entry `REQ #?` (in flight, HTTP 404, or transcript not yet
written; the token pane lacks such a request too); haiku `H`, zero-context `S` (never in the token
pane). `REQ #?` is excluded from the collision highlight.

Turn headers reuse `token_format._format_turn_header_line`. Turn assignment stays the existing
timestamp-based `_assign_turns_to_entries`: it agreed with the request_id join on every mappable row
(0 disagreements of 149, 340, 122, 366).

## One counter

`token_format.call_numbers(turns)` (per-turn lists of running numbers) is the only place that counts.
`format_cache_tracker`, `panes/token_search.py` (it had a third private counter, affecting the
`REQ #n` search match text) and `request_numbers_by_id` (request_id -> number, for proxy_display) use
it. `request_numbers_by_id` alone could not serve the token pane: it skips calls with an empty
request_id, which the token pane still numbers. Byte identity of the token pane was checked before
and after on the sidebar and monitor-cc transcripts (180 calls, widths 40/60/80/120, expanded and
collapsed, two scroll offsets, `nav_out`, six search queries): hash `5770bd30...` both times, and
`dev/panes/render_byte_identity.py` `f1a8329a...` both times.

## Continue requests break the forwarded parser (companion fix)

Worker sessions send `thread: continue` requests: sonnet, `counts.tools == 0`, only 1-2 msgs
(`messages_delta` keys `0` or `0,1`), `diagnostics.previous_message_id` set (`_forwarded` has no
`thread` key; the diagnostics field is the discriminator, 817 of 817 such entries). The per-family
accumulator applied them like a normal request, truncated its message list to 2, padded `{}`, and
the next create (sidebar entry 104, msgs 290, empty delta) raised `KeyError: 'role'` in
`proxy.logging._diff_modified_count`. Now `forwarded_parser._is_continue_entry` entries bypass
`acc_by_family` (`_process_continue_entry`), carry `is_continue=True`, `diff_from_prev` vs `None`.
`_lazy_load_messages_forwarded` skips them in its temp accumulator and returns their own msgs.
`format._is_standalone_entry` returns False for them; `render_turn._resolve_prev_same_family`
gives them no `prev_same` and skips them when looking for a create's `prev_same` (otherwise every
continue showed a false `🔧-15` and `⚠T`).

## Verification (real logs, `dev/proxy_display/verify_req_numbering.py`)

- sidebar `api_requests_worker_5dd99b09_sidebar_1790187567`: 131 proxy entries, 122 token REQ rows,
  122 numbered proxy rows, 7 `REQ #?`; (number, turn) pairs identical. Turn 5: proxy `REQ #78..#86`
  against token `REQ #78..#86`.
- monitor-cc main `api_requests_opus_monitor_cc_1790241323`: 57 entries, 54 token rows, 54
  numbered, 1 `REQ #?`; identical. Turn 11: `REQ #52..#54` on both sides.
- Reports: `dev/proxy_display/md/`.

## Tests

`dev/proxy_display/test_req_prefix_turn_headers.py` 16/16, `test_standalone_sidecar.py` 8/8 (adapted:
`render_turn_expanded(group, entries, states, width, number_by_flow, label_counts)` returns
`(lines, keys)`). `render_byte_identity.py` (proxy_display) hashes the label text, so any baseline
taken before this change differs; not re-run. Other dev scripts touching the render cluster return
the same codes before and after; `thinking/render_brain_badge.py`, `thinking/render_thinking_expander.py`
and `proxy_dual_log/A_render_refactor_proof/A_render_refactor_proof.py` return non-zero both ways.

## Not done / observed

- `strip_vocab.classify_tags` raises `TypeError: 'NoneType' object is not subscriptable`
  (`entry['messages']` None) for expanded REQs; 308 tracebacks in `/tmp/monitor_cc_error.log` on
  2026-09-24. Left alone on request.
- Not run inside a live TUI, only via log replay through the same functions.
- Hypothesis, never observed: a non-consecutive duplicate request_id in the transcript; the id map
  keeps the first number.
