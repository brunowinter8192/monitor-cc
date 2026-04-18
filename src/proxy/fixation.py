# INFRASTRUCTURE
import os

from .tool_injection import _load_active_plugins

# FUNCTIONS

# Capture fixation values from first modified payload — sys[2] text, msg[0] project-rules block, active_plugins
def _capture_fixation(payload: dict, modifications: list) -> dict:
    fixated = {}
    system = payload.get("system", [])
    if isinstance(system, list) and len(system) > 2:
        block2 = system[2]
        if isinstance(block2, dict) and block2.get("type") == "text":
            fixated["sys2_text"] = block2.get("text", "")
    if "injected_project_rules" in modifications:
        msgs = payload.get("messages", [])
        if msgs:
            content = msgs[0].get("content", "")
            if isinstance(content, list) and content:
                first_block = content[0]
                if isinstance(first_block, dict) and first_block.get("type") == "text":
                    fixated["msg0_pr_block"] = first_block.get("text", "")
            elif isinstance(content, str):
                end_tag = "</system-reminder>"
                idx = content.find(end_tag)
                if idx != -1:
                    fixated["msg0_pr_block_str"] = content[:idx + len(end_tag)]
    project_path = os.environ.get("PROXY_PROJECT_PATH", "")
    fixated["active_plugins"] = _load_active_plugins(project_path)
    return fixated


# Apply fixated content to payload — replaces sys[2] text, msg[0] rules block; updates active_plugins fixation if changed
def _apply_fixation(payload: dict, modifications: list, fixated: dict) -> dict:
    if not fixated:
        return payload
    result = payload
    if "sys2_text" in fixated:
        system = result.get("system", [])
        if isinstance(system, list) and len(system) > 2:
            block2 = system[2]
            if isinstance(block2, dict) and block2.get("type") == "text":
                new_system = list(system)
                new_system[2] = {**block2, "text": fixated["sys2_text"]}
                result = {**result, "system": new_system}
    if "injected_project_rules" in modifications:
        msgs = result.get("messages", [])
        if msgs:
            content = msgs[0].get("content", "")
            if isinstance(content, list) and content and "msg0_pr_block" in fixated:
                first_block = content[0]
                if isinstance(first_block, dict) and first_block.get("type") == "text":
                    new_content = [{**first_block, "text": fixated["msg0_pr_block"]}] + list(content[1:])
                    new_msgs = list(msgs)
                    new_msgs[0] = {**msgs[0], "content": new_content}
                    result = {**result, "messages": new_msgs}
            elif isinstance(content, str) and "msg0_pr_block_str" in fixated:
                end_tag = "</system-reminder>"
                idx = content.find(end_tag)
                if idx != -1:
                    old_prefix_end = idx + len(end_tag)
                    new_content_str = fixated["msg0_pr_block_str"] + content[old_prefix_end:]
                    new_msgs = list(msgs)
                    new_msgs[0] = {**msgs[0], "content": new_content_str}
                    result = {**result, "messages": new_msgs}
    if "active_plugins" in fixated:
        project_path = os.environ.get("PROXY_PROJECT_PATH", "")
        current_plugins = _load_active_plugins(project_path)
        if current_plugins != fixated["active_plugins"]:
            fixated["active_plugins"] = current_plugins
            modifications.append("active_plugins_changed")
    return result
