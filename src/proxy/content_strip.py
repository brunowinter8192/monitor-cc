# INFRASTRUCTURE
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


# Strip description field from all tools in payload.tools[] — keeps name + input_schema intact.
# Returns (modified_payload, count_stripped). Idempotent: tools already empty-description are skipped.
def _strip_tool_descriptions(payload: dict) -> tuple:
    tools = payload.get("tools", [])
    if not tools:
        return payload, 0
    stripped = 0
    new_tools = []
    for tool in tools:
        if tool.get("description", "") != "":
            new_tools.append({**tool, "description": ""})
            stripped += 1
        else:
            new_tools.append(tool)
    if stripped == 0:
        return payload, 0
    return {**payload, "tools": new_tools}, stripped


# Replace sys[3].text with "." — strips claudeMd context block from system prompt.
# Returns (modified_payload, was_stripped: bool). Idempotent: skips if already ".".
def _strip_sys3(payload: dict) -> tuple:
    system = payload.get("system", [])
    if not isinstance(system, list) or len(system) < 4:
        return payload, False
    block = system[3]
    if not isinstance(block, dict) or block.get("type") != "text":
        return payload, False
    if block.get("text", "") == ".":
        return payload, False
    new_system = list(system)
    new_system[3] = {**block, "text": "."}
    return {**payload, "system": new_system}, True
