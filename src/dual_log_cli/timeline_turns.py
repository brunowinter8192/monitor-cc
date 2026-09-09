# INFRASTRUCTURE
from ..proxy.message_summary import _summarize_message

PREVIEW_CHARS = 100


# FUNCTIONS


# One-line preview: first non-empty line of the text, whitespace-collapsed and truncated
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


# Display label for one content block
def _block_label(block: dict) -> str:
    btype = block.get("type", "text")
    if btype == "tool_use":
        return f"tool_use[{block.get('preview', '') or '?'}]"
    if btype == "tool_result" and block.get("is_error"):
        return "tool_result!err"
    return btype


# Preview text for one content block — tool_use shows its input, not just the tool name
def _block_preview(block: dict) -> str:
    full = block.get("full_text", "") or ""
    if block.get("type") == "tool_use":
        _, _, input_json = full.partition("\n")
        return _preview(input_json or full)
    return _preview(full)


# Compact rows for every message of a payload. full_text is dropped here — only the msgs of the
# expand window are re-summarized for their content dump, so peak memory stays near the parsed
# payload.
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
            # str content (CC delivers role='system' messages that way) — no block list exists
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


# Stream every block of every message as {turn, role, block_types, block, label, text, chars}.
# `block_types` is every block type the MESSAGE carries, so a caller can apply a block-level
# --only to whole messages without re-summarizing them. `chars` is the same original-payload chars
# value `build_turns`/`full_turn` read off the block (`block.get("chars", 0)`, or `summary["chars"]`
# for the no-blocks pseudo-block) — search reports it unchanged, never re-measuring `text`. A
# generator, so a 14 MB payload is never doubled by holding all full_text values at once —
# build_turns drops them for exactly the same reason.
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


# Full content of one turn: [(label, chars, full_text), ...]
def full_turn(payload: dict, turn_index: int) -> list:
    messages = payload.get("messages", []) or []
    if turn_index < 0 or turn_index >= len(messages):
        return []
    summary = _summarize_message(messages[turn_index])
    blocks = summary.get("blocks", [])
    if not blocks:
        return [(summary.get("type", "text"), summary.get("chars", 0), summary.get("content_preview", ""))]
    return [(_block_label(b), b.get("chars", 0), b.get("full_text", "") or "") for b in blocks]
