# INFRASTRUCTURE
from .rules_config import _load_config

# FUNCTIONS

# Inject model override fields from proxy_rules.json config if enabled and model is opus or sonnet — returns (modified_payload, injected_bool)
def _inject_model_override(payload: dict, model_family: str) -> tuple:
    try:
        config = _load_config()
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
    except Exception:
        return payload, False


# Inject context_management block from proxy_rules.json config if enabled — returns (modified_payload, injected_bool)
def _inject_context_management(payload: dict) -> tuple:
    try:
        config = _load_config()
        cm_config = config.get("context_management", {})
        if not cm_config.get("enabled", False):
            return payload, False

        edits = []

        # clear_thinking MUST be first in edits[] per Anthropic API requirement
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


# Apply post-sleep effort cap (effort=low, max_tokens=2000) if 'capped_post_sleep' in modifications — runs AFTER _inject_model_override so cap always wins — returns modified_payload
def _apply_post_sleep_cap(payload: dict, modifications: list) -> dict:
    if 'capped_post_sleep' not in modifications:
        return payload
    result = dict(payload)
    output_config = dict(result.get("output_config") or {})
    output_config["effort"] = "low"
    result["output_config"] = output_config
    result["max_tokens"] = 2000
    return result
