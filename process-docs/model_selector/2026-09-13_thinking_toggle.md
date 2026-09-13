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
