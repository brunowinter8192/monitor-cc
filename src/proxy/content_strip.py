# INFRASTRUCTURE
import re

_REJECTION_MARKER = "The user doesn't want to proceed with this tool use"

# FUNCTIONS

# Check if user message content contains a tool_result block with the rejection marker
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


# Replace rejection tool_result block content with '.'
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


# Extract SessionStart system-reminder block from MSG[0] content. Returns (modified_content, extracted_text_or_None).
def _extract_session_start_block(content):
    _RULES_MARKER = "SessionStart hook additional context:"
    _TAG_OPEN = "<system-reminder>"
    _TAG_CLOSE = "</system-reminder>"

    def _extract_from_text(text: str):
        if _RULES_MARKER not in text:
            return text, None
        marker_idx = text.index(_RULES_MARKER)
        open_idx = text.rfind(_TAG_OPEN, 0, marker_idx)
        if open_idx == -1:
            return text, None
        close_idx = text.find(_TAG_CLOSE, marker_idx)
        if close_idx == -1:
            return text, None
        close_end = close_idx + len(_TAG_CLOSE)
        extracted = text[open_idx:close_end]
        remaining = (text[:open_idx] + text[close_end:]).strip() or "."
        return remaining, extracted

    if isinstance(content, str):
        return _extract_from_text(content)
    if isinstance(content, list):
        for i, block in enumerate(content):
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            new_text, extracted = _extract_from_text(block.get("text", ""))
            if extracted:
                new_blocks = list(content)
                new_blocks[i] = {**block, "text": new_text}
                return new_blocks, extracted
    return content, None


# Remove '# Session-specific guidance' section from text, keeping '# Environment' onward.
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


# Strip gitStatus section (always at bottom of sys[3]) from text — everything from 'gitStatus:' to end.
def _strip_git_status(text: str) -> str:
    marker = "gitStatus:"
    idx = text.find(marker)
    if idx == -1:
        return text
    return text[:idx].rstrip()


# Strip description fields from all tools in payload.tools[] — top-level description and all
# input_schema.properties[*].description. Returns (modified_payload, count_stripped, originals_dict).
# originals_dict = {tool_name: {"description": "...", "params": {param_name: "..."}}} — only tools
# where anything was actually stripped; only keys present when non-empty. Idempotent.
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


# Build replacement text for a persisted-output block — extracts size if present.
def _build_persisted_replacement(content: str) -> str:
    for line in content.splitlines()[:5]:
        m = re.search(r'\(([\d.]+\s*[KMG]?B)\)', line, re.IGNORECASE)
        if m:
            return f"[Persisted — {m.group(1)}. Use Read(offset/limit), Grep, or Bash(head/tail/grep) to extract.]"
    return "[Persisted output stripped. Use Read(offset/limit), Grep, or Bash(head/tail/grep) to extract.]"


# Strip <persisted-output> blocks from tool_result content in payload.messages[].
# Returns (modified_payload, count_stripped, originals_dict) where
# originals_dict = {msg_idx: {block_idx: original_content_string}}. Idempotent.
def _strip_persisted_output(payload: dict) -> tuple:
    messages = payload.get("messages", [])
    if not messages:
        return payload, 0, {}
    count_stripped = 0
    originals = {}
    new_messages = []
    changed = False
    for msg_idx, msg in enumerate(messages):
        content = msg.get("content")
        if not isinstance(content, list):
            new_messages.append(msg)
            continue
        new_content = []
        msg_changed = False
        for block_idx, block in enumerate(content):
            tool_content = block.get("content") if isinstance(block, dict) else None
            if (isinstance(block, dict)
                    and block.get("type") == "tool_result"
                    and isinstance(tool_content, str)
                    and "<persisted-output>" in tool_content):
                if msg_idx not in originals:
                    originals[msg_idx] = {}
                originals[msg_idx][block_idx] = tool_content
                new_content.append({**block, "content": _build_persisted_replacement(tool_content)})
                count_stripped += 1
                msg_changed = True
            else:
                new_content.append(block)
        if msg_changed:
            new_messages.append({**msg, "content": new_content})
            changed = True
        else:
            new_messages.append(msg)
    if not changed:
        return payload, 0, {}
    return {**payload, "messages": new_messages}, count_stripped, originals


# Replace sys[3].text with "." — strips claudeMd context block from system prompt.
# Returns (modified_payload, was_stripped: bool, original_text_or_None). Idempotent: skips if already ".".
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
