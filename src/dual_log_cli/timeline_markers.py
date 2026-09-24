# INFRASTRUCTURE


class UnknownRequestNumberError(Exception):
    pass


class AmbiguousRequestNumberError(Exception):
    pass


# FUNCTIONS


def request_markers(boundaries: list) -> dict:
    numbers = _boundary_numbers(boundaries)
    grouped: dict = {}
    for position, boundary in enumerate(boundaries):
        start = boundary["msg_start"] if "msg_start" in boundary else boundary.get("start_index")
        if start is not None:
            grouped.setdefault(start, []).append(position)
    markers = {}
    for index, positions in grouped.items():
        owner = _group_owner(boundaries, positions)
        markers[index] = {
            "number": numbers[owner],
            "timestamp": boundaries[owner]["timestamp"],
            "clock_timestamp": boundaries[owner].get("pane_time") or boundaries[owner]["timestamp"],
            "pane_turn": boundaries[owner].get("pane_turn"),
            "refires": len(positions) - 1,
            "flow_id": boundaries[owner].get("flow_id", ""),
            "sys_lines": boundaries[owner].get("sys_lines", []),
            "tool_lines": boundaries[owner].get("tool_lines", []),
            "message_count": boundaries[owner].get("message_count", 0),
        }
    return markers


def _running_request_numbers(boundaries: list) -> list:
    numbers = []
    adding = 0
    for boundary in boundaries:
        if boundary["start_index"] < boundary["message_count"]:
            adding += 1
        numbers.append(adding)
    return numbers


def _boundary_numbers(boundaries: list) -> list:
    if boundaries and all("pane_number" in boundary for boundary in boundaries):
        return [boundary["pane_number"] for boundary in boundaries]
    running = _running_request_numbers(boundaries)
    return [
        boundary["pane_number"] if "pane_number" in boundary else running[position]
        for position, boundary in enumerate(boundaries)
    ]


def _group_owner(boundaries: list, positions: list) -> int:
    last = positions[-1]
    if "pane_number" not in boundaries[last]:
        return last
    mapped = [p for p in positions if boundaries[p]["pane_number"] is not None]
    return mapped[-1] if mapped else last


def request_numbers_by_flow(boundaries: list) -> dict:
    numbers = _boundary_numbers(boundaries)
    return {
        boundary["flow_id"]: numbers[position]
        for position, boundary in enumerate(boundaries)
        if boundary.get("flow_id") and numbers[position] is not None
    }


def request_msg_range(markers: dict, req_from: int, req_to: int, last_msg_index: int) -> tuple:
    by_number: dict = {}
    for msg_index, marker in markers.items():
        if marker["number"] is None:
            continue
        by_number.setdefault(marker["number"], []).append(msg_index)
    for number in (req_from, req_to):
        candidates = by_number.get(number)
        if not candidates:
            raise UnknownRequestNumberError(f"REQ {number} not found")
        if len(candidates) > 1:
            indices = ", ".join(str(i) for i in sorted(candidates))
            raise AmbiguousRequestNumberError(
                f"REQ {number} is ambiguous — msg indices {indices} all carry it "
                f"(a re-fire or restart repeated the number; refusing to guess)")
    start = by_number[req_from][0]
    to_start = by_number[req_to][0]
    later_starts = sorted(idx for idx in markers if idx > to_start)
    end = later_starts[0] - 1 if later_starts else last_msg_index
    return start, end


def resolve_req_range_with_next(requests: list, req_from: int, req_to: int, last_msg_index: int) -> tuple:
    markers = request_markers(requests or [])
    starts_by_number = {marker["number"]: index for index, marker in markers.items() if marker["number"] is not None}
    chain = sorted({request["pane_number"] for request in requests if request.get("pane_number") is not None})
    if req_from not in chain or req_to not in chain:
        missing = req_from if req_from not in chain else req_to
        raise UnknownRequestNumberError(f"REQ {missing} not found")
    wanted = [n for n in chain if req_from <= n <= req_to] + [n for n in chain if n > req_to][:1]
    starts = [starts_by_number[n] for n in wanted if n in starts_by_number]
    if not starts:
        raise UnknownRequestNumberError(f"REQ {req_from} owns no located msgs")
    later_starts = sorted(idx for idx in markers if idx > max(starts))
    end = later_starts[0] - 1 if later_starts else last_msg_index
    return min(starts), end


def resolve_req_output_range(requests: list, req_number: int, last_msg_index: int) -> tuple:
    markers = request_markers(requests or [])
    starts_by_number = {marker["number"]: index for index, marker in markers.items() if marker["number"] is not None}
    chain = sorted({request["pane_number"] for request in requests if request.get("pane_number") is not None})
    if req_number not in chain:
        raise UnknownRequestNumberError(f"REQ {req_number} not found")
    following = [n for n in chain if n > req_number]
    if not following:
        raise UnknownRequestNumberError(f"REQ {req_number}'s reply is not recorded (no later request in the log)")
    successor = following[0]
    if successor not in starts_by_number:
        raise UnknownRequestNumberError(
            f"REQ {req_number}'s reply could not be located: the next request, REQ {successor}, "
            f"is a turn opener or newer than the last recorded payload")
    start = starts_by_number[successor]
    later_starts = sorted(idx for idx in markers if idx > start)
    return start, (later_starts[0] - 1 if later_starts else last_msg_index)


def resolve_req_range(boundaries: list, req_from: int, req_to: int, last_msg_index: int) -> tuple:
    markers = request_markers(boundaries or [])
    return request_msg_range(markers, req_from, req_to, last_msg_index)
