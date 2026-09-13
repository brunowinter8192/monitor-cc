# 2026-09-13 — Thinking on/off toggle for the Models pane

## Task

The Models pane could cycle model/effort/max_tokens for Main and Worker, but the `thinking`
config (`{"type": "adaptive", "display": "summarized"}`) was a hardcoded default only written
the first time a `model_params` entry was created, with no UI path to change it. Requirement: a
cyclable row per side (Main/Worker) that toggles thinking on/off, persisted through Apply the same
way effort/max_tokens are, landing in the outgoing payload as `{"type": "disabled"}` when off.

## Design decisions

**Toggle, not a 3+ value `_next_in` cycle.** `_next_model`/`_next_effort`/`_next_max_tokens` all go
through the generic `_next_in(choices_tuple, current)` index-cycle helper, which is the right shape
for an ordered value set with an "unrecognized value starts at the first choice" fallback. Thinking
has exactly two states and no natural "first" state to fall back to when it's neither known shape —
a binary flip reads better: `_thinking_is_enabled(thinking) -> bool` (checks `type != "disabled"`)
and `_next_thinking(current) -> dict` (returns `_THINKING_OFF` if currently enabled, else
`_THINKING_ON`). This also means an on-disk `thinking` value that's neither of the two known dicts
still classifies as "enabled" (anything not `type: disabled` counts as on) and one click switches it
to the canonical `_THINKING_OFF` — no crash, no third state introduced.

**`_load_model_params_for` return shape changed from a 2-tuple to a 3-tuple** (`effort, max_tokens,
thinking`) rather than adding a second sibling-function. The three values are always loaded and
cycled together per side inside `_PendingSelection` (on `load()`, and again on `cycle_main`/
`cycle_worker` since switching the model_id must re-read that model's own current params) — keeping
them as one call avoids two file reads per side and keeps `_PendingSelection` symmetric with how
effort/max_tokens already worked. This is a breaking signature change with exactly two callers
outside `model_selection.py` itself: `model_controller.py` (in-file usage inside the same module,
not really "outside") and `dev/menubar/model_controller_byte_identity.py` (dynamic-import harness,
not a package caller) — both updated in the same commit. Caller check: `grep` for
`_load_model_params_for` across the repo found only those two files plus
`dev/model_selector/verify_model_cycle_and_io.py` (which does not call this particular function,
only `_write_proxy_rules_model_params`/cycle helpers) and process-docs entries (historical, not
touched).

**`_write_proxy_rules_model_params` similarly grew two new required positional params**
(`main_thinking`, `worker_thinking`, inserted right after each side's `max_tokens` — before the next
side's `model_id`) rather than keyword-only optional params defaulting to the old adaptive/
summarized shape. Deliberate: thinking is now a first-class per-side choice exactly like effort and
max_tokens, so making it silently optional would let a future caller forget to pass it and
unknowingly reset thinking to the default instead of preserving pending state. Every call site
(`_PendingSelection.write()`, both dev/ harnesses) was updated in the same commit — no default was
worth adding for a two-caller-total function.

**Per-model entry dict construction simplified.** The old code seeded a missing entry with
`{"thinking": dict(_DEFAULT_THINKING)}` specifically so a first-ever-created entry had *some*
thinking key before `effort`/`max_tokens` got set on it. Now that `thinking` is always one of the
three values explicitly assigned into `entry` on every write (`entry["thinking"] = dict(thinking)`
happens unconditionally, first, before `effort`/`max_tokens`), the missing-entry seed collapses to
plain `{}` — the assignment order (`thinking`, then `effort`, then `max_tokens`) reproduces the
exact key order the byte-identity fixture (`dev/model_selector/verify_model_cycle_and_io.py`'s
`_FIXTURE_RAW`) expects, both for touched-existing entries (dict key order preserved from the
loaded JSON, values updated in place) and freshly-created ones.

## Verification

- `./venv/bin/python dev/model_selector/verify_model_cycle_and_io.py` — new Section 4
  (`_verify_thinking_cycle`) added as the regression guard for the toggle logic itself (off->on,
  on->off, double-toggle round-trip, `_thinking_is_enabled` on both canonical dicts). Sections 5-9
  renumbered from the old 4-8 to make room. Sections 8 (`_verify_proxy_rules_read_modify_write`) and
  9 (malformed-fallback) now drive an explicit thinking-state change through
  `_write_proxy_rules_model_params` (main entry flipped to disabled, worker's freshly-created entry
  left on) instead of always passing the untouched default, so the full read-modify-write path is
  exercised end to end, not just the cycle-logic unit. Result: PASS, all 9 sections, see
  `dev/model_selector/md/verify_model_cycle_and_io.md`.
- `./venv/bin/python dev/menubar/model_controller_byte_identity.py` — persistence hash sequence
  extended with 1 main-thinking toggle + 2 worker-thinking toggles (net: main flips once, worker
  round-trips back to its start value, both deliberately asymmetric so a broken toggle would show up
  in the hash); UI hash sequence extended with `handle_cycle_main_thinking`/
  `handle_cycle_worker_thinking`. Both hashes computed clean (`PERSISTENCE_HASH`/`UI_HASH` printed,
  no exceptions) — this harness has no baseline to diff against since the behavior it hashes
  intentionally changed (new rows), so a clean run (no exception, both hashes present) is the bar,
  not hash equality with a pre-change run.
- `./venv/bin/python dev/model_selector/verify_three_tab_ring.py` — unchanged, run to confirm the
  panel-cycle wiring around `ModelController` still holds after the row/height changes. PASS.

## Not touched, with evidence

`src/proxy/inject_helpers.py` needed no change. `_inject_model_params`
(`src/proxy/inject_helpers.py:37-51`) does `if "thinking" in params: result["thinking"] =
params["thinking"]` — a verbatim copy with no branching on the dict's shape or the model family. It
already faithfully forwards whatever is stored in `model_params.<model_id>.thinking`, so writing
`{"type": "disabled"}` there through `model_selection.py` was sufficient to make it reach the
outgoing payload; confirmed by reading the function body directly, not by running the live proxy.

## 2026-09-13 (same-day follow-up) — the thinking toggle broke real sessions: `clear_thinking_20251015` self-consistency fix

### Observed failure

Once the thinking toggle above reached production, every session under it died with a 400:
`` `clear_thinking_20251015` strategy requires `thinking` to be enabled or adaptive ``. Root cause,
read directly off a real capture (`api_requests_worker_25c51a2e_cache-write-run_1789308787`, main
checkout `src/logs/dual_log/`, flow `a025836e-2d7f-4ce0-bda5-869a45030d82`):

- Claude Code's own request carried `thinking: {"type": "adaptive", "display": "summarized"}`
  together with `context_management: {"edits": [{"type": "clear_thinking_20251015", "keep":
  "all"}]}`.
- The proxy's `model_params` injection (this exact thinking-toggle feature, `claude-sonnet-5` set
  to thinking-off at the time) overwrote `thinking` to `{"type": "disabled"}` and left the
  `clear_thinking_20251015` edit untouched — a self-contradictory payload the API rejects.
- `context_management.enabled` was confirmed `false` in `~/.claude/shared-rules/proxy_rules.json`
  at the time, so the proxy's own `_inject_context_management` was not the source of the edit —
  Claude Code sent it.
- **Evidence that Claude Code itself knows about this constraint:** the same capture's third
  request, to Haiku, has Claude Code setting `thinking: {"type": "disabled"}` *itself* (not via any
  proxy injection), and that request carries **no** `context_management` key at all. Claude Code
  drops the edit when it disables thinking on its own — the proxy's model-override injection path
  is the only place in the whole system that was disabling thinking *without* also dropping the
  now-incompatible edit, since it runs downstream of, and independently from, Claude Code's own
  request construction.

### Fix

Added `_strip_clear_thinking_edit(payload) -> (payload, changed)` to `src/proxy/inject_helpers.py`
and wired it into `addon.py:_run_post_fixation_pipeline`, immediately after `_inject_model_override`
(the last step that can change `thinking` for any given request). Placed at the end of the
post-fixation pipeline rather than inside `_inject_model_override` itself, specifically so it also
covers a hypothetical future case where thinking ends up disabled through a path other than
`model_params`/legacy-override injection — the fix is keyed purely off the FINAL payload's
`thinking.type`, never off which function set it.

Behavior: if `thinking.type == "disabled"` and `context_management.edits` contains a
`clear_thinking_20251015` entry, that entry alone is removed; other edits (e.g.
`clear_tool_uses_20250919`) survive untouched; if removing it empties the edits list, the whole
`context_management` key is dropped rather than left as `{"edits": []}` — chosen specifically
because that's what Claude Code's own Haiku request already does when disabling thinking itself,
so the fix mirrors the reference client's own convention instead of inventing a new payload shape.
When thinking is not disabled, the function returns the original payload object unchanged (`is`,
not just `==`) — proven in the regression test, not just asserted.

Also added the forwarded `thinking` value to `src/proxy/logging.py:_build_forwarded_delta`'s entry
(it previously logged `max_tokens`/`output_config`/`context_management` but not `thinking`, which
is exactly why this failure could not be read directly off the forwarded dual-log — it had to be
inferred from the original log plus the known injection logic).

### Follow-up review point: attribution of the new STRIP direction for `context_management`

A reviewer flagged that `context_management` had only ever been an INJECTED field before (only
`_inject_context_management` ever added it) — my fix is the first path that ever REMOVES it, and
`src/proxy/strip_inject_delta.py`'s `_FIELD_STRIP_FN`/`_FIELD_INJECT_FN` maps (which look like the
attribution table for exactly this) list `context_management` only on the inject side.

**Investigation, with evidence:** built a real `stripped_delta` entry via
`_build_stripped_injected_deltas` for a synthetic thinking-disable + `clear_thinking` edit request.
Result: `context_management` does appear in `stripped_entry["fields_delta"]`, but
`stripped_entry["fn_map"]` is `{}` — empty. Tracing `_build_stripped_injected_deltas`, `s_fn_map =
{**s_sys_fn, **s_tools_fn, **s_msgs_fn}` — the fields section's own processing function,
`_process_fields_section`, returns only `(s_fields, i_fields, s_hashes, i_hashes)`, no `s_fn`/`i_fn`
pair at all. **`_FIELD_STRIP_FN`/`_FIELD_INJECT_FN` in `src/proxy/strip_inject_delta.py` are dead
code** — defined, never referenced anywhere else in that file or anywhere in `src/` or `dev/`
(confirmed by the reviewer independently via their own grep). This was already true for
`thinking`/`max_tokens`/`output_config`/`model` before this fix — the real JSONL `fn_map` never
attributed ANY top-level field to a function, for any request, ever. So my change does not make
`strip_inject_delta.py`'s own `fn_map` output any less correct than it already was; there was
nothing there to break. Left that file untouched.

**The live attribution consumer is a different file:** `dev/proxy_dual_log/attribution_coverage.py`
does NOT read `fn_map` for fields — it reads `fields_delta` directly and looks the key up in its
OWN, separately-maintained, local copy of the same two maps (`_FIELD_STRIP_FN`/`_FIELD_INJECT_FN`,
defined again inside `attribution_coverage.py` itself, not imported from `strip_inject_delta.py`).
That local copy's strip-side map was also missing `context_management`, and this one is genuinely
live: `ac._FIELD_STRIP_FN.get("context_management", "UNATTR:context_management")` returned
`"UNATTR:context_management"` before the fix, confirmed by direct invocation. Fixed by adding
`"context_management": "_strip_clear_thinking_edit (removed: thinking disabled)"` to that map. The
two files' maps are independent and must be kept in sync by hand — there is no shared import
between them; a future person touching one without the other reintroduces this same gap.

### Verification

- `dev/native-model-start/p2_model_params_probe.py` (existing regression-guard file for
  `inject_helpers.py`, already used earlier this session) — added Test 13
  (`_strip_clear_thinking_edit`: sibling-edit survival, empty-edits-list drops the key,
  byte-identical-object when not disabled, no-op cases, and an end-to-end replay of the exact
  observed 400 shape through `_inject_model_override` + `_strip_clear_thinking_edit` together),
  Test 14 (`_build_forwarded_delta` records forwarded `thinking` on/off/absent), and Test 15 (the
  dead-code finding pinned as a check — real `fn_map` stays `{}` for fields — plus
  `attribution_coverage.py`'s field maps now resolving `context_management` correctly on both
  strip and inject sides). Run: `./venv/bin/python dev/native-model-start/p2_model_params_probe.py`
  → **73/73 checks passed** (68 before Test 15, +5 in Test 15).
- Replayed the real failing capture's sonnet request through
  `apply_modification_rules` → `_inject_context_management` → `_inject_model_override` →
  `_strip_clear_thinking_edit` directly (not a synthetic fixture): `thinking` flips
  `adaptive→disabled`, `context_management` flips from the single `clear_thinking_20251015` edit to
  `None` — confirms the fix against the actual 400-causing payload.
- Replayed all three requests from the same capture (haiku/sonnet/haiku) through the same chain:
  the first and third (Claude-Code-disabled-thinking Haiku, no `context_management` to begin with)
  are correctly no-ops (`stripped=False`); only the sonnet one strips, and its `context_management`
  becomes the same object reference as before whenever thinking is NOT disabled in a control check
  — proving the byte-identical-when-untouched claim against real data, not just a fixture.
- `dev/proxy/pipeline_byte_identity.py` and `dev/proxy/addon_hook_byte_identity.py` (broader
  pipeline/`ProxyAddon` hash harnesses) both run clean (no exceptions) after the change; their
  hashes are expected to differ from any pre-fix run since real behavior changed, which is fine —
  neither harness asserts equality against a stored baseline.
