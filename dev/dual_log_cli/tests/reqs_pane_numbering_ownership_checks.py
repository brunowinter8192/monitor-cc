# INFRASTRUCTURE

import io
from contextlib import redirect_stderr

from src.dual_log_cli.cli_args import _parse_args
from src.dual_log_cli.commands import _req_error_text, _req_output_window, _resolve_range
from src.dual_log_cli.render_expand import render_expand_full
from src.dual_log_cli.render_msgs import render_msgs
from src.dual_log_cli.timeline_markers import (
    UnknownRequestNumberError, request_markers, resolve_req_output_range, resolve_req_range_with_next,
)

from dev.dual_log_cli.tests.reqs_pane_numbering_fixtures import _clock, _ownership_payload, _ownership_view, check


# FUNCTIONS

def _raises_text(call) -> str:
    try:
        call()
    except UnknownRequestNumberError as exc:
        return str(exc)
    return ""


def test_msg_start_of_creates_and_continues() -> None:
    _session_dict, boundaries, continues, numbering = _ownership_view()
    starts = {r["flow_id"]: r.get("msg_start") for r in numbering["requests"]}
    check("each located request starts at the assistant reply it answers: c1 0, k1 1, k2 4, c2 7, k3 10",
          starts == {"c1": 0, "k1": 1, "k2": 4, "c2": 7, "k3": 10, "k4": None, "k5": None}, starts)
    markers = request_markers(numbering["requests"])
    check("markers carry the pane numbers 1..5 at those starts",
          {index: m["number"] for index, m in markers.items()} == {0: 1, 1: 2, 4: 3, 7: 4, 10: 5}, markers)


def test_req_range_covers_own_group_and_next() -> None:
    _session_dict, boundaries, continues, numbering = _ownership_view()
    requests = numbering["requests"]
    check("--req 2 (a continue) = its own group [1..3] plus the next request's group [4..6], the tool_use it caused sits at msg 4",
          resolve_req_range_with_next(requests, 2, 2, 12) == (1, 6), resolve_req_range_with_next(requests, 2, 2, 12))
    check("--req 3 reaches the create's group that follows: msgs 4..9",
          resolve_req_range_with_next(requests, 3, 3, 12) == (4, 9))
    check("--req 4 (a create) = its group [7..9] plus the next continue's group [10..12]",
          resolve_req_range_with_next(requests, 4, 4, 12) == (7, 12))
    check("--req 5 whose successor owns nothing = its own group only", resolve_req_range_with_next(requests, 5, 5, 12) == (10, 12))
    check("--req 2 3 spans both groups plus the group after: msgs 1..9", resolve_req_range_with_next(requests, 2, 3, 12) == (1, 9))
    data = {"boundaries": boundaries, "continues": continues, "requests": requests}
    check("the command layer routes transcript numbering to the with-next rule",
          _resolve_range(data, numbering, 2, 2, 12) == (1, 6))


def test_unlocated_continues_own_no_msgs() -> None:
    _session_dict, boundaries, continues, numbering = _ownership_view()
    requests = numbering["requests"]
    raised = False
    try:
        resolve_req_range_with_next(requests, 6, 6, 12)
    except UnknownRequestNumberError:
        raised = True
    check("the opener continue (REQ 6, no tool_result to locate) owns no msgs", raised)
    data = {"boundaries": boundaries, "continues": continues, "requests": requests}
    text = _req_error_text(UnknownRequestNumberError("x"), data, (6, 6))
    check("the message names it a continue whose msgs could not be located", "could not be located" in text and "REQ 6" in text, text)
    unknown = False
    try:
        resolve_req_range_with_next(requests, 99, 99, 12)
    except UnknownRequestNumberError:
        unknown = True
    check("a number outside the recorded requests stays 'not found'", unknown)


def test_msgs_prints_continue_separators() -> None:
    _session_dict, boundaries, continues, numbering = _ownership_view()
    turns = [{"index": i, "role": m["role"], "type": "text", "chars": 4,
              "blocks": [{"label": "text", "type": "text", "chars": 4, "sig_chars": 0, "preview": ""}]}
             for i, m in enumerate(_ownership_payload())]
    out = render_msgs({"boundaries": boundaries, "requests": numbering["requests"], "turns": turns}, 1, 6, numbering["usage"])
    seps = [line for line in out.split("\n") if line.startswith("── REQ")]
    check("msgs 1..6 print the continue separators REQ 2 and REQ 3 with their response-end times",
          [x.split()[2] for x in seps] == ["2", "3"] and _clock("2026-09-04T10:01:05Z") in seps[0] and _clock("2026-09-04T10:02:05Z") in seps[1], seps)
    check("the tool_use msg 4 sits under REQ 3's separator", out.index("── REQ 3") < out.index("[  4]"), out)


def test_expand_req_selects_reply_and_returned_result() -> None:
    _session_dict, boundaries, continues, numbering = _ownership_view()
    requests = numbering["requests"]
    check("expand --req 1 (a create) = the next request's group: reply msg 1 plus the result that came back",
          resolve_req_output_range(requests, 1, 12) == (1, 3), resolve_req_output_range(requests, 1, 12))
    check("expand --req 2 (a continue) = msgs 4..6, the tool_use it produced and the tool_result REQ 3 sent",
          resolve_req_output_range(requests, 2, 12) == (4, 6))
    check("expand --req 3 = msgs 7..9 (the next request is a create)", resolve_req_output_range(requests, 3, 12) == (7, 9))
    check("expand --req 4 = msgs 10..12", resolve_req_output_range(requests, 4, 12) == (10, 12))
    data = {"requests": requests}
    check("the command layer resolves the same window on the transcript path",
          _req_output_window(data, numbering, 2, 12) == (4, 6))


def test_expand_req_errors_and_cli() -> None:
    _session_dict, boundaries, continues, numbering = _ownership_view()
    requests = numbering["requests"]
    text = _raises_text(lambda: resolve_req_output_range(requests, 5, 12))
    check("REQ 5: the next request is an unlocated opener -> 'could not be located'", "could not be located" in text and "REQ 6" in text, text)
    text = _raises_text(lambda: resolve_req_output_range(requests, 6, 12))
    check("the last request's reply is not recorded", "reply is not recorded" in text, text)
    check("an unknown number stays 'not found'", _raises_text(lambda: resolve_req_output_range(requests, 99, 12)) == "REQ 99 not found")
    buffer = io.StringIO()
    with redirect_stderr(buffer):
        window = _req_output_window({"requests": requests}, {"path": "boundaries"}, 2, 12)
    check("without the transcript path expand --req refuses and says why", window is None and "transcript numbering" in buffer.getvalue(), buffer.getvalue())
    by_req = _parse_args(["expand", "s", "--req", "3"], "")
    by_msg = _parse_args(["expand", "s", "5"], "")
    check("argparse: --req replaces the msg argument, a bare msg still parses",
          (by_req.msg, by_req.req) == (None, 3) and (by_msg.msg, by_msg.req) == (5, None), (by_req, by_msg))
    out = render_expand_full({"turns": [{}] * 13, "turn_times": {}, "session": {"stem": "s", "project": "p", "start": "2026-09-04T10:00:00Z"}},
                             None, 4, 6, "", [], None, "what REQ 2 produced")
    check("the header names the REQ instead of an anchor msg", "what REQ 2 produced" in out and "anchor" not in out, out)
