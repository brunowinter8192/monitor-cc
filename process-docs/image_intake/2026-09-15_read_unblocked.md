# Read taken back out of TOOL_BLOCKLIST (2026-09-15)

## Why this entry lives here, not in proxy_tool_stripping

`process-docs/image_intake/2026-09-13_main_session.md` opened the question of how a session gets
an actual image into its context once `Read`/`Edit`/`Write` were blocked, parked a proxy-side
image-injection mechanism as unbuilt and unmeasured, and closed with OCR as the working answer for
that session. This entry is the sequel to that question, not to the blocklist's own history: the
mechanism that changed is the tool blocklist (`TOOL_BLOCKLIST` in `src/constants.py`), and that
mechanism's own change log lives in `process-docs/proxy_tool_stripping/` (an area reference, not a
specific file — several dated entries there record every prior addition to the same frozenset).
Nothing from that area's own file set was edited for this change; per the write-once rule, their
"Read is blocked" statements stay correct as historical, dated snapshots.

## What changed

`Read` came back out of `TOOL_BLOCKLIST`. `Edit` and `Write` stay in. Diff of the frozenset's
membership:

- Before: `..., "SendFeedback", "ListAgents", "Read", "Edit", "Write"`
- After: `..., "SendFeedback", "ListAgents", "Edit", "Write"`

No other entry touched. `src/proxy/tools.py::_strip_unused_tools` and
`src/proxy/payload_helpers.py::_strip_blocked_tool_references` needed no code change — both filter
purely off the frozenset, the same mechanism every prior addition to this list has used.

This answers the image_intake question with a different mechanism than the one that entry parked:
instead of building proxy-side injection of a synthetic `image` content block into a Bash tool
result (still unbuilt, still unmeasured, still parked), the session now gets the real `Read` tool
back, which natively returns an `image` content block for PNG/JPG paths per its own captured
description (`dev/ToolsSystemPrompts/Read.md`: "Can read images (PNG, JPG, etc.) — presented
visually as multimodal LLM"). The proxy-side injection idea is not superseded or closed by this —
it remains a live option for the case Read cannot cover (an image arriving as a Bash byte stream
rather than a filesystem path) — but the direct blocker for the filesystem-path case is gone.

## The measured cost of carrying Read again

`dev/ToolsSystemPrompts/_index.md` is this repo's own measured per-tool description+schema
snapshot (captured against one specific CC version — the file's own Gotcha says to re-capture
rather than trust stale figures). For `Read`, as of that capture: **1779 description chars + 912
schema chars = 2691 chars total**, matching the literal captured text in
`dev/ToolsSystemPrompts/Read.md`.

That figure is an upper bound on the wire cost, not the wire cost itself, for a reason worth
recording precisely: `src/proxy/content_strip.py::_strip_tool_descriptions` runs unconditionally on
every tool present in the forwarded `tools` array — it already does this to `Bash` and `Skill`
today — blanking the top-level `description` field AND every per-parameter schema `description` to
`""` before the payload leaves the proxy. `Read` gets the identical treatment the moment it is no
longer blocklist-removed. So what actually reaches the API per request is the description-free
schema skeleton (property names, types, the `required` list, `additionalProperties`) — smaller than
2691 chars, by an amount this repo does not have a direct measurement for. `dev/ToolsSystemPrompts/
_review.md`'s own per-tool phase-B analysis put Read's description content at "denser than it
looks... 49% strip is the honest ceiling," which is a description-content judgment, not a measurement
of the post-`_strip_tool_descriptions` schema-only remainder — the two numbers should not be
conflated. No new number was computed for this entry; 2691 chars is the sourced figure, quoted with
this caveat rather than adjusted by an estimate.

## Two hooks go from dead code back to live code

`process-docs/model_selector/2026-09-13_thinking_toggle.md` recorded, at the time Read/Edit/Write
were added to the blocklist, that `src/hooks/hook_setup.py`'s `_HOOK_SCRIPTS` registrations matched
against the literal `"Read"` (`block_path_typo.py`, `block_read_directory.py`) and `src/utils.py`'s
`first_word_of_call`'s `Read` branch became unreachable — a `PreToolUse` hook only fires when the
model actually calls a tool it was offered, and Read was no longer offered. As of this change those
two hook registrations and that display-helper branch are reachable again: nothing about them was
modified, they were already written to handle Read calls correctly, they simply start firing again
the moment a session using the new blocklist calls Read. Worth knowing if a Read-tool-triggered hook
behavior reappears and looks surprising — it is not new code, it is previously-dormant code waking
back up.

## Two probe corrections, one verified and one not

`dev/proxy_instrumentation/p4_blocklist_223_probe.py`'s `EXPECTED_KEPT` constant and its top-of-file
docstring both stated `{Bash, Skill}` / `{Bash, Edit, Read, Write, Skill}` at different points —
already inconsistent with each other before this change, a drift left over from the 2026-09-13
Read/Edit/Write addition that updated the constant but not the docstring's prose. Both are now
corrected to state `{Bash, Read, Skill}`, consistent with each other and with the current
`TOOL_BLOCKLIST`. **This correction is unverified** — `p4`'s hardcoded session log
(`api_requests_opus_websearch_1786052022_original.jsonl`) has aged out of the live
`src/logs/dual_log/` corpus by log rotation (already noted as broken in
`dev/proxy_instrumentation/DOCS.md`'s own Gotchas, unrelated to this change), so the script still
raises `FileNotFoundError` and cannot be executed to confirm the corrected assertion actually
passes. The correction is a source-level fix for internal consistency, not a proven-passing test.

`dev/proxy_instrumentation/p7_blocklist_258_probe.py` is glob-driven (no hardcoded stem) and did
run, against the main checkout's `src/logs/dual_log/` corpus (12 `*_original.jsonl` files present
at run time). Result: 7/8 checks pass, including `post_strip_set_is_exact` now reading
`kept=['Bash', 'Read', 'Skill']` — Read confirmed forwarded again through the real pipeline. The one
failure, `rw_live_tool_use_present_corpus_wide_by_design`, is a corpus-rotation artefact that
predates this change and is not caused by it: the check asserts more than zero corpus-wide live
`tool_use` hits for the still-blocked tools (`Edit`, `Write`), reflecting the expectation recorded in
`process-docs/model_selector/2026-09-13_thinking_toggle.md` that these are dominant, heavily-used
tools. Measured before touching anything (same script, same corpus, before any edit in this
session): 12 files scanned, 0 hits for `{Edit, Read, Write}` across 0 files — the three-tool corpus
this check was written against (25 files, 450,847 hits, per the earlier entry) has rotated down to
12 files that happen to carry none of these three tools' `tool_use` blocks. Measured after the fix,
same corpus, two-tool set: 12 files scanned, 0 hits for `{Edit, Write}` across 0 files — same
failure, same cause, unrelated to Read's removal. The check's own logic is sound; the corpus it
reads from is gitignored, live-growing runtime data (`dev/proxy_instrumentation/DOCS.md`'s own
Gotcha on this), so its exact pass/fail on this specific check is expected to fluctuate with
whatever sessions have recently run, independent of any code change here.

## Regression

`dev/proxy/test_strip_fix.py` (264/264, unaffected — no `TOOL_BLOCKLIST` dependency) and
`dev/proxy_dual_log/proxy_176_strip_tests.py` (33/33 PASS, 0 FAIL, unaffected — same reason), both
run before and after this change with identical results.
