# INFRASTRUCTURE
import json

from cc_injection_aggregation import _process_segment_occurrence


# FUNCTIONS

def _process_file(path, registry: dict, pending: dict, dedup_seen: dict, counters: dict,
                   max_entries, msg_dedup_seen: set) -> dict:
    n_entries = 0
    n_messages = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if max_entries is not None and n_entries >= max_entries:
                break
            entry = json.loads(line)
            n_entries += 1
            payload = entry.get("payload", {}) or {}
            tool_names = _build_tool_name_map(payload.get("messages", []) or [])
            _process_system_blocks(path, payload, dedup_seen, registry, pending, counters)
            n_messages += _process_messages(path, payload, tool_names, dedup_seen, registry, pending,
                                             counters, msg_dedup_seen)

    return {"file": path.name, "entries": n_entries, "messages": n_messages,
            "size_bytes": path.stat().st_size}


def _build_tool_name_map(messages: list) -> dict:
    m = {}
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tid, name = block.get("id"), block.get("name")
                if tid and name:
                    m[tid] = name
    return m


def _process_system_blocks(path, payload, dedup_seen, registry, pending, counters) -> None:
    for idx, block in enumerate(payload.get("system", []) or []):
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        text = block.get("text", "")
        if not text:
            continue
        key = (path.name, "system", idx, text)
        _process_segment_occurrence(key, dedup_seen, registry, pending, counters,
                                     role=None, section="system", block_type=f"system[{idx}]",
                                     text=text, tool_name=None, sys_idx=idx)


def _process_messages(path, payload, tool_names, dedup_seen, registry, pending, counters,
                       msg_dedup_seen) -> int:
    n_messages = 0
    for msg in payload.get("messages", []) or []:
        n_messages += 1
        role = msg.get("role")
        content = msg.get("content")
        counters["raw_messages"] += 1
        msg_key = (path.name, role, content if isinstance(content, str)
                   else json.dumps(content, sort_keys=True, default=str))
        if msg_key not in msg_dedup_seen:
            msg_dedup_seen.add(msg_key)
            counters["distinct_messages"] += 1
        if isinstance(content, str):
            if content:
                key = (path.name, role, "plain_string", content)
                _process_segment_occurrence(key, dedup_seen, registry, pending, counters,
                                             role=role, section="messages", block_type="plain_string",
                                             text=content, tool_name=None)
        elif isinstance(content, list):
            _process_content_blocks(path, role, content, tool_names, dedup_seen, registry, pending, counters)
    return n_messages


def _process_content_blocks(path, role, content, tool_names, dedup_seen, registry, pending, counters) -> None:
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text = block.get("text", "")
            if not text:
                continue
            key = (path.name, role, "text", text)
            _process_segment_occurrence(key, dedup_seen, registry, pending, counters,
                                         role=role, section="messages", block_type="text",
                                         text=text, tool_name=None)
        elif btype == "tool_result":
            _process_tool_result_block(path, role, block, tool_names, dedup_seen, registry, pending, counters)


def _process_tool_result_block(path, role, block, tool_names, dedup_seen, registry, pending, counters) -> None:
    tname = tool_names.get(block.get("tool_use_id"))
    inner = block.get("content")
    if isinstance(inner, str):
        if not inner:
            return
        key = (path.name, role, "tool_result_str", inner)
        _process_segment_occurrence(key, dedup_seen, registry, pending, counters,
                                     role=role, section="messages",
                                     block_type="tool_result_str", text=inner,
                                     tool_name=tname)
    elif isinstance(inner, list):
        for sub in inner:
            if not (isinstance(sub, dict) and sub.get("type") == "text"):
                continue
            stext = sub.get("text", "")
            if not stext:
                continue
            key = (path.name, role, "tool_result_text", stext)
            _process_segment_occurrence(key, dedup_seen, registry, pending, counters,
                                         role=role, section="messages",
                                         block_type="tool_result_text", text=stext,
                                         tool_name=tname)
