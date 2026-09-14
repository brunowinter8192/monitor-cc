# Accept-Encoding Identity Fix — answering_model in real traffic

## Scope of this entry

Worker task on branch `identity`, worktree `.claude/worktrees/identity/`. Continues the
`_response`-model-capture line of work started by the `modelcheck` worker
(`process-docs/proxy_instrumentation/2026-09-13_answering_model_capture_m1.md`, M1/M2/M3 — probe,
token-pane display, warnings-pane mismatch alert, all already merged). This task fixes the actual
reason `answering_model` was empty on every real (non-synthetic) request despite M1-M3 being
correct: the response body arriving compressed. Display-side code (`src/panes/`, `src/format/`,
`src/proxy_display/`) was explicitly out of scope and untouched.

## Root cause — handed down already measured, not re-derived here

Main gave this as pre-measured fact, and I did not re-derive it: every recorded `_response` entry
across the corpus at task start carried a `content-encoding` header — 55/58 `gzip`, 3 `br`. The
`br` entries are `content-type: application/json` non-streaming side calls answered by
`claude-haiku-4-5` (small side calls, e.g. title/classification calls), explicitly out of scope.
`response_model_probe.py`'s regex operates on raw wire bytes handed to `flow.response.stream` — a
compressed body never contains the literal `"message_start"` text, so the probe always burns its
8 KB budget and gives up. The instruction was explicit: do NOT build a decompression path, not even
as a fallback — fix it by asking the API for an uncompressed body instead.

## What changed

**`src/proxy/addon.py`** (321 → 326 LOC). New function `_request_identity_encoding(flow)`:
```python
def _request_identity_encoding(flow: http.HTTPFlow) -> None:
    flow.request.headers["accept-encoding"] = "identity"
```
Called from `ProxyAddon.request()` immediately after the existing
`flow.request.headers.pop("content-encoding", None)` line — still inside the `_is_messages_request`
gate that already scopes every other request mutation in this hook. This is byte-identical to what
mitmproxy's own `Request.anticomp()` does internally (`venv/lib/python3.14/site-packages/mitmproxy/
http.py:918`).

**Design decision: own scoped hook, not mitmproxy's global `anticomp` option.** Read
`venv/.../mitmproxy/addons/anticomp.py` and `Request.anticomp()` first — the global `--set
anticomp=true` option would flip `accept-encoding` for EVERY flow this mitmdump instance proxies,
not just `POST /v1/messages` to `api.anthropic.com`; this proxy is CC's general HTTP(S) forward
proxy (env-var routed), so other traffic (WebFetch, MCP servers, anything else CC routes through it)
would silently lose compression too — well outside "scoped to the Messages requests." It would also
require editing `src/claude_proxy_start.sh` (shared infra, more rollout risk) instead of one line in
an already-existing, already-scoped hook, and would live in mitmdump's CLI/opts machinery where no
`dev/` harness can unit-test it directly.

**Also considered and rejected: calling `flow.request.anticomp()` directly instead of writing the
header myself.** Would have been marginally more "reuse mitmproxy's own tested code," but four
existing `dev/` fake-flow harnesses construct a bare `_FakeRequest`/`_FakeHeaders(dict)` with no
`anticomp()` method and drive `addon.request(flow)` directly:
`dev/proxy/addon_hook_byte_identity.py`, `dev/bg_wakeup_id_line/p2_bg_escape_probe.py`,
`dev/native-model-start/p3_cache_breakpoints_probe.py`,
`dev/timer-loop/p3_project_scope_incident_probe.py`. Calling `.anticomp()` would `AttributeError`
in all four, forcing unrelated edits to 4 files just to keep a one-line header-set testable. Writing
the header directly needs zero changes to any of them (`_FakeHeaders(dict)` already supports plain
`__setitem__`).

## Test added

`dev/proxy_instrumentation/p11_request_identity_encoding_test.py` (51 LOC, next number in this
area's `pN_` sequence) — direct unit test of `_request_identity_encoding` against a fake
flow/headers object: asserts the header is set from empty, and that an existing `"gzip, br"` value
gets fully overwritten (not merged) to `"identity"`.

**Before/after evidence, both actually run, not asserted from memory:**
- Before implementing: `from proxy.addon import _request_identity_encoding` raised
  `ImportError: cannot import name '_request_identity_encoding'` — confirmed the function didn't
  exist pre-change.
- After: `[p11_request_identity_encoding_test] all checks passed`, exit 0.

## Existing regression guards, run before and after, all unaffected

`p8_answering_model_probe_test.py` (5 checks), `p9_response_entry_abort_survival_test.py`
(5 checks), `p10_model_mismatch_warning_test.py` (7 checks) — all PASS identically before and after.
None of the three touch `request()` or the new function; `response_model_probe.py` itself is
completely untouched by this milestone (no decompression path, per instruction), so
`p8::_test_gzip_body_defeats_parsing` still correctly documents the probe's permanent inability to
parse compressed bytes if it were ever handed any — that assertion is not stale, it is the tripwire
against someone later sneaking a decompression path into the probe itself.

`dev/proxy/addon_hook_byte_identity.py` is the one harness that actually drives
`ProxyAddon().request()` end-to-end (not just imported helper functions) — the real caller-safety
check for this change. First unpinned run showed DIFFERENT hashes before/after
(`6796958c7755b9aabf3a416fe5e90fbc41864be4f7e44abd6712319e2a40b87a`, 34 payloads, vs.
`8ba3827b69e28caaf6c959c340876e763bf1069154a4979c8077863c999af8fb`, 44 payloads) — **this was NOT a
regression signal.** `_source_log()` defaults to the newest `*_original.jsonl` by mtime under the
MAIN checkout's `src/logs/dual_log/`, and the file it picked
(`api_requests_worker_25c51a2e_identity_1789386926_original.jsonl`) was THIS VERY WORKER's own live
proxy session log, actively growing while I worked (34 → 44 lines between the two runs, still under
the harness's 60-line prefix bound). Re-ran pinned via the harness's own override,
`ADDON_HOOK_BYTE_IDENTITY_LOG=/tmp/pinned_original.jsonl` (a frozen copy, 46 payloads), before
(`git stash`) and after (`git stash pop`) on the identical source bytes: HASH IDENTICAL both times —
`f3ab512a2bd2c3a49638c828e7552ea3141260f8768cb6dacb40dcf8542ce9a7`. Proves the change writes nothing
different to any of the six hashed dual-log files — only `flow.request.headers` (never logged)
changes.

**Landmine for whoever next runs `addon_hook_byte_identity.py` from inside a live worker session:**
its default source-log auto-pick is NOT a frozen fixture — it is whatever `*_original.jsonl` under
the main checkout happens to have the newest mtime at run time, and a worker's own proxy session
actively writes to a file under that exact glob while the worker works. Two runs minutes apart can
disagree for reasons that have nothing to do with the code under test. Always use
`ADDON_HOOK_BYTE_IDENTITY_LOG=<pinned copy>` for a real before/after comparison; do not trust an
unpinned hash diff as a regression signal without checking `payloads: N` for a count change first.

## DOCS.md — a review-caught mistake, and the fix

First pass appended a clause to `addon.py`'s **Purpose** field in `src/proxy/DOCS.md` describing the
accept-encoding change (`... 'request()' also forces 'accept-encoding: identity' on the outbound
Messages request so the response body arrives uncompressed for 'response_model_probe'.`), landing
the sentence at 40 words. Documentation rules cap `DOCS.md` Purpose at one sentence, 25 words max —
missed on the first pass because the PRE-EXISTING Purpose sentence (`count_tokens requests pass
through unmodified`, 22 words) was already close to the cap and I didn't recount after appending.
Caught by review, fixed by dropping the appended clause entirely rather than trying to reword it
shorter — the fact stays fully discoverable via the **Writes** field (already updated: `flow.request.
headers (content-encoding popped, accept-encoding: identity forced via _request_identity_encoding)`)
and a new **Gotcha** paragraph added at the end of the file explaining the whole "why identity, not
decompression" reasoning. **Landmine:** any future one-clause append to an already-dense Purpose
line in this file needs an explicit word count check first, not just a read-through — the format
gives zero headroom on lines already near 22-25 words, and the natural instinct to bolt the new fact
onto the existing sentence is exactly what blows the cap.

## The `br` entries — investigated as asked, confirmed out of scope, no code change

Non-streaming `content-type: application/json` side calls answered by `claude-haiku-4-5`, same
`/v1/messages` endpoint as the streamed conversation calls (not a different path — this is why the
`_is_messages_request` gate can't distinguish them at request time, and why the fix necessarily
applies to both). This is not new handling for them: no branching was added, the accept-encoding
header is set unconditionally for every Messages request regardless of whether the response turns
out to stream. Functionally nothing changes for them after the fix either: Anthropic's non-streaming
JSON response body is `{"type": "message", ...}`, never `{"type": "message_start", ...}` — so the
probe's regex correctly finds nothing for these requests with or without compression, same behavior
as before, `answering_model` correctly stays `""` for them. No further work needed here; flagging it
only because the task asked what these entries actually were.

## What a live verification would need to show (not attempted this session)

Every running proxy (main + all live workers) executes a frozen `src/logs/.proxy_live_<id>/proxy/`
copy taken before this change lands (see `src/proxy/DOCS.md` Gotchas, "Hot-reload resets..." /
"Worker proxies are frozen at spawn time") — a live check in this session would only exercise the
old, pre-change code and prove nothing. After a real proxy restart, re-running
`dev/proxy_instrumentation/response_model_corpus_report.py` against fresh `*_response.jsonl` entries
should show: streamed-conversation entries with `content-encoding` absent or `identity` (not
`gzip`), and a non-zero, growing count of entries with `answering_model` populated for those same
streamed entries, with `cc_requested_model`/`proxy_forwarded_model`/`answering_model` agreeing in the
common no-override case. The `br`/JSON side calls should continue to show `answering_model: ""`
regardless — that remains correct, not a gap to chase.

## Recap close-out

Self-audit (`git diff integration --name-only`): `dev/proxy_instrumentation/DOCS.md`,
`dev/proxy_instrumentation/p11_request_identity_encoding_test.py`, `src/proxy/DOCS.md`,
`src/proxy/addon.py`. Both touched DOCS.md files checked against `wc -l` on this pass:
`src/proxy/DOCS.md`'s `addon.py` entry says 326 LOC, actual `wc -l src/proxy/addon.py` = 326, match;
`dev/proxy_instrumentation/DOCS.md`'s `p11_request_identity_encoding_test.py` entry says 51 LOC,
actual `wc -l` = 51, match. `addon.py`'s Purpose field re-verified at 22 words (within cap) after
the review fix. No further work planned by this worker on this line — the milestone (make
`accept-encoding: identity` reach the wire for Messages requests) is complete as scoped; the next
open item in this area is the live-restart verification described above, left for whoever runs it
next since it needs an actual proxy restart this session couldn't perform.
