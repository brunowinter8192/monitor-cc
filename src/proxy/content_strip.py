# INFRASTRUCTURE
_REJECTION_MARKER = "The user doesn't want to proceed with this tool use"

# FUNCTIONS

def _message_has_rejection(content) -> bool:
    if isinstance(content, str):
        return _REJECTION_MARKER in content
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            tool_content = block.get("content", "")
            if isinstance(tool_content, str):
                if _REJECTION_MARKER in tool_content and len(tool_content) <= 200:
                    return True
            elif isinstance(tool_content, list):
                for sub in tool_content:
                    if not isinstance(sub, dict):
                        continue
                    sub_text = sub.get("text", "")
                    if _REJECTION_MARKER in sub_text and len(sub_text) <= 200:
                        return True
    return False


def _strip_rejection_message(content):
    if isinstance(content, str):
        return "."
    if isinstance(content, list):
        result = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                tool_content = block.get("content", "")
                has_rejection = (isinstance(tool_content, str) and _REJECTION_MARKER in tool_content) or (
                    isinstance(tool_content, list) and any(
                        _REJECTION_MARKER in sub.get("text", "")
                        for sub in tool_content if isinstance(sub, dict)
                    )
                )
                result.append({**block, "content": "."} if has_rejection else block)
            else:
                result.append(block)
        return result
    return content


def _strip_session_guidance(text: str) -> str:
    marker = "# Session-specific guidance"
    env_marker = "# Environment"
    if marker not in text:
        return text
    start = text.index(marker)
    env_idx = text.find(env_marker, start)
    if env_idx == -1:
        return text[:start].strip() or "."
    return (text[:start] + text[env_idx:]).strip()


def _strip_git_status(text: str) -> str:
    marker = "gitStatus:"
    idx = text.find(marker)
    if idx == -1:
        return text
    return text[:idx].rstrip()


def _strip_tool_descriptions(payload: dict) -> tuple:
    tools = payload.get("tools", [])
    if not tools:
        return payload, 0, {}
    stripped = 0
    originals = {}
    new_tools = []
    for tool in tools:
        t_name = tool.get("name", "")
        top_desc = tool.get("description", "")
        input_schema = tool.get("input_schema", {})
        props = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}

        param_originals = {}
        new_props = {}
        for p_name, p_info in props.items():
            if isinstance(p_info, dict) and p_info.get("description", "") != "":
                param_originals[p_name] = p_info["description"]
                new_props[p_name] = {**p_info, "description": ""}
            else:
                new_props[p_name] = p_info

        if top_desc != "" or param_originals:
            orig_entry = {}
            if top_desc != "":
                orig_entry["description"] = top_desc
            if param_originals:
                orig_entry["params"] = param_originals
            originals[t_name] = orig_entry
            stripped += 1
            new_tool = {**tool, "description": ""}
            if param_originals:
                new_tool = {**new_tool, "input_schema": {**input_schema, "properties": new_props}}
            new_tools.append(new_tool)
        else:
            new_tools.append(tool)

    if stripped == 0:
        return payload, 0, {}
    return {**payload, "tools": new_tools}, stripped, originals


def _strip_sys3(payload: dict) -> tuple:
    system = payload.get("system", [])
    if not isinstance(system, list) or len(system) < 4:
        return payload, False, None
    block = system[3]
    if not isinstance(block, dict) or block.get("type") != "text":
        return payload, False, None
    original_text = block.get("text", "")
    if original_text == ".":
        return payload, False, None
    new_system = list(system)
    new_system[3] = {**block, "text": "."}
    return {**payload, "system": new_system}, True, original_text
