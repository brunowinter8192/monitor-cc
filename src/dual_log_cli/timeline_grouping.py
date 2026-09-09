# INFRASTRUCTURE
import bisect

from .timeline_markers import request_markers

# FUNCTIONS


def _is_turn_opener(turn: dict) -> bool:
    if turn.get("role") != "user":
        return False
    types = {block.get("type") for block in turn.get("blocks", [])}
    return "text" in types and "tool_result" not in types


def turn_openers(turns: list) -> list:
    return [turn["index"] for turn in turns if _is_turn_opener(turn)]


def _turn_preview(turn: dict) -> str:
    preview = ""
    for block in turn.get("blocks", []):
        if block.get("type") == "text":
            preview = block.get("preview", "")
    return preview


def _group_markers_by_turn(turns: list, boundaries: list) -> tuple:
    markers = request_markers(boundaries or [])
    openers = turn_openers(turns)
    groups = [[] for _ in openers]
    if openers:
        for msg_index in sorted(markers):
            marker = markers[msg_index]
            position = bisect.bisect_right(openers, marker["message_count"] - 1)
            position = max(1, min(position, len(openers))) - 1
            groups[position].append(msg_index)
    return markers, openers, groups
