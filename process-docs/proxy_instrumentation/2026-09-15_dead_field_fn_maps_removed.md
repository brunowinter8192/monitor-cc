# 2026-09-15 — removed the dead `_FIELD_STRIP_FN`/`_FIELD_INJECT_FN` pair from `strip_inject_delta.py`

## Task

`src/proxy/strip_inject_delta.py` defined `_FIELD_STRIP_FN`/`_FIELD_INJECT_FN`, a hand-written
attribution table mapping top-level payload fields (`model`/`max_tokens`/`thinking`/
`output_config`/`context_management`) to the proxy function responsible for changing them. The
2026-07-30 `fn_map_attribution_left_as_guessed.md` entry in this same area had already flagged
these as dead — never wired into the real `fn_map` — and noted that `dev/proxy_dual_log/
attribution_coverage.py` keeps its own separately-maintained copy of the same two maps, by hand,
with no import between the files.

## Investigation, re-verified fresh (not trusted from the prior entry)

`grep -rn "_FIELD_STRIP_FN\|_FIELD_INJECT_FN" --include='*.py' src/ dev/` found exactly two
definitions and zero cross-file reads: `strip_inject_delta.py`'s own dicts were referenced only by
each other (`_FIELD_INJECT_FN = {**_FIELD_STRIP_FN, ...}`), never by `_process_fields_section`
(the function that actually builds `fields_delta`) or by `_build_stripped_injected_deltas`'s
`s_fn_map`/`i_fn_map` construction (`{**s_sys_fn, **s_tools_fn, **s_msgs_fn}` — no fields
component at all, confirmed by reading the function body directly). `attribution_coverage.py`'s
copy is the only one actually read, at `_analyse_all_pairs` lines ~250/256.

**New finding beyond the prior entry:** the two copies had already drifted in *content*, not just
in never being synced. `strip_inject_delta.py`'s `_FIELD_STRIP_FN` has no `context_management` key
at all (added to the strip side only in `attribution_coverage.py`, 2026-09-13, following the
thinking-toggle `_strip_clear_thinking_edit` fix — see `process-docs/model_selector/
2026-09-13_thinking_toggle.md`). `attribution_coverage.py`'s values also carry report-display
annotation suffixes (`"_inject_model_override (orig replaced)"`) that `strip_inject_delta.py`'s
bare function-name strings never had. This settled the direction: a "single definition serves
both" wiring was not actually available without either (a) putting dev-report-formatted strings
into a module the live mitmproxy addon loads on every process start, or (b) `strip_inject_delta.py`
staying the "clean" copy while `attribution_coverage.py` still needs its own annotation layer on
top — not a real single source of truth either way, just a different shape of duplication.

## What was done

Deleted `_FIELD_STRIP_FN`/`_FIELD_INJECT_FN` from `src/proxy/strip_inject_delta.py` (293 → 286
LOC). Left `_SYS_FN` and `_MSG_CODE_TO_FN` in the same file untouched — both are genuinely used
(`_SYS_FN` in `_process_system_section`, `_MSG_CODE_TO_FN` in the message-block attribution path).
Left `_process_fields_section` and the real `fn_map`/JSONL shape untouched — populating `fn_map`
for fields for real was explicitly out of scope (would be a production behavior change, and the
2026-07-30 entry already priced the real fix as disproportionate: pass-name carry-through through
`rules.py`'s loop plus widening `fn_map` to a list per location).

`attribution_coverage.py`'s own `_FIELD_STRIP_FN`/`_FIELD_INJECT_FN` were left completely
untouched — they are the correct, live, sole remaining definition.

Updated three places that described or asserted the now-removed dicts, so they keep expressing the
truth after the removal:
- `src/proxy/DOCS.md` — the Gotcha paragraph previously said "dead code — never wired into
  `fn_map`"; now says the maps were removed and attribution for fields lives solely in
  `attribution_coverage.py`.
- `dev/proxy_dual_log/DOCS.md` — the `attribution_coverage.py` entry previously said
  `strip_inject_delta.py`'s same-named maps are dead code; now says they were removed from that
  module.
- `dev/native-model-start/p2_model_params_probe.py` — Test 15 previously asserted
  `"context_management" not in strip_inject_delta._FIELD_STRIP_FN` (would `AttributeError` once
  the dict is gone). Replaced with `not hasattr(strip_inject_delta, "_FIELD_STRIP_FN") and not
  hasattr(strip_inject_delta, "_FIELD_INJECT_FN")` — keeps the check meaningful (proves removal,
  not just one missing key) instead of deleting it. Also updated the module docstring's Test 15
  description and the in-function comment block to say "removed" rather than "left unchanged."

## Verification

`./venv/bin/python dev/native-model-start/p2_model_params_probe.py` → **73/73 checks passed**
(same total as before — Test 15's assertions were rewritten in place, not added to or removed
from). Also re-ran, as a broader sweep for anything importing `strip_inject_delta` that might
reference the removed names: `dev/proxy_dual_log/proxy_176_agent_types_tests.py`,
`proxy_176_bg_launch_ack_tests.py`, `proxy_176_strip_tests.py` (all PASS), and `dev/proxy/
test_strip_fix.py` (264/264 PASS). A repo-wide grep for the two dict names after the edit turned up
only `attribution_coverage.py`'s definitions/uses and `p2_model_params_probe.py`'s updated
docstring/check text — no stray references left anywhere.

## What a future reader must not assume

The real `fn_map` written to `stripped_delta`/`injected_delta` JSONL entries **still** never
carries a field-level entry, for any top-level field, for any request — that has not changed and
was never the point of this cleanup. If a future task wants real field-level `fn_map` attribution,
that is the same disproportionate-cost fix the 2026-07-30 entry already declined (pass-name
carry-through + `fn_map` widened to a list per location), not something this removal makes any
closer or further away.

If `attribution_coverage.py`'s field maps and the functions they name ever diverge from reality
again (a new pass added that strips or injects one of these five fields), there is still no import
or shared source enforcing sync — the only fix location now is `attribution_coverage.py` itself.

# 2026-09-15 (same session, new milestone) — isolating the zero-tool CC-internal sidecar from the proxy delta chain and pane REQ numbering

## Task

Claude Code sends a second kind of request alongside the real conversation — a zero-tool
CC-internal call (this session's investigation found session-titling and a bare `"quota"` call;
an earlier process-doc, `process-docs/dual_log_cli/2026-09-03_sidecar_exclusion_and_delta_hash_fix.md`,
found a "security monitor" system-prompted one). It shares the real conversation's
`model_family` bucket in `src/proxy/addon_dual_log.py`'s per-family delta-hash chain
(`DeltaState.forwarded_hashes_by_model`), which the 2026-09-03 entry explicitly left unfixed on the
write side ("Follow-up for the proxy area (not fixed here, `src/proxy` untouched)... no existing
`process-docs/proxy_*` area matches this specific mechanism... this paragraph is the record until
one is opened"). This entry is that record. Two deliverables: (1) the write-side chain does not
diff against a sidecar call, (2) the proxy pane (`src/proxy_display/`, NOT `dual_log_cli`, which
already had its own independent read-side fix) does not count a sidecar as a numbered REQ.

## Investigation — re-measured fresh, not trusted from the 2026-09-03 entry

Repo-wide scan of `src/logs/dual_log/*_forwarded.jsonl` at investigation time (20 files, main
checkout): **33 sidecar-shaped entries** (`counts.tools == 0`), spread across **all 20/20 files**
(1-2 each). All 33 were `claude-haiku-4-5-20251001`, all exactly 1 message. Two distinct call
shapes by system-prompt/content: 20 session-titling calls (`<session>...</session>` content,
system prompt `"You are naming a coding session..."`), 13 bare `"quota"` calls. Traced both back to
the matching `_original.jsonl` lines by `flow_id` to confirm the true (unstripped) system prompt
and content — not visible on the `_forwarded` side alone since the proxy's own strip passes reduce
most system blocks to `"."` stubs. **Zero non-haiku, zero-tool entries found anywhere in the
corpus** — the exact "security monitor, sonnet family" shape the 2026-09-03 entry measured no
longer appears in the current, smaller corpus (it may have rotated out, or CC's internal sidecar
implementation may have changed models since — not determinable from what's on disk today).

The corpus is live and actively rotating: a re-scan mid-session (after the log janitor pruned old
files) found only 6 files / 10 sidecar entries, same shapes, no non-haiku ones either. Re-ran the
non-haiku scan a THIRD time after review pushback (below), across every `_forwarded.jsonl` AND
every `_original.jsonl` on disk at that point (6 + 6 files) — 0 non-haiku, zero-tool entries in
either stream. A stray `/tmp/dual_log/` from an earlier dev-harness run (`flow_id: "fake-flow-id"`)
was excluded as synthetic test output, not real corpus.

## Deliverable 1 (write side) — kept, has a real observation behind it

`src/proxy/addon_dual_log.py`: added `_is_sidecar_payload(payload) -> bool` (`len(payload.get
("tools") or []) == 0`), the same criterion as `dual_log_cli.timeline_boundaries._is_sidecar`
(`counts.tools == 0`) applied directly to the payload since `addon_dual_log.py` has no `counts`
dict built yet at this point. `_write_request_dual_logs` now skips assigning `curr_delta` into
`delta_state.forwarded_hashes_by_model[model_family]` when the modified payload is a sidecar — the
sidecar's own `forwarded_delta` line is still written (full evidence, matches
`process-docs/proxy_tool_stripping/sidecar_idle_recap_removal.md`'s "observation over mutation"
stance; the existing `counts.tools == 0` field is the reader-facing discriminator, no new field
added), only the chain STATE is left un-advanced.

**This has a real, reproduced effect on the current corpus**, unlike deliverable 2 below: of 10
sidecar entries measured in the smaller re-scan, 4 were logged `is_first: False` (silently chained
against a PRECEDING, unrelated sidecar call — e.g. a session-titling call's delta computed against
a prior quota call's hashes, or vice versa) before the fix. Reproduced directly through the real
`ProxyAddon` (not a synthetic fixture) on
`api_requests_opus_monitor_cc_1789492730_original.jsonl`: entries 0 and 1 are both haiku
sidecars; before the fix entry 1 was `is_first: False` (delta against entry 0); after, `is_first:
True` (independent full dump — correct, since entry 0 and entry 1 are two unrelated auxiliary
calls, not a continuation of one another). This generalizes to the REAL-conversation case the
2026-09-03 entry measured (a non-haiku sidecar polluting a same-family real request's delta) even
though that specific case isn't in the current corpus — the fix is keyed on the same tool-count
signal regardless of family, so it protects against recurrence.

Regression guard: `dev/proxy/test_sidecar_delta_chain.py` (new), 13/13 — unit coverage of
`_is_sidecar_payload`, an end-to-end `_write_request_dual_logs` sequence (real → sidecar → real,
same family) proving the third write's delta is empty against the byte-identical first write (not
polluted by the sidecar in between), and proving a GENUINE change right after a sidecar is still
reported (the chain skip doesn't swallow real changes). Confirmed the test fails
(`ImportError`, pre-fix — the function didn't exist yet) via `git stash`.

## Deliverable 2 (pane REQ numbering) — reverted after review pushback, with reasoning

**First attempt:** widened `src/proxy_display/format.py::_is_standalone_entry` to treat ANY
zero-tool entry as standalone (dropped the `sys_chars == 0 and` requirement, leaving `tools_chars
== 0` alone, OR'd with the existing haiku check) — reasoning by analogy to deliverable 1's `tools
== 0` criterion, without first checking whether the existing haiku-only check already covered every
real case.

**Review caught this precisely:** all 33 measured sidecars are haiku, and `_is_standalone_entry`'s
existing `'haiku' in model` branch already excludes every one of them from the numbered `#N` REQ
sequence — confirmed independently by `render_byte_identity.py` coming out BYTE-IDENTICAL before
vs. after the widening on a real log containing 2 sidecar entries (proof the change altered nothing
ever actually observed). The widening only changes behavior for an UNOBSERVED case: a non-haiku
zero-tool entry — which could be a future non-haiku sidecar, OR could be a real conversation
request that genuinely carries zero tools for some other reason, since `_is_standalone_entry` has
FOUR callers across the package (`render_turn.py`'s REQ-number gate AND
`_resolve_prev_same_family`, `proxy_pane_shared.py`, `search.py`) — widening it changes behavior
everywhere at once for a case with zero corpus evidence either way.

**Resolution:** per explicit instruction, re-scanned every `_forwarded.jsonl` AND every
`_original.jsonl` on disk for a non-haiku, zero-tool entry. Found none (see Investigation above).
Reverted `format.py` to byte-identical with pre-task (`git diff HEAD~1 -- format.py` is empty) and
removed the matching `src/proxy_display/DOCS.md` Gotcha. `src/proxy/DOCS.md`'s
`addon_dual_log._is_sidecar_payload` Gotcha was corrected to say explicitly that `format.py` was
NOT widened to match, and why.

`dev/proxy_display/test_standalone_sidecar.py` was kept (per instruction) but rewritten to drop
every assertion that only existed for the unobserved non-haiku case, keeping only: the haiku branch
correctly catches the one real shape (haiku, zero tools, NON-zero system — every sidecar on disk
has its own system prompt, so this specifically pins that the OLD `sys_chars == 0 and` requirement
is not needed for the observed case, since haiku short-circuits the OR before that check is even
reached), the old zero-context shape (`sys==0 and tools==0`, non-haiku) still standalone, and a real
non-zero-tools non-haiku request still NOT standalone. The end-to-end `render_turn_expanded` test
now uses a haiku-model sidecar (matching every observed shape) instead of a synthetic non-haiku
one, and asserts the `H` label — 8/8 passed against the REVERTED code (was 5/10 against the
reverted code with the old, wider-case assertions still in it, confirming those assertions really
were testing only the unobserved case).

## What a future reader must not assume

`tools_total_chars == 0` (mirroring `dual_log_cli.timeline_boundaries._is_sidecar`'s `counts.tools
== 0`, model-agnostic) IS the precise, correct criterion to switch `_is_standalone_entry` to if a
non-haiku sidecar is ever actually observed — this was not reverted because the reasoning was wrong,
it was reverted because there was no observation to justify it yet, per this project's evidence-
burden rule (a fixture written by the person requesting the guard is not an observation). If a
non-haiku zero-tool entry ever shows up in `src/logs/dual_log/`, re-apply the same one-line change
this entry's first attempt made (drop `sys_chars == 0 and`, see the format.py diff in this
worktree's git history for the exact form) and restore the corresponding DOCS.md Gotcha.

The corpus composition can change without any code change on either side — the sidecar's own
model, system prompt, and call shape are 100% Claude-Code-side behavior, not proxy-side. The
"33 haiku, 0 non-haiku" measurement is a snapshot, not a guarantee; re-check before trusting the
haiku-only assumption in any FUTURE change to `_is_standalone_entry` or anything that reasons about
"the sidecar" by model name instead of by `tools == 0`.
