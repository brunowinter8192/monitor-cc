# INFRASTRUCTURE
import importlib.util
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))
sys.path.insert(0, str(WORKTREE_ROOT))

from src.proxy.inject_helpers import _inject_model_override, _strip_clear_thinking_edit
from src.proxy.logging import _build_forwarded_delta
from src.proxy import strip_inject_delta
from src.proxy.strip_inject_delta import _build_stripped_injected_deltas

from model_params_test_infra import check, _with_config


# FUNCTIONS

def _load_attribution_coverage_module():
    path = WORKTREE_ROOT / "dev" / "proxy_dual_log" / "attribution_coverage" / "attribution_coverage_classify.py"
    spec = importlib.util.spec_from_file_location("attribution_coverage_probe", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _test_clear_thinking_removal_cases():
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

    payload_b = {
        "model": "claude-sonnet-5",
        "thinking": {"type": "disabled"},
        "context_management": {"edits": [{"type": "clear_thinking_20251015", "keep": "all"}]},
    }
    result_b, changed_b = _strip_clear_thinking_edit(payload_b)
    check("(b) sole edit removed -> context_management key dropped entirely (no empty edits list)",
          changed_b is True and "context_management" not in result_b)


def _test_clear_thinking_noop_cases():
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

    payload_d = {"model": "claude-sonnet-5", "thinking": {"type": "disabled"}}
    result_d, changed_d = _strip_clear_thinking_edit(payload_d)
    check("(d) no context_management -> no-op, changed=False", changed_d is False and result_d == payload_d)

    payload_e = {
        "model": "claude-sonnet-5",
        "thinking": {"type": "disabled"},
        "context_management": {"edits": [{"type": "clear_tool_uses_20250919"}]},
    }
    result_e, changed_e = _strip_clear_thinking_edit(payload_e)
    check("(e) no clear_thinking edit present -> untouched, changed=False", changed_e is False)


def _test_clear_thinking_end_to_end():
    observed_payload, injected = _with_config(
        {"model_params": {"claude-sonnet-5": {"thinking": {"type": "disabled"}, "effort": "high", "max_tokens": 64000}}},
        lambda: _inject_model_override({
            "model": "claude-sonnet-5",
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": "low"},
            "context_management": {"edits": [{"type": "clear_thinking_20251015", "keep": "all"}]},
        }))
    check("(f) model_params injection (thinking toggle OFF) set thinking to disabled",
          injected is True and observed_payload["thinking"] == {"type": "disabled"})
    fixed_payload, fixed = _strip_clear_thinking_edit(observed_payload)
    check("(f) end-to-end: the self-contradictory 400-causing payload is now self-consistent",
          fixed is True and "context_management" not in fixed_payload)


def test_clear_thinking_edit_stripped_when_thinking_disabled():
    print("\n[Test 13] _strip_clear_thinking_edit: thinking/context_management self-consistency")
    _test_clear_thinking_removal_cases()
    _test_clear_thinking_noop_cases()
    _test_clear_thinking_end_to_end()


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


def test_context_management_strip_is_attributed():
    print("\n[Test 15] context_management strip: fn_map dead-code removal check + attribution_coverage fix")

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
    check("(a) confirms by content: src/proxy/strip_inject_delta.py's own _FIELD_STRIP_FN/"
          "_FIELD_INJECT_FN have been removed entirely (they were never live)",
          not hasattr(strip_inject_delta, "_FIELD_STRIP_FN")
          and not hasattr(strip_inject_delta, "_FIELD_INJECT_FN"))
    strip_fn = ac._FIELD_STRIP_FN.get("context_management", "UNATTR:context_management")
    check("(b) attribution_coverage.py now attributes the strip to _strip_clear_thinking_edit, "
          f"not UNATTR (got: {strip_fn!r})",
          strip_fn != "UNATTR:context_management" and "_strip_clear_thinking_edit" in strip_fn)
    inject_fn = ac._FIELD_INJECT_FN.get("context_management", "UNATTR:context_management")
    check("(b) the inject side (Claude Code / _inject_context_management adding the edit) is "
          "unchanged and still correctly attributed",
          inject_fn == "_inject_context_management")
