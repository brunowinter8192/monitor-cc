# INFRASTRUCTURE
from pathlib import Path

from src.dual_log_cli.usage import resolve_transcript, usage_from_transcript
from src.format.token_format import call_numbers
from src.panes.cache_turns import build_cache_turns

_PATH_TRANSCRIPT = "transcript"
_PATH_BOUNDARIES = "boundaries"


# ORCHESTRATOR


def build_session_numbering(session: dict, boundaries: list, continues: list, projects_root: Path = None) -> dict:
    main_thread = sorted(boundaries + continues, key=lambda request: request["timestamp"])
    transcript_path, flow_status = resolve_transcript(session, main_thread, projects_root)
    usage = usage_from_transcript(transcript_path, flow_status)
    turns = _transcript_turns(transcript_path)
    if not any(turn.get("api_calls") for turn in turns):
        return {"usage": usage, "pane_turns": None, "path": _PATH_BOUNDARIES}
    _annotate(main_thread, flow_status, _index_by_request_id(turns))
    return {"usage": usage, "pane_turns": turns, "path": _PATH_TRANSCRIPT}


# FUNCTIONS


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


def _annotate(main_thread: list, flow_status: dict, index: dict) -> None:
    for request in main_thread:
        request_id = flow_status.get(request.get("flow_id", ""), ("", None))[0]
        hit = index.get(request_id)
        request["pane_number"] = hit[0] if hit else None
        request["pane_turn"] = hit[1] if hit else None
        request["pane_time"] = (hit[2] or None) if hit else None
