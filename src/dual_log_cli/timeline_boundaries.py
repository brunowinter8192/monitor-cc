# INFRASTRUCTURE
import json
from pathlib import Path

from ..proxy.logging import _delta_hash
from .reader import infer_family, iter_jsonl

_BILLING_HEADER_SYS_INDEX = 0


# FUNCTIONS


def _system_block_chars(block) -> int:
    if isinstance(block, dict):
        return len(block.get("text", "") or "")
    return len(str(block))


def _tool_chars(tool) -> int:
    return len(json.dumps(tool))


def _sys_lines(delta: dict, hash_by_index: dict, is_first: bool) -> list:
    lines = []
    for key in sorted(delta, key=int):
        index = int(key)
        if index == _BILLING_HEADER_SYS_INDEX and not is_first:
            continue
        element = delta[key]
        content_hash = _delta_hash(element)
        if is_first:
            tag = None
        else:
            prev_hash = hash_by_index.get(index)
            if prev_hash == content_hash:
                continue
            tag = "changed" if index in hash_by_index else "new"
        hash_by_index[index] = content_hash
        lines.append({"label": f"sys[{index}]", "chars": _system_block_chars(element), "tag": tag})
    return lines


def _tool_lines(delta: dict, tools_count: int, name_by_index: dict, hash_by_name: dict, is_first: bool) -> list:
    if is_first:
        lines = []
        for key in sorted(delta, key=int):
            element = delta[key]
            name = element.get("name", "?") if isinstance(element, dict) else "?"
            name_by_index[int(key)] = name
            hash_by_name[name] = _delta_hash(element)
            lines.append({"label": f"tool[{name}]", "chars": _tool_chars(element), "tag": None})
        return lines

    old_names = set(name_by_index.values())
    old_index_by_name = {name: index for index, name in name_by_index.items()}
    touched = {int(key): delta[key] for key in delta}

    new_name_by_index = {}
    for index in range(tools_count):
        if index in touched:
            element = touched[index]
            new_name_by_index[index] = element.get("name", "?") if isinstance(element, dict) else "?"
        elif index in name_by_index:
            new_name_by_index[index] = name_by_index[index]
    removed_names = old_names - set(new_name_by_index.values())

    lines = []
    for index in sorted(touched):
        element = touched[index]
        name = element.get("name", "?") if isinstance(element, dict) else "?"
        content_hash = _delta_hash(element)
        if name in old_names and hash_by_name.get(name) == content_hash:
            hash_by_name[name] = content_hash
            continue
        tag = "changed" if name in old_names else "new"
        hash_by_name[name] = content_hash
        lines.append({"label": f"tool[{name}]", "chars": _tool_chars(element), "tag": tag})
    for name in sorted(removed_names, key=lambda n: old_index_by_name.get(n, tools_count)):
        lines.append({"label": f"tool[{name}]", "chars": None, "tag": "removed"})

    name_by_index.clear()
    name_by_index.update(new_name_by_index)
    return lines


def _is_sidecar(counts: dict) -> bool:
    return counts.get("tools", 0) == 0


def request_boundaries(forwarded_path: Path, family: str) -> list:
    boundaries = []
    request_no = 0
    prev_count = 0
    sys_hash_by_index: dict = {}
    tools_name_by_index: dict = {}
    tools_hash_by_name: dict = {}
    for entry in iter_jsonl(forwarded_path):
        if entry.get("type") != "forwarded_delta":
            continue
        if infer_family(entry.get("model", "")) != family:
            continue
        counts = entry.get("counts", {}) or {}
        if _is_sidecar(counts):
            continue
        request_no += 1
        count = counts.get("messages", 0)
        restart = count < prev_count
        is_first = bool(entry.get("is_first", False))
        boundaries.append({
            "request_no": request_no,
            "flow_id": entry.get("flow_id", ""),
            "timestamp": entry.get("timestamp", ""),
            "model": entry.get("model", ""),
            "start_index": 0 if restart else prev_count,
            "message_count": count,
            "restart": restart,
            "sys_lines": _sys_lines(entry.get("system_delta") or {}, sys_hash_by_index, is_first),
            "tool_lines": _tool_lines(entry.get("tools_delta") or {}, counts.get("tools", 0),
                                       tools_name_by_index, tools_hash_by_name, is_first),
        })
        prev_count = count
    return boundaries


def build_turn_times(boundaries: list) -> dict:
    chain = boundaries
    covered = 0
    for position, boundary in enumerate(boundaries):
        if boundary["restart"]:
            chain = boundaries[position:]
            covered = boundary["message_count"]
    times = {}
    for boundary in chain:
        count = boundary["message_count"]
        if count <= covered:
            continue
        for index in range(covered, count):
            times[index] = boundary["timestamp"]
        covered = count
    return times
