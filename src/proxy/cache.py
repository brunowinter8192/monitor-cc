# INFRASTRUCTURE
from .logging import _summarize_message, _compute_diff
from .message_summary import _has_cache_control

# FUNCTIONS

# Collapse single-text-block list to plain string for user messages
def _normalize_user_content_shape(msg: dict) -> dict:
    if msg.get("role") != "user":
        return msg
    content = msg.get("content")
    if not isinstance(content, list) or len(content) != 1:
        return msg
    block = content[0]
    if not isinstance(block, dict):
        return msg
    if set(block.keys()) == {"type", "text"} and block["type"] == "text":
        return {**msg, "content": block["text"]}
    return msg


# Remove ALL cache_control markers from payload (system, tools, messages)
def _strip_all_cache_control(payload: dict) -> dict:
    result = dict(payload)

    system = result.get("system", [])
    if isinstance(system, list):
        new_system = []
        for block in system:
            if isinstance(block, dict) and "cache_control" in block:
                block = {k: v for k, v in block.items() if k != "cache_control"}
            new_system.append(block)
        result["system"] = new_system

    tools = result.get("tools", [])
    if tools:
        new_tools = []
        for tool in tools:
            if isinstance(tool, dict) and "cache_control" in tool:
                tool = {k: v for k, v in tool.items() if k != "cache_control"}
            new_tools.append(tool)
        result["tools"] = new_tools

    messages = result.get("messages", [])
    new_messages = []
    for msg in messages:
        new_msg = {k: v for k, v in msg.items() if k != "cache_control"}
        content = new_msg.get("content", "")
        if isinstance(content, list):
            new_blocks = []
            for block in content:
                if isinstance(block, dict) and "cache_control" in block:
                    block = {k: v for k, v in block.items() if k != "cache_control"}
                new_blocks.append(block)
            new_msg["content"] = new_blocks
        new_msg = _normalize_user_content_shape(new_msg)
        new_messages.append(new_msg)
    result["messages"] = new_messages

    return result


# BP1: system[2] — cross-session cache anchor for system blocks 0..2. sys[3] carries gitStatus +
# cwd (drifts between commits/sessions) and is excluded from this prefix. Mutates result["system"]
# in place when it fires; returns True/False (bp_count contribution).
def _apply_bp1_system(result: dict, cc_marker: dict) -> bool:
    system = result.get("system", [])
    if isinstance(system, list) and len(system) >= 3 and isinstance(system[2], dict):
        new_system = list(system)
        new_system[2] = {**new_system[2], "cache_control": cc_marker}
        result["system"] = new_system
        return True
    return False


# BP2: last non-defer tool (end of tools section). Mutates result["tools"] in place.
def _apply_bp2_tools(result: dict, cc_marker: dict) -> bool:
    tools = result.get("tools", [])
    if not tools:
        return False
    new_tools = list(tools)
    end_idx = -1
    for ti in range(len(new_tools) - 1, -1, -1):
        if isinstance(new_tools[ti], dict) and not new_tools[ti].get("defer_loading"):
            end_idx = ti
            break
    hit = False
    if end_idx >= 0:
        new_tools[end_idx] = {**new_tools[end_idx], "cache_control": cc_marker}
        hit = True
    result["tools"] = new_tools
    return hit


# BP3: last message that is UNCHANGED from previous request. Returns (messages, hit).
def _apply_bp3_unchanged_tail(messages: list, prev_mod_messages, cc_marker: dict) -> tuple:
    if not messages or prev_mod_messages is None:
        return messages, False
    curr_summaries = [_summarize_message(m) for m in messages]
    diff = _compute_diff(prev_mod_messages, curr_summaries)
    first_diff = diff.get("first_diff_index", -1)
    if first_diff > 0:
        bp3_idx = first_diff - 1
        messages = list(messages)
        messages[bp3_idx] = _add_cache_control_to_message(messages[bp3_idx], cc_marker)
        return messages, True
    return messages, False


# BP4: last message (for next request's cache). Returns (messages, hit).
def _apply_bp4_last_message(messages: list, cc_marker: dict) -> tuple:
    if not messages:
        return messages, False
    last_idx = len(messages) - 1
    if not _has_cache_control(messages[last_idx]):
        messages = list(messages) if not isinstance(messages, list) else messages
        messages[last_idx] = _add_cache_control_to_message(messages[last_idx], cc_marker)
        return messages, True
    return messages, False


# Set our own cache_control breakpoints (max 4) on the already-modified, stripped payload.
# prev_mod_messages: summaries from the PREVIOUS request's modified payload (for BP3).
def _set_cache_breakpoints(payload: dict, prev_mod_messages: list = None) -> dict:
    result = dict(payload)
    bp_count = 0
    cc_marker = {"type": "ephemeral", "ttl": "1h"}

    if _apply_bp1_system(result, cc_marker):
        bp_count += 1
    if _apply_bp2_tools(result, cc_marker):
        bp_count += 1

    messages = result.get("messages", [])
    messages, hit3 = _apply_bp3_unchanged_tail(messages, prev_mod_messages, cc_marker)
    if hit3:
        bp_count += 1
    messages, hit4 = _apply_bp4_last_message(messages, cc_marker)
    if hit4:
        bp_count += 1

    result["messages"] = messages
    return result


# Add cache_control to the last content block of a message
def _add_cache_control_to_message(msg: dict, cc_marker: dict) -> dict:
    new_msg = dict(msg)
    content = new_msg.get("content", "")
    if isinstance(content, list) and content:
        new_blocks = list(content)
        last_block = new_blocks[-1]
        if isinstance(last_block, dict):
            new_blocks[-1] = {**last_block, "cache_control": cc_marker}
        new_msg["content"] = new_blocks
    elif isinstance(content, str):
        new_msg["content"] = [{"type": "text", "text": content, "cache_control": cc_marker}]
    return new_msg
