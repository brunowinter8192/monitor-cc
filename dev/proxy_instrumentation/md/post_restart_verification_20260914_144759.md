# Post-Restart Verification

Generated: 2026-09-14T14:47:59.285857+00:00Z
Log dir: `/tmp/pre_restart_logs`
Session stem: `api_requests_opus_monitor_cc_1789383190`

## [CONTRADICTED] accept-encoding: identity / answering_model

- 212 streamed conversation responses observed
- 212/212 still carry a compressed content-encoding (expected 0)
- 0/212 carry answering_model (expected 212)
- 1 non-streaming application/json side call(s) observed, 1/1 correctly show an empty answering_model -- expected, not a gap

## [CONTRADICTED] auto-backgrounded-on-timeout strip (wording 3)

- genuine trigger found in _original (msg index 198, role=user tool_result, anchored prefix match)
- _stripped: a "_apply_bg_launch_ack_strip" strip whose removed chunk is the wording-3 text was NOT found
- _forwarded: the compact timeout-aware replacement was NOT found

## [MISSING DATA] poread full-content injection

- no whole-block poread marker found (role=user tool_result, matching the real _parse_poread_marker fullmatch) in the newest session's _original log -- a marker with anything else in the same block (e.g. chained after another command) does not count, by design
- **ACTION:** run `poread <path>` via Bash, alone in its own call (nothing chained after it), against a file well under 500,000 bytes

