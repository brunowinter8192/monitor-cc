# INFRASTRUCTURE
import json

from .strip_bg_completed import _WAKEUP_TEXT

# FUNCTIONS

# Append _WAKEUP_TEXT to content (str or list) as wake-up hint for failed bg-task signals
def _append_wakeup_text_to_content(content):
    if isinstance(content, str):
        sep = '' if not content or content.endswith('\n') else '\n'
        return content + sep + _WAKEUP_TEXT
    if isinstance(content, list):
        return list(content) + [{'type': 'text', 'text': _WAKEUP_TEXT}]
    return content


# Minimal (offset, removed, injected) op from (before, after) text pair via common-prefix/suffix
def _extract_block_op(before: str, after: str) -> list:
    if before == after:
        return []
    p = 0
    while p < len(before) and p < len(after) and before[p] == after[p]:
        p += 1
    s = 0
    max_s = min(len(before) - p, len(after) - p)
    while s < max_s and before[-(s + 1)] == after[-(s + 1)]:
        s += 1
    removed  = before[p: (len(before) - s) if s else len(before)]
    injected = after[p:  (len(after)  - s) if s else len(after)]
    return [(p, removed, injected)]


# Extract plain text from a single content block for op recording
def _block_inner_text(block) -> str:
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        if "text" in block:
            return str(block["text"])
        if block.get("type") == "tool_result":
            c = block.get("content", "")
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                return "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and "text" in b)
        return json.dumps(block, ensure_ascii=False)
    return json.dumps(block, ensure_ascii=False)


# Per-block ops {blk_idx: [(offset, removed, injected)]} from a content change — used by op-recording passes
def _ops_from_content_change(old_content, new_content) -> dict:
    ops: dict = {}
    if isinstance(old_content, list) and isinstance(new_content, list):
        for bi in range(max(len(old_content), len(new_content))):
            bt = _block_inner_text(old_content[bi]) if bi < len(old_content) else ""
            at = _block_inner_text(new_content[bi]) if bi < len(new_content) else ""
            for op in _extract_block_op(bt, at):
                ops.setdefault(bi, []).append(op)
    elif isinstance(old_content, str) and isinstance(new_content, str):
        for op in _extract_block_op(old_content, new_content):
            ops.setdefault(0, []).append(op)
    return ops


# Merge per-block ops from one pass into the accumulated ops dict
def _merge_ops(dst: dict, src: dict) -> None:
    for msg_idx, blk_map in src.items():
        for blk_idx, op_list in blk_map.items():
            dst.setdefault(msg_idx, {}).setdefault(blk_idx, []).extend(op_list)
