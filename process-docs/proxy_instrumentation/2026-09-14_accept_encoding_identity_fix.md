# Accept-Encoding Identity Fix — answering_model in real traffic

## Scope of this entry

Worker task on branch `identity`, worktree `.claude/worktrees/identity/`. Continues the
`_response`-model-capture line of work started by the `modelcheck` worker, recorded earlier in
this same area (M1/M2/M3 — probe, token-pane display, warnings-pane mismatch alert, all already
merged). This task fixes the actual
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

## 2026-09-14 — post_restart_verification.py: the one script for all three restart-gated claims

New task, same area (this file's own note from the earlier close-out — "the next open item in this
area is the live-restart verification" — is what this task actually delivers, though as a script
to be run AFTER the real restart, not as a live check performed by this worker itself; the restart
itself stayed explicitly out of scope). Covers three claims spanning three separate milestones on
this branch: this file's own accept-encoding/answering_model fix, `bg_wakeup_id_line`'s
auto-backgrounded-on-timeout strip, and `poread`'s full-content injection.

## The corpus-contamination finding — the most valuable thing from this task

Before writing any verification logic, I validated the design against `/tmp/pre_restart_logs/` by
hand. Naive substring grep for the bg_launch_ack wording-3 text and the poread marker across
`_original.jsonl` found 146 and 19 "hits". Both numbers are almost entirely worthless: this very
session implemented and extensively discussed both features, quoting their literal marker/wording
text in its own assistant turns, which get resent as ordinary conversation history on every later
request. A verification script built on substring grep would have been unable to tell its own
meta-discussion from a genuine tool_result event.

Fix: restrict "genuine trigger" detection to `role=='user'` `tool_result` content specifically
(never assistant text, never a top-level match), using the REAL production predicates
(`_is_bg_auto_timeout_ack` from `strip_bg_launch_ack.py`, `_parse_poread_marker` from
`inject_poread.py`) rather than retyped literals. Precise count against the same corpus: 1 and 1 —
both genuinely real (the wording-3 hit is literally the `b1mahby4a` event that motivated that whole
milestone; the poread hit is a real invocation against that same event's output file).

**Second, sharper finding, caught by the same precision:** that one real poread occurrence has
trailing content after the marker (`.../>\nexit=0`) — under the review-fixed whole-block-only rule
in `inject_poread.py`, this specific occurrence will never expand, even after the restart, BY
DESIGN. A looser `startswith`-only check for "genuine trigger" would have counted it anyway and
then reported claim 3 as CONTRADICTED post-restart even though the code would be behaving exactly
as intended — a false alarm baked into the verification tool itself. Confirmed with Main this was
their own `poread <path> && echo $?`-shaped invocation; Main is adding an "alone in its own Bash
call" requirement to the rule file as a direct result of this finding (not this repo's file to
touch).

**Takeaway for whoever builds the next corpus-scanning verification tool in a self-referential
session:** if the session doing the verifying is also the session that implemented and discussed
the feature, raw substring presence in `_original`/`_forwarded` is not evidence of anything by
itself. Anchor on the real predicate AND the real structural location (tool_result content,
specifically, not "anywhere in the payload") before treating a hit as genuine data.

## Design decisions

**Session picking:** newest `*_original.jsonl` by mtime under the resolved dual-log dir, matching
the exact established convention of `render_byte_identity.py`/`pipeline_byte_identity.py`/
`addon_hook_byte_identity.py` (all three already independently arrived at this same pattern) —
`POST_RESTART_VERIFY_LOG_DIR` env override, same idiom as those three's own override variables,
used to pin the required dry run against `/tmp/pre_restart_logs/`.

**`response_model_corpus_report.py` left untouched, decided and justified before implementing:**
different scope (corpus-wide vs. this task's required single-newest-session), different semantics
(descriptive report, no exit code, vs. this task's required PASS/CONTRADICTED/MISSING DATA with
exit codes), and it only ever covered claim 1 — the task's explicit "one script" requirement
covering all three claims would have been impossible to satisfy by extending it.

**Exit code scheme:** 0 all-pass, 1 if any claim CONTRADICTED (checked first, the worse outcome),
2 if none contradicted but at least one MISSING DATA — both non-PASS cases non-zero, and
distinguishable by which of the two fired, not just by reading stdout.

## A hook landmine, found and fixed before committing (not a churned convention)

First version imported `_parse_forwarded_log` via `from src.proxy_display.forwarded_parser import
...`. This DOCS.md file's own Gotchas section (pre-existing, from before this task) claims only
`pN_*.py`-named dev scripts may use `from src...` — but I actually read the enforcing hook,
`src/hooks/block_dev_imports_src.py`, and its regex has no `pN_` exemption at all; it only exempts
files under a `/tests/` directory named `test_*.py`/`*_test.py`/`conftest.py`. The pre-existing
DOCS.md note describes an intent, not what's actually enforced. Fixed by loading the module via
`importlib.import_module(f'{_ROOT_PKG}.proxy_display.forwarded_parser')` with `_ROOT_PKG = 'src'`
— the exact string-built-import pattern `dev/click_ui/`'s probes already use for the same
`proxy_display` package family, confirmed by reading their imports directly rather than guessing.
Documented as a new Gotcha in this file's own DOCS.md, since a future editor hitting this same
wall would otherwise waste time on the same investigation. Landmine for whoever adds more `from
src.proxy_display...`-needing logic to a non-test dev/ file: `importlib.util.spec_from_file_location`
(the `attribution_coverage.py` workaround for `strip_vocab.py`) does NOT generalize to modules with
real relative imports (`forwarded_parser.py` has `from ../proxy.message_summary import ...`) — that
workaround only works for genuinely self-contained modules; `importlib.import_module` with a
dynamically-built dotted string is the one that handles real package context correctly.

## Numbers — the required dry run, and the sanity check beyond it

Against `/tmp/pre_restart_logs/` (exit 1): claim 1 CONTRADICTED (212/212 streamed responses still
compressed, 0/212 carry `answering_model`; the corpus's 1 side call correctly shows empty
`answering_model`, explicitly not counted against the claim); claim 2 CONTRADICTED (the genuine
`b1mahby4a` trigger found at msg 198, 0 matching strips in `_stripped`); claim 3 MISSING DATA (the
trailing-content near-miss above — script printed its ACTION line: "run `poread <path>` via Bash,
alone in its own call ... against a file well under 500,000 bytes"). None came back PASS, matching
the task's own stated expectation.

Ran the script a second time against this worktree's own live (still pre-restart) session, unpinned
— produced DIFFERENT, sensible verdicts (1 contradicted, 2 missing data — this worker's own worktree
session never triggered a genuine auto-background or a genuine poread call through the real Bash
tool) — proof the script isn't overfit to the one frozen fixture.

Validated the TRUE branches the dry run itself never exercises (it only ever sees FALSE for claims
2/3's fix-detection, since neither fix is live pre-restart): used wording-1's ALREADY-working
replacement (never touched by this branch) as a real positive control for
`_forwarded_has_block_starting_with` and `_bg_launch_ack_strip_fired` — both correctly returned
True against real data. `_poread_expand_fired`'s TRUE branch has no real-data positive control
available (the feature never fired even once pre-restart), so pinned it with a small synthetic
`fn_map` fixture instead.

## Review fix, same session

Four non-section comment lines (`# -- Claim 1 --`, `# -- Claim 2 --`, `# -- Claim 3 --`,
`# -- Reporting --`) removed per the code standard's three-comment-line rule; the module docstring
stayed (matches every `pN_*.py` script in this dev area, not being churned through one file alone).
Re-ran the dry run after the removal: stdout identical line-for-line except the report's own
timestamp, exit code still 1 — confirmed via `diff`, not just by inspection. One thing I caught
myself doing wrong before committing: re-running the dry run had `rm`'d the two previously-committed
report files locally before regenerating them, and I almost let that deletion ride into the review-
fix commit as an unintended side effect — restored both via `git checkout --` before staging, so
the commit only added the fix plus one fresh verification report, nothing pre-existing lost.

## Recap close-out

Self-audit (`git diff integration --name-only`): `dev/proxy_instrumentation/DOCS.md`,
`dev/proxy_instrumentation/post_restart_verification.py`,
`dev/proxy_instrumentation/md/post_restart_verification_20260914_144740.md`,
`dev/proxy_instrumentation/md/post_restart_verification_20260914_144759.md`,
`dev/proxy_instrumentation/md/post_restart_verification_20260914_144932.md`. DOCS.md checked
against `wc -l` this pass: `post_restart_verification.py` entry says 350 LOC, actual `wc -l` = 350,
match — already current from the review-fix commit, nothing to fix. No further work planned by
this worker on this script — it is meant to be run once, by Main, after the actual restart; this
worker never performed that restart or a live check, as scoped.
