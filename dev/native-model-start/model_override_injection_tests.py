# INFRASTRUCTURE
import sys
from pathlib import Path
from unittest import mock

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))
sys.path.insert(0, str(WORKTREE_ROOT))

from proxy import inject_helpers
from proxy.inject_helpers import _inject_model_override

from model_params_test_infra import check, _with_config

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


# FUNCTIONS

def test_legacy_only_is_ignored():
    print("\n[Test 1] Legacy-only config (no model_params) -> ignored, payload untouched")
    for model in ("claude-opus-4-8", "claude-sonnet-4-5", "claude-haiku-4"):
        payload = _base_payload(model)
        result, injected = _with_config(_LEGACY_CONFIG, lambda: _inject_model_override(payload))
        check(f"{model}: injected=False, payload untouched", injected is False and result == payload)


def test_model_params_hit():
    print("\n[Test 2] model_params hit -> params applied, model field NEVER touched")
    payload = _base_payload("claude-fable-5")
    result, injected = _with_config(_MODEL_PARAMS_CONFIG, lambda: _inject_model_override(payload))
    check("injected=True", injected is True)
    check("model field UNCHANGED (still claude-fable-5, not rewritten)", result["model"] == "claude-fable-5")
    check("thinking applied", result["thinking"] == {"type": "adaptive", "display": "omitted"})
    check("effort applied via output_config", result["output_config"]["effort"] == "high")
    check("max_tokens applied", result["max_tokens"] == 64000)

    payload_o = _base_payload("claude-opus-5")
    result_o, injected_o = _with_config(_MODEL_PARAMS_CONFIG, lambda: _inject_model_override(payload_o))
    check("claude-opus-5 hit: injected=True, model untouched",
          injected_o is True and result_o["model"] == "claude-opus-5")

    payload_s = _base_payload("claude-sonnet-5")
    result_s, injected_s = _with_config(_MODEL_PARAMS_CONFIG, lambda: _inject_model_override(payload_s))
    check("claude-sonnet-5 hit: injected=True, model untouched",
          injected_s is True and result_s["model"] == "claude-sonnet-5")


def test_model_params_miss():
    print("\n[Test 3] model_params miss -> payload untouched")
    payload = _base_payload("claude-haiku-4")
    result, injected = _with_config(_MODEL_PARAMS_CONFIG, lambda: _inject_model_override(payload))
    check("injected=False", injected is False)
    check("payload identical (same dict values)", result == payload)


def test_suffixed_model_id_is_deliberate_miss():
    print("\n[Test 4] Suffixed model-id variant -> deliberate MISS (no normalization)")
    config = {"model_params": {"claude-opus-4-8": {"effort": "high"}}}
    payload = _base_payload("claude-opus-4-8[1m]")
    result, injected = _with_config(config, lambda: _inject_model_override(payload))
    check("suffixed id 'claude-opus-4-8[1m]' vs table key 'claude-opus-4-8' -> exact match FAILS",
          injected is False and result == payload)


def test_model_params_presence_wins_over_legacy():
    print("\n[Test 5] model_params PRESENT (non-empty) alongside legacy sections -> model_params wins")
    mixed_config = {**_LEGACY_CONFIG, **_MODEL_PARAMS_CONFIG}
    payload = _base_payload("claude-fable-5")
    result, injected = _with_config(mixed_config, lambda: _inject_model_override(payload))
    check("injected=True (from model_params, not legacy)", injected is True)
    check("model NOT rewritten despite legacy model_override.model=claude-fable-5 being present too",
          result["model"] == "claude-fable-5")
    check("thinking/effort/max_tokens match model_params values", result["max_tokens"] == 64000)

    print("\n[Test 5b] model_params PRESENT as an EMPTY {} -> still wins, legacy fully disabled")
    empty_mp_config = {**_LEGACY_CONFIG, "model_params": {}}
    payload_o = _base_payload("claude-opus-4-8")
    result_o, injected_o = _with_config(empty_mp_config, lambda: _inject_model_override(payload_o))
    check("empty model_params {} -> injected=False (no entry for this model)", injected_o is False)
    check("model NOT rewritten to claude-fable-5 — legacy path never consulted despite being 'enabled'",
          result_o["model"] == "claude-opus-4-8")


def test_empty_and_partial_entries():
    print("\n[Test 6] Empty per-model entry -> untouched; partial entry -> only that key applied")
    config_empty_entry = {"model_params": {"claude-fable-5": {}}}
    payload = _base_payload("claude-fable-5")
    result, injected = _with_config(config_empty_entry, lambda: _inject_model_override(payload))
    check("empty {} entry for a matched model -> injected=False, untouched",
          injected is False and result == payload)

    config_partial = {"model_params": {"claude-fable-5": {"effort": "medium"}}}
    payload2 = _base_payload("claude-fable-5")
    result2, injected2 = _with_config(config_partial, lambda: _inject_model_override(payload2))
    check("partial entry (effort only): injected=True", injected2 is True)
    check("effort applied", result2["output_config"]["effort"] == "medium")
    check("thinking NOT added (key absent from entry)", "thinking" not in result2)
    check("max_tokens UNCHANGED from original payload (key absent from entry, not injected)",
          result2["max_tokens"] == payload2["max_tokens"] == 8000)


def test_config_load_failure_fails_open():
    print("\n[Test 7] _load_config raising -> fail-open, no raise")
    payload = _base_payload("claude-fable-5")
    with mock.patch.object(inject_helpers, "_load_config", side_effect=RuntimeError("simulated")):
        try:
            result, injected = _inject_model_override(payload)
            raised = False
        except Exception:
            result, injected, raised = payload, False, True
    check("no raise propagated", not raised)
    check("injected=False, payload untouched", injected is False and result == payload)


def test_fixation_pins_model_params_snapshot():
    print("\n[Test 8] Fixation: model_params pins on first request, later config change ignored")
    config1 = {"model_params": {"claude-fable-5": {"effort": "low", "max_tokens": 32000}}}
    config2 = {"model_params": {"claude-fable-5": {"effort": "high", "max_tokens": 128000}}}
    fixated = {}
    payload1 = _base_payload("claude-fable-5")
    result1, injected1 = _with_config(config1, lambda: _inject_model_override(payload1, fixated))
    check("(a) first request applies config1 (effort=low)", result1["output_config"]["effort"] == "low")
    check("(a) first request applies config1 (max_tokens=32000)", result1["max_tokens"] == 32000)
    check("(a) fixated dict now holds an entry for claude-fable-5", "claude-fable-5" in fixated)

    payload2 = _base_payload("claude-fable-5")
    result2, injected2 = _with_config(config2, lambda: _inject_model_override(payload2, fixated))
    check("(b) SAME fixated dict: config2 change ignored, still effort=low", result2["output_config"]["effort"] == "low")
    check("(b) SAME fixated dict: config2 change ignored, still max_tokens=32000", result2["max_tokens"] == 32000)
    check("(b) injected still True on the pinned replay", injected2 is True)


def test_fixation_fresh_instance_picks_up_new_config():
    print("\n[Test 9] Fixation: a fresh fixated dict picks up the changed config")
    config2 = {"model_params": {"claude-fable-5": {"effort": "high", "max_tokens": 128000}}}
    fresh_fixated = {}
    payload3 = _base_payload("claude-fable-5")
    result3, injected3 = _with_config(config2, lambda: _inject_model_override(payload3, fresh_fixated))
    check("(c) fresh dict applies config2 (effort=high)", result3["output_config"]["effort"] == "high")
    check("(c) fresh dict applies config2 (max_tokens=128000)", result3["max_tokens"] == 128000)


def test_fixation_legacy_only_config_pins_no_op():
    print("\n[Test 10] Fixation: legacy-only config pins a no-op snapshot")
    fixated = {}
    payload1 = _base_payload("claude-opus-4-8")
    result1, injected1 = _with_config(_LEGACY_CONFIG, lambda: _inject_model_override(payload1, fixated))
    check("(d) legacy-only first call: injected=False, payload untouched", injected1 is False and result1 == payload1)
    check("(d) fixated dict holds the empty snapshot for claude-opus-4-8", fixated.get("claude-opus-4-8") == {})

    config_now_has_entry = {"model_params": {"claude-opus-4-8": {"effort": "high"}}}
    payload2 = _base_payload("claude-opus-4-8")
    result2, injected2 = _with_config(config_now_has_entry, lambda: _inject_model_override(payload2, fixated))
    check("(d) SAME fixated dict: pinned no-op stays, still injected=False", injected2 is False and result2 == payload2)


def test_fixation_miss_is_pinned_too():
    print("\n[Test 11] Fixation: a genuine miss pins 'no injection', not just a hit")
    config_without_entry = {"model_params": {"claude-opus-5": {"effort": "high"}}}
    fixated = {}
    payload1 = _base_payload("claude-fable-5")
    result1, injected1 = _with_config(config_without_entry, lambda: _inject_model_override(payload1, fixated))
    check("miss: injected=False on first call", injected1 is False)
    check("miss: fixated dict still records the (empty) snapshot", "claude-fable-5" in fixated)

    config_now_has_entry = {"model_params": {"claude-fable-5": {"effort": "high", "max_tokens": 128000}}}
    payload2 = _base_payload("claude-fable-5")
    result2, injected2 = _with_config(config_now_has_entry, lambda: _inject_model_override(payload2, fixated))
    check("miss stays pinned: still injected=False despite the entry now existing", injected2 is False)
    check("miss stays pinned: payload2 unchanged", result2 == payload2)


def test_fixation_load_failure_does_not_pin():
    print("\n[Test 12] Fixation: a load failure on first call does not pin — next call retries live")
    fixated = {}
    payload1 = _base_payload("claude-fable-5")
    with mock.patch.object(inject_helpers, "_load_config", side_effect=RuntimeError("simulated")):
        result1, injected1 = _inject_model_override(payload1, fixated)
    check("load failure: injected=False, no raise", injected1 is False and result1 == payload1)
    check("load failure: nothing pinned for claude-fable-5", "claude-fable-5" not in fixated)

    config_ok = {"model_params": {"claude-fable-5": {"effort": "medium", "max_tokens": 64000}}}
    payload2 = _base_payload("claude-fable-5")
    result2, injected2 = _with_config(config_ok, lambda: _inject_model_override(payload2, fixated))
    check("next call retries live and succeeds: injected=True", injected2 is True)
    check("next call retries live and succeeds: effort=medium applied", result2["output_config"]["effort"] == "medium")
    check("next call retries live and succeeds: now pinned for claude-fable-5", "claude-fable-5" in fixated)
