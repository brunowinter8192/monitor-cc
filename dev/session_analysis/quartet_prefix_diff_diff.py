# INFRASTRUCTURE
import json

import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")

# FUNCTIONS

def diff_system_block(prev_blk, curr_blk):
    prev_txt = (prev_blk or {}).get("text", "")
    curr_txt = (curr_blk or {}).get("text", "")
    return {
        "changed": prev_txt != curr_txt,
        "prev_chars": len(prev_txt), "curr_chars": len(curr_txt),
        "delta_chars": len(curr_txt) - len(prev_txt),
    }

def block_type_counts(msg):
    content = (msg or {}).get("content", "")
    if not isinstance(content, list):
        return {}
    counts = {}
    for b in content:
        if not isinstance(b, dict):
            continue
        t = b.get("type", "?")
        counts[t] = counts.get(t, 0) + 1
        if t == "tool_result":
            nested = b.get("content")
            if isinstance(nested, list):
                for nb in nested:
                    if isinstance(nb, dict):
                        nt = nb.get("type", "?")
                        counts[nt] = counts.get(nt, 0) + 1
    return counts

def normalize_content_shape(msg):
    content = (msg or {}).get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list) and len(content) == 1:
        b = content[0]
        if isinstance(b, dict) and b.get("type") == "text" and set(b.keys()) <= {"type", "text", "cache_control"}:
            return b.get("text", "")
    return None

def classify_message_change(prev, curr):
    prev_types, curr_types = block_type_counts(prev), block_type_counts(curr)
    prev_img, curr_img = prev_types.get("image", 0), curr_types.get("image", 0)
    if curr_img < prev_img:
        return f"image(s) evicted: {prev_img - curr_img} removed (incl. nested tool_result images)"
    if prev.get("role") == curr.get("role"):
        norm_prev, norm_curr = normalize_content_shape(prev), normalize_content_shape(curr)
        if norm_prev is not None and norm_prev == norm_curr:
            return "format normalization only (list-of-one-text-block <-> bare string, same text)"
    return "content modified (non-image)"

def _diff_common_message_rows(prev_msgs, curr_msgs, n_common):
    rows = []
    first_diff = None
    for i in range(n_common):
        p, c = prev_msgs[i], curr_msgs[i]
        p_json = json.dumps(p, sort_keys=True) if p else ""
        c_json = json.dumps(c, sort_keys=True) if c else ""
        if p_json == c_json:
            continue
        if first_diff is None:
            first_diff = i
        p_types, c_types = block_type_counts(p), block_type_counts(c)
        rows.append({
            "idx": i, "status": "modified",
            "prev_chars": len(p_json), "curr_chars": len(c_json),
            "delta_chars": len(c_json) - len(p_json),
            "prev_image_count": p_types.get("image", 0), "curr_image_count": c_types.get("image", 0),
            "prev_types": p_types, "curr_types": c_types,
            "note": classify_message_change(p, c),
        })
    return rows, first_diff

def _diff_added_removed_message_rows(prev_msgs, curr_msgs, n_common, first_diff):
    n_prev, n_curr = len(prev_msgs), len(curr_msgs)
    rows = []
    for i in range(n_common, n_curr):
        if first_diff is None:
            first_diff = i
        c = curr_msgs[i]
        c_json = json.dumps(c, sort_keys=True) if c else ""
        c_types = block_type_counts(c)
        rows.append({
            "idx": i, "status": "added",
            "prev_chars": 0, "curr_chars": len(c_json), "delta_chars": len(c_json),
            "prev_image_count": 0, "curr_image_count": c_types.get("image", 0),
            "prev_types": {}, "curr_types": c_types, "note": "-",
        })
    for i in range(n_common, n_prev):
        if first_diff is None:
            first_diff = i
        p = prev_msgs[i]
        p_json = json.dumps(p, sort_keys=True) if p else ""
        p_types = block_type_counts(p)
        rows.append({
            "idx": i, "status": "removed",
            "prev_chars": len(p_json), "curr_chars": 0, "delta_chars": -len(p_json),
            "prev_image_count": p_types.get("image", 0), "curr_image_count": 0,
            "prev_types": p_types, "curr_types": {}, "note": "-",
        })
    return rows, first_diff

def diff_messages(prev_msgs, curr_msgs):
    n_common = min(len(prev_msgs), len(curr_msgs))
    rows, first_diff = _diff_common_message_rows(prev_msgs, curr_msgs, n_common)
    more_rows, first_diff = _diff_added_removed_message_rows(prev_msgs, curr_msgs, n_common, first_diff)
    rows.extend(more_rows)
    rows.sort(key=lambda r: r["idx"])
    return rows, first_diff

def diff_original_vs_forwarded(msg_rows, flow_id_prev, flow_id_curr, orig_by_flow):
    orig_prev = orig_by_flow.get(flow_id_prev)
    orig_curr = orig_by_flow.get(flow_id_curr)
    if orig_prev is None or orig_curr is None:
        return {"available": False, "rows": []}

    op_msgs, oc_msgs = orig_prev["messages"], orig_curr["messages"]
    rows = []
    for row in msg_rows:
        if row["status"] != "modified":
            continue
        idx = row["idx"]
        op = op_msgs[idx] if idx < len(op_msgs) else None
        oc = oc_msgs[idx] if idx < len(oc_msgs) else None
        if op is None or oc is None:
            verdict = "INCONCLUSIVE (index out of range in original — structural drift vs forwarded)"
            op_chars = len(json.dumps(op, sort_keys=True)) if op else 0
            oc_chars = len(json.dumps(oc, sort_keys=True)) if oc else 0
        else:
            op_json = json.dumps(op, sort_keys=True)
            oc_json = json.dumps(oc, sort_keys=True)
            op_chars, oc_chars = len(op_json), len(oc_json)
            if op_json == oc_json:
                verdict = "PROXY-SIDE (original identical prev->curr at this index — forwarded diff is ours)"
            elif oc_chars < op_chars and row["delta_chars"] < 0:
                verdict = "CLIENT-SIDE (original already shrinks prev->curr at this index)"
            else:
                verdict = f"AMBIGUOUS (original prev={op_chars:,} curr={oc_chars:,} chars)"
        rows.append({
            "idx": idx, "orig_prev_chars": op_chars, "orig_curr_chars": oc_chars, "verdict": verdict,
        })
    return {"available": True, "rows": rows}

def reconcile(p_state, gt_prev, gt_curr):
    bp1_json = json.dumps(p_state["system"][:3], ensure_ascii=False)
    bp1_tokens = len(ENC.encode(bp1_json))
    tools_json = json.dumps(p_state["tools"], ensure_ascii=False)
    tools_tokens = len(ENC.encode(tools_json))
    recovery_match = gt_curr["cr"] == gt_prev["cr"] + gt_prev["cc"]
    return {
        "bp1_estimate_tokens": bp1_tokens,
        "bp1_plus_tools_estimate_tokens": bp1_tokens + tools_tokens,
        "actual_cr_curr": gt_curr["cr"],
        "recovery_identity_holds": recovery_match,
        "recovery_lhs": gt_curr["cr"], "recovery_rhs": gt_prev["cr"] + gt_prev["cc"],
    }

def _diff_order_and_first_divergence(n_sys, sys_rows, tools_changed, msg_rows):
    order = []
    for i in range(n_sys):
        order.append(("system", i, sys_rows[i]["changed"]))
    order.append(("tools", None, tools_changed))
    for r in msg_rows:
        order.append(("messages", r["idx"], True))
    first_diverge_any = next(((seg, idx) for seg, idx, ch in order if ch), (None, None))
    first_diverge_no_sys0 = next(
        ((seg, idx) for seg, idx, ch in order if ch and not (seg == "system" and idx == 0)),
        (None, None),
    )
    return first_diverge_any, first_diverge_no_sys0

def analyze_pair(mapped, req_prev, req_curr, orig_by_flow=None):
    by_req = {m["req"]: m for m in mapped}
    p, c = by_req[req_prev], by_req[req_curr]
    p_state, c_state = p["state"], c["state"]

    sys_rows = []
    n_sys = max(len(p_state["system"]), len(c_state["system"]))
    for i in range(n_sys):
        pb = p_state["system"][i] if i < len(p_state["system"]) else None
        cb = c_state["system"][i] if i < len(c_state["system"]) else None
        sys_rows.append({"idx": i, **diff_system_block(pb, cb)})

    tools_prev_json = json.dumps(p_state["tools"], sort_keys=True)
    tools_curr_json = json.dumps(c_state["tools"], sort_keys=True)
    tools_changed = tools_prev_json != tools_curr_json
    tools_names_prev = [t.get("name", "") for t in p_state["tools"] if isinstance(t, dict)]
    tools_names_curr = [t.get("name", "") for t in c_state["tools"] if isinstance(t, dict)]

    msg_rows, first_msg_diff = diff_messages(p_state["messages"], c_state["messages"])

    first_diverge_any, first_diverge_no_sys0 = _diff_order_and_first_divergence(
        n_sys, sys_rows, tools_changed, msg_rows,
    )

    reconciliation = reconcile(p_state, p, c)
    original_attribution = None
    if orig_by_flow is not None:
        original_attribution = diff_original_vs_forwarded(
            msg_rows, p_state["flow_id"], c_state["flow_id"], orig_by_flow,
        )

    return {
        "req_prev": req_prev, "req_curr": req_curr,
        "gt_prev": p, "gt_curr": c,
        "sys_rows": sys_rows,
        "tools_changed": tools_changed,
        "tools_names_prev": tools_names_prev, "tools_names_curr": tools_names_curr,
        "msg_rows": msg_rows, "first_msg_diff": first_msg_diff,
        "n_msg_prev": len(p_state["messages"]), "n_msg_curr": len(c_state["messages"]),
        "first_diverge_any": first_diverge_any, "first_diverge_no_sys0": first_diverge_no_sys0,
        "reconciliation": reconciliation,
        "original_attribution": original_attribution,
    }
