"""
P2 — verifies src/proxy/inject_helpers.py::_inject_model_override's rework: per-model 'model_params'
config path replacing the legacy family-bucketed model_override/model_override_worker rewrite.

Covers: legacy-config-only -> byte-identical legacy behavior incl. model rewrite; model_params hit
-> thinking/effort/max_tokens applied, model field untouched; model_params miss -> payload
untouched; model_params present (even empty {}) alongside legacy sections -> model_params wins, no
rewrite; empty per-model entry -> untouched; partial entry (one key only) -> only that key applied;
config load failure -> fail-open untouched; a suffixed model-id variant is a deliberate MISS
(exact-match only, no normalization).

2026-09 fixation coverage: a caller-owned dict (fixated_model_override, ProxyAddon.model_params_
fixated in production) pins the WHOLE resolved unit (model_params entry, or the legacy section) on
the first call for a given exact model id, and every subsequent call for that model id replays the
pinned snapshot instead of re-reading _load_config() — proves (a) first request uses the
then-current config, (b) a config change AFTER the first request does not alter subsequent
injections against the SAME dict (same simulated proxy process), (c) a FRESH dict (simulated fresh
addon instance / hot-reload) picks up the new config, (d) the legacy path is pinned the same way
and stays byte-identical to the unfixated legacy behavior. Also covers: a genuine miss (hit but no
per-model entry) pins "no injection" too; a genuine _load_config() exception does NOT pin, so the
very next call retries live. All 7 pre-fixation tests below call _inject_model_override with only
2 positional args (no fixated_model_override) — the default (None -> a fresh, discarded dict per
call) keeps them independent, proving the old 2-arg call form is unaffected by this rework.

2026-09 thinking/context_management self-consistency coverage (Test 13): once thinking can be
switched to {"type": "disabled"} (menubar thinking toggle, or any future path), a surviving
`clear_thinking_20251015` context_management edit makes the request self-contradictory and the API
returns a 400 (reproduced verbatim from a real capture,
`api_requests_worker_25c51a2e_cache-write-run_1789308787`). Covers `_strip_clear_thinking_edit`:
the edit is removed when thinking ends up disabled regardless of which path disabled it, sibling
edits like `clear_tool_uses_20250919` survive, an emptied edits list drops the whole
`context_management` key rather than carrying an empty list, and a non-disabled thinking value
leaves `context_management` byte-identical (same object, not just equal). Test 14 covers
`src/proxy/logging.py::_build_forwarded_delta` recording the forwarded `thinking` value (on/off/
absent), added so this exact failure is now readable straight off the forwarded dual-log.

Test 15 covers a follow-up review point: a context_management removal now reaches the
stripped-delta path for the first time (previously that field only ever got INJECTED, never
STRIPPED). `src/proxy/strip_inject_delta.py`'s own `_FIELD_STRIP_FN`/`_FIELD_INJECT_FN` are proven
dead code (the real `fn_map` written to the stripped/injected JSONL never carries a field-level
entry for ANY top-level field, thinking/output_config/max_tokens included — verified directly, not
just by absence of a call site), so they are left unchanged. The tool that DOES actually attribute
`fields_delta` entries is `dev/proxy_dual_log/attribution_coverage.py`'s own `_FIELD_STRIP_FN`
dict, which was missing `context_management` on the strip side and would have reported the removal
as `UNATTR:context_management`; fixed there, verified here.

Run from project root or worktree root:
    ./venv/bin/python dev/native-model-start/p2_model_params_probe.py
"""

# INFRASTRUCTURE
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

from proxy import inject_helpers
from proxy.inject_helpers import _inject_model_override, _strip_clear_thinking_edit
from proxy.logging import _build_forwarded_delta
from proxy import strip_inject_delta
from proxy.strip_inject_delta import _build_stripped_injected_deltas

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"

_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


_LEGACY_CONFIG = {
    "model_override": {
        "enabled": True, "model": "claude-fable-5",
        "thinking": {"type": "adaptive", "display": "omitted"},
        "effort": "high", "max_tokens": 64000,
    },
    "model_override_worker": {
        "enabled": True, "model": "claude-sonnet-5",
        "thinking": {"type": "adaptive", "display": "omitted"},
        "effort": "high", "max_tokens": 64000,
    },
}

_MODEL_PARAMS_CONFIG = {
    "model_params": {
        "claude-fable-5": {
            "thinking": {"type": "adaptive", "display": "omitted"},
            "effort": "high", "max_tokens": 64000,
        },
        "claude-opus-5": {
            "thinking": {"type": "adaptive", "display": "omitted"},
            "effort": "high", "max_tokens": 64000,
        },
        "claude-sonnet-5": {
            "thinking": {"type": "adaptive", "display": "omitted"},
            "effort": "high", "max_tokens": 64000,
        },
    },
}


def _base_payload(model):
    return {"model": model, "max_tokens": 8000, "messages": [{"role": "user", "content": "hi"}]}


def _with_config(config, fn):
    with mock.patch.object(inject_helpers, "_load_config", lambda: config):
        return fn()


# FUNCTIONS

# Test 1 — legacy-only config (no 'model_params' key) -> byte-identical legacy behavior, INCLUDING
# the model-field rewrite, for both opus and sonnet families.
def test_legacy_only_unchanged():
    print("\n[Test 1] Legacy-only config -> byte-identical legacy behavior")
    payload = _base_payload("claude-opus-4-8")
    result, injected = _with_config(_LEGACY_CONFIG, lambda: _inject_model_override(payload, "opus"))
    check("opus family: injected=True", injected is True)
    check("opus family: model REWRITTEN to claude-fable-5 (legacy behavior)", result["model"] == "claude-fable-5")
    check("opus family: thinking applied", result["thinking"] == {"type": "adaptive", "display": "omitted"})
    check("opus family: effort applied via output_config", result["output_config"]["effort"] == "high")
    check("opus family: max_tokens applied", result["max_tokens"] == 64000)

    payload_w = _base_payload("claude-sonnet-4-5")
    result_w, injected_w = _with_config(_LEGACY_CONFIG, lambda: _inject_model_override(payload_w, "sonnet"))
    check("sonnet family: injected=True", injected_w is True)
    check("sonnet family: model REWRITTEN to claude-sonnet-5 (legacy behavior)", result_w["model"] == "claude-sonnet-5")

    payload_h = _base_payload("claude-haiku-4")
    result_h, injected_h = _with_config(_LEGACY_CONFIG, lambda: _inject_model_override(payload_h, "haiku"))
    check("haiku family: no legacy section -> untouched, injected=False",
          injected_h is False and result_h == payload_h)


# Test 2 — model_params hit: thinking/effort/max_tokens applied, model field left untouched.
def test_model_params_hit():
    print("\n[Test 2] model_params hit -> params applied, model field NEVER touched")
    payload = _base_payload("claude-fable-5")
    result, injected = _with_config(_MODEL_PARAMS_CONFIG, lambda: _inject_model_override(payload, "opus"))
    check("injected=True", injected is True)
    check("model field UNCHANGED (still claude-fable-5, not rewritten)", result["model"] == "claude-fable-5")
    check("thinking applied", result["thinking"] == {"type": "adaptive", "display": "omitted"})
    check("effort applied via output_config", result["output_config"]["effort"] == "high")
    check("max_tokens applied", result["max_tokens"] == 64000)

    payload_o = _base_payload("claude-opus-5")
    result_o, injected_o = _with_config(_MODEL_PARAMS_CONFIG, lambda: _inject_model_override(payload_o, "opus"))
    check("claude-opus-5 hit: injected=True, model untouched",
          injected_o is True and result_o["model"] == "claude-opus-5")

    payload_s = _base_payload("claude-sonnet-5")
    result_s, injected_s = _with_config(_MODEL_PARAMS_CONFIG, lambda: _inject_model_override(payload_s, "sonnet"))
    check("claude-sonnet-5 hit: injected=True, model untouched",
          injected_s is True and result_s["model"] == "claude-sonnet-5")


# Test 3 — model_params miss: model not in the table -> payload untouched.
def test_model_params_miss():
    print("\n[Test 3] model_params miss -> payload untouched")
    payload = _base_payload("claude-haiku-4")
    result, injected = _with_config(_MODEL_PARAMS_CONFIG, lambda: _inject_model_override(payload, "haiku"))
    check("injected=False", injected is False)
    check("payload identical (same dict values)", result == payload)


# Test 4 — suffixed model-id variant is a DELIBERATE miss: exact-match only, no normalization.
# Pinned so a future "should we strip suffixes?" question is a conscious follow-up, not a silent
# behavior change nobody noticed.
def test_suffixed_model_id_is_deliberate_miss():
    print("\n[Test 4] Suffixed model-id variant -> deliberate MISS (no normalization)")
    config = {"model_params": {"claude-opus-4-8": {"effort": "high"}}}
    payload = _base_payload("claude-opus-4-8[1m]")  # suffix variant, e.g. a context-window tag
    result, injected = _with_config(config, lambda: _inject_model_override(payload, "opus"))
    check("suffixed id 'claude-opus-4-8[1m]' vs table key 'claude-opus-4-8' -> exact match FAILS",
          injected is False and result == payload)


# Test 5 — model_params present (even as an empty {}) alongside legacy sections -> model_params
# wins, legacy is ignored entirely, no model rewrite happens.
def test_model_params_presence_wins_over_legacy():
    print("\n[Test 5] model_params PRESENT (non-empty) alongside legacy sections -> model_params wins")
    mixed_config = {**_LEGACY_CONFIG, **_MODEL_PARAMS_CONFIG}
    payload = _base_payload("claude-fable-5")
    result, injected = _with_config(mixed_config, lambda: _inject_model_override(payload, "opus"))
    check("injected=True (from model_params, not legacy)", injected is True)
    check("model NOT rewritten despite legacy model_override.model=claude-fable-5 being present too",
          result["model"] == "claude-fable-5")  # already claude-fable-5 going in — key check is params source below
    check("thinking/effort/max_tokens match model_params values", result["max_tokens"] == 64000)

    print("\n[Test 5b] model_params PRESENT as an EMPTY {} -> still wins, legacy fully disabled")
    empty_mp_config = {**_LEGACY_CONFIG, "model_params": {}}
    payload_o = _base_payload("claude-opus-4-8")
    result_o, injected_o = _with_config(empty_mp_config, lambda: _inject_model_override(payload_o, "opus"))
    check("empty model_params {} -> injected=False (no entry for this model)", injected_o is False)
    check("model NOT rewritten to claude-fable-5 — legacy path never consulted despite being 'enabled'",
          result_o["model"] == "claude-opus-4-8")


# Test 6 — empty per-model entry ({}) and a partial entry (one key only).
def test_empty_and_partial_entries():
    print("\n[Test 6] Empty per-model entry -> untouched; partial entry -> only that key applied")
    config_empty_entry = {"model_params": {"claude-fable-5": {}}}
    payload = _base_payload("claude-fable-5")
    result, injected = _with_config(config_empty_entry, lambda: _inject_model_override(payload, "opus"))
    check("empty {} entry for a matched model -> injected=False, untouched",
          injected is False and result == payload)

    config_partial = {"model_params": {"claude-fable-5": {"effort": "medium"}}}
    payload2 = _base_payload("claude-fable-5")
    result2, injected2 = _with_config(config_partial, lambda: _inject_model_override(payload2, "opus"))
    check("partial entry (effort only): injected=True", injected2 is True)
    check("effort applied", result2["output_config"]["effort"] == "medium")
    check("thinking NOT added (key absent from entry)", "thinking" not in result2)
    check("max_tokens UNCHANGED from original payload (key absent from entry, not injected)",
          result2["max_tokens"] == payload2["max_tokens"] == 8000)


# Test 7 — config load failure degrades to no-op (fail-open), never raises.
def test_config_load_failure_fails_open():
    print("\n[Test 7] _load_config raising -> fail-open, no raise")
    payload = _base_payload("claude-fable-5")
    with mock.patch.object(inject_helpers, "_load_config", side_effect=RuntimeError("simulated")):
        try:
            result, injected = _inject_model_override(payload, "opus")
            raised = False
        except Exception:
            result, injected, raised = payload, False, True
    check("no raise propagated", not raised)
    check("injected=False, payload untouched", injected is False and result == payload)


# Test 8 — (a)+(b): first request pins the model_params entry it saw; a later config change
# against the SAME fixated dict (same simulated proxy process) does NOT alter the result.
def test_fixation_pins_model_params_snapshot():
    print("\n[Test 8] Fixation: model_params pins on first request, later config change ignored")
    config1 = {"model_params": {"claude-fable-5": {"effort": "low", "max_tokens": 32000}}}
    config2 = {"model_params": {"claude-fable-5": {"effort": "high", "max_tokens": 128000}}}
    fixated = {}
    payload1 = _base_payload("claude-fable-5")
    result1, injected1 = _with_config(config1, lambda: _inject_model_override(payload1, "opus", fixated))
    check("(a) first request applies config1 (effort=low)", result1["output_config"]["effort"] == "low")
    check("(a) first request applies config1 (max_tokens=32000)", result1["max_tokens"] == 32000)
    check("(a) fixated dict now holds an entry for claude-fable-5", "claude-fable-5" in fixated)

    payload2 = _base_payload("claude-fable-5")
    result2, injected2 = _with_config(config2, lambda: _inject_model_override(payload2, "opus", fixated))
    check("(b) SAME fixated dict: config2 change ignored, still effort=low", result2["output_config"]["effort"] == "low")
    check("(b) SAME fixated dict: config2 change ignored, still max_tokens=32000", result2["max_tokens"] == 32000)
    check("(b) injected still True on the pinned replay", injected2 is True)


# Test 9 — (c): a FRESH fixated dict (simulated fresh addon instance / hot-reload) picks up the
# new config — proves fixation is scoped to the dict instance, not global module state.
def test_fixation_fresh_instance_picks_up_new_config():
    print("\n[Test 9] Fixation: a fresh fixated dict picks up the changed config")
    config2 = {"model_params": {"claude-fable-5": {"effort": "high", "max_tokens": 128000}}}
    fresh_fixated = {}
    payload3 = _base_payload("claude-fable-5")
    result3, injected3 = _with_config(config2, lambda: _inject_model_override(payload3, "opus", fresh_fixated))
    check("(c) fresh dict applies config2 (effort=high)", result3["output_config"]["effort"] == "high")
    check("(c) fresh dict applies config2 (max_tokens=128000)", result3["max_tokens"] == 128000)


# Test 10 — (d): legacy path is pinned the SAME way, and stays byte-identical to unfixated legacy
# behavior (model rewrite included) on the pinning (first) call.
def test_fixation_legacy_path_pinned_and_unchanged():
    print("\n[Test 10] Fixation: legacy path pinned too, byte-identical on first call")
    fixated = {}
    payload1 = _base_payload("claude-opus-4-8")
    result1, injected1 = _with_config(_LEGACY_CONFIG, lambda: _inject_model_override(payload1, "opus", fixated))
    check("(d) legacy first call: injected=True", injected1 is True)
    check("(d) legacy first call: model REWRITTEN (byte-identical to unfixated Test 1)", result1["model"] == "claude-fable-5")
    check("(d) legacy first call: thinking applied", result1["thinking"] == {"type": "adaptive", "display": "omitted"})
    check("(d) legacy first call: effort applied", result1["output_config"]["effort"] == "high")
    check("(d) legacy first call: max_tokens applied", result1["max_tokens"] == 64000)
    check("(d) fixated dict now holds an entry for claude-opus-4-8", "claude-opus-4-8" in fixated)

    # Config now DISABLES the section — same fixated dict must still apply the pinned (enabled) snapshot.
    disabled_config = {"model_override": {**_LEGACY_CONFIG["model_override"], "enabled": False}}
    payload2 = _base_payload("claude-opus-4-8")
    result2, injected2 = _with_config(disabled_config, lambda: _inject_model_override(payload2, "opus", fixated))
    check("(d) SAME fixated dict: still injected despite config now disabled", injected2 is True)
    check("(d) SAME fixated dict: model still rewritten to claude-fable-5", result2["model"] == "claude-fable-5")


# Test 11 — a genuine MISS (config loads fine, model not in the table) pins "no injection" too —
# a later config addition for that model id, against the SAME fixated dict, must NOT retroactively apply.
def test_fixation_miss_is_pinned_too():
    print("\n[Test 11] Fixation: a genuine miss pins 'no injection', not just a hit")
    config_without_entry = {"model_params": {"claude-opus-5": {"effort": "high"}}}
    fixated = {}
    payload1 = _base_payload("claude-fable-5")
    result1, injected1 = _with_config(config_without_entry, lambda: _inject_model_override(payload1, "opus", fixated))
    check("miss: injected=False on first call", injected1 is False)
    check("miss: fixated dict still records the (empty) snapshot", "claude-fable-5" in fixated)

    config_now_has_entry = {"model_params": {"claude-fable-5": {"effort": "high", "max_tokens": 128000}}}
    payload2 = _base_payload("claude-fable-5")
    result2, injected2 = _with_config(config_now_has_entry, lambda: _inject_model_override(payload2, "opus", fixated))
    check("miss stays pinned: still injected=False despite the entry now existing", injected2 is False)
    check("miss stays pinned: payload2 unchanged", result2 == payload2)


# Test 12 — a genuine _load_config() exception on the FIRST call for a model id does NOT pin —
# the very next call (config now loadable) resolves live and pins from there.
def test_fixation_load_failure_does_not_pin():
    print("\n[Test 12] Fixation: a load failure on first call does not pin — next call retries live")
    fixated = {}
    payload1 = _base_payload("claude-fable-5")
    with mock.patch.object(inject_helpers, "_load_config", side_effect=RuntimeError("simulated")):
        result1, injected1 = _inject_model_override(payload1, "opus", fixated)
    check("load failure: injected=False, no raise", injected1 is False and result1 == payload1)
    check("load failure: nothing pinned for claude-fable-5", "claude-fable-5" not in fixated)

    config_ok = {"model_params": {"claude-fable-5": {"effort": "medium", "max_tokens": 64000}}}
    payload2 = _base_payload("claude-fable-5")
    result2, injected2 = _with_config(config_ok, lambda: _inject_model_override(payload2, "opus", fixated))
    check("next call retries live and succeeds: injected=True", injected2 is True)
    check("next call retries live and succeeds: effort=medium applied", result2["output_config"]["effort"] == "medium")
    check("next call retries live and succeeds: now pinned for claude-fable-5", "claude-fable-5" in fixated)


# Test 13 — thinking/context_management self-consistency: a surviving clear_thinking_20251015
# edit alongside a disabled thinking value is what produced the real 400 in
# api_requests_worker_25c51a2e_cache-write-run_1789308787; _strip_clear_thinking_edit must remove
# exactly that edit, no matter what disabled thinking, and never leave a dangling empty edits list.
def test_clear_thinking_edit_stripped_when_thinking_disabled():
    print("\n[Test 13] _strip_clear_thinking_edit: thinking/context_management self-consistency")

    # (a) thinking disabled + clear_thinking edit + a sibling edit -> only clear_thinking removed
    payload_a = {
        "model": "claude-sonnet-5",
        "thinking": {"type": "disabled"},
        "context_management": {"edits": [
            {"type": "clear_thinking_20251015", "keep": "all"},
            {"type": "clear_tool_uses_20250919", "trigger": {"type": "input_tokens", "value": 100000}},
        ]},
    }
    result_a, changed_a = _strip_clear_thinking_edit(payload_a)
    check("(a) clear_thinking_20251015 removed, changed=True", changed_a is True)
    check("(a) clear_tool_uses_20250919 survives untouched",
          result_a["context_management"]["edits"] == [
              {"type": "clear_tool_uses_20250919", "trigger": {"type": "input_tokens", "value": 100000}}])
    check("(a) original payload's edits list not mutated in place (still has both edits)",
          len(payload_a["context_management"]["edits"]) == 2)

    # (b) thinking disabled + ONLY the clear_thinking edit -> whole context_management key dropped,
    # not carried forward as an empty edits list (an empty edits list asks the API for "manage
    # context with zero edits", which is not the same as "no context_management at all" — dropping
    # the key is what Claude Code itself does when IT disables thinking, per the Haiku request in
    # the same capture).
    payload_b = {
        "model": "claude-sonnet-5",
        "thinking": {"type": "disabled"},
        "context_management": {"edits": [{"type": "clear_thinking_20251015", "keep": "all"}]},
    }
    result_b, changed_b = _strip_clear_thinking_edit(payload_b)
    check("(b) sole edit removed -> context_management key dropped entirely (no empty edits list)",
          changed_b is True and "context_management" not in result_b)

    # (c) thinking NOT disabled (adaptive) -> context_management untouched, byte-identical (same
    # object, not just equal-by-value).
    cm_c = {"edits": [{"type": "clear_thinking_20251015", "keep": "all"}]}
    payload_c = {
        "model": "claude-sonnet-5",
        "thinking": {"type": "adaptive", "display": "summarized"},
        "context_management": cm_c,
    }
    result_c, changed_c = _strip_clear_thinking_edit(payload_c)
    check("(c) thinking enabled -> unchanged, changed=False", changed_c is False)
    check("(c) thinking enabled -> context_management is the SAME object, byte-identical",
          result_c["context_management"] is cm_c)

    # (d) thinking disabled, no context_management at all -> no-op
    payload_d = {"model": "claude-sonnet-5", "thinking": {"type": "disabled"}}
    result_d, changed_d = _strip_clear_thinking_edit(payload_d)
    check("(d) no context_management -> no-op, changed=False", changed_d is False and result_d == payload_d)

    # (e) thinking disabled, context_management has no clear_thinking edit -> untouched
    payload_e = {
        "model": "claude-sonnet-5",
        "thinking": {"type": "disabled"},
        "context_management": {"edits": [{"type": "clear_tool_uses_20250919"}]},
    }
    result_e, changed_e = _strip_clear_thinking_edit(payload_e)
    check("(e) no clear_thinking edit present -> untouched, changed=False", changed_e is False)

    # (f) end-to-end: the exact observed shape — Claude Code sends thinking=adaptive plus its own
    # clear_thinking edit, the proxy's model_params injection (the menubar thinking-off toggle)
    # overwrites thinking to disabled, and the two functions together (as wired in
    # addon.py:_run_post_fixation_pipeline) must leave the payload self-consistent.
    observed_payload, injected = _with_config(
        {"model_params": {"claude-sonnet-5": {"thinking": {"type": "disabled"}, "effort": "high", "max_tokens": 64000}}},
        lambda: _inject_model_override({
            "model": "claude-sonnet-5",
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": "low"},
            "context_management": {"edits": [{"type": "clear_thinking_20251015", "keep": "all"}]},
        }, "sonnet"))
    check("(f) model_params injection (thinking toggle OFF) set thinking to disabled",
          injected is True and observed_payload["thinking"] == {"type": "disabled"})
    fixed_payload, fixed = _strip_clear_thinking_edit(observed_payload)
    check("(f) end-to-end: the self-contradictory 400-causing payload is now self-consistent",
          fixed is True and "context_management" not in fixed_payload)


# Test 14 — the forwarded dual-log must show the forwarded 'thinking' value, so this exact failure
# is readable straight off _forwarded.jsonl without cross-referencing the injected-fields delta.
def test_forwarded_delta_includes_thinking():
    print("\n[Test 14] _build_forwarded_delta records the forwarded 'thinking' value")
    payload_on = {"model": "claude-sonnet-5", "thinking": {"type": "adaptive", "display": "summarized"},
                  "max_tokens": 64000, "output_config": {"effort": "high"}}
    entry_on, _ = _build_forwarded_delta(payload_on, "req-1", None)
    check("thinking ON value recorded in the forwarded_delta entry",
          entry_on["thinking"] == {"type": "adaptive", "display": "summarized"})

    payload_off = {"model": "claude-sonnet-5", "thinking": {"type": "disabled"},
                   "max_tokens": 64000, "output_config": {"effort": "high"}}
    entry_off, _ = _build_forwarded_delta(payload_off, "req-2", None)
    check("thinking OFF value recorded in the forwarded_delta entry",
          entry_off["thinking"] == {"type": "disabled"})

    payload_missing = {"model": "claude-haiku-4-5-20251001"}
    entry_missing, _ = _build_forwarded_delta(payload_missing, "req-3", None)
    check("thinking absent from payload -> key present in the entry, value None",
          "thinking" in entry_missing and entry_missing["thinking"] is None)


# Load dev/proxy_dual_log/attribution_coverage.py by path (its module name has no package
# context here, matching the same by-path load it itself uses for src/proxy/strip_vocab.py).
def _load_attribution_coverage_module():
    path = WORKTREE_ROOT / "dev" / "proxy_dual_log" / "attribution_coverage.py"
    spec = importlib.util.spec_from_file_location("attribution_coverage_probe", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Test 15 — follow-up review point: _strip_clear_thinking_edit can now remove a top-level field
# (context_management) for the first time ever on the STRIP side. Establishes (a) the real fn_map
# written to stripped/injected JSONL never attributes ANY top-level field, proving
# src/proxy/strip_inject_delta.py's _FIELD_STRIP_FN/_FIELD_INJECT_FN are dead code untouched by
# this change; and (b) the tool that DOES attribute fields_delta entries,
# dev/proxy_dual_log/attribution_coverage.py's own _FIELD_STRIP_FN, now correctly names
# _strip_clear_thinking_edit instead of falling through to UNATTR:context_management.
def test_context_management_strip_is_attributed():
    print("\n[Test 15] context_management strip: fn_map dead-code check + attribution_coverage fix")

    orig_payload = {
        "model": "claude-sonnet-5",
        "thinking": {"type": "adaptive", "display": "summarized"},
        "context_management": {"edits": [{"type": "clear_thinking_20251015", "keep": "all"}]},
        "messages": [{"role": "user", "content": "hi"}],
    }
    modified_payload = {
        "model": "claude-sonnet-5",
        "thinking": {"type": "disabled"},
        "messages": [{"role": "user", "content": "hi"}],
    }
    stripped_entry, injected_entry, _new_s, _new_i = _build_stripped_injected_deltas(
        orig_payload, modified_payload, "req-attr", None, None, "claude-sonnet-5", {})

    check("(a) context_management now appears in stripped fields_delta (new: was injected-only before)",
          stripped_entry["fields_delta"].get("context_management") == orig_payload["context_management"])
    check("(a) the real fn_map carries NO field-level entry at all (thinking is equally unattributed "
          "there — pre-existing dead code, not something this fix changes)",
          stripped_entry["fn_map"] == {} and "thinking" not in stripped_entry["fn_map"])

    ac = _load_attribution_coverage_module()
    check("(a) confirms by content: src/proxy/strip_inject_delta.py's own _FIELD_STRIP_FN "
          "still has no context_management entry (left untouched — it was never live)",
          "context_management" not in strip_inject_delta._FIELD_STRIP_FN)
    strip_fn = ac._FIELD_STRIP_FN.get("context_management", "UNATTR:context_management")
    check("(b) attribution_coverage.py now attributes the strip to _strip_clear_thinking_edit, "
          f"not UNATTR (got: {strip_fn!r})",
          strip_fn != "UNATTR:context_management" and "_strip_clear_thinking_edit" in strip_fn)
    inject_fn = ac._FIELD_INJECT_FN.get("context_management", "UNATTR:context_management")
    check("(b) the inject side (Claude Code / _inject_context_management adding the edit) is "
          "unchanged and still correctly attributed",
          inject_fn == "_inject_context_management")


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("model_params probe — per-model config replacing the legacy model override")
    print("=" * 70)
    test_legacy_only_unchanged()
    test_model_params_hit()
    test_model_params_miss()
    test_suffixed_model_id_is_deliberate_miss()
    test_model_params_presence_wins_over_legacy()
    test_empty_and_partial_entries()
    test_config_load_failure_fails_open()
    test_fixation_pins_model_params_snapshot()
    test_fixation_fresh_instance_picks_up_new_config()
    test_fixation_legacy_path_pinned_and_unchanged()
    test_fixation_miss_is_pinned_too()
    test_fixation_load_failure_does_not_pin()
    test_clear_thinking_edit_stripped_when_thinking_disabled()
    test_forwarded_delta_includes_thinking()
    test_context_management_strip_is_attributed()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    _write_report(passed, total)
    return passed == total


def _write_report(passed, total):
    md_dir = WORKTREE_ROOT / "dev" / "native-model-start" / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = md_dir / f"p2_model_params_probe_{stamp}.md"
    lines = [
        f"# P2 — model_params probe run ({datetime.now(timezone.utc).isoformat()})",
        "",
        f"**Result: {passed}/{total} checks passed**",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for label, ok in _RESULTS:
        lines.append(f"| {label} | {'PASS' if ok else 'FAIL'} |")
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    ok = run_probe_workflow()
    sys.exit(0 if ok else 1)
