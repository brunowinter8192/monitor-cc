# INFRASTRUCTURE
import argparse
import sys
from datetime import datetime

from src.dual_log_cli.classifier import BadClassifierError, matches_only, parse_only
from src.dual_log_cli.diagnostics import report_skip
from src.dual_log_cli.discovery import (
    AmbiguousSessionError,
    UnknownSessionError,
    build_session,
    filter_by_family,
    filter_sessions,
    group_streams,
    list_sessions,
    resolve_stem,
)
from src.dual_log_cli.numbering import build_session_numbering
from src.dual_log_cli.overlay import build_overlay, build_sys_tool_overlay
from src.dual_log_cli.project_map import build_project_index
from src.dual_log_cli.render_expand import render_expand_full
from src.dual_log_cli.render_msgs import render_msgs
from src.dual_log_cli.render_reqs import render_reqs, render_reqs_merged
from src.dual_log_cli.render_search import render_search
from src.dual_log_cli.render_sessions import render_sessions
from src.dual_log_cli.search import find_matches
from src.dual_log_cli.timeline import load_timeline
from src.dual_log_cli.timeline_markers import (
    AmbiguousRequestNumberError, UnknownRequestNumberError, resolve_req_output_range, resolve_req_range,
    resolve_req_range_with_next,
)
from src.dual_log_cli.timeline_turns import full_turn

# FUNCTIONS


def _run_sessions(dual_log_dir, args: argparse.Namespace) -> int:
    code = _reject_bad_days(args)
    if code:
        return code
    sessions = filter_sessions(
        list_sessions(dual_log_dir),
        context=args.context,
        since=args.since,
        until=args.until,
    )
    sys.stdout.write(render_sessions(sessions))
    return 0


def _reject_bad_days(args: argparse.Namespace) -> int:
    for flag, value in (("--since", args.since), ("--until", args.until)):
        if value and not _valid_day(value):
            print(f"{flag}: {value!r} is not a valid date, expected YYYY-MM-DD", file=sys.stderr)
            return 2
    return 0


def _valid_day(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _run_search(dual_log_dir, args: argparse.Namespace) -> int:
    if not args.term.strip():
        print("search term is empty", file=sys.stderr)
        return 2
    code = _reject_bad_days(args)
    if code:
        return code
    try:
        wanted = parse_only(args.only)
    except BadClassifierError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    sessions = filter_sessions(
        list_sessions(dual_log_dir),
        scope=args.scope,
        since=args.since,
        until=args.until,
    )
    results, skipped = [], 0
    for session in sessions:
        try:
            data = load_timeline(session)
        except (FileNotFoundError, ValueError) as exc:
            report_skip("timeline", session["stem"], f"{type(exc).__name__}: {exc}")
            skipped += 1
            continue
        hits = find_matches(data["payload"], args.term, args.case_sensitive, wanted)
        if hits:
            results.append((session, hits))
    sys.stdout.write(render_search(args.term, args.case_sensitive, results, skipped))
    return 0


def _run_reqs(dual_log_dir, args: argparse.Namespace) -> int:
    code = _reject_bad_days(args)
    if code:
        return code
    if args.gap is not None and args.gap < 0:
        print("--gap must be 0 or greater", file=sys.stderr)
        return 2
    sessions = filter_sessions(
        list_sessions(dual_log_dir),
        scope=args.scope,
        since=args.since,
        until=args.until,
    )
    sessions = filter_by_family(sessions, main=args.main, worker=args.worker)
    results, skipped = [], 0
    turns_by_stem = {}
    continues_by_stem = {}
    for session in sessions:
        try:
            data = load_timeline(session)
        except (FileNotFoundError, ValueError) as exc:
            report_skip("timeline", session["stem"], f"{type(exc).__name__}: {exc}")
            skipped += 1
            continue
        results.append((session, data["boundaries"]))
        turns_by_stem[session["stem"]] = data["turns"]
        continues_by_stem[session["stem"]] = data["continues"]
    numbering_by_stem = {
        session["stem"]: build_session_numbering(session, boundaries, continues_by_stem[session["stem"]])
        for session, boundaries in results
    }
    usage_by_stem = {stem: numbering["usage"] for stem, numbering in numbering_by_stem.items()}
    pane_turns_by_stem = {stem: numbering["pane_turns"] for stem, numbering in numbering_by_stem.items()}
    _report_numbering_paths(numbering_by_stem)
    render = render_reqs_merged if args.merged else render_reqs
    sys.stdout.write(render(
        results, skipped, args.turn, args.gap, usage_by_stem, args.rebuild, args.drop, turns_by_stem,
        continues_by_stem, pane_turns_by_stem))
    return 0


def _report_numbering_paths(numbering_by_stem: dict) -> None:
    fallback = [f"{stem} ({numbering['reason']})" for stem, numbering in numbering_by_stem.items() if numbering["path"] != "transcript"]
    transcript = len(numbering_by_stem) - len(fallback)
    line = f"numbering: {transcript} session(s) via transcript (pane REQ numbers, response-end times)"
    if fallback:
        line += f"; {len(fallback)} via boundaries fallback, transcript unresolved (create requests only, own numbers, send times): {', '.join(fallback)}"
    print(line, file=sys.stderr)


def _run_msgs(dual_log_dir, args: argparse.Namespace) -> int:
    data, code = _load_for(dual_log_dir, args.session)
    if data is None:
        return code
    last = len(data["turns"]) - 1
    if last < 0:
        print("session carries no msgs", file=sys.stderr)
        return 2
    numbering = _numbered_view(data)
    if args.req is not None:
        if args.from_msg is not None or args.to_msg is not None:
            print("--req cannot be combined with FROM/TO", file=sys.stderr)
            return 2
        if len(args.req) not in (1, 2):
            print("--req takes one or two REQ numbers: --req F [T]", file=sys.stderr)
            return 2
        req_from = args.req[0]
        req_to = args.req[1] if len(args.req) > 1 else req_from
        try:
            start, end = _resolve_range(data, numbering, req_from, req_to, last)
        except (UnknownRequestNumberError, AmbiguousRequestNumberError) as exc:
            print(_req_error_text(exc, data, (req_from, req_to)), file=sys.stderr)
            return 2
        if end < start:
            print(f"REQ {req_to} ends before REQ {req_from} begins (msg {end} < msg {start})", file=sys.stderr)
            return 2
    else:
        start = 0 if args.from_msg is None else args.from_msg
        end = last if args.to_msg is None else args.to_msg
        for label, value in (("FROM", start), ("TO", end)):
            if value < 0 or value > last:
                print(f"{label} {value} out of range (0..{last})", file=sys.stderr)
                return 2
        if end < start:
            print(f"TO {end} is before FROM {start}", file=sys.stderr)
            return 2
    usage_by_flow = numbering["usage"]
    overlay = build_overlay(data["session"], data["family"], data["requests"])
    sys_tool_overlay = build_sys_tool_overlay(data["session"], data["family"], data["requests"])
    sys.stdout.write(render_msgs(data, start, end, usage_by_flow, overlay, sys_tool_overlay))
    return 0


def _load_for(dual_log_dir, session_arg: str) -> tuple:
    try:
        stem = resolve_stem(dual_log_dir, session_arg)
    except (AmbiguousSessionError, UnknownSessionError) as exc:
        print(str(exc), file=sys.stderr)
        return None, 2
    session = build_session(stem, group_streams(dual_log_dir)[stem], build_project_index())
    return load_timeline(session), 0


def _numbered_view(data: dict) -> dict:
    messages = (data.get("payload") or {}).get("messages") or []
    numbering = build_session_numbering(
        data["session"], data["boundaries"], data["continues"], messages=messages)
    _report_numbering_paths({data["session"]["stem"]: numbering})
    data["requests"] = numbering.get("requests") or data["boundaries"]
    return numbering


def _resolve_range(data: dict, numbering: dict, req_from: int, req_to: int, last: int) -> tuple:
    if numbering["path"] == "transcript":
        return resolve_req_range_with_next(data["requests"], req_from, req_to, last)
    return resolve_req_range(data["boundaries"], req_from, req_to, last)


def _req_error_text(exc: Exception, data: dict, requested: tuple) -> str:
    unlocated = {request.get("pane_number") for request in data["continues"] if "msg_start" not in request} - {None}
    hit = [number for number in requested if number in unlocated]
    if isinstance(exc, UnknownRequestNumberError) and hit:
        return (f"REQ {hit[0]} is a continue request whose msgs could not be located "
                f"(a turn opener, or newer than the last recorded payload); it owns no msgs")
    return str(exc)


def _run_expand(dual_log_dir, args: argparse.Namespace) -> int:
    data, code = _load_for(dual_log_dir, args.session)
    if data is None:
        return code
    msgs = data["turns"]
    if (args.msg is None) == (args.req is None):
        print("expand takes exactly one of: a msg index, or --req N", file=sys.stderr)
        return 2
    try:
        wanted = parse_only(args.only)
    except BadClassifierError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.before < 0 or args.after < 0:
        print("--before and --after must be 0 or greater", file=sys.stderr)
        return 2
    numbering = _numbered_view(data)
    if args.req is not None:
        window = _req_output_window(data, numbering, args.req, len(msgs) - 1)
        if window is None:
            return 2
        start, end = max(0, window[0] - args.before), min(len(msgs) - 1, window[1] + args.after)
        anchor, scope_label = None, f"what REQ {args.req} produced"
    else:
        if args.msg < 0 or args.msg >= len(msgs):
            print(f"msg {args.msg} out of range (0..{len(msgs) - 1})", file=sys.stderr)
            return 2
        start, end = _window(args.msg, args.before, args.after, len(msgs))
        anchor, scope_label = args.msg, ""
    dumped = [
        (msg, full_turn(data["payload"], msg["index"]))
        for msg in msgs[start:end + 1]
        if matches_only(msg["role"], [b["type"] for b in msg["blocks"]], wanted)
    ]
    overlay = build_overlay(data["session"], data["family"], data["requests"])
    sys.stdout.write(render_expand_full(data, anchor, start, end, args.only, dumped, overlay, scope_label))
    return 0


def _req_output_window(data: dict, numbering: dict, req_number: int, last: int):
    if numbering["path"] != "transcript":
        print("expand --req needs the transcript numbering, which did not resolve for this session", file=sys.stderr)
        return None
    try:
        return resolve_req_output_range(data["requests"], req_number, last)
    except UnknownRequestNumberError as exc:
        print(str(exc), file=sys.stderr)
        return None


def _window(anchor: int, before: int, after: int, total: int) -> tuple:
    return max(0, anchor - before), min(total - 1, anchor + after)
