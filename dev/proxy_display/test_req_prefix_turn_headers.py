# INFRASTRUCTURE
import json
import re
import sys
import tempfile
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(WORKTREE_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dev.refactoring.strand_runner import strand_workflow

_SYSTEM_DELTA = {"0": {"type": "text", "text": "x-anthropic-billing-header: cc_version=1"}}
_TOOLS_DELTA = {"0": {"name": "Bash", "description": "d", "input_schema": {}}}
_BEFORE_TURN_2 = "2026-09-24T10:05:00.000Z"
_TURN_2_START = "2026-09-24T10:10:00.000Z"
_CALL_TIMES = {
    "r1": "2026-09-24T10:00:11.000Z",
    "r2": "2026-09-24T10:00:21.500Z",
    "r3": "2026-09-24T10:00:31.000Z",
    "r4": "2026-09-24T10:10:12.000Z",
}

_STRANDS = [
    'test_continue_entries_do_not_corrupt_accumulator',
    'test_lazy_load_of_continue_and_following_create',
    'test_req_prefix_and_turn_headers',
    'test_numbering_matches_token_pane',
    'test_refire_and_unmapped_labels',
    'test_right_aligned_times_in_both_panes',
    'test_time_survives_truncation',
    'test_same_time_for_same_req_in_both_panes',
    'test_transcript_parser_records_last_entry_time',
    'test_http_status_marker_and_line',
]

# ORCHESTRATOR

def run_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='test_req_prefix_turn_headers')

# FUNCTIONS

def check(name, condition, detail=""):
    if not condition:
        print(f"  FAIL  {name}" + (f": {detail}" if detail != "" else ""))
        raise AssertionError(name)
    print(f"  PASS  {name}")
    return True

def _msg(role, text):
    return {"role": role, "content": text}

def _fwd(flow_id, ts, model, counts, system_delta, tools_delta, messages_delta, previous_message_id, is_first=False):
    return {
        "type": "forwarded_delta",
        "flow_id": flow_id,
        "request_id": "",
        "timestamp": ts,
        "model": model,
        "max_tokens": 128000,
        "is_first": is_first,
        "counts": counts,
        "system_delta": system_delta,
        "tools_delta": tools_delta,
        "messages_delta": messages_delta,
        "diagnostics": {"previous_message_id": previous_message_id},
    }

def _forwarded_lines() -> list:
    sonnet = "claude-sonnet-5"
    return [
        _fwd("h0", "2026-09-24T10:00:00.000Z", "claude-haiku-4-5-20251001",
             {"system": 1, "tools": 0, "messages": 1}, _SYSTEM_DELTA, {}, {"0": _msg("user", "t")}, None, True),
        _fwd("f1", "2026-09-24T10:00:01.000Z", sonnet,
             {"system": 1, "tools": 1, "messages": 2}, _SYSTEM_DELTA, _TOOLS_DELTA,
             {"0": _msg("user", "go"), "1": _msg("assistant", "ok")}, None, True),
        _fwd("f2", "2026-09-24T10:00:10.000Z", sonnet,
             {"system": 1, "tools": 0, "messages": 2}, _SYSTEM_DELTA, {}, {"0": _msg("user", "r1")}, "msg_a"),
        _fwd("f3", "2026-09-24T10:00:20.000Z", sonnet,
             {"system": 1, "tools": 0, "messages": 2}, _SYSTEM_DELTA, {}, {"0": _msg("user", "r2")}, "msg_b"),
        _fwd("f4", "2026-09-24T10:10:01.000Z", sonnet,
             {"system": 1, "tools": 1, "messages": 6}, {}, {},
             {"2": _msg("user", "r1"), "3": _msg("assistant", "a"), "4": _msg("user", "r2"), "5": _msg("user", "next")}, "msg_c"),
        _fwd("f5", "2026-09-24T10:10:30.000Z", sonnet,
             {"system": 1, "tools": 0, "messages": 2}, _SYSTEM_DELTA, {}, {"0": _msg("user", "r3")}, "msg_d"),
    ]

def _write_forwarded() -> Path:
    handle = tempfile.NamedTemporaryFile(mode="w", suffix="_forwarded.jsonl", delete=False)
    with handle:
        for line in _forwarded_lines():
            handle.write(json.dumps(line) + "\n")
    return Path(handle.name)

def _call(request_id):
    return {"request_id": request_id, "cache_read": 1000, "cache_creation": 100, "direct": 2,
            "output_tokens": 50, "content_blocks": [], "timestamp": _CALL_TIMES[request_id]}

def _turns() -> list:
    return [
        {"prompt": "first prompt", "timestamp": "2026-09-24T09:59:59.000Z", "api_calls": [_call("r1"), _call("r2"), _call("r3")]},
        {"prompt": "second prompt", "timestamp": _TURN_2_START, "api_calls": [_call("r4")]},
    ]

def _request_id_by_flow() -> dict:
    return {"f1": "r1", "f2": "r2", "f3": "r3", "f4": "r4"}

def _plain_lines(ansi: str) -> list:
    from src.utils import _ANSI_ESCAPE_RE
    return [_ANSI_ESCAPE_RE.sub("", line).replace("\x1b[K", "").rstrip() for line in ansi.split("\n")]

def _parsed_entries() -> list:
    from src.proxy_display.forwarded_parser import _parse_forwarded_log
    path = _write_forwarded()
    try:
        entries, _ = _parse_forwarded_log(path, 0, {}, keep_last=None)
    finally:
        path.unlink()
    return entries

def test_continue_entries_do_not_corrupt_accumulator():
    from src.proxy_display.forwarded_parser import _parse_forwarded_log
    print("\n[Test 1] forwarded parser: continue requests leave the family accumulator alone")
    path = _write_forwarded()
    acc = {}
    try:
        entries, _ = _parse_forwarded_log(path, 0, acc, keep_last=None)
    finally:
        path.unlink()
    check("all 6 forwarded lines parse without raising", len(entries) == 6)
    check("f2, f3, f5 are flagged is_continue, f1 and f4 are not",
          [bool(e.get("is_continue")) for e in entries[1:]] == [False, True, True, False, True])
    check("the create after two continues carries its full 6-message count", entries[4]["message_count"] == 6)
    check("family accumulator ends at the create's 6 messages, not the continue's 2", len(acc["sonnet"]["messages"]) == 6)
    check("the create after the continues shows +4 messages, so it stays a fresh request",
          entries[4]["diff_from_prev"]["messages_added"] == 4)

def test_lazy_load_of_continue_and_following_create():
    from src.proxy_display.forwarded_parser import _lazy_load_messages_forwarded, _parse_forwarded_log
    print("\n[Test 2] lazy load replays continue and create entries consistently")
    path = _write_forwarded()
    try:
        entries, _ = _parse_forwarded_log(path, 0, {}, keep_last=1)
        cont, create = entries[2], entries[4]
        cont["messages"] = None
        create["messages"] = None
        _lazy_load_messages_forwarded(cont, path)
        _lazy_load_messages_forwarded(create, path)
    finally:
        path.unlink()
    check("a continue lazy-loads to its own 2 messages", len(cont["messages"]) == 2)
    check("the create after it lazy-loads to its full 6 messages", len(create["messages"]) == 6)

def test_req_prefix_and_turn_headers():
    from src.proxy_display.format import format_proxy_block
    print("\n[Test 3] format_proxy_block: REQ #n prefix and Turn header rows")
    entries = _parsed_entries()
    ansi, _ = format_proxy_block(entries, {}, None, None, 200, 120, 0, _turns(), request_id_by_flow=_request_id_by_flow())
    lines = [line for line in _plain_lines(ansi) if line.strip()]
    req_lines = [line for line in lines if "sonnet" in line or "haiku" in line]
    check("every mapped sonnet row starts with 'REQ #<n>'",
          [line.split()[1] + " " + line.split()[2] for line in req_lines[1:5]] == ["REQ #1", "REQ #2", "REQ #3", "REQ #4"], req_lines)
    check("the haiku sidecar keeps the 'H' label", req_lines[0].split()[1] == "H", req_lines[0])
    check("a sonnet row without a transcript call renders 'REQ #?'", req_lines[5].split()[1:3] == ["REQ", "#?"], req_lines[5])
    headers = [i for i, line in enumerate(lines) if line.startswith("Turn ")]
    check("two Turn header rows are rendered", len(headers) == 2, lines)
    check("Turn 1 header precedes REQ #1 and Turn 2 header sits between REQ #3 and REQ #4",
          lines.index(next(l for l in lines if "REQ #1" in l)) > headers[0]
          and lines.index(next(l for l in lines if "REQ #3" in l)) < headers[1] < lines.index(next(l for l in lines if "REQ #4" in l)), lines)
    check("Turn 2 header carries the prompt text", '"second prompt"' in lines[headers[1]], lines[headers[1]])

def test_numbering_matches_token_pane():
    from src.format.token_format import format_cache_tracker
    from src.proxy_display.format import format_proxy_block
    print("\n[Test 4] proxy numbering and turn headers equal the token pane's for the same requests")
    turns = _turns()
    token_ansi, _keys, _sticky, _start, _count = format_cache_tracker(turns, {}, 200, 120, 0)
    token_lines = [line for line in _plain_lines("\n".join(token_ansi)) if line.strip()]
    token_numbers = [int(m.group(1)) for line in token_lines for m in [re.search(r"REQ #(\d+)", line)] if m]
    token_headers = [line for line in token_lines if line.startswith("Turn ")]
    entries = _parsed_entries()
    ansi, _ = format_proxy_block(entries, {}, None, None, 200, 120, 0, turns, request_id_by_flow=_request_id_by_flow())
    proxy_lines = [line for line in _plain_lines(ansi) if line.strip()]
    proxy_numbers = [int(m.group(1)) for line in proxy_lines for m in [re.search(r"REQ #(\d+)", line)] if m]
    proxy_headers = [line for line in proxy_lines if line.startswith("Turn ")]
    check("REQ number sequence is identical", proxy_numbers == token_numbers == [1, 2, 3, 4], (proxy_numbers, token_numbers))
    check("Turn header rows are byte-identical", proxy_headers == token_headers, (proxy_headers, token_headers))

def test_refire_and_unmapped_labels():
    from src.proxy_display.format import format_proxy_block
    print("\n[Test 5] a refire sharing a request_id shows REQ #n.m")
    entries = _parsed_entries()
    mapping = {"f1": "r1", "f2": "r2", "f3": "r2", "f4": "r4"}
    ansi, _ = format_proxy_block(entries, {}, None, None, 200, 120, 0, _turns(), request_id_by_flow=mapping)
    labels = [" ".join(line.split()[1:3]) for line in _plain_lines(ansi) if "sonnet" in line]
    check("the second entry of one request_id is REQ #2.1", labels[1:3] == ["REQ #2", "REQ #2.1"], labels)

def _cells(text: str) -> int:
    from src.utils import _cell_width
    return sum(_cell_width(ch) for ch in text)

def _local(iso: str) -> str:
    from src.utils import format_timestamp
    return format_timestamp(iso)

def _pane_rows(pane: str, width: int) -> list:
    from src.format.token_format import format_cache_tracker
    from src.proxy_display.format import format_proxy_block
    turns = _turns()
    if pane == "token":
        ansi = format_cache_tracker(turns, {}, 200, width, 0, copy_feedback={})[0]
        return [line for line in _plain_lines("\n".join(ansi)) if line.strip()]
    ansi, _ = format_proxy_block(_parsed_entries(), {}, None, None, 200, width, 0, turns,
                                 request_id_by_flow=_request_id_by_flow(), copy_feedback={})
    return [line for line in _plain_lines(ansi) if line.strip()]

def _time_columns(rows: list) -> list:
    out = []
    for row in rows:
        body = row.rstrip()
        if body.endswith("⎘"):
            body = body[:-1].rstrip()
        match = re.search(r"(\d\d:\d\d:\d\d)$", body)
        if match and (row.startswith("Turn ") or "REQ #" in row or " #" in row):
            out.append((match.group(1), _cells(body), row))
    return out

def test_right_aligned_times_in_both_panes():
    print("\n[Test 6] time of day right-aligned in one column on turn rows and REQ rows, both panes, narrow and wide")
    for pane, width in (("token", 50), ("token", 120), ("proxy", 50), ("proxy", 120)):
        rows = _pane_rows(pane, width)
        columns = _time_columns(rows)
        turn_rows = [r for r in rows if r.startswith("Turn ")]
        req_rows = [r for r in rows if r.lstrip().startswith("▶")]
        timed_req_rows = [c for c in columns if not c[2].startswith("Turn ")]
        check(f"{pane} w={width}: both turn rows end in a time", sum(1 for c in columns if c[2].startswith("Turn ")) == 2, turn_rows)
        check(f"{pane} w={width}: every mapped REQ row ends in a time before the copy symbol",
              len(timed_req_rows) == 4, (len(timed_req_rows), req_rows))
        check(f"{pane} w={width}: all times end in the same column (width - 3)",
              {c[1] for c in columns} == {width - 3}, sorted({c[1] for c in columns}))
        check(f"{pane} w={width}: every REQ row is exactly {width} cells wide with its copy symbol",
              all(_cells(r) == width for r in req_rows if "REQ #?" not in r and " H " not in r and " S " not in r and r.rstrip().endswith("⎘") and re.search(r"\d\d:\d\d:\d\d\s+⎘$", r)),
              [(_cells(r), r) for r in req_rows])
        expected_turn_times = [_local(t["timestamp"]) for t in _turns()]
        check(f"{pane} w={width}: turn row times are the turn timestamps, no inline [time] left",
              [c[0] for c in columns if c[2].startswith("Turn ")] == expected_turn_times and all("[" not in r for r in turn_rows), turn_rows)

def test_time_survives_truncation():
    print("\n[Test 7] a row too long for the pane is cut, the right-aligned time stays")
    for pane, width in (("token", 62), ("proxy", 40)):
        rows = _pane_rows(pane, width)
        req_rows = [r for r in rows if "REQ #" in r and "REQ #?" not in r]
        check(f"{pane} w={width}: REQ rows contain the ellipsis cut", all("…" in r for r in req_rows), req_rows)
        check(f"{pane} w={width}: REQ rows still end in time and copy symbol, width {width} exact",
              all(re.search(r"\d\d:\d\d:\d\d\s+⎘$", r) and _cells(r) == width for r in req_rows), [(_cells(r), r) for r in req_rows])
    from src.panes.token_search import build_token_search_matches
    matches = build_token_search_matches(_local(_CALL_TIMES["r2"]), _turns(), 120, {})
    check("token pane search matches a REQ by its time text", (0, 1) in matches, matches)

def test_same_time_for_same_req_in_both_panes():
    print("\n[Test 8] the same REQ shows the same time in the token pane and the proxy pane")
    def times(rows):
        out = {}
        for row in rows:
            number = re.search(r"REQ #(\d+)\b|^\s*▶ #(\d+)\b", row)
            clock = re.search(r"(\d\d:\d\d:\d\d)\s+⎘$", row)
            if number and clock:
                out[int(number.group(1) or number.group(2))] = clock.group(1)
        return out
    for width in (50, 120):
        token = times(_pane_rows("token", width))
        proxy = times(_pane_rows("proxy", width))
        expected = {i + 1: _local(_CALL_TIMES[f"r{i + 1}"]) for i in range(4)}
        check(f"w={width}: token pane REQ times equal the transcript call times", token == expected, token)
        check(f"w={width}: proxy pane REQ times equal the token pane's", proxy == token, (proxy, token))

def test_transcript_parser_records_last_entry_time():
    from src.jsonl.jsonl_cache_turns import extract_cache_turns
    print("\n[Test 9] extract_cache_turns keeps the LAST assistant entry time of a request")
    usage = {"cache_read_input_tokens": 10, "cache_creation_input_tokens": 1, "input_tokens": 2, "output_tokens": 3}
    messages = [
        {"type": "user", "userType": "external", "message": {"content": "go"}, "timestamp": "2026-09-24T10:00:00.000Z"},
        {"type": "assistant", "requestId": "rq", "message": {"usage": usage, "content": [{"type": "thinking", "thinking": "t"}]}, "timestamp": "2026-09-24T10:00:05.000Z"},
        {"type": "assistant", "requestId": "rq", "message": {"usage": usage, "content": [{"type": "text", "text": "x"}]}, "timestamp": "2026-09-24T10:00:09.000Z"},
    ]
    turns = extract_cache_turns(messages)
    check("one call, timestamp of the later entry", len(turns[0]["api_calls"]) == 1 and turns[0]["api_calls"][0]["timestamp"] == "2026-09-24T10:00:09.000Z", turns)

def _status_entries() -> list:
    entries = _parsed_entries()
    statuses = {"f1": 200, "f2": 200, "f3": 200, "f4": 200, "f5": 404}
    for entry in entries:
        entry["http_status"] = statuses.get(entry["flow_id"])
    return entries

def test_http_status_marker_and_line() -> None:
    from src.proxy_display.format import format_proxy_block
    from src.proxy_display.proxy_pane_shared import _accumulate_request_ids, _attach_http_status
    print("\n[Test 10] HTTP status: marker on the header row, status line in the expanded section")
    handle = tempfile.NamedTemporaryFile(mode="w", suffix="_response.jsonl", delete=False)
    with handle:
        handle.write(json.dumps({"flow_id": "f4", "request_id": "r4", "status_code": 200, "timestamp": "t"}) + "\n")
        handle.write(json.dumps({"flow_id": "f5", "request_id": "r7", "status_code": 404, "timestamp": "t"}) + "\n")
    path = Path(handle.name)
    by_flow, status = {}, {}
    try:
        _accumulate_request_ids(path, 0, by_flow, status)
    finally:
        path.unlink()
    check("_accumulate_request_ids keeps flow -> request_id and flow -> status_code",
          by_flow == {"f4": "r4", "f5": "r7"} and status == {"f4": 200, "f5": 404}, (by_flow, status))
    entries = _parsed_entries()
    _attach_http_status(entries, status)
    check("entries with a response line carry their status, the others stay pending (None)",
          [e["http_status"] for e in entries] == [None, None, None, None, 200, 404], [e.get("http_status") for e in entries])
    entries = _status_entries()
    rejected_idx = next(i for i, e in enumerate(entries) if e["flow_id"] == "f5")
    ansi, _ = format_proxy_block(entries, {("req", rejected_idx): True}, None, None, 200, 120, 0, _turns(),
                                 request_id_by_flow=_request_id_by_flow(), copy_feedback={})
    lines = [line for line in _plain_lines(ansi) if line.strip()]
    rejected = next(l for l in lines if l.strip().startswith("▼"))
    ok_rows = [l for l in lines if "REQ #" in l and "REQ #?" not in l and "▶" in l]
    check("the rejected row shows [404] on its header row without expanding", "REQ #?" in rejected and "[404]" in rejected, rejected)
    check("200 rows show no marker", ok_rows and all("[200]" not in l and "[pending]" not in l for l in ok_rows), ok_rows)
    check("the expanded section starts with 'status: 404'", any(l.strip() == "status: 404" for l in lines), lines)
    ansi, _ = format_proxy_block(entries, {("req", 3): True}, None, None, 200, 120, 0, _turns(),
                                 request_id_by_flow=_request_id_by_flow(), copy_feedback={})
    check("a finished 200 request shows 'status: 200' when expanded", any(l.strip() == "status: 200" for l in _plain_lines(ansi)))
    pending = _parsed_entries()
    for entry in pending:
        entry["http_status"] = None
    ansi, _ = format_proxy_block(pending, {("req", 1): True}, None, None, 200, 120, 0, _turns(),
                                 request_id_by_flow=_request_id_by_flow(), copy_feedback={})
    plain = _plain_lines(ansi)
    check("a request without a _response line is marked [pending], distinct from finished ones",
          any("[pending]" in l for l in plain) and any("status: pending" in l for l in plain), plain)
    bare = _plain_lines(format_proxy_block(_parsed_entries(), {}, None, None, 200, 120, 0, _turns(),
                                           request_id_by_flow=_request_id_by_flow(), copy_feedback={})[0])
    check("without any response info (no http_status key) nothing changes: no marker at all",
          not any("[" in l and "]" in l and "REQ" in l for l in bare), bare)
    check("REQ numbers and times stay the parity ones from Test 8 (same rows, numbers 1..4)",
          [int(m.group(1)) for l in lines for m in [re.search(r"REQ #(\d+)\b", l)] if m] == [1, 2, 3, 4])

if __name__ == '__main__':
    sys.exit(run_workflow())
