# Response Model Corpus Report

Generated: 2026-09-13T19:15:21.740602+00:00Z
Source: `/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log` (9 `*_response.jsonl` files)

## Headline numbers

- Total `_response` entries: 1892
- Entries carrying an `answering_model`: 0
- Entries missing `answering_model`: 1892
- Entries carrying a `proxy_forwarded_model`: 0
- Entries where proxy_forwarded_model == answering_model: 0
- Entries where proxy_forwarded_model != answering_model: 0
- Entries where cc_requested_model != proxy_forwarded_model (override active): 0

## Status codes observed

- `200`: 1892

## content-type values observed

- none — no entry in the corpus carries a `content-type` header value (all entries predate the header-filter change; `_filter_response_headers` previously dropped it)

## content-encoding values observed

- none — no entry in the corpus carries a `content-encoding` header value (same reason as content-type above)

## cc_requested_model vs. proxy_forwarded_model vs. answering_model

No entry in the corpus carries `cc_requested_model`/`proxy_forwarded_model`/`answering_model` — the entire 1892-entry corpus predates this milestone's `addon.py`/`response_model_probe.py` change. Every worker/main proxy in this session is running from a frozen `src/logs/.proxy_live_<id>/proxy/` copy (see `src/proxy/DOCS.md` Gotchas); none can produce the new fields until killed and respawned. This is the expected, documented state as of this milestone — not a bug in the parsing logic (see `p8_answering_model_probe_test.py` for unit-level verification of the parser against synthetic SSE bytes).

