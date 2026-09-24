# INFRASTRUCTURE
import json
import re
import sys
import tempfile
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_RESULTS = []

_SYSTEM_DELTA = {"0": {"type": "text", "text": "x-anthropic-billing-header: cc_version=1"}}
_TOOLS_DELTA = {"0": {"name": "Bash", "description": "d", "input_schema": {}}}
_BEFORE_TURN_2 = "2026-09-24T10:05:00.000Z"
_TURN_2_START = "2026-09-24T10:10:00.000Z"


# ORCHESTRATOR

def run_workflow():
    print("=" * 70)
    print("REQ prefix and turn header rows (src/proxy_display/format.py)")
    print("=" * 70)
    test_continue_entries_do_not_corrupt_accumulator()
    test_lazy_load_of_continue_and_following_create()
    test_req_prefix_and_turn_headers()
    test_numbering_matches_token_pane()
    test_refire_and_unmapped_labels()
    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)
    return passed == total


# FUNCTIONS

def check(label, condition, detail=""):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    if not condition and detail != "":
        print(f"        detail: {detail}")
    return condition


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
            "output_tokens": 50, "content_blocks": []}


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


if __name__ == "__main__":
    sys.exit(0 if run_workflow() else 1)
