# Response Model Corpus Report

Generated: 2026-09-13T19:08:10.145183+00:00Z
Source: `/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log` (9 `*_response.jsonl` files)

## Headline numbers

- Total `_response` entries: 1808
- Entries carrying an `answering_model`: 0
- Entries missing `answering_model`: 1808
- Entries carrying a `requested_model`: 0
- Entries where requested == answering: 0
- Entries where requested != answering: 0

## Status codes observed

- `200`: 1808

## content-type values observed

- none — no entry in the corpus carries a `content-type` header value (all entries predate the header-filter change; `_filter_response_headers` previously dropped it)

## content-encoding values observed

- none — no entry in the corpus carries a `content-encoding` header value (same reason as content-type above)

## Requested vs. answering model

No entry in the corpus carries `requested_model`/`answering_model` — the entire 1808-entry corpus predates this milestone's `addon.py`/`response_model_probe.py` change. Every worker/main proxy in this session is running from a frozen `src/logs/.proxy_live_<id>/proxy/` copy (see `src/proxy/DOCS.md` Gotchas); none can produce the new fields until killed and respawned. This is the expected, documented state as of this milestone — not a bug in the parsing logic (see `p8_answering_model_probe_test.py` for unit-level verification of the parser against synthetic SSE bytes).

