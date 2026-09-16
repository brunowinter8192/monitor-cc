# INFRASTRUCTURE
import json

# FUNCTIONS

def _strip_cache_control(obj):
    if isinstance(obj, dict):
        return {k: _strip_cache_control(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [_strip_cache_control(item) for item in obj]
    return obj


def _block_text(block) -> str:
    if block is None:
        return ""
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        t = block.get("text")
        if t is not None:
            return str(t)
        return json.dumps(block, ensure_ascii=False)
    return json.dumps(block, ensure_ascii=False)


def _find_sys2_block(matched: list, diff_text) -> dict:
    for req_num, (oe, _, fs) in enumerate(matched, 1):
        o_sys = [b for b in (oe.get("payload", {}).get("system", []) or []) if isinstance(b, dict)]
        f_sys = [b for b in (fs.get("system", []) or []) if isinstance(b, dict)]
        if len(o_sys) <= 2 or len(f_sys) <= 2:
            continue
        o_text = _block_text(_strip_cache_control(o_sys[2]))
        f_text = _block_text(_strip_cache_control(f_sys[2]))
        if len(o_text) < 1000 or len(f_text) < 10000:
            continue
        spans = diff_text(o_text, f_text)
        if any(t == "stripped" for t, _ in spans) and any(t == "injected" for t, _ in spans):
            return {
                "label": "B1 — sys[2] full-replace",
                "req_num": req_num, "loc": "sys[2]",
                "orig_norm_text": o_text,
                "fwd_norm_text": f_text,
                "fwd_raw_text": _block_text(f_sys[2]),
                "spans": spans,
            }
    return None


def _find_sys3_block(matched: list, diff_text) -> dict:
    for req_num, (oe, _, fs) in enumerate(matched, 1):
        o_sys = [b for b in (oe.get("payload", {}).get("system", []) or []) if isinstance(b, dict)]
        f_sys = [b for b in (fs.get("system", []) or []) if isinstance(b, dict)]
        if len(o_sys) <= 3 or len(f_sys) <= 3:
            continue
        o_text = _block_text(_strip_cache_control(o_sys[3]))
        f_text = _block_text(_strip_cache_control(f_sys[3]))
        if len(o_text) < 1000 or len(f_text) > 5:
            continue
        spans = diff_text(o_text, f_text)
        if any(t == "stripped" for t, _ in spans):
            return {
                "label": "B2 — sys[3] strip-to-dot",
                "req_num": req_num, "loc": "sys[3]",
                "orig_norm_text": o_text,
                "fwd_norm_text": f_text,
                "fwd_raw_text": _block_text(f_sys[3]),
                "spans": spans,
            }
    return None


def _find_msg_wordlevel_block(matched: list, diff_text) -> dict:
    for req_num, (oe, _, fs) in enumerate(matched, 1):
        o_msgs = oe.get("payload", {}).get("messages", []) or []
        f_msgs = fs.get("messages", []) or []
        for midx in range(min(len(o_msgs), len(f_msgs))):
            om = o_msgs[midx]
            fm = f_msgs[midx]
            if not (om and fm):
                continue
            o_content = om.get("content", "")
            f_content = fm.get("content", "")
            if not (isinstance(o_content, list) and isinstance(f_content, list)):
                continue
            for bidx in range(min(len(o_content), len(f_content))):
                ob_raw = o_content[bidx]
                fb_raw = f_content[bidx]
                f_text = _block_text(_strip_cache_control(fb_raw))
                fb_raw_text = _block_text(fb_raw)
                if fb_raw_text == f_text:
                    continue
                o_text = _block_text(_strip_cache_control(ob_raw))
                spans = diff_text(o_text, f_text)
                n_eq = sum(1 for t, _ in spans if t == "equal")
                has_s = any(t == "stripped" for t, _ in spans)
                has_i = any(t == "injected" for t, _ in spans)
                if n_eq >= 1 and has_s and has_i:
                    return {
                        "label": f"B3 — msg[{midx}][{bidx}] word-level mixed",
                        "req_num": req_num, "loc": f"msg[{midx}][{bidx}]",
                        "orig_norm_text": o_text,
                        "fwd_norm_text": f_text,
                        "fwd_raw_text": fb_raw_text,
                        "spans": spans,
                        "has_cc_diff": True,
                    }
    return None
