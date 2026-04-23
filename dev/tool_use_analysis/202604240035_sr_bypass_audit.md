# SR Bypass Audit — 2026-04-24 00:35

## Methodology

- **bypassed**: SR blocks found in `raw_payload.messages` content after proxy processing (text, tool_result string, nested text).
- **captured**: SR blocks found in `stripped_msg_removed` entries (confirmed removed by proxy).
- **bypass_rate**: `bypassed / (bypassed + captured)`. Reported as `n/a` when both are 0.
- **Limitation**: `stripped_all_sr_msg0` (final pass, msg[0] only) does NOT write to `stripped_msg_removed`,
  so captures from msg[0] via the final pass are not counted in `captured`. This underestimates
  `captured` for templates without a dedicated elif branch. The `bypassed` column is the reliable signal.

## api_requests_opus_monitor_cc_1776977437.jsonl
Opus entries: 141

| template | mode | captured | bypassed | bypass_rate |
|---|---|---|---|---|
| task-tools-nag | full | 1329 | 0 | 0.0% |
| pyright-diagnostics | full | 124 | 0 | 0.0% |
| deferred-tools | full | 141 | 0 | 0.0% |
| user-interrupt | partial | 0 | 0 | n/a |
| system-notification | full | 0 | 82 | 100.0% |
| file-modified | full | 0 | 0 | n/a |
| claudemd-contents | full | 141 | 0 | 0.0% |
| date-changed | full | 0 | 52 | 100.0% |
| skills-available | full | 141 | 0 | 0.0% |
| plan-mode | full | 0 | 0 | n/a |

## api_requests_opus_monitor_cc_1776966942.jsonl
Opus entries: 295

| template | mode | captured | bypassed | bypass_rate |
|---|---|---|---|---|
| task-tools-nag | full | 4205 | 288 | 6.4% |
| pyright-diagnostics | full | 1528 | 0 | 0.0% |
| deferred-tools | full | 295 | 0 | 0.0% |
| user-interrupt | partial | 141 | 141 | 50.0% |
| system-notification | full | 221 | 752 | 77.3% |
| file-modified | full | 0 | 109 | 100.0% |
| claudemd-contents | full | 295 | 295 | 50.0% |
| date-changed | full | 0 | 0 | n/a |
| skills-available | full | 295 | 0 | 0.0% |
| plan-mode | full | 0 | 0 | n/a |

## api_requests_opus_monitor_cc_1776956156.jsonl
Opus entries: 187

| template | mode | captured | bypassed | bypass_rate |
|---|---|---|---|---|
| task-tools-nag | full | 1854 | 0 | 0.0% |
| pyright-diagnostics | full | 192 | 0 | 0.0% |
| deferred-tools | full | 186 | 0 | 0.0% |
| user-interrupt | partial | 0 | 1 | 100.0% |
| system-notification | full | 0 | 0 | n/a |
| file-modified | full | 0 | 0 | n/a |
| claudemd-contents | full | 186 | 304 | 62.0% |
| date-changed | full | 0 | 0 | n/a |
| skills-available | full | 186 | 0 | 0.0% |
| plan-mode | full | 0 | 0 | n/a |

## Aggregate Summary (all logs)

| template | mode | captured | bypassed | bypass_rate |
|---|---|---|---|---|
| task-tools-nag | full | 7388 | 288 | 3.8% |
| pyright-diagnostics | full | 1844 | 0 | 0.0% |
| deferred-tools | full | 622 | 0 | 0.0% |
| user-interrupt | partial | 141 | 142 | 50.2% |
| system-notification | full | 221 | 834 | 79.1% |
| file-modified | full | 0 | 109 | 100.0% |
| claudemd-contents | full | 622 | 599 | 49.1% |
| date-changed | full | 0 | 52 | 100.0% |
| skills-available | full | 622 | 0 | 0.0% |
| plan-mode | full | 0 | 0 | n/a |
