# INFRASTRUCTURE
from .rules_config import _load_config

# FUNCTIONS

def _model_params_dict_for(model_id: str, entry: dict) -> dict:
    return {model_id: entry} if entry else {}


def _inject_model_override(payload: dict, model_family: str, fixated_model_override: dict = None) -> tuple:
    if fixated_model_override is None:
        fixated_model_override = {}
    model_id = payload.get("model", "")
    if model_id in fixated_model_override:
        snapshot = fixated_model_override[model_id]
        if snapshot["kind"] == "model_params":
            return _inject_model_params(payload, _model_params_dict_for(model_id, snapshot["entry"]))
        return _inject_legacy_model_override(payload, model_family, snapshot["config"])
    try:
        config = _load_config()
        if "model_params" in config:
            entry = config["model_params"].get(model_id) or {}
            fixated_model_override[model_id] = {"kind": "model_params", "entry": entry}
            return _inject_model_params(payload, _model_params_dict_for(model_id, entry))
        if model_family == "opus":
            legacy_config = {"model_override": config.get("model_override", {})}
        elif model_family == "sonnet":
            legacy_config = {"model_override_worker": config.get("model_override_worker", {})}
        else:
            legacy_config = {}
        fixated_model_override[model_id] = {"kind": "legacy", "config": legacy_config}
        return _inject_legacy_model_override(payload, model_family, legacy_config)
    except Exception:
        return payload, False


def _inject_model_params(payload: dict, model_params: dict) -> tuple:
    model_id = payload.get("model", "")
    params = model_params.get(model_id)
    if not params:
        return payload, False
    result = dict(payload)
    if "thinking" in params:
        result["thinking"] = params["thinking"]
    if "effort" in params:
        output_config = dict(result.get("output_config") or {})
        output_config["effort"] = params["effort"]
        result["output_config"] = output_config
    if "max_tokens" in params:
        result["max_tokens"] = params["max_tokens"]
    return result, True


def _inject_legacy_model_override(payload: dict, model_family: str, config: dict) -> tuple:
    if model_family == "opus":
        mo_config = config.get("model_override", {})
    elif model_family == "sonnet":
        mo_config = config.get("model_override_worker", {})
    else:
        return payload, False
    if not mo_config.get("enabled", False):
        return payload, False
    result = dict(payload)
    if "model" in mo_config:
        result["model"] = mo_config["model"]
    if "thinking" in mo_config:
        result["thinking"] = mo_config["thinking"]
    if "effort" in mo_config:
        output_config = dict(result.get("output_config") or {})
        output_config["effort"] = mo_config["effort"]
        result["output_config"] = output_config
    if "max_tokens" in mo_config:
        result["max_tokens"] = mo_config["max_tokens"]
    return result, True


def _inject_context_management(payload: dict) -> tuple:
    try:
        config = _load_config()
        cm_config = config.get("context_management", {})
        if not cm_config.get("enabled", False):
            return payload, False

        edits = []

        clear_thinking = cm_config.get("clear_thinking", {})
        if clear_thinking.get("enabled", True):
            edits.append({
                "type": "clear_thinking_20251015",
                "keep": {
                    "type": "thinking_turns",
                    "value": clear_thinking.get("keep_thinking_turns", 2),
                },
            })

        clear_tool_uses = cm_config.get("clear_tool_uses", {})
        if clear_tool_uses.get("enabled", True):
            edits.append({
                "type": "clear_tool_uses_20250919",
                "trigger": {
                    "type": "input_tokens",
                    "value": clear_tool_uses.get("trigger_input_tokens", 100000),
                },
                "keep": {
                    "type": "tool_uses",
                    "value": clear_tool_uses.get("keep_tool_uses", 5),
                },
                "clear_at_least": {
                    "type": "input_tokens",
                    "value": clear_tool_uses.get("clear_at_least_tokens", 10000),
                },
            })

        if not edits:
            return payload, False

        result = dict(payload)
        result["context_management"] = {"edits": edits}
        return result, True
    except Exception:
        return payload, False
