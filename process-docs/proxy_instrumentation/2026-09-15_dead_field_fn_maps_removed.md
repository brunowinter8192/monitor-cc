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
