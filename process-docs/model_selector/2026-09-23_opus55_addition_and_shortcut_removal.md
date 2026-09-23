# 2026-09-23 — claude-opus-5-5 added to the Models-tab cycle; launcher shortcuts removed

## Task framing

Two changes landed together in one worker session: (1) add `claude-opus-5-5` as a selectable
model in the menubar's Models tab, pinned behind CC 2.1.280 (see
`process-docs/cc_version_pin/2026-09-23_bump_to_280_and_shortcut_removal.md` for the version-pin
half); (2) a scope change the user added after reviewing the plan — remove the `--fable`/`--opus`
CLI shortcuts from `src/claude_proxy_start.sh` entirely, since the user's only invocation is now
`--project <path>` with model steering happening exclusively through the menubar.

## Design decision — addition, not replacement, confirmed by the user

Before implementing, I flagged this as the one real judgment call: does `claude-opus-5-5` REPLACE
`claude-opus-5` in `_MODEL_CHOICES`, or join it as a 5th value? The only directly comparable
precedent in this repo's own history is `claude-fable-5-1`, added alongside `claude-fable-5` in
milestone 4 (`process-docs/model_selector/2026-09-01_milestone4_model_id_and_param_rows.md`) — the
cycle grew 3→4, the old value was never dropped. I proposed following that precedent and the user
confirmed explicitly: "Addition is correct. claude-opus-5 stays in the cycle, claude-opus-5-5
joins it, default main becomes claude-opus-5-5, default worker stays claude-sonnet-5."

## What changed, `src/menubar/model_selection.py`

`_MODEL_CHOICES` grew 4→5, `claude-opus-5-5` inserted directly after `claude-opus-5` (mirrors
where `claude-fable-5-1` sits relative to `claude-fable-5` — the newer variant immediately after
its base):

```python
_MODEL_CHOICES = ("claude-opus-5", "claude-opus-5-5", "claude-fable-5", "claude-fable-5-1", "claude-sonnet-5")
_DEFAULT_MAIN   = _MODEL_CHOICES[1]   # claude-opus-5-5 — was index 0 (claude-opus-5) before this session
_DEFAULT_WORKER = _MODEL_CHOICES[4]   # claude-sonnet-5, unchanged value — index shifted 3 -> 4 because the tuple grew
```

The defaults are index-derived (`_MODEL_CHOICES[N]`), not literal strings — this is the thing the
orchestrator's prompt specifically flagged to watch for. Everything downstream
(`_next_model`/`_load_model_selection`/`_PendingSelection`) is already generic over
`_MODEL_CHOICES`'s length, so no other line in that file needed touching. No comments were added —
the file carries none today (post the 2026-09-16 comment-salvage pass), and stays that way.

## `dev/model_selector/verify_model_cycle_and_io.py` — extended in place

`_verify_model_cycle`: `assert len(choices) == 4` → `== 5`, header string `(4 values)` →
`(5 values)`, `fourth_wraps` renamed `last_wraps` (still `_next_model(choices[-1]) == choices[0]`,
just no longer literally the 4th element). Everything else in that function already iterates
generically over `choices`; no other section of the 9-section script needed a change, since none
of them assert a specific `_MODEL_CHOICES` value beyond what's now `_DEFAULT_MAIN`/`_DEFAULT_WORKER`
(those are read dynamically via `ms._DEFAULT_MAIN`/`ms._DEFAULT_WORKER`, already correct).

Full run, all 9 sections PASS — report at `dev/model_selector/md/verify_model_cycle_and_io.md`
(this is one of the FIXED-name tracked reports per the 2026-09-16 comment-salvage session's
convention; its content diff this run is a genuine behavior change — new cycle values, new
defaults on missing/malformed file — not run-to-run timestamp noise, so it was committed as-is
rather than restored via `git checkout --`).

## Scope change — --fable/--opus removed from the launcher

User instruction, verbatim: "the --opus and --fable shortcuts are removed from the launcher
entirely. The user steers the model exclusively through the menubar." Implemented in
`src/claude_proxy_start.sh`: deleted the `--fable`/`--opus` case branches and the `SHORTCUT_MODEL`
variable from the parse loop; the injection logic collapsed from a 4-tier if/elif
(shortcut-wins / config-wins / nothing) to a single `if` (config-wins / nothing), since the
shortcut tier no longer exists. Full precedence is now: explicit `--model` anywhere in the args >
`"main"` from `~/.claude/shared-rules/model_selection.json` > nothing injected. The header comment
block and the usage line were rewritten to match — no stale shortcut claim survives (confirmed by
a whole-file grep for `opus`/`fable`/`SHORTCUT` after the edit; the only hits left are the
`opus_` log-id prefix and `api_requests_opus_*` dual-log naming convention, which are unrelated
main-vs-worker log-file naming, not the removed shortcut).

`--project` itself is untouched — it was never part of the shortcut mechanism, just parsed in the
same loop.

## `dev/model_selector/verify_launcher_model_precedence.sh` — brought into sync

In scope per the user's explicit instruction ("yes, in scope, bring it in sync"). The script's own
header already commits it to mirroring `claude_proxy_start.sh`'s parse loop "keep in sync when
editing either" — rewritten `_parse_args()` to drop the `--fable`/`--opus` branches identically to
production, and replaced the old 12-case suite (which exercised the now-gone shortcut tier) with
an 11-case suite proving the 3 remaining tiers:

- Tier 1 sanity (no config in play): no flag → byte-identical; explicit `--model` → passed
  through; `--project` alone → extracted, nothing injected.
- Tier 2 (config present): no flag → config's `main` injected; **`--project` alone with a valid
  config → config's `main` injected — this is the actual real-world invocation shape the user
  now uses**, called out explicitly per the user's instruction to prove exactly this case;
  `--project` + another passthrough flag → both the flag and the model survive; explicit `--model`
  + valid config → explicit wins, config never consulted.
- Tier 3 degradation (4 cases, unchanged from before): missing file, malformed JSON, missing
  `"main"` key, empty `"main"` value — all inject nothing, no crash.

Result: 11/11 PASS. Report: `dev/model_selector/md/
verify_launcher_model_precedence_20260923_093701.md` (this script's reports are timestamped and
genuinely accumulate — the 2026-08-28 report from milestone 3 is still tracked in the same
directory, confirmed via `git log` before assuming it should be cleaned up).

## DOCS.md updates, same commits as the code

- `dev/model_selector/DOCS.md`: `verify_launcher_model_precedence.sh` LOC 200 → 186, Purpose text
  dropped "shortcut flag >" from the precedence description.
- `src/DOCS.md`: `claude_proxy_start.sh` LOC 416 → 402.
- `src/menubar/DOCS.md`: no change needed — `model_selection.py`'s LOC stayed 162 (editing one
  tuple line doesn't add/remove lines) and its Purpose text never hardcoded a model name or a
  cycle count.
- `src/spawn/DOCS.md` (iterative-dev): `Calls out` line's `claude-223` → `claude-280` (covered in
  the cc_version_pin process-docs entry, not repeated here since it's the same edit).

## What I did NOT touch, with reasons

- `bin/worker-cli`'s own `MODEL="${4:-claude-sonnet-5}"` fallback (iterative-dev) — this is the
  separate *worker model resolution* hardcode site documented in
  `process-docs/model_selector/2026-08-28_milestone3_launcher_and_worker_readers.md`'s "Finding"
  section (a different mechanism from the `CLAUDE_BIN` binary-wrapper path this task's scope
  covers). Confirmed via grep it carries no `CLAUDE_BIN`/version-wrapper reference at all — out of
  scope for a CC-version bump.
- `process-docs/cc_version_pin/cc_version_pin.md` itself — not edited, per the standing rule that
  only my own session's process-docs file is writable; see the sibling entry in
  `process-docs/cc_version_pin/` for the version-pin narrative instead.
- No `setup_py2app.py` run, no menubar rebuild, no real session start — explicitly the
  orchestrator's own next step, not this task's.
