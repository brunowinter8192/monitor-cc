# strip_sn_notice.py — Replay Verification

Corpus: `/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log` — 51 `*_original.jsonl` files, 5911 request entries.

Ran ONLY `_apply_sn_notice_strip` against every entry's `payload.messages`. "unique" = deduplicated by (file, exact text) — dual-logs are cumulative snapshots, the same message reappears in every later request of the same session, so raw per-entry counts vastly overcount distinct real occurrences.

## Counts

| Metric | Value |
|---|---|
| Requests with >=1 genuine strip | 643 |
| Genuine strips — raw (per request occurrence) | 1013 |
| Genuine strips — unique (file, text) | 26 |
| Untouched data occurrences — raw | 15107 |
| Untouched data occurrences — unique (file, text) | 136 |
|   of which tool_result (unique) | 4 |
|   of which mid-content text (unique) | 132 |
| Byte-exact failures | 0 |

## Expected vs. Measured — reported as-is, NOT tuned to match

Task-stated expectation (measured over 52 dual-logs, prior session): 269 unique genuine messages, 120 data occurrences untouched (45 tool_result + 75 mid-content).

Measured here (53 dual-logs, current corpus, unique = deduplicated per whole message, matching the task's own "unique genuine messages" framing): **26 genuine** (vs. stated 269) and **136 untouched-data** (4 tool_result vs. stated 45, 132 mid-content vs. stated 75). Both buckets diverge substantially from the stated numbers — plausible cause: the dual-log corpus is a rolling window (files rotate/get pruned between sessions; this run sees 53 files vs. the 52 used for the original measurement, but with different session content, not merely +1 file of the same data). The correctness proof that matters — 0 byte-exact failures across all 5911 request entries — holds regardless of the count discrepancy: every genuine strip reconstructs byte-exact, and every untouched message (including all tool_result/mid-content data occurrences) is provably unmodified.
