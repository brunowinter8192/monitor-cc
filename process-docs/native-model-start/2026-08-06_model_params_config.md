# Per-model parameter config replacing the model-rewrite override, 2026-08-06

Follow-up to the same session's `--fable`/`--opus` native model-start flags, recorded earlier
this same day in this area. With the model now chosen at
session start, the proxy's existing `model_override`/`model_override_worker` config sections
became actively wrong — they rewrote `payload["model"]` back to a config value every request,
overriding whatever the session actually started as. The parameter injection they also carried
(`thinking`/`effort`/`max_tokens`) is still wanted, just needs to key off the model that's actually
running instead of forcing a model choice.

## Design

`src/proxy/inject_helpers.py::_inject_model_override` becomes a two-path dispatcher on a new
`model_params` config key, keyed by EXACT model id (no family bucketing, no id normalization):

- **`model_params` present** (checked by key membership, `"model_params" in config` — NOT
  truthiness; an empty `{}` still counts as present) → `_inject_model_params`: `payload["model"]`
  looked up exactly; hit applies `thinking`/`effort`(→`output_config.effort`)/`max_tokens` (each
  independently optional, same mechanics as before) and NEVER touches `model`; miss (or an empty
  per-model entry) leaves the payload completely untouched. Legacy sections are ignored entirely in
  this branch, even if still present in the file — no partial mixing.
- **`model_params` absent** → `_inject_legacy_model_override`, the original function body moved
  verbatim (not rewritten) — family-bucketed (`opus`→`model_override`, `sonnet`→
  `model_override_worker`), each gated by its own `enabled` flag, INCLUDING the `model` rewrite.
  Byte-identical to pre-2026-08-06 behavior — the safe-rollout path for an unmigrated config.

`addon.py`'s call site (`_run_post_fixation_pipeline`) needed no change: `model_family` is still
the right thing to pass since the legacy branch still needs it; the new branch gets the exact model
id from `payload["model"]`, already available inside the function without a new parameter.

## Ready-to-paste config snippet (NOT applied by this task — `~/.claude/shared-rules/proxy_rules.json`
is user config outside the repo)

Read from the live config on this machine: `model_override` and `model_override_worker` both
currently carry identical `thinking`/`effort`/`max_tokens` values (`adaptive`/`omitted`, `high`,
`64000`) — that's the value set carried into all three keys below, including `claude-opus-5`, which
has no legacy equivalent to draw from and gets the same uniform values as a starting point:

```json
"model_params": {
    "claude-fable-5": {"thinking": {"type": "adaptive", "display": "omitted"}, "effort": "high", "max_tokens": 64000},
    "claude-opus-5": {"thinking": {"type": "adaptive", "display": "omitted"}, "effort": "high", "max_tokens": 64000},
    "claude-sonnet-5": {"thinking": {"type": "adaptive", "display": "omitted"}, "effort": "high", "max_tokens": 64000}
}
```
Adding this key to `proxy_rules.json` immediately switches the proxy to the new path for every
model with an entry — no code change or restart flag needed, just a config edit (the running proxy
picks it up via `rules_config._load_config`'s mtime-based cache invalidation).

## A deliberate non-feature: no model-id normalization

`claude-opus-4-8[1m]`-style suffixed variants (e.g. a context-window tag) are NOT matched against
a bare `claude-opus-4-8` table entry — exact string equality only. Pinned as its own test case
(`dev/native-model-start/p2_model_params_probe.py`, Test 4) specifically so a future report of "the
override didn't fire for a suffixed model id" is recognized as this known, intentional boundary and
handled as a conscious follow-up (adding normalization) rather than investigated as a fresh bug.

## Verification

30/30 checks in `dev/native-model-start/p2_model_params_probe.py` (config injected via
`mock.patch.object(inject_helpers, "_load_config", ...)`, no existing mocking precedent for
`rules_config` existed in this repo — pattern mirrors the `mock.patch.object(module, "_fn", ...)`
style already used in the `bg_wakeup_id_line`/`timer-loop` areas' probes): legacy-only config byte-
identical to pre-change behavior including the model rewrite (opus, sonnet, and the haiku no-op
case); `model_params` hit for each of the three snippet models with the model field verified
UNCHANGED; miss leaves payload untouched; the suffixed-id deliberate-miss case; `model_params`
present (both non-empty and empty `{}`) alongside legacy sections wins in both cases, legacy never
consulted; empty per-model entry vs a partial one-key entry; `_load_config` raising fails open with
no exception propagated. No regressions in `dev/proxy/test_strip_fix.py` (150/150) or
`dev/native-model-start/p1_arg_parse_dry_run.sh` (8/8, unrelated to this change but re-run as a
sanity check since it lives in the same area).

Not verified here: an actual mitmdump load test against the new config shape (mandatory post-merge
check, explicitly the user's gate after merge per this task's instructions) and live behavior
against the real `~/.claude/shared-rules/proxy_rules.json` once the snippet above is pasted in.
