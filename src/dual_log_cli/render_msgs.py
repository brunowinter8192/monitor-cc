# INFRASTRUCTURE
from .render_format import _clock
from .timeline_boundaries import _BILLING_HEADER_SYS_INDEX, _system_block_chars, _tool_chars
from .timeline_markers import request_markers

_MSG_PREFIX_WIDTH = 12
_MSG_LABEL_WIDTH = 20
_MSG_CHARS_WIDTH = 6
_BLOCK_INDENT = "        "
_BLOCK_LABEL_WIDTH = _MSG_PREFIX_WIDTH + _MSG_LABEL_WIDTH - len(_BLOCK_INDENT)


# FUNCTIONS


def render_msgs(data: dict, start: int, end: int, usage_by_flow: dict = None,
                overlay: dict = None, sys_tool_overlay: tuple = None) -> str:
    markers = request_markers(data.get("boundaries") or [])
    payload = data.get("payload") or {}
    orig_system = payload.get("system", []) or []
    orig_tools = payload.get("tools", []) or []
    sys_overlay, tools_overlay = sys_tool_overlay or ({}, {})
    lines = []
    group_req = None
    for offset, msg in enumerate(data["turns"][start:end + 1]):
        marker = markers.get(msg["index"])
        if marker is None and offset == 0:
            marker = _governing_marker(markers, msg["index"])
        if marker is not None:
            lines.append(_req_separator(marker, usage_by_flow))
            lines.extend(_req_delta_lines(marker, orig_system, orig_tools, sys_overlay, tools_overlay, marker["number"]))
            group_req = marker["number"]
        blocks = msg["blocks"]
        label = blocks[0]["type"] if len(blocks) == 1 else f"{len(blocks)} blocks"
        chars_value = msg["chars"]
        chars = f"{chars_value:,}c"
        tail = _msg_delta_tail(msg["index"], blocks, chars_value, overlay, group_req)
        lines.append(f"[{msg['index']:3d}] {msg['role'][:4]:<4}  {label:<{_MSG_LABEL_WIDTH}}{chars:>{_MSG_CHARS_WIDTH}}{tail}")
        if len(blocks) > 1:
            lines.extend(_block_sub_lines(msg["index"], blocks, overlay, group_req))
    return "\n".join(lines) + "\n"


def _req_delta_lines(marker: dict, orig_system: list, orig_tools: list,
                     sys_overlay: dict, tools_overlay: dict, group_req) -> list:
    lines = []
    tools_by_name = {t.get("name", "?"): t for t in orig_tools if isinstance(t, dict)}
    seen_names = set()
    for item in marker.get("sys_lines") or []:
        idx = _sys_index_from_label(item["label"])
        if idx == _BILLING_HEADER_SYS_INDEX:
            lines.append(_delta_line(item, None, None, group_req))
            continue
        original = _system_block_chars(orig_system[idx]) if 0 <= idx < len(orig_system) else None
        lines.append(_delta_line(item, original, sys_overlay.get(str(idx)), group_req))
    for item in marker.get("tool_lines") or []:
        name = _tool_name_from_label(item["label"])
        seen_names.add(name)
        if item.get("chars") is None:
            lines.append(f"{_BLOCK_INDENT}{item['label']:<{_BLOCK_LABEL_WIDTH}}  {item['tag']}")
            continue
        original = _tool_chars(tools_by_name[name]) if name in tools_by_name else None
        lines.append(_delta_line(item, original, tools_overlay.get(name), group_req))
    for name in sorted(tools_overlay):
        slot = tools_overlay[name]
        if name in seen_names or not slot.get("whole") or slot.get("flow_id") != marker.get("flow_id"):
            continue
        if name not in tools_by_name:
            continue
        original = _tool_chars(tools_by_name[name])
        lines.append(_delta_line({"label": f"tool[{name}]", "tag": None}, original, slot, group_req))
    return lines


def _sys_index_from_label(label: str) -> int:
    return int(label[len("sys["):-1])


def _tool_name_from_label(label: str) -> str:
    return label[len("tool["):-1]


def _delta_line(item: dict, original_chars, slot, group_req) -> str:
    label = f"{item['label']:<{_BLOCK_LABEL_WIDTH}}"
    chars_value = original_chars if original_chars is not None else item["chars"]
    chars = f"{chars_value:,}c"
    tail = ""
    if slot:
        wire_chars = 0 if slot.get("whole") else item["chars"]
        injected_chars = sum(len(t) for t in slot.get("injected") or [])
        stripped_chars = chars_value - wire_chars + injected_chars
        if stripped_chars or injected_chars:
            tail = _delta_tail(stripped_chars, injected_chars, chars_value, slot.get("req"), group_req)
    tag_suffix = f"  {item['tag']}" if item.get("tag") else ""
    return f"{_BLOCK_INDENT}{label}{chars:>{_MSG_CHARS_WIDTH}}{tail}{tag_suffix}"


def _block_sub_lines(msg_index: int, blocks: list, overlay: dict, group_req) -> list:
    lines = []
    for blk_index, block in enumerate(blocks):
        chars_value = block["chars"]
        chars = f"{chars_value:,}c"
        totals = _block_overlay_totals(overlay, msg_index, blk_index)
        if totals:
            stripped_chars, injected_chars, req = totals
            tail = _delta_tail(stripped_chars, injected_chars, chars_value, req, group_req)
        else:
            tail = ""
        lines.append(f"{_BLOCK_INDENT}{block['label']:<{_BLOCK_LABEL_WIDTH}}{chars:>{_MSG_CHARS_WIDTH}}{tail}")
    return lines


def _msg_delta_tail(msg_index: int, blocks: list, chars_value: int, overlay: dict, group_req) -> str:
    total_stripped = 0
    total_injected = 0
    reqs = set()
    touched = False
    for blk_index in range(len(blocks)):
        totals = _block_overlay_totals(overlay, msg_index, blk_index)
        if totals is None:
            continue
        touched = True
        stripped_chars, injected_chars, req = totals
        total_stripped += stripped_chars
        total_injected += injected_chars
        if req is not None:
            reqs.add(req)
    if not touched:
        return ""
    req = next(iter(reqs)) if len(reqs) == 1 else None
    return _delta_tail(total_stripped, total_injected, chars_value, req, group_req)


def _block_overlay_totals(overlay: dict, msg_index: int, blk_index: int):
    slot = (overlay or {}).get((msg_index, blk_index))
    if not slot:
        return None
    stripped_chars = sum(len(t) for t in slot.get("stripped") or [])
    injected_chars = sum(len(t) for t in slot.get("injected") or [])
    if not stripped_chars and not injected_chars:
        return None
    return stripped_chars, injected_chars, slot.get("req")


def _delta_tail(stripped_chars: int, injected_chars: int, chars_value: int, req, group_req) -> str:
    wire_chars = chars_value - stripped_chars + injected_chars
    tail = f"  −{stripped_chars:,} +{injected_chars:,} → {wire_chars:,}c"
    if req is not None and req != group_req:
        tail += f" by REQ {req}"
    return tail


def _governing_marker(markers: dict, index: int):
    starts = [s for s in markers if s <= index]
    return markers[max(starts)] if starts else None


def _req_separator(marker: dict, usage_by_flow: dict = None) -> str:
    refires = marker["refires"]
    extra = ""
    if refires:
        extra = f"  (+{refires} re-fire{'s' if refires != 1 else ''})"
    usage = (usage_by_flow or {}).get(marker.get("flow_id"))
    usage_part = f"  {_fmt_usage(*usage)}" if usage else ""
    return f"── REQ {marker['number']}  {_clock(marker['timestamp'])}{usage_part} ──{extra}"


def _fmt_usage(cache_read: int, cache_creation: int) -> str:
    return f"CR {cache_read:,}  CC {cache_creation:,}"
