# INFRASTRUCTURE
import json
import re

FLOW_ID_PEEK_RE = re.compile(r'"flow_id":\s*"([^"]*)"')
FLOW_ID_PEEK_CHARS = 300
REBUILD_CR_RATIO_THRESHOLD = 0.2  # matches 03_cache_rebuild_context.py REBUILD_THRESHOLD

# FUNCTIONS

def infer_model_family(model):
    m = model.lower()
    if "haiku" in m:
        return "haiku"
    if "sonnet" in m:
        return "sonnet"
    return "opus"

def load_ground_truth(session_path):
    groups = []
    last_tuple = None
    with open(session_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("type") != "assistant":
                continue
            msg = d.get("message", {})
            usage = msg.get("usage", {})
            if not usage:
                continue
            cr = usage.get("cache_read_input_tokens", 0) or 0
            cc = usage.get("cache_creation_input_tokens", 0) or 0
            inp = usage.get("input_tokens", 0) or 0
            out = usage.get("output_tokens", 0) or 0
            model = msg.get("model", "")
            tup = (cr, cc, inp, out)
            if tup == last_tuple:
                continue
            groups.append({
                "cr": cr, "cc": cc, "d": inp, "out": out,
                "model": model, "timestamp": d.get("timestamp", ""),
            })
            last_tuple = tup

    opus_groups = [g for g in groups if infer_model_family(g["model"]) == "opus"]
    for i, g in enumerate(opus_groups):
        g["req"] = i + 1
    return opus_groups

def dict_to_list(delta, count):
    lst = [None] * count
    for k, v in delta.items():
        i = int(k)
        if i < count:
            lst[i] = v
    return lst

def apply_delta(prev, delta, count):
    lst = list(prev)
    for k, v in delta.items():
        i = int(k)
        while len(lst) <= i:
            lst.append(None)
        lst[i] = v
    if len(lst) > count:
        lst = lst[:count]
    elif len(lst) < count:
        lst.extend([None] * (count - len(lst)))
    return lst

def load_forwarded_opus_states(fwd_path):
    acc = {"system": [], "tools": [], "messages": []}
    first_done = False
    states = []
    with open(fwd_path) as f:
        for line_idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("type") != "forwarded_delta":
                continue
            if infer_model_family(d.get("model", "")) != "opus":
                continue
            counts = d.get("counts", {})
            sc, tc, mc = counts.get("system", 0), counts.get("tools", 0), counts.get("messages", 0)
            if d.get("is_first") or not first_done:
                acc = {
                    "system": dict_to_list(d.get("system_delta") or {}, sc),
                    "tools": dict_to_list(d.get("tools_delta") or {}, tc),
                    "messages": dict_to_list(d.get("messages_delta") or {}, mc),
                }
                first_done = True
            else:
                acc = {
                    "system": apply_delta(acc["system"], d.get("system_delta") or {}, sc),
                    "tools": apply_delta(acc["tools"], d.get("tools_delta") or {}, tc),
                    "messages": apply_delta(acc["messages"], d.get("messages_delta") or {}, mc),
                }
            states.append({
                "fwd_line_idx": line_idx,
                "timestamp": d.get("timestamp", ""),
                "flow_id": d.get("flow_id", ""),
                "system": list(acc["system"]),
                "tools": list(acc["tools"]),
                "messages": list(acc["messages"]),
            })
    return states

def peek_flow_id(raw_line):
    m = FLOW_ID_PEEK_RE.search(raw_line[:FLOW_ID_PEEK_CHARS])
    return m.group(1) if m else None

def collect_target_flow_ids(mapped, pairs):
    by_req = {m["req"]: m for m in mapped}
    flow_ids = set()
    for p1, p2 in pairs:
        flow_ids.add(by_req[p1]["state"]["flow_id"])
        flow_ids.add(by_req[p2]["state"]["flow_id"])
    return {f for f in flow_ids if f}

def load_original_payloads(original_path, target_flow_ids):
    found = {}
    remaining = set(target_flow_ids)
    if not remaining:
        return found
    with open(original_path) as f:
        for raw_line in f:
            if not remaining:
                break
            fid = peek_flow_id(raw_line)
            if fid is None or fid not in remaining:
                continue
            d = json.loads(raw_line)
            payload = d.get("payload", {})
            found[fid] = {
                "system": payload.get("system", []) or [],
                "tools": payload.get("tools", []) or [],
                "messages": payload.get("messages", []) or [],
            }
            remaining.discard(fid)
    return found

def map_requests_to_fwd_states(ground_truth, fwd_states):
    fi = 0
    mapped = []
    n_fwd = len(fwd_states)
    for g in ground_truth:
        gts = g["timestamp"]
        best = None
        while fi < n_fwd and fwd_states[fi]["timestamp"] <= gts:
            best = fwd_states[fi]
            fi += 1
        mapped.append({**g, "state": best})
    unmatched_gt = sum(1 for m in mapped if m["state"] is None)
    leftover_fwd = n_fwd - fi
    notes = {
        "opus_fwd_entries": n_fwd,
        "opus_gt_groups": len(ground_truth),
        "unmatched_ground_truth": unmatched_gt,
        "unconsumed_forwarded_entries": leftover_fwd,
    }
    return mapped, notes

def detect_cr_collapse_points(mapped):
    collapse = []
    prev_max_cr = 0
    for m in mapped:
        cr, cc = m["cr"], m["cc"]
        if prev_max_cr > 0 and cc > cr and cr < prev_max_cr * REBUILD_CR_RATIO_THRESHOLD:
            collapse.append(m["req"])
        prev_max_cr = max(prev_max_cr, cr)
    return collapse

def build_range_pairs(range_str):
    a, b = (int(x) for x in range_str.split("-"))
    return [(r, r + 1) for r in range(a, b)]

def pair_available(mapped, req_prev, req_curr):
    by_req = {m["req"]: m for m in mapped}
    p, c = by_req.get(req_prev), by_req.get(req_curr)
    return p is not None and c is not None and p["state"] is not None and c["state"] is not None
