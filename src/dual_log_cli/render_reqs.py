# INFRASTRUCTURE
from .discovery import stem_identity
from .reader import local_datetime
from .render_format import _clock, _fmt_duration, _skipped_lines
from .timeline_grouping import _group_markers_by_turn, _turn_preview

_REQ_NUMBER_WIDTH = 4


# FUNCTIONS


def render_reqs(results: list, skipped: int = 0, turn: int = None, gap_minutes: int = None,
                usage_by_stem: dict = None, rebuild: bool = False, drop: bool = False,
                turns_by_stem: dict = None) -> str:
    if not results:
        lines = ["no sessions found"]
        return "\n".join(lines + _skipped_lines(skipped)) + "\n"
    lines = []
    for session, boundaries in results:
        stem = session.get("stem", "")
        lines.append(f"session {stem}")
        usage_map = (usage_by_stem or {}).get(stem, {})
        turns = (turns_by_stem or {}).get(stem, [])
        entries, separators = _session_entries_and_separators(boundaries, turns, usage_map, stem)
        entries = _apply_filters(entries, turn, gap_minutes, rebuild, drop)
        lines.extend(_grouped_lines(entries, separators, merged=False))
        lines.append("")
    return "\n".join(lines[:-1] + _skipped_lines(skipped)) + "\n"


def render_reqs_merged(results: list, skipped: int = 0, turn: int = None, gap_minutes: int = None,
                       usage_by_stem: dict = None, rebuild: bool = False, drop: bool = False,
                       turns_by_stem: dict = None) -> str:
    if not results:
        lines = ["no sessions found"]
        return "\n".join(lines + _skipped_lines(skipped)) + "\n"
    entries, separators = _merged_entries(results, turns_by_stem, usage_by_stem)
    entries = _apply_filters(entries, turn, gap_minutes, rebuild, drop)
    lines = [f"merged {len(results)} sessions"]
    lines.extend(_grouped_lines(entries, separators, merged=True))
    return "\n".join(lines + _skipped_lines(skipped)) + "\n"


def _req_line(marker: dict, tag: str, usage, cr_width: int) -> str:
    tag_part = f"  {tag}" if tag else ""
    return f"REQ {marker['number']:<{_REQ_NUMBER_WIDTH}}{_clock(marker['timestamp'])}{tag_part}{_usage_part(usage, cr_width)}"


def _usage_part(usage, cr_width: int) -> str:
    cr_str = f"{usage[0]:,}" if usage else "?"
    cc_str = f"{usage[1]:,}" if usage else "?"
    return f"  CR {cr_str:<{cr_width}}  CC {cc_str}"


def _session_tag(session: dict) -> str:
    identity = stem_identity(session.get("stem", ""))
    return identity[-1] if identity else session.get("stem", "")


def _session_entries_and_separators(boundaries: list, turns: list, usage_map: dict,
                                    stem: str, tag: str = "") -> tuple:
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


def _entries_for_session(markers: dict, usage_map: dict, turn_by_msg_index: dict,
                         stem: str, tag: str = "") -> list:
    entries = []
    prev_usage = None
    for msg_index in sorted(markers):
        marker = markers[msg_index]
        dt = local_datetime(marker["timestamp"])
        if dt is None:
            continue
        usage = (usage_map or {}).get(marker.get("flow_id"))
        turn_number = turn_by_msg_index.get(msg_index)
        entries.append((dt, stem, marker, tag, turn_number, usage, prev_usage))
        prev_usage = usage
    return entries


def _merged_entries(results: list, turns_by_stem: dict = None, usage_by_stem: dict = None) -> tuple:
    entries = []
    separators = {}
    for session, boundaries in results:
        stem = session.get("stem", "")
        tag = _session_tag(session)
        usage_map = (usage_by_stem or {}).get(stem, {})
        turns = (turns_by_stem or {}).get(stem, [])
        session_entries, session_separators = _session_entries_and_separators(
            boundaries, turns, usage_map, stem, tag)
        entries.extend(session_entries)
        separators.update(session_separators)
    entries.sort(key=lambda entry: entry[0])
    return entries, separators


def _bracket_gap_positions(entries: list, gap_minutes: int) -> dict:
    positions = {}
    for i in range(len(entries) - 1):
        dt_before = entries[i][0]
        dt_after = entries[i + 1][0]
        elapsed = int((dt_after - dt_before).total_seconds() // 60)
        if elapsed < gap_minutes:
            continue
        positions.setdefault(i, None)
        positions[i + 1] = None
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
        if key != current_key:
            text = separators.get(key)
            if text is not None:
                lines.append(text)
            current_key = key
        cr_width = cr_width_by_stem.get(stem, 1)
        lines.append(_req_line(marker, tag if merged else "", usage, cr_width))
    return lines
