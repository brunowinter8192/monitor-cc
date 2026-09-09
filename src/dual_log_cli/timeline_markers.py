# INFRASTRUCTURE


class UnknownRequestNumberError(Exception):
    pass


class AmbiguousRequestNumberError(Exception):
    pass


# FUNCTIONS


# Which request opened each msg index -> {msg_index: {number, timestamp, refires, flow_id,
# sys_lines, tool_lines, message_count}}. flow_id is the owner's — what `usage.build_usage_by_flow`
# keys its {flow_id: (cr, cc)} map by, so a separator can look up its own request's prompt-cache
# usage without a second index. sys_lines/tool_lines are the OWNER boundary's own — a re-fire group
# shows only the owner's delta, matching the timestamp and usage the separator already carries.
# message_count (2026-09-08, for `reqs --turns`) is the owner's OWN total msg count as SENT — the
# msg count this request's payload already carried, which can run past the msg-index KEY this
# marker is grouped under (see `_group_markers_by_turn`'s Gotcha: a request whose own send bundles
# the previous turn's idle text reply together with the NEXT turn's new prompt keys a LOW msg
# index here but its message_count already covers the next turn's opener).
#
# Boundaries are grouped by the index they open. Several land on one index when a request re-fired
# without adding a msg (a retry/abort re-send) or when a restart reset the index to 0. At most ONE
# boundary of a group can add msgs, and it is always the LAST: every member shares the same
# prev_count, so the one that raises message_count ends the group. That member owns the group — its
# timestamp is when the msgs below actually arrived, and the earlier members are counted as refires.
#
# `number` counts only msg-ADDING requests, which is what makes it equal the proxy pane's `#N` for
# the same session (measured: 0 mismatches over 967 requests in 3 sessions, comparing number,
# message count and timestamp). The raw request_no would NOT match — it also counts re-fires, which
# the pane renders as `#N.M` without advancing N.
def request_markers(boundaries: list) -> dict:
    numbers = _running_request_numbers(boundaries)
    grouped: dict = {}
    for position, boundary in enumerate(boundaries):
        grouped.setdefault(boundary["start_index"], []).append(position)
    markers = {}
    for index, positions in grouped.items():
        owner = positions[-1]
        markers[index] = {
            "number": numbers[owner],
            "timestamp": boundaries[owner]["timestamp"],
            "refires": len(positions) - 1,
            "flow_id": boundaries[owner].get("flow_id", ""),
            "sys_lines": boundaries[owner].get("sys_lines", []),
            "tool_lines": boundaries[owner].get("tool_lines", []),
            "message_count": boundaries[owner].get("message_count", 0),
        }
    return markers


# Running REQ number per boundary position — the shared counting rule: only a msg-ADDING request
# advances the number, which is what keeps it equal to the proxy pane's `#N`. A re-fire carries the
# number of the request before it.
def _running_request_numbers(boundaries: list) -> list:
    numbers = []
    adding = 0
    for boundary in boundaries:
        if boundary["start_index"] < boundary["message_count"]:
            adding += 1
        numbers.append(adding)
    return numbers


# {flow_id: REQ number} for the boundaries of one session — the same numbering `msgs` prints, so an
# overlay attributed to a flow can name the request a reader already sees there. A re-fire maps to
# the number of the msg-adding request before it; the overlay renderer shows "?" for a flow absent
# here entirely (a sidecar the boundary list never carried).
def request_numbers_by_flow(boundaries: list) -> dict:
    numbers = _running_request_numbers(boundaries)
    return {
        boundary["flow_id"]: numbers[position]
        for position, boundary in enumerate(boundaries)
        if boundary.get("flow_id")
    }


# Msg-index range [start, end] spanned by REQ numbers req_from..req_to inclusive, for `msgs --req`.
# `markers` is `request_markers`'s own {msg_index: {number, ...}}; `start` is req_from's own msg
# index, `end` is the msg index right before the NEXT marker (by msg-index order) after req_to's
# own, or `last_msg_index` when req_to's group is the last one — the exact msg-index range the
# equivalent `FROM TO` positionals would need to select the same request groups, so the caller
# hands it straight to the unmodified `render_msgs`.
#
# Raises UnknownRequestNumberError when req_from/req_to names no marker at all, and
# AmbiguousRequestNumberError when it names MORE than one — proven possible even without a
# restart: a re-fire that adds no NEW msg opens its own group (a start_index no earlier group
# used) but `_running_request_numbers`' counter does not advance for a non-adding boundary, so
# that group's owner is assigned the SAME number as the group before it. A genuine restart can
# produce the identical symptom when the restarted boundary itself adds nothing. Refusing to guess
# either way is the point — see the callers in __main__.py for the reported message.
def request_msg_range(markers: dict, req_from: int, req_to: int, last_msg_index: int) -> tuple:
    by_number: dict = {}
    for msg_index, marker in markers.items():
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


# Convenience wrapper: builds `request_markers` from `boundaries` and delegates to
# `request_msg_range` — the one call `__main__.py` needs for `msgs --req`.
def resolve_req_range(boundaries: list, req_from: int, req_to: int, last_msg_index: int) -> tuple:
    markers = request_markers(boundaries or [])
    return request_msg_range(markers, req_from, req_to, last_msg_index)
