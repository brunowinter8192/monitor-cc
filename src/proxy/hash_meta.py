# INFRASTRUCTURE
import hashlib
import json
from typing import Optional

from .message_summary import _has_cache_control

# FUNCTIONS

# Compute MD5[:10] hashes for each system block
def _compute_sys_block_hashes(system) -> list:
    if not isinstance(system, list):
        return []
    return [hashlib.md5(json.dumps(b).encode("utf-8")).hexdigest()[:10] for b in system]


# Compute MD5[:10] hashes for each tool
def _compute_tool_hashes(tools: list) -> list:
    return [hashlib.md5(json.dumps(t).encode("utf-8")).hexdigest()[:10] for t in tools]


# Compute per-message hashes: first 10 individually, middle as rolling summary, last 5 individually
def _compute_msg_hashes(messages: list) -> list:
    def _mhash(msg: dict) -> str:
        return hashlib.md5(json.dumps(msg).encode("utf-8")).hexdigest()[:10]

    n = len(messages)
    if n == 0:
        return []
    first_count = min(10, n)
    last_count = min(5, n)
    middle_start = first_count
    middle_end = max(first_count, n - last_count)
    last_start = middle_end

    result = []
    for i in range(first_count):
        result.append({"idx": i, "role": messages[i].get("role", ""), "hash": _mhash(messages[i])})

    chunk_size = 5
    for chunk_start in range(middle_start, middle_end, chunk_size):
        chunk_end = min(chunk_start + chunk_size, middle_end)
        chunk_hashes = [_mhash(messages[i]) for i in range(chunk_start, chunk_end)]
        rolling = hashlib.md5("".join(chunk_hashes).encode("utf-8")).hexdigest()[:10]
        count = chunk_end - chunk_start
        result.append({
            "idx": f"{chunk_start}-{chunk_end - 1}",
            "role": "middle_chunk",
            "hash": f"count={count},rolling={rolling}",
        })

    for i in range(last_start, n):
        result.append({"idx": i, "role": messages[i].get("role", ""), "hash": _mhash(messages[i])})

    return result


# Compute per-block hashes for messages[0].content
def _compute_msg0_block_hashes(messages: list) -> list:
    if not messages:
        return []
    content = messages[0].get("content", "")
    if isinstance(content, str):
        return [hashlib.md5(content.encode("utf-8")).hexdigest()[:10]]
    if isinstance(content, list):
        return [hashlib.md5(json.dumps(b).encode("utf-8")).hexdigest()[:10] for b in content]
    return []


# Compare current hash fields against previous — detect unexpected drift in stable prefix fields
def _compute_drift_report(curr: dict, prev: Optional[dict]) -> dict:
    if prev is None:
        return {"initial": True}

    report: dict = {"sys": [], "tools": [], "msgs": [], "msg0_blocks": []}

    curr_sys = curr.get("sys_block_hashes", [])
    prev_sys = prev.get("sys_block_hashes", [])
    for i in range(min(len(curr_sys), len(prev_sys))):
        if curr_sys[i] != prev_sys[i]:
            report["sys"].append(i)

    curr_tools = curr.get("tool_hashes", [])
    prev_tools = prev.get("tool_hashes", [])
    for i in range(min(len(curr_tools), len(prev_tools))):
        if curr_tools[i] != prev_tools[i]:
            report["tools"].append(i)

    curr_msgs = curr.get("msg_hashes", [])
    prev_msgs = prev.get("msg_hashes", [])
    total_curr = 0
    for e in curr_msgs:
        idx = e.get("idx")
        if isinstance(idx, str) and "-" in idx:
            parts = idx.split("-")
            try:
                total_curr += int(parts[1]) - int(parts[0]) + 1
            except (ValueError, IndexError):
                total_curr += 1
        else:
            total_curr += 1
    stable_threshold = max(0, total_curr - 2)
    for ec, ep in zip(curr_msgs, prev_msgs):
        c_idx = ec.get("idx")
        p_idx = ep.get("idx")
        if c_idx != p_idx:
            break
        if isinstance(c_idx, str) and "-" in c_idx:
            if ec.get("hash") != ep.get("hash"):
                report["msgs"].append(c_idx)
            continue
        if isinstance(c_idx, int) and c_idx >= stable_threshold:
            continue
        if ec.get("hash") != ep.get("hash"):
            report["msgs"].append(c_idx)

    curr_m0 = curr.get("msg0_block_hashes", [])
    prev_m0 = prev.get("msg0_block_hashes", [])
    for i in range(min(len(curr_m0), len(prev_m0))):
        if curr_m0[i] != prev_m0[i]:
            report["msg0_blocks"].append(i)

    return report


# Build sent_meta entry from the final modified payload — logs what was actually sent to the API
def _build_sent_meta(payload: dict, request_id: str, timestamp: str, prev_hashes: Optional[dict] = None) -> dict:
    tools = payload.get("tools", []) or []
    system = payload.get("system", []) or []
    messages = payload.get("messages", []) or []
    tool_names = sorted(t.get("name", "") for t in tools if isinstance(t, dict))

    sys_bps = [i for i, b in enumerate(system) if isinstance(b, dict) and b.get("cache_control")]
    tool_bps = [i for i, t in enumerate(tools) if isinstance(t, dict) and t.get("cache_control")]
    msg_bps = [i for i, m in enumerate(messages) if _has_cache_control(m)]

    bp1_idx = sys_bps[0] if sys_bps else None
    bp2_idx = tool_bps[0] if tool_bps else None
    bp3_idx = msg_bps[0] if msg_bps else None
    bp4_idx = msg_bps[-1] if len(msg_bps) >= 2 else None

    def _md5(data: str) -> str:
        return hashlib.md5(data.encode("utf-8")).hexdigest()[:10]

    prefix_hash_bp1 = _md5(json.dumps(system[0:bp1_idx + 1])) if bp1_idx is not None else None
    prefix_hash_bp2 = _md5(json.dumps({"system": system, "tools": tools[0:bp2_idx + 1]})) if bp2_idx is not None else None
    prefix_hash_bp3 = _md5(json.dumps({"system": system, "tools": tools, "messages": messages[0:bp3_idx + 1]})) if bp3_idx is not None else None
    prefix_hash_bp4 = _md5(json.dumps({"system": system, "tools": tools, "messages": messages[0:bp4_idx + 1]})) if bp4_idx is not None else None

    sys_block_hashes = _compute_sys_block_hashes(system)
    tool_hashes = _compute_tool_hashes(tools)
    msg_hashes = _compute_msg_hashes(messages)
    msg0_block_hashes = _compute_msg0_block_hashes(messages)

    curr_hashes = {
        "sys_block_hashes": sys_block_hashes,
        "tool_hashes": tool_hashes,
        "msg_hashes": msg_hashes,
        "msg0_block_hashes": msg0_block_hashes,
    }
    drift_report = _compute_drift_report(curr_hashes, prev_hashes)

    return {
        "type": "sent_meta",
        "request_id": request_id,
        "timestamp": timestamp,
        "sent_tools_count": len(tools),
        "sent_tools_hash": hashlib.md5(json.dumps(tool_names).encode()).hexdigest()[:8],
        "sent_cache_breakpoints": {
            "system": sys_bps,
            "tools": tool_bps,
            "messages": msg_bps,
        },
        "sent_system_hash": hashlib.md5(json.dumps(system).encode()).hexdigest()[:8],
        "sent_tools_bytes_hash": hashlib.md5(json.dumps(tools).encode()).hexdigest()[:8],
        "prefix_hash_bp1_sys": prefix_hash_bp1,
        "prefix_hash_bp2_tools": prefix_hash_bp2,
        "prefix_hash_bp3_msg": prefix_hash_bp3,
        "prefix_hash_bp4_msg": prefix_hash_bp4,
        "sys_block_hashes": sys_block_hashes,
        "tool_hashes": tool_hashes,
        "msg_hashes": msg_hashes,
        "msg0_block_hashes": msg0_block_hashes,
        "drift_report": drift_report,
    }
