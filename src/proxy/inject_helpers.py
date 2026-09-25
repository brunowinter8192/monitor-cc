# INFRASTRUCTURE
from src.proxy.proxy_error_log import clear_proxy_error, log_proxy_error_on_change
from src.proxy.rules_config import _load_config

_CLEAR_THINKING_EDIT_TYPE = "clear_thinking_20251015"
_MODEL_OVERRIDE_SOURCE = "inject_helpers.model_override"
_CONTEXT_MANAGEMENT_SOURCE = "inject_helpers.context_management"

# FUNCTIONS

def _inject_model_override(payload: dict, fixated_model_override: dict = None) -> tuple:
    if fixated_model_override is None:
        fixated_model_override = {}
    model_id = payload.get("model", "")
    if model_id not in fixated_model_override:
        try:
            fixated_model_override[model_id] = _load_model_params_entry(model_id)
        except Exception as e:
            log_proxy_error_on_change(_MODEL_OVERRIDE_SOURCE, e)
            return payload, False
        clear_proxy_error(_MODEL_OVERRIDE_SOURCE)
    return _inject_model_params(payload, _model_params_dict_for(model_id, fixated_model_override[model_id]))


def _load_model_params_entry(model_id: str) -> dict:
    return _load_config().get("model_params", {}).get(model_id) or {}


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


def _model_params_dict_for(model_id: str, entry: dict) -> dict:
    return {model_id: entry} if entry else {}


def _inject_context_management(payload: dict) -> tuple:
    try:
        result = _apply_context_management(payload)
    except Exception as e:
        log_proxy_error_on_change(_CONTEXT_MANAGEMENT_SOURCE, e)
        return payload, False
    clear_proxy_error(_CONTEXT_MANAGEMENT_SOURCE)
    return result


def _apply_context_management(payload: dict) -> tuple:
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


def _strip_clear_thinking_edit(payload: dict) -> tuple:
    if not _thinking_is_disabled(payload):
        return payload, False
    cm = payload.get("context_management")
    if not isinstance(cm, dict):
        return payload, False
    edits = cm.get("edits")
    if not isinstance(edits, list):
        return payload, False
    filtered_edits = [e for e in edits
                      if not (isinstance(e, dict) and e.get("type") == _CLEAR_THINKING_EDIT_TYPE)]
    if len(filtered_edits) == len(edits):
        return payload, False
    result = dict(payload)
    if filtered_edits:
        result["context_management"] = {**cm, "edits": filtered_edits}
    else:
        del result["context_management"]
    return result, True


def _thinking_is_disabled(payload: dict) -> bool:
    thinking = payload.get("thinking")
    return isinstance(thinking, dict) and thinking.get("type") == "disabled"
