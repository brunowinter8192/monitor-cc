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

## 2026-09-13 — Review fix: abort survival + three-field model naming

Two findings from review, both fixed in this same session, same file (no new process-docs file).

### Finding 1 — the response-hook-only write silently lost entries on the common path

The first version of this milestone moved the `_response` write from `responseheaders()` (fires
before any body bytes) to `response()` (fires only after the full body has streamed) so the entry
could carry `answering_model`. That is wrong for this project specifically: `process-docs/abort_cascade/`
documents that Claude Code aborts an in-flight SSE stream and refires on almost any incoming event
(user keystroke, background-task completion, subagent task-notification) — cascades of depth 3+ are
observed, not hypothetical, and the abort-cascade doc's own framing is that this is the *common* case
during active orchestration, not an edge case.

Traced the actual mitmproxy behavior on abort by reading
`venv/lib/python3.14/site-packages/mitmproxy/proxy/layers/http/__init__.py::handle_protocol_error`
(reached when the client closes the connection mid-response): it calls `HttpErrorHook`, never
`HttpResponseHook`. `_hooks.py`'s `HttpErrorHook` docstring states the exact guarantee: "Every flow
will receive either an error or an response event, but not both." So `response()` genuinely never
fires for an aborted flow — moving the write there was a straight regression, not a subtle one.

**Fix:** `_write_response_entry` is now called from both `ProxyAddon.response()` and a new
`ProxyAddon.error()` hook. Guarded by `flow.metadata["mc_response_entry_written"]` so a violation of
mitmproxy's "never both" guarantee (future version change, or my own misunderstanding of it) degrades
to a no-op second call rather than a duplicate log line.

**Verified for both abort shapes named in review, via `dev/proxy_instrumentation/p9_response_entry_abort_survival_test.py`:**
- *Abort right after headers, before the first chunk:* `responseheaders()` already ran (so
  `flow.response` exists, headers/status known), but the probe was never called with any bytes —
  `mc_answering_model_state["model"]` is still `""`. `error()` fires, entry is written with
  `answering_model: ""`. This exactly matches what the OLD (pre-this-milestone) code produced for
  every abort — headers survive, model is unknown either way, nothing regresses.
- *Abort mid-stream, after `message_start` already arrived:* since `message_start` is documented as
  the SSE stream's first event, in practice the model is very often already captured in
  `mc_answering_model_state` by the time any abort happens later in the stream. `error()` fires,
  `_write_response_entry` reads whatever the probe closure had already found — the entry carries a
  real `answering_model` even though the response never completed. This is strictly better than the
  pre-milestone baseline (which had no `answering_model` field at all).
- Both cases produce exactly one JSONL line (double-write guard test), and a normal non-aborted
  completion still goes through `response()` unchanged.

**Landmine for whoever touches this next:** any FUTURE per-request write that needs to survive to the
same degree — i.e. anything that should exist "once per REQ, regardless of how the REQ ended" — must
follow the same response()+error() dual-registration pattern. Writing only in `response()` (or only in
`responseheaders()` if it needs body data) is a proven-repeatable mistake here specifically because
this project's traffic pattern makes aborts frequent, not rare.

### Finding 2 — `requested_model` collapsed three distinct values into one ambiguous field

Original field `requested_model` was sourced from `mc_modified_payload` — deliberately, reasoning
documented above under "Design choice", because that is what actually went out on the wire for this
exact HTTP exchange. Review's point (independent of whether the proxy pane today happens to render
`_forwarded.model` or something else — I checked `src/proxy_display/forwarded_parser.py` and the pane
row's `model` field is in fact sourced from `_forwarded`, i.e. post-override, contra the review
description, but the underlying concern holds regardless of which one the pane currently shows) is
structural: there are three genuinely distinct model values in play for one request/response cycle,
and cramming two of them behind one ambiguous name (`requested_model`) forces every future reader to
either guess which one it is or go read this file. Not defensible against "names the reader cannot
mis-resolve."

**Fix — three explicit fields, all three always present when known:**
- `cc_requested_model` — `mc_original_payload["model"]`, what Claude Code itself put in the request
  it composed (before any proxy modification).
- `proxy_forwarded_model` — `mc_modified_payload["model"]`, what the proxy actually sent to
  `api.anthropic.com` for this exchange (can differ from the above under
  `inject_helpers._inject_legacy_model_override`'s config-driven override path).
- `answering_model` — unchanged, from the SSE probe.

A `cc_requested_model != proxy_forwarded_model` mismatch is now a directly visible, correctly-named
signal that a model override fired for this request — pinned by
`p9_response_entry_abort_survival_test.py::_test_model_override_visible_via_three_distinct_fields`.

`dev/proxy_instrumentation/response_model_corpus_report.py` was updated to the new field names and
adds one more headline number: count of entries where `cc_requested_model != proxy_forwarded_model`
(override-active count). Re-ran against the same 9-file real corpus — all three new fields are still
0/N-present for the same frozen-live-copy reason as before (see original entry above); this is expected,
not a new finding.

## 2026-09-13 — Recap close-out

Session end. Both review findings from the same day are fixed and committed (see section above).
Final touched-file inventory (`git diff integration --name-only`): `dev/proxy_instrumentation/DOCS.md`,
`dev/proxy_instrumentation/md/response_model_corpus_report.md`,
`dev/proxy_instrumentation/p8_answering_model_probe_test.py`,
`dev/proxy_instrumentation/p9_response_entry_abort_survival_test.py`,
`dev/proxy_instrumentation/response_model_corpus_report.py`,
`process-docs/proxy_instrumentation/2026-09-13_answering_model_capture_m1.md`, `src/proxy/DOCS.md`,
`src/proxy/addon.py`, `src/proxy/response_model_probe.py`. `src/proxy/DOCS.md` and
`dev/proxy_instrumentation/DOCS.md` LOC values checked against `wc -l` on this pass — both already
current (were updated as part of the review-fix commit, not stale).

Two unit-level regression guards now exist and both pass as of this commit:
`dev/proxy_instrumentation/p8_answering_model_probe_test.py` (the SSE parser itself — split-chunk,
budget, pass-through, gzip-gap) and `dev/proxy_instrumentation/p9_response_entry_abort_survival_test.py`
(the `_write_response_entry`/`response()`+`error()` wiring — abort survival, double-write guard,
three-field naming). Run both after any future touch to `addon.py`'s response/error hooks or
`response_model_probe.py`.

**Still open for a later milestone (not this one):** display-side rendering of
`cc_requested_model`/`proxy_forwarded_model`/`answering_model` in the proxy/token pane —
`src/panes/`, `src/format/`, `src/proxy_display/` were read for caller-safety only, never touched, per
scope. Live verification of the whole mechanism (real compressed/uncompressed content-encoding
reading, a real override-mismatch instance, an actually-observed abort producing a partial-model
entry) needs a proxy restart, which is explicitly out of scope for this session — the corpus report
script exists precisely so a future session can re-run it after a restart without re-deriving anything.

## 2026-09-13 — M2: answering model in the token pane

New task, same file (M2 continues the same area). Scope: `src/panes/token_pane.py`,
`src/format/token_format.py`, `src/proxy_display/side_logs.py` only — `src/proxy/` untouched (M1
is merged and closed), warnings pane and proxy pane untouched.

### How the entry flows from read_response_log to the rendered line

`token_pane._refresh_tokens_data` calls `find_response_log_path` + `read_response_log`, merges the
result into module-level `_response_rid_map` (`{request_id: entry}`), and passes it into
`format_cache_tracker(..., response_rid_map=_response_rid_map, ...)` on every render
(`_build_tokens_output`). `format_cache_tracker` threads it down through `_render_turn_lines` →
`_render_expanded_call_lines(call, response_rid_map)`, which now calls three line-group renderers in
order: usage-extras, rate-limit, **`_render_answering_model_line`** (new), content-blocks. Each group
looks up its own data via `call['request_id']` — `response_rid_map` is keyed by `request_id`
end-to-end, never by `flow_id` or list position, matching the existing rate-limit lookup.

**The one shape change that makes this possible:** `side_logs.read_response_log` used to store only
`entry.get('headers', {})` per `request_id` — everything else in the M1 `_response` entry
(`cc_requested_model`, `proxy_forwarded_model`, `answering_model`) was discarded at read time, before
it ever reached the pane. Changed to store the full parsed `entry` dict. `_render_rate_limit_lines`
updated in lockstep (`entry.get('headers')` instead of treating the stored value itself as the headers
dict) — this is the one place the shape change could have silently broken something, since it was
already a caller of the old contract; covered by
`dev/panes/answering_model_line_test.py::_test_rate_limit_lines_still_work_with_new_shape`.

### Exact rendered line, both cases (raw bytes, verified via direct call)

Equal (`proxy_forwarded_model == answering_model`, or `proxy_forwarded_model` unknown):
```
    \x1b[2mmodel: claude-opus-4-6-20260701\x1b[39m
```
(`DIM` = `\x1b[2m`, `SOFT_RESET` = `\x1b[39m` — same DIM+SOFT_RESET pattern every other unobtrusive
expanded-detail line in this file already uses, e.g. the `rl:`/`tier:`/`5m:` lines.)

Mismatch (`proxy_forwarded_model != answering_model`, both known):
```
    \x1b[38;2;243;139;168mmodel: claude-opus-4-6-20260815\x1b[39m
```
(`RED` = `\x1b[38;2;243;139;168m`.) Both confirmed byte-for-byte via a direct
`_render_answering_model_line(call, response_rid_map)` call in a throwaway REPL snippet during
implementation, then pinned as hard `==` assertions in
`dev/panes/answering_model_line_test.py::_test_equal_models_render_dim` /
`_test_mismatch_models_render_red`.

### Empty-field safety

Three cases, all return `(lines=[], keys=[])` — i.e. render nothing, assert nothing:
1. No entry at all for this `request_id` (`response_rid_map.get(rid)` is `None` — e.g. `_response`
   log not yet polled this far, or the request predates M1).
2. Entry present but `answering_model == ''` — the documented M1 case: stream aborted before the
   first chunk, or the SSE body was compressed and the probe never matched (see M1 entry above).
3. `call` itself carries no `request_id` (defensive — shouldn't happen given `extract_cache_turns`
   always sets it, but the function must not `KeyError`/`None`-index on it).

One more asymmetric case, deliberately NOT a mismatch: `answering_model` known but
`proxy_forwarded_model` empty/missing. Colors DIM, not RED — coloring red here would assert a
mismatch the code cannot actually verify. Pinned in
`_test_missing_forwarded_model_shows_plain`.

### Tests run, numbers before/after

- `dev/panes/answering_model_line_test.py` (NEW, this task) — 7 assertions, all pass, both before
  writing the fix would be meaningless (function didn't exist) and after.
- `dev/display/test_hover_map.py` — **45 passed, 0 failed**, identical before and after (this suite
  doesn't touch `response_rid_map` at all, included as a broad caller-safety sweep over
  `format_cache_tracker`/related render code).
- `dev/panes/render_byte_identity.py` (pinned via `PANES_BYTE_IDENTITY_JSONL=/tmp/mc_pin/pinned_session_prefix.jsonl`,
  a frozen 300-line prefix of the newest real session JSONL at task start) — HASH before:
  `95aa658e7b90090cd21630d4117b06fbb6b25fd3111d052fe65c081a18dec532`; HASH after fixing the
  fixture's `response_rid_map` shape to match the new full-entry contract (and extending it with a
  mismatching model pair, since this harness is this exact render path's one dedicated fixture):
  `5c7fc44cb8aab9f6302ba6a3d59548a88c833eee213a6593469905d8a70d95a9`. The hash change is the
  EXPECTED, intended result of a real behavior change, not a regression — confirmed by first running
  the harness with the OLD fixture shape against the NEW code (hash
  `c412908cd19402f4a911ac313e188f519584c764302073b62f88bc637a9eca0a`, differs from both — silently
  losing the `rl:`/warn lines because `entry.get('headers')` no longer finds anything in a
  flat-headers-shaped dict), which is what proved the fixture itself needed updating, not just
  tolerating a new hash.
- `dev/pane_search/p6_tokens_pane_parity_test.py`, `dev/pane_search/p7_workers_pane_parity_test.py`,
  `dev/click_ui/p2_copy_click_probe.py` — **could not complete in this sandbox**: all three call
  `os.get_terminal_size()` (via `token_pane._build_tokens_output` / `worker_render._workers_terminal_size`)
  which raises `OSError: [Errno 25] Inappropriate ioctl for device` with no real TTY attached. Verified
  this is pre-existing and unrelated to this change: `git stash` + re-run reproduces the IDENTICAL
  failure (same 3/3/2 PASS lines printed before the same crash) on the unmodified code. Running under
  `script -q /dev/null` gets past `get_terminal_size` (pty provides a size) but then hits an unrelated
  `IndexError` in `_compute_cache_viewport`, ALSO reproduced identically on unmodified code via the
  same stash test — pre-existing environment limitation, not a regression caused here. Landmine for
  whoever runs these next in a similar sandboxed worker: they need a real TTY (or a `pty`-based
  harness fix, not attempted here — out of scope) to run to completion; do not treat their failure to
  start as a signal about `src/format/`/`src/panes/` correctness without first checking they fail
  identically on `git stash`.

### Design note carried over from M1 review

The comparison target is `proxy_forwarded_model`, not `cc_requested_model`, per this task's explicit
instruction: the API answered the request the proxy actually sent, and a `cc_requested_model` /
`proxy_forwarded_model` difference is our own override feature firing, not an API deviation. Matches
the M1 rationale already recorded above under "Design choice" in the first dated section of this file.

## 2026-09-13 — Recap close-out (M2)

Session end for the M2 task. Self-audit (`git diff integration --name-only`, integration already
carries M1 as of `55de9bd merge: worker modelcheck`): `dev/panes/DOCS.md`,
`dev/panes/answering_model_line_test.py`, `dev/panes/render_byte_identity.py`,
`process-docs/proxy_instrumentation/2026-09-13_answering_model_capture_m1.md`, `src/format/DOCS.md`,
`src/format/token_format.py`, `src/panes/DOCS.md`, `src/proxy_display/DOCS.md`,
`src/proxy_display/side_logs.py`. All touched-file DOCS.md entries (`dev/panes/DOCS.md`,
`src/format/DOCS.md`, `src/proxy_display/DOCS.md`, `src/panes/DOCS.md`) were kept current inline
during the task itself, not deferred to this recap pass — checked again now against `wc -l` on each
file, all LOC values and Purpose/Reads/Writes text still match the committed state, nothing to fix.

**One thing worth flagging for whoever picks up the next milestone in this area:** the three
TTY-dependent pane-parity harnesses (`dev/pane_search/p6_tokens_pane_parity_test.py`,
`dev/pane_search/p7_workers_pane_parity_test.py`, `dev/click_ui/p2_copy_click_probe.py`) cannot run to
completion in this sandboxed worker environment at all (`os.get_terminal_size()` has no real TTY to
query). This is a standing environment gap, not something either M1 or M2 introduced or should try to
fix — confirmed via `git stash` both times work in this area touched pane rendering. Don't spend time
debugging it as if it were a regression; it reproduces identically on unmodified `integration` HEAD.

M1 + M2 are both complete and merged into `integration` as of this recap. No further work on this
`_response`-model-capture line is planned by this worker — the milestone as scoped (M1: capture +
survive-abort + three-field naming; M2: token-pane display) is done.
