# INFRASTRUCTURE

from dev.dual_log_cli.tests.reqs_pane_numbering_fixtures import _clock, _render_filtered, _req_lines, _unmapped_turn_view, check


# FUNCTIONS

def test_unmapped_req_sits_in_its_turn_by_send_time() -> None:
    view = _unmapped_turn_view()
    out = _render_filtered(view)
    lines = [l for l in out.split("\n") if l.startswith("REQ") or l.startswith("── turn")]
    kinds = [l.split()[1] if l.startswith("REQ") else "T" + l.split()[2] for l in lines]
    check("both rejected attempts sit inside turn 2, before/among the mapped REQs of that turn",
          kinds == ["T1", "1", "T2", "?", "2", "3", "?", "4"], lines)
    turn2 = next(l for l in lines if l.startswith("── turn 2"))
    check("the separator shows the prompt time 10:20:00, not the first REQ's time",
          f"turn 2  {_clock('2026-09-04T10:20:00Z')}  " in turn2 and _clock("2026-09-04T10:20:01Z") not in turn2, turn2)
    check("the span still runs from the first to the last REQ of the turn (10:20:01 -> 10:25:15)", "5m14s" in turn2, turn2)
    only_turn_2 = _render_filtered(view, turn=2)
    check("--turn 2 keeps the REQ ? rows of that turn", only_turn_2.count("REQ ?") == 2 and "── turn 1" not in only_turn_2, only_turn_2)


def test_unmapped_req_stays_out_of_gap_pairs() -> None:
    out = _render_filtered(_unmapped_turn_view(), gap=2)
    lines = [l for l in out.split("\n") if l.startswith("REQ")]
    check("--gap 2 pairs the numbered REQs 3 -> 4 (4m05s) and never lists a REQ ?", [l.split()[1] for l in lines] == ["3", "4"], lines)


def test_non_200_status_is_visible_on_the_req_line() -> None:
    view = _unmapped_turn_view()
    out = _render_filtered(view)
    rejected = [l for l in out.split("\n") if l.startswith("REQ ?")]
    check("both rejected continues print their status right after the time, before CR/CC",
          len(rejected) == 2 and all(f"  404  CR ?" in l for l in rejected)
          and rejected[0].startswith(f"REQ ?   {_clock('2026-09-04T10:20:01Z')}  404"), rejected)
    numbered = [l for l in out.split("\n") if l.startswith("REQ ") and not l.startswith("REQ ?")]
    check("numbered 200 rows are byte-unchanged: no status text", all("404" not in l and "200" not in l for l in numbered), numbered)
    check("--gap output is unchanged by the status column", [l.split()[1] for l in _req_lines(_render_filtered(view, gap=2))] == ["3", "4"])
    statuses = {r["flow_id"]: r["http_status"] for r in view[3]["requests"]}
    check("every main-thread request carries its response status", statuses == {"f1": 200, "u1": 404, "f2": 200, "k1": 200, "u2": 404, "k2": 200}, statuses)
