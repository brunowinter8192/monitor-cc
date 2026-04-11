# INFRASTRUCTURE
from .logging import _summarize_message, _compute_diff
from .message_summary import _has_cache_control

# FUNCTIONS

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
        new_messages.append(new_msg)
    result["messages"] = new_messages

    return result


# Set our own cache_control breakpoints (max 4) on the already-modified, stripped payload.
# prev_mod_messages: summaries from the PREVIOUS request's modified payload (for BP3).
def _set_cache_breakpoints(payload: dict, prev_mod_messages: list = None) -> dict:
    result = dict(payload)
    bp_count = 0
    cc_marker = {"type": "ephemeral", "ttl": "1h"}

    # BP1: rules block (system[2]), fallback to last system block
    system = result.get("system", [])
    if isinstance(system, list) and system:
        new_system = list(system)
        target_idx = 2 if len(new_system) > 2 else len(new_system) - 1
        target = new_system[target_idx]
        if isinstance(target, dict):
            new_system[target_idx] = {**target, "cache_control": cc_marker}
            result["system"] = new_system
            bp_count += 1

    # BP2: last tool WITHOUT defer_loading (defer_loading + cache_control = API error)
    tools = result.get("tools", [])
    if tools:
        new_tools = list(tools)
        for ti in range(len(new_tools) - 1, -1, -1):
            tool = new_tools[ti]
            if isinstance(tool, dict) and not tool.get("defer_loading"):
                new_tools[ti] = {**tool, "cache_control": cc_marker}
                bp_count += 1
                break
        result["tools"] = new_tools

    # BP3: last message that is UNCHANGED from previous request
    messages = result.get("messages", [])
    if messages and prev_mod_messages is not None:
        curr_summaries = [_summarize_message(m) for m in messages]
        diff = _compute_diff(prev_mod_messages, curr_summaries)
        first_diff = diff.get("first_diff_index", -1)

        if first_diff > 0:
            bp3_idx = first_diff - 1
            messages = list(messages)
            messages[bp3_idx] = _add_cache_control_to_message(messages[bp3_idx], cc_marker)
            bp_count += 1

    # BP4: last message (for next request's cache)
    if messages:
        last_idx = len(messages) - 1
        if not _has_cache_control(messages[last_idx]):
            messages = list(messages) if not isinstance(messages, list) else messages
            messages[last_idx] = _add_cache_control_to_message(messages[last_idx], cc_marker)
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
