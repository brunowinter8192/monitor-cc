# INFRASTRUCTURE
import json

# FUNCTIONS

def _strip_cache_control(obj):
    if isinstance(obj, dict):
        return {k: _strip_cache_control(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [_strip_cache_control(i) for i in obj]
    return obj


def _get_inner_text(block) -> str:
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
                return "\n".join(
                    b.get("text", "") for b in c
                    if isinstance(b, dict) and "text" in b
                )
        return json.dumps(block, ensure_ascii=False)
    return json.dumps(block, ensure_ascii=False)


def _block_text(content, blk_idx: int) -> str:
    if isinstance(content, list):
        return _get_inner_text(content[blk_idx]) if blk_idx < len(content) else ""
    if isinstance(content, str):
        return content if blk_idx == 0 else ""
    if content is None:
        return ""
    return json.dumps(content) if blk_idx == 0 else ""


def extract_ops_from_pair(before: str, after: str) -> list:
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


def apply_edit_to_spans(spans: list, offset: int, removed: str, injected: str) -> list:
    if not removed and not injected:
        return spans
    rem_end = offset + len(removed)
    new_spans = []
    ck_cursor = 0
    inject_emitted = not bool(injected)

    for tag, text in spans:
        if tag == "stripped":
            new_spans.append((tag, text))
            continue
        span_start = ck_cursor
        span_end   = ck_cursor + len(text)
        ck_cursor  = span_end

        if span_end <= offset:
            new_spans.append((tag, text))
        elif span_start >= rem_end:
            if not inject_emitted:
                new_spans.append(("injected", injected))
                inject_emitted = True
            new_spans.append((tag, text))
        else:
            lo       = max(offset, span_start) - span_start
            hi       = min(rem_end, span_end)  - span_start
            prefix_t = text[:lo]
            mid_t    = text[lo:hi]
            suffix_t = text[hi:]
            if prefix_t:
                new_spans.append((tag, prefix_t))
            if mid_t and tag == "equal":
                new_spans.append(("stripped", mid_t))
            if not inject_emitted:
                new_spans.append(("injected", injected))
                inject_emitted = True
            if suffix_t:
                new_spans.append((tag, suffix_t))

    if not inject_emitted:
        new_spans.append(("injected", injected))
    return new_spans


def get_block_pairs(before_content, after_content) -> list:
    if isinstance(before_content, list) and isinstance(after_content, list):
        pairs = []
        for bi in range(max(len(before_content), len(after_content))):
            bb = before_content[bi] if bi < len(before_content) else None
            ab = after_content[bi]  if bi < len(after_content)  else None
            bt = _get_inner_text(bb) if bb is not None else ""
            at = _get_inner_text(ab) if ab is not None else ""
            if bt != at:
                pairs.append((bi, bt, at))
        return pairs
    bt = before_content if isinstance(before_content, str) else (
         "" if before_content is None else json.dumps(before_content))
    at = after_content  if isinstance(after_content,  str) else (
         "" if after_content  is None else json.dumps(after_content))
    if bt != at:
        return [(0, bt, at)]
    return []


def compose_block(c0_text: str, block_ops: list) -> list:
    spans = [("equal", c0_text)] if c0_text else []
    for _, off, rem, inj in block_ops:
        spans = apply_edit_to_spans(spans, off, rem, inj)
    return spans


def check_invariants(spans: list, c0_text: str, cfwd_text: str) -> tuple:
    recon_c0  = "".join(t for tag, t in spans if tag in ("equal", "stripped"))
    recon_fwd = "".join(t for tag, t in spans if tag in ("equal", "injected"))
    ok1 = recon_c0  == c0_text
    ok2 = recon_fwd == cfwd_text
    if ok1 and ok2:
        return True, "OK"
    details = []
    if not ok1:
        mi = next((i for i, (a, b) in enumerate(zip(recon_c0, c0_text)) if a != b),
                  min(len(recon_c0), len(c0_text)))
        details.append(f"C0_recon_FAIL got={len(recon_c0)} want={len(c0_text)} first_diff={mi}")
    if not ok2:
        mi = next((i for i, (a, b) in enumerate(zip(recon_fwd, cfwd_text)) if a != b),
                  min(len(recon_fwd), len(cfwd_text)))
        details.append(f"Cfwd_recon_FAIL got={len(recon_fwd)} want={len(cfwd_text)} first_diff={mi}")
    return False, "; ".join(details)
