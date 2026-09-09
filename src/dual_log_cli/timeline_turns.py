# INFRASTRUCTURE
from ..proxy.message_summary import _summarize_message

PREVIEW_CHARS = 100


# FUNCTIONS


def _preview(text: str, limit: int = PREVIEW_CHARS) -> str:
    if not text:
        return ""
    line = ""
    for candidate in text.split("\n"):
        if candidate.strip():
            line = " ".join(candidate.split())
            break
    if not line:
        line = " ".join(text.split())
    return line[:limit] + ("…" if len(line) > limit else "")


def _block_label(block: dict) -> str:
    btype = block.get("type", "text")
    if btype == "tool_use":
        return f"tool_use[{block.get('preview', '') or '?'}]"
    if btype == "tool_result" and block.get("is_error"):
        return "tool_result!err"
    return btype


def _block_preview(block: dict) -> str:
    full = block.get("full_text", "") or ""
    if block.get("type") == "tool_use":
        _, _, input_json = full.partition("\n")
        return _preview(input_json or full)
    return _preview(full)


def build_turns(payload: dict) -> list:
    turns = []
    for index, message in enumerate(payload.get("messages", []) or []):
        summary = _summarize_message(message)
        blocks = [
            {
                "label": _block_label(block),
                "type": block.get("type", "text"),
                "chars": block.get("chars", 0),
                "sig_chars": block.get("sig_chars", 0),
                "preview": _block_preview(block),
            }
            for block in summary.get("blocks", [])
        ]
        if not blocks:
            blocks = [{
                "label": summary.get("type", "text"),
                "type": summary.get("type", "text"),
                "chars": summary.get("chars", 0),
                "sig_chars": 0,
                "preview": _preview(summary.get("content_preview", "")),
            }]
        turns.append({
            "index": index,
            "role": summary.get("role", "?"),
            "type": summary.get("type", "text"),
            "chars": summary.get("chars", 0),
            "blocks": blocks,
        })
    return turns


def iter_block_texts(payload: dict):
    for index, message in enumerate(payload.get("messages", []) or []):
        summary = _summarize_message(message)
        role = summary.get("role", "?")
        blocks = summary.get("blocks", [])
        if blocks:
            block_types = [b.get("type", "text") for b in blocks]
            for position, block in enumerate(blocks):
                yield {
                    "turn": index,
                    "role": role,
                    "block_types": block_types,
                    "block": position,
                    "label": _block_label(block),
                    "text": block.get("full_text", "") or "",
                    "chars": block.get("chars", 0),
                }
        else:
            yield {
                "turn": index,
                "role": role,
                "block_types": [summary.get("type", "text")],
                "block": 0,
                "label": summary.get("type", "text"),
                "text": summary.get("content_preview", "") or "",
                "chars": summary.get("chars", 0),
            }


def full_turn(payload: dict, turn_index: int) -> list:
    messages = payload.get("messages", []) or []
    if turn_index < 0 or turn_index >= len(messages):
        return []
    summary = _summarize_message(messages[turn_index])
    blocks = summary.get("blocks", [])
    if not blocks:
        return [(summary.get("type", "text"), summary.get("chars", 0), summary.get("content_preview", ""))]
    return [(_block_label(b), b.get("chars", 0), b.get("full_text", "") or "") for b in blocks]
