# INFRASTRUCTURE
from .rules import _load_config

# FUNCTIONS

# Inject model override fields from proxy_rules.json config if enabled and model is opus — returns (modified_payload, injected_bool)
def _inject_model_override(payload: dict, model_family: str) -> tuple:
    try:
        config = _load_config()
        mo_config = config.get("model_override", {})
        if not mo_config.get("enabled", False):
            return payload, False
        if model_family != "opus":
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
