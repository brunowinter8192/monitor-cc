# INFRASTRUCTURE
from src.proxy_display.format import _assign_turns_to_entries

from src.dual_log_cli.discovery import stem_identity
from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_format import _clock, _fmt_duration, _skipped_lines
from src.dual_log_cli.timeline_grouping import _group_markers_by_turn, _turn_preview

_REQ_NUMBER_WIDTH = 4
_PREVIEW_CHARS = 100
_NO_REQS_LINE = "no REQs to show"


# FUNCTIONS


def render_reqs(results: list, skipped: int = 0, turn: int = None, gap_minutes: int = None,
                usage_by_stem: dict = None, rebuild: bool = False, drop: bool = False,
                turns_by_stem: dict = None, continues_by_stem: dict = None,
                pane_turns_by_stem: dict = None) -> str:
    if not results:
        lines = ["no sessions found"]
        return "\n".join(lines + _skipped_lines(skipped)) + "\n"
    blocks = []
    for session, boundaries in results:
        stem = session.get("stem", "")
        usage_map = (usage_by_stem or {}).get(stem, {})
        turns = (turns_by_stem or {}).get(stem, [])
        entries, separators = _session_entries_and_separators(
            boundaries, turns, usage_map, stem, "", (continues_by_stem or {}).get(stem),
            (pane_turns_by_stem or {}).get(stem))
        entries = _apply_filters(entries, turn, gap_minutes, rebuild, drop)
        if entries:
            blocks.append([f"session {stem}"] + _grouped_lines(entries, separators, merged=False))
    if not blocks:
        return _no_reqs_output(skipped)
    lines = []
    for block in blocks:
        lines.extend(block + [""])
    return "\n".join(lines[:-1] + _skipped_lines(skipped)) + "\n"


def render_reqs_merged(results: list, skipped: int = 0, turn: int = None, gap_minutes: int = None,
                       usage_by_stem: dict = None, rebuild: bool = False, drop: bool = False,
                       turns_by_stem: dict = None, continues_by_stem: dict = None,
                       pane_turns_by_stem: dict = None) -> str:
    if not results:
        lines = ["no sessions found"]
        return "\n".join(lines + _skipped_lines(skipped)) + "\n"
    entries, separators = _merged_entries(results, turns_by_stem, usage_by_stem, continues_by_stem, pane_turns_by_stem)
    entries = _apply_filters(entries, turn, gap_minutes, rebuild, drop)
    if not entries:
        return _no_reqs_output(skipped)
    lines = [f"merged {len(results)} sessions"]
    lines.extend(_grouped_lines(entries, separators, merged=True))
    return "\n".join(lines + _skipped_lines(skipped)) + "\n"


def _no_reqs_output(skipped: int) -> str:
    return "\n".join([_NO_REQS_LINE] + _skipped_lines(skipped)) + "\n"


def _req_line(marker: dict, tag: str, usage, cr_width: int) -> str:
    tag_part = f"  {tag}" if tag else ""
    number = "?" if marker["number"] is None else marker["number"]
    status = marker.get("http_status")
    status_part = f"  {status}" if status not in (None, 200) else ""
    return (f"REQ {number:<{_REQ_NUMBER_WIDTH}}{_clock(_clock_source(marker))}{tag_part}"
            f"{status_part}{_usage_part(usage, cr_width)}")


def _clock_source(marker: dict) -> str:
    return marker.get("clock_timestamp") or marker["timestamp"]


def _usage_part(usage, cr_width: int) -> str:
    cr_str = f"{usage[0]:,}" if usage else "?"
    cc_str = f"{usage[1]:,}" if usage else "?"
    return f"  CR {cr_str:<{cr_width}}  CC {cc_str}"


def _session_tag(session: dict) -> str:
    identity = stem_identity(session.get("stem", ""))
    return identity[-1] if identity else session.get("stem", "")


def _session_entries_and_separators(boundaries: list, turns: list, usage_map: dict,
                                    stem: str, tag: str = "", continues: list = None,
                                    pane_turns: list = None) -> tuple:
    if pane_turns:
        return _pane_entries_and_separators(boundaries, continues or [], pane_turns, usage_map, stem, tag)
    markers, openers, groups = _group_markers_by_turn(turns or [], boundaries or [])
    turn_by_msg_index = {}
    separators = {}
    for position, opener in enumerate(openers):
        group = groups[position]
        if not group:
            continue
        turn_number = position + 1
        for msg_index in group:
            turn_by_msg_index[msg_index] = turn_number
        group_markers = [markers[msg_index] for msg_index in group]
        first_dt = local_datetime(group_markers[0]["timestamp"])
        last_dt = local_datetime(group_markers[-1]["timestamp"])
        span = (last_dt - first_dt).total_seconds() if first_dt and last_dt else None
        tag_part = f"  {tag}" if tag else ""
        separators[(stem, turn_number)] = (
            f"── turn {turn_number}  {_clock(group_markers[0]['timestamp'])}  "
            f"{_fmt_duration(span)}{tag_part}  {_turn_preview(turns[opener])} ──"
        )
    entries = _entries_for_session(markers, usage_map, turn_by_msg_index, stem, tag)
    return entries, separators


def _require_datetime(timestamp: str, stem: str):
    dt = local_datetime(timestamp)
    if dt is None:
        raise ValueError(f"request in {stem} has no timestamp")
    return dt


def _entries_for_session(markers: dict, usage_map: dict, turn_by_msg_index: dict,
                         stem: str, tag: str = "") -> list:
    entries = []
    prev_usage = None
    for msg_index in sorted(markers):
        marker = markers[msg_index]
        dt = _require_datetime(_clock_source(marker), stem)
        usage = (usage_map or {}).get(marker.get("flow_id"))
        turn_number = turn_by_msg_index.get(msg_index)
        entries.append((dt, stem, marker, tag, turn_number, usage, prev_usage))
        prev_usage = usage
    return entries


def _pane_entries_and_separators(boundaries: list, continues: list, pane_turns: list,
                                 usage_map: dict, stem: str, tag: str) -> tuple:
    requests = [_request_marker(request) for request in (boundaries or [])]
    requests.extend(_request_marker(request) for request in continues)
    _assign_unmapped_turns(requests, pane_turns)
    entries = _chronological_entries(requests, usage_map, stem, tag)
    return entries, _pane_turn_separators(entries, pane_turns, stem, tag)


def _assign_unmapped_turns(requests: list, pane_turns: list) -> None:
    unmapped = [request for request in requests if request.get("pane_turn") is None]
    for group in _assign_turns_to_entries(unmapped, pane_turns):
        for _position, request in group["entry_pairs"]:
            request["pane_turn"] = group["turn_idx"] + 1


def _request_marker(request: dict) -> dict:
    return {
        "number": request.get("pane_number"),
        "timestamp": request["timestamp"],
        "clock_timestamp": request.get("pane_time") or request["timestamp"],
        "pane_turn": request.get("pane_turn"),
        "http_status": request.get("http_status"),
        "flow_id": request["flow_id"],
        "refires": 0,
    }


def _chronological_entries(requests: list, usage_map: dict, stem: str, tag: str) -> list:
    dated = [(_require_datetime(_clock_source(request), stem), request) for request in requests]
    dated = sorted(dated, key=lambda pair: pair[0])
    entries = []
    prev_usage = None
    for dt, request in dated:
        usage = (usage_map or {}).get(request.get("flow_id"))
        entries.append((dt, stem, request, tag, request.get("pane_turn"), usage, prev_usage))
        prev_usage = usage
    return entries


def _pane_turn_separators(entries: list, pane_turns: list, stem: str, tag: str) -> dict:
    times_by_turn = {}
    for entry in entries:
        if entry[4] is not None:
            times_by_turn.setdefault(entry[4], []).append(entry[0])
    separators = {}
    tag_part = f"  {tag}" if tag else ""
    for turn_number, times in times_by_turn.items():
        span = (times[-1] - times[0]).total_seconds()
        turn = pane_turns[turn_number - 1] if turn_number <= len(pane_turns) else {}
        prompt = turn.get("prompt", "")
        clock = _clock(turn["timestamp"]) if turn.get("timestamp") else times[0].strftime("%H:%M:%S")
        preview = " ".join(prompt.split())
        preview = preview[:_PREVIEW_CHARS] + ("…" if len(preview) > _PREVIEW_CHARS else "")
        separators[(stem, turn_number)] = (
            f"── turn {turn_number}  {clock}  {_fmt_duration(span)}{tag_part}  {preview} ──"
        )
    return separators


def _merged_entries(results: list, turns_by_stem: dict = None, usage_by_stem: dict = None,
                    continues_by_stem: dict = None, pane_turns_by_stem: dict = None) -> tuple:
    entries = []
    separators = {}
    for session, boundaries in results:
        stem = session.get("stem", "")
        tag = _session_tag(session)
        usage_map = (usage_by_stem or {}).get(stem, {})
        turns = (turns_by_stem or {}).get(stem, [])
        session_entries, session_separators = _session_entries_and_separators(
            boundaries, turns, usage_map, stem, tag, (continues_by_stem or {}).get(stem),
            (pane_turns_by_stem or {}).get(stem))
        entries.extend(session_entries)
        separators.update(session_separators)
    entries.sort(key=lambda entry: entry[0])
    return entries, separators


def _bracket_gap_positions(entries: list, gap_minutes: int) -> dict:
    positions = {}
    last_index_by_turn = {}
    for i, entry in enumerate(entries):
        turn_number = entry[4]
        if turn_number is None or entry[2]["number"] is None:
            continue
        key = (entry[1], turn_number)
        previous = last_index_by_turn.get(key)
        last_index_by_turn[key] = i
        if previous is None:
            continue
        elapsed = int((entry[0] - entries[previous][0]).total_seconds() // 60)
        if elapsed < gap_minutes:
            continue
        positions[previous] = None
        positions[i] = None
    return positions


def _rebuild_drop_qualifies(usage, prev_usage, rebuild: bool, drop: bool) -> bool:
    if usage is None:
        return False
    cache_read, cache_creation = usage
    if rebuild and not (cache_creation > cache_read):
        return False
    if drop:
        if prev_usage is None:
            return False
        prev_read, prev_creation = prev_usage
        if cache_read >= prev_read + prev_creation:
            return False
    return True


def _apply_filters(entries: list, turn: int, gap_minutes: int, rebuild: bool, drop: bool) -> list:
    if turn is not None:
        entries = [entry for entry in entries if entry[4] == turn]
    if gap_minutes is not None:
        positions = _bracket_gap_positions(entries, gap_minutes)
        entries = [entries[i] for i in sorted(positions)]
    if rebuild or drop:
        entries = [entry for entry in entries if _rebuild_drop_qualifies(entry[5], entry[6], rebuild, drop)]
    return entries


def _cr_width_by_stem(entries: list) -> dict:
    widths = {}
    for _dt, stem, _marker, _tag, _turn, usage, _prev_usage in entries:
        cr_str = f"{usage[0]:,}" if usage else "?"
        widths[stem] = max(widths.get(stem, 0), len(cr_str))
    return widths


def _grouped_lines(entries: list, separators: dict, merged: bool) -> list:
    cr_width_by_stem = _cr_width_by_stem(entries)
    lines = []
    current_key = None
    for _dt, stem, marker, tag, turn_number, usage, _prev_usage in entries:
        key = (stem, turn_number)
        if turn_number is not None and key != current_key:
            text = separators.get(key)
            if text is not None:
                lines.append(text)
            current_key = key
        cr_width = cr_width_by_stem.get(stem, 1)
        lines.append(_req_line(marker, tag if merged else "", usage, cr_width))
    return lines
