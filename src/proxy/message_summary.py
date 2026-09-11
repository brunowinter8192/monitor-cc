# INFRASTRUCTURE
import json

# FUNCTIONS

def _infer_model_family(model: str) -> str:
    m = (model or "").lower()
    if "haiku" in m:
        return "haiku"
    if "sonnet" in m:
        return "sonnet"
    return "opus"


def _summarize_block(block: dict) -> dict:
    btype = block.get("type", "text")
    has_cc = bool(block.get("cache_control"))
    sig_chars = 0
    if btype == "text":
        text = block.get("text", "")
        bchars = len(text)
        bpreview = text.split('\n')[0][:60]
        bfull = text
    elif btype == "tool_use":
        name = block.get("name", "")
        bchars = len(name) + len(json.dumps(block.get("input", {})))
        bpreview = name
        bfull = name + "\n" + json.dumps(block.get("input", {}))
    elif btype == "tool_result":
        rc = block.get("content", "")
        if isinstance(rc, str):
            bchars = len(rc)
            bpreview = rc.split('\n')[0][:60]
            bfull = rc
        elif isinstance(rc, list):
            bchars = sum(len(s.get("text", "")) for s in rc if isinstance(s, dict))
            bpreview = next((s.get("text", "").split('\n')[0][:60] for s in rc if isinstance(s, dict) and s.get("text")), "")
            bfull = "\n".join(s.get("text", "") for s in rc if isinstance(s, dict) and s.get("text"))
        else:
            bchars = 0
            bpreview = ""
            bfull = ""
    elif btype == "thinking":
        thinking_text = block.get("thinking", "")
        signature = block.get("signature", "")
        bchars = len(thinking_text)
        bpreview = thinking_text.split('\n')[0][:60]
        bfull = thinking_text
        sig_chars = len(signature)
    else:
        bchars = len(json.dumps(block))
        bpreview = btype
        bfull = json.dumps(block)
    block_dict = {"type": btype, "chars": bchars, "preview": bpreview, "full_text": bfull, "has_cc": has_cc}
    if btype == "thinking":
        block_dict["sig_chars"] = sig_chars
    if btype == "tool_use":
        block_dict["id"] = block.get("id", "")
    if btype == "tool_result":
        block_dict["is_error"] = bool(block.get("is_error", False))
        block_dict["tool_use_id"] = block.get("tool_use_id", "")
    return block_dict


def _summarize_message(msg: dict) -> dict:
    role = msg.get("role", "unknown")
    content = msg.get("content", "")
    msg_type, chars, preview = _classify_content(role, content)
    blocks = []
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            blocks.append(_summarize_block(block))
    return {
        "role": role,
        "type": msg_type,
        "chars": chars,
        "has_cache_control": _has_cache_control(msg),
        "content_preview": preview if preview else "",
        "blocks": blocks,
    }


def _has_cache_control(msg: dict) -> bool:
    if msg.get("cache_control"):
        return True
    content = msg.get("content", "")
    if isinstance(content, list):
        return any(isinstance(b, dict) and b.get("cache_control") for b in content)
    return False


def _classify_content(role: str, content) -> tuple:
    if role == "system":
        if isinstance(content, str):
            return "system", len(content), content
        if isinstance(content, list):
            text = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
            return "system", len(text), text
        return "system", 0, ""

    if isinstance(content, str):
        return _classify_text(content), len(content), content

    if isinstance(content, list):
        return _classify_blocks(content)

    return "text", 0, ""


def _classify_text(text: str) -> str:
    if "<system-reminder>" in text:
        return "system-reminder"
    if "<task-notification>" in text:
        return "task-notification"
    if "<command-message>" in text:
        return "command-message"
    return "text"


def _extract_tool_result_parts(result_content) -> tuple:
    total_chars = 0
    parts = []
    if isinstance(result_content, str):
        total_chars += len(result_content)
        if result_content:
            parts.append(result_content)
    elif isinstance(result_content, list):
        for sub in result_content:
            if isinstance(sub, dict):
                t = sub.get("text", "")
                total_chars += len(t)
                if t:
                    parts.append(t)
    if not parts:
        parts.append("[tool_result]")
    return total_chars, parts


def _classify_blocks(blocks: list) -> tuple:
    total_chars = 0
    parts = []
    primary_type = "text"

    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type", "text")

        if btype == "text":
            text = block.get("text", "")
            total_chars += len(text)
            if not parts:
                classified = _classify_text(text)
                if classified != "text":
                    primary_type = classified
            parts.append(text)

        elif btype == "tool_use":
            primary_type = "tool_use"
            name = block.get("name", "")
            input_str = json.dumps(block.get("input", {}))
            total_chars += len(name) + len(input_str)
            parts.append(f"[tool_use:{name}]\n{input_str}")

        elif btype == "tool_result":
            primary_type = "tool_result"
            chars_delta, result_parts = _extract_tool_result_parts(block.get("content", ""))
            total_chars += chars_delta
            parts.extend(result_parts)

        elif btype == "thinking":
            if primary_type == "text":
                primary_type = "thinking"
            thinking_text = block.get("thinking", "")
            total_chars += len(thinking_text)
            parts.append(thinking_text)

    preview = "\n".join(parts)
    return primary_type, total_chars, preview
