# INFRASTRUCTURE
import bisect
from pathlib import Path

from src.dual_log_cli.usage import flow_status_ids, resolve_transcript, usage_from_transcript
from src.format.token_format import call_numbers
from src.panes.cache_turns import build_cache_turns

_PATH_TRANSCRIPT = "transcript"
_PATH_BOUNDARIES = "boundaries"


# ORCHESTRATOR


def build_session_numbering(session: dict, boundaries: list, continues: list, projects_root: Path = None,
                            messages: list = None) -> dict:
    main_thread = sorted(boundaries + continues, key=lambda request: request["timestamp"])
    _annotate_status(main_thread, session)
    transcript_path, flow_status, reason = resolve_transcript(session, main_thread, projects_root)
    usage = usage_from_transcript(transcript_path, flow_status)
    turns = _transcript_turns(transcript_path)
    if not any(turn.get("api_calls") for turn in turns):
        return {"usage": usage, "pane_turns": None, "path": _PATH_BOUNDARIES,
                "reason": reason or "transcript carries no api calls"}
    _annotate(main_thread, flow_status, _index_by_request_id(turns))
    _locate_msgs(main_thread, messages or [])
    return {"usage": usage, "pane_turns": turns, "path": _PATH_TRANSCRIPT, "requests": main_thread}


# FUNCTIONS


def _annotate_status(main_thread: list, session: dict) -> None:
    response_path = (session.get("streams") or {}).get("response")
    statuses = flow_status_ids(response_path) if response_path is not None else {}
    for request in main_thread:
        request["http_status"] = statuses.get(request.get("flow_id", ""), ("", None))[1]


def _transcript_turns(transcript_path: Path) -> list:
    if transcript_path is None:
        return []
    turns, _position = build_cache_turns(transcript_path, 0, [])
    return turns


def _index_by_request_id(turns: list) -> dict:
    index = {}
    for turn_number, (turn, row) in enumerate(zip(turns, call_numbers(turns)), start=1):
        for call, number in zip(turn.get("api_calls", []), row):
            request_id = call.get("request_id", "")
            if request_id and request_id not in index:
                index[request_id] = (number, turn_number, call.get("timestamp", ""))
    return index


def _locate_msgs(main_thread: list, messages: list) -> None:
    assistants = [index for index, message in enumerate(messages) if message.get("role") == "assistant"]
    result_index = _tool_result_index(messages)
    for request in main_thread:
        if request.get("pane_number") is None:
            continue
        start = _msg_start(request, assistants, result_index, len(messages))
        if start is not None:
            request["msg_start"] = start


def _tool_result_index(messages: list) -> dict:
    index = {}
    for position, message in enumerate(messages):
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("tool_use_id"):
                index[block["tool_use_id"]] = position
    return index


def _msg_start(request: dict, assistants: list, result_index: dict, total: int):
    if "message_count" in request:
        last_sent = min(request["message_count"], total) - 1
    else:
        positions = [result_index[i] for i in request.get("tool_use_ids", []) if i in result_index]
        if not positions or len(positions) != len(request["tool_use_ids"]):
            return None
        last_sent = min(positions)
    if last_sent < 0:
        return None
    before = bisect.bisect_left(assistants, last_sent) - 1
    return assistants[before] if before >= 0 else 0


def _annotate(main_thread: list, flow_status: dict, index: dict) -> None:
    for request in main_thread:
        request_id = flow_status.get(request.get("flow_id", ""), ("", None))[0]
        hit = index.get(request_id)
        request["pane_number"] = hit[0] if hit else None
        request["pane_turn"] = hit[1] if hit else None
        request["pane_time"] = (hit[2] or None) if hit else None
