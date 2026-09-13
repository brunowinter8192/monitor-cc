# Answering-Model Capture — M1 (response-side, no body buffering)

## Scope of this entry

Worker task `modelcheck`. Delivers M1 only: the `_response` dual-log entry now records
`requested_model` and `answering_model` side by side, via a streaming `flow.response.stream`
callable that inspects SSE bytes for `message_start.model` without buffering the response body.
Display-side rendering of these two new fields is explicitly out of scope (a later milestone) —
`src/panes/`, `src/format/`, `src/proxy_display/` were read for caller-safety only, never edited.

## What changed and why

**`src/proxy/response_model_probe.py` (new, 28 LOC).** `make_answering_model_probe()` returns
`(probe, state)`. `probe` is the callable assigned to `flow.response.stream`; it is called once per
response-body chunk (plus one final `b""` call at end-of-message, per
`mitmproxy/proxy/layers/http/__init__.py::state_stream_response_body`). It always returns the input
chunk unmodified — the pass-through guarantee holds unconditionally, regardless of parse outcome.
Internally it accumulates chunks into a `bytearray` and re-searches the *whole* accumulated buffer
each call with `_MESSAGE_START_MODEL_RE` (a DOTALL regex requiring `"type":"message_start"` before
`"model":"..."` in the same buffer). Re-searching the whole buffer on every call — not just the new
chunk — is what makes a split `message_start` event safe: if chunk 1 ends mid-JSON with no complete
match, `state["done"]` stays `False` and the next chunk's bytes get appended before the retry.
Verified in `dev/proxy_instrumentation/p8_answering_model_probe_test.py::_test_split_across_two_chunks_finds_model`
by slicing a real SSE `message_start` payload at an arbitrary byte offset inside the `"model"` value
itself and feeding the two halves as separate `probe()` calls — the model is absent after chunk 1,
present and correct after chunk 2, and both chunks come back byte-identical to their input.

**Byte budget = 8192 bytes** (`_MODEL_PROBE_BYTE_BUDGET` in `response_model_probe.py`). Once the
buffer reaches this size without a match, `state["done"]` is set `True` permanently and every
subsequent call (including ones that *would* contain a valid `message_start`, per the
`_test_budget_exceeded_stops_inspection` case) skips the regex search entirely and just returns the
chunk. This is deliberate — Anthropic's `message_start` is documented as the stream's first event
and is small (message metadata only, no content), so 8 KB is generous headroom for TCP-segment
fragmentation without ever meaningfully buffering the body (worst case: one extra bytearray copy of
at most ~8 KB per response, freed once `done` flips).

**Compressed bodies are an accepted, documented gap, not a bug to fix.** The regex operates on raw
bytes; if `content-encoding` is `gzip` (or any other encoding), the SSE text never appears
uncompressed in the buffer and the probe simply never matches — `answering_model` stays `""`, cost
is at most one wasted 8 KB scan. `_test_gzip_body_defeats_parsing` pins this exact behavior with a
real `gzip.compress()`'d payload, so a future change that silently added a decompression path would
break this test loudly rather than the gap regressing unnoticed. The task explicitly said to report
this rather than build a decompression path — see `## content-encoding values observed` below for
what the corpus actually shows once real traffic is captured.

**`_filter_response_headers`** (`addon.py`) now keeps `content-type` and `content-encoding` in
addition to the prior five keys — needed precisely to answer the "is the SSE stream compressed"
question from recorded data, since the probe itself cannot decode compressed bytes to tell you.

**The `_response` entry write moved from `responseheaders()` to `response()`.** This was not
optional — `responseheaders()` fires when the status line + headers arrive, *before* any body bytes
are seen, so the answering model cannot possibly be known yet at that point. `response()` fires
after `state_stream_response_body` finishes (confirmed by reading
`mitmproxy/proxy/layers/http/__init__.py`: the `ResponseEndOfMessage` branch calls
`self.flow.response.stream(b"")` — the final probe call — and only afterward calls
`self.send_response(already_streamed=True)`, which is what triggers the `response` hook). By the
time `response()` runs, `flow.metadata["mc_answering_model_state"]["model"]` already holds its final
value. Trade-off accepted: previously `_response` entries were written unconditionally at
`responseheaders()` time regardless of what happened to the body; now a connection that dies mid-stream
before `ResponseEndOfMessage` fires would skip the `_response` write entirely (whereas before it
would still have written headers-only). Not tested here — no repro exists in recorded data, and
building a synthetic one would be a fixture-invented edge case, not an observed failure.

## Exact new `_response` entry shape (quoted, from `addon._write_response_entry`)

```json
{
  "flow_id": "<flow.id>",
  "timestamp": "<iso8601>Z",
  "request_id": "<from flow.response.headers>",
  "status_code": 200,
  "headers": {"...": "... (filtered subset, now includes content-type/content-encoding)"},
  "requested_model": "<mc_modified_payload['model']>",
  "answering_model": "<probe state['model'], '' if not found>"
}
```

**Design choice: `requested_model` is sourced from `mc_modified_payload`, not `mc_original_payload`.**
Both are available on `flow.metadata` (per the task prompt). `mc_original_payload['model']` is what
Claude Code asked for and is already captured verbatim in the `_original` dual-log's `model` field —
duplicating it here adds nothing new. `mc_modified_payload['model']` is what the proxy actually put on
the wire for *this* HTTP request/response pair (after `_inject_model_override`'s legacy-override path,
which can rewrite `model` — see `src/proxy/inject_helpers.py::_inject_legacy_model_override`). Pairing
"what we actually asked the API for on this exchange" with "what the API says it answered with" is the
meaningful mismatch signal (e.g. would catch a silent API-side model substitution); pairing CC's original
ask against the answer would also catch every *intentional* proxy-side override as a false "mismatch".
If a future milestone wants the CC-originated model in the same record too, it is a one-line add
(`mc_original_payload.get('model', '')`) — deliberately left out here to stay inside M1's stated scope.

## Corpus report — what real data shows as of 2026-09-13

`dev/proxy_instrumentation/response_model_corpus_report.py` reads every `*_response.jsonl` under the
main checkout (`/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log` — the dev worktree
itself carries no logs, same reason as every other `pN_*` probe in this directory). Result at time of
writing: **1808 entries across 9 files, all status 200, 0 with `answering_model`/`requested_model`,
0 with `content-type`/`content-encoding` header values.** This is the expected pre-restart baseline,
not a finding about the parser — every live proxy in this session (main + all active workers) runs
from a frozen `src/logs/.proxy_live_<id>/proxy/` copy taken before this change landed (see
`src/proxy/DOCS.md` Gotchas, "Hot-reload resets..." / "Worker proxies are frozen at spawn time").
None of them can produce the new fields until killed and respawned against this code. Re-run the
report after a restart to get a real compressed/uncompressed content-encoding reading and a real
requested-vs-answering comparison — do not treat the current all-zero numbers as a red flag.

## Landmines for the next agent

- **Do not try to live-verify this in the current session.** The task explicitly said not to — the
  frozen-copy mechanic means a live check right now would just prove the old code still runs, telling
  you nothing about the new code.
- **`response_model_probe.py`'s regex assumes `message_start` is genuinely the first SSE event.** If a
  future Anthropic API change interposes something before it (the task's own source material notes
  packet boundaries — not event *ordering* — are the documented unreliability), the DOTALL regex with
  no distance cap would still find a `message_start` later in the buffer, just after burning more of
  the 8 KB budget. This is fine at current budget size; if the budget ever needs to grow substantially,
  reconsider whether the regex should be bounded to avoid a pathological far-scan.
- **The mitmproxy source used to confirm this design lives in this repo's own `venv/`,** not
  system-installed — `venv/lib/python3.14/site-packages/mitmproxy/http.py` (the `stream` attribute
  type signature, line ~247) and
  `venv/lib/python3.14/site-packages/mitmproxy/proxy/layers/http/__init__.py`
  (`state_stream_response_body`, confirming per-chunk callable semantics and hook ordering). No system
  `mitmproxy` Python package exists outside this venv in this environment — `pip3 install mitmproxy`
  fails (`externally-managed-environment`, no network access from a worker session anyway).
