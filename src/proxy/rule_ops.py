# INFRASTRUCTURE
import json

# FUNCTIONS

def _extract_block_op(before: str, after: str, full_replace: bool = False) -> list:
    if before == after:
        return []
    if full_replace:
        return [(0, before, after)]
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


def _ops_from_content_change(old_content, new_content, full_replace: bool = False) -> dict:
    ops: dict = {}
    if isinstance(old_content, list) and isinstance(new_content, list):
        for bi in range(max(len(old_content), len(new_content))):
            bt = _block_inner_text(old_content[bi]) if bi < len(old_content) else ""
            at = _block_inner_text(new_content[bi]) if bi < len(new_content) else ""
            for op in _extract_block_op(bt, at, full_replace):
                ops.setdefault(bi, []).append(op)
    elif isinstance(old_content, list) and isinstance(new_content, str):
        for bi in range(len(old_content)):
            bt = _block_inner_text(old_content[bi])
            at = new_content if bi == 0 else ""
            for op in _extract_block_op(bt, at, full_replace):
                ops.setdefault(bi, []).append(op)
    elif isinstance(old_content, str) and isinstance(new_content, str):
        for op in _extract_block_op(old_content, new_content, full_replace):
            ops.setdefault(0, []).append(op)
    return ops


def _merge_ops(dst: dict, src: dict) -> None:
    for msg_idx, blk_map in src.items():
        for blk_idx, op_list in blk_map.items():
            dst.setdefault(msg_idx, {}).setdefault(blk_idx, []).extend(op_list)
