"""dual_log_cli — read-only inspector for src/logs/dual_log/.

Commands:
    sessions                 list every session (start, context, stem), newest first
    sessions <context>       keep only sessions whose context contains that text (substring, any case)
    sessions --since D --until D   bound that listing by start day, inclusive, YYYY-MM-DD
    search <term> [scope]    find a term across the deduplicated timelines, each match reported once
                             scope matches a session's context OR stem; omit it to search all
                             --only restricts hits to one classifier (role, type, or role/type)
    reqs [scope]             per session: a REQ number + time line per request, nothing else —
                             scope matches context OR stem like search; --main/--worker (mutually
                             exclusive) keep only opus/ or worker/ sessions
    reqs [scope] --gap M     only the REQs bracketing a gap of >= M minutes between consecutive
                             requests; the after-REQ carries "  +Nm"; a session with no qualifying
                             gap prints only its "session" header line
    reqs [scope] --merged    merge every session in scope into ONE chronological REQ chain (the
                             prompt cache is shared across a project's workers) instead of one
                             listing per session; each line tagged with its worker/project;
                             combines with --gap, evaluated over the merged chain
    reqs [scope] --rebuild   only REQs where CC > CR (this request's own cache write outweighs
                             what it read back); every printed line carries a "  CR c  CC c" tail
    reqs [scope] --drop      only REQs n where CR(n) < CR(n-1) + CC(n-1) — part of the prefix the
                             PREVIOUS request had cached was not read again; REQ 1 of a chain never
                             qualifies (no predecessor); the line also carries "  −N" (the
                             shortfall). --rebuild/--drop combine with each other (AND), with
                             --gap (filtering the lines --gap would print), and with --merged (the
                             "previous" request is then the merged chain's, across sessions)
    msgs <session>           request groups: a REQ separator (with CR/CC prompt-cache usage when
                             resolvable) listing the system blocks and tools that request sent —
                             in full for the family's first request, else only what changed or is
                             new since the previous one of the same model (the billing header,
                             system block 0, is excluded from that comparison — it changes on
                             every request by construction) — then the msgs that request added, a
                             proxy-transformed msg/block also carrying its strip/inject delta and
                             wire size
    msgs <session> F T       the same, restricted to msg indices F..T (inclusive)
    msgs <session> --req F [T]   the same, restricted to REQ numbers F..T (T defaults to F) — the
                             same numbers the REQ separators already print, translated into the
                             msg-index range that covers them; mutually exclusive with F T above
    turns <session>          one line per turn (everything between two prompts the human/
                             orchestrator typed): turn number, the clock of its first request,
                             total duration split into model time (time spent generating) and tool
                             time (time spent running tools between requests), request count,
                             summed output tokens, and a preview of the prompt that opened it — "?"
                             for the duration/model/tool/token columns when the transcript join
                             this needs does not resolve for the turn
    turns <session> N        one line per REQUEST of turn N instead: REQ number/clock, model
                             seconds, tool seconds (none for the turn's own last request), output
                             tokens, and the tool_use names of that request's own reply
    expand <s> <msg>         full content of that msg, plus what the proxy stripped/injected there
    expand <s> <msg> [--before N] [--after N] [--only X]   full content of the window around it

Usage (from project root, or via bin/duallog once symlinked into PATH):
    ./venv/bin/python -m src.dual_log_cli sessions
    ./venv/bin/python -m src.dual_log_cli search "worker-cli merge" gh_cli_1787939513
    ./venv/bin/python -m src.dual_log_cli search Reißleine websearch --since 2026-08-28
    ./venv/bin/python -m src.dual_log_cli reqs websearch --main
    ./venv/bin/python -m src.dual_log_cli reqs websearch --gap 30
    ./venv/bin/python -m src.dual_log_cli reqs websearch --merged --gap 30
    ./venv/bin/python -m src.dual_log_cli reqs websearch --merged --rebuild
    ./venv/bin/python -m src.dual_log_cli reqs websearch --drop
    ./venv/bin/python -m src.dual_log_cli msgs websearch_1787924727
    ./venv/bin/python -m src.dual_log_cli msgs websearch_1787924727 700 740
    ./venv/bin/python -m src.dual_log_cli msgs websearch_1787924727 --req 259
    ./venv/bin/python -m src.dual_log_cli msgs websearch_1787924727 --req 259 261
    ./venv/bin/python -m src.dual_log_cli turns websearch_1787924727
    ./venv/bin/python -m src.dual_log_cli turns websearch_1787924727 1
    ./venv/bin/python -m src.dual_log_cli expand websearch_1787924727 721
    ./venv/bin/python -m src.dual_log_cli expand websearch_1787924727 721 --before 2 --after 1

<session> is a full stem or any unambiguous substring of one. The log directory is resolved from
MONITOR_CC_ROOT, else from the repo root, else from the main checkout when run inside a worktree.
Every access is read-only — nothing under src/logs/dual_log/ is written, created or locked.
"""

# INFRASTRUCTURE
import argparse
import os
import sys
from datetime import datetime

from .classifier import BadClassifierError, ONLY_FORMS, matches_only, parse_only
from .discovery import (
    AmbiguousSessionError,
    UnknownSessionError,
    build_session,
    filter_by_family,
    filter_sessions,
    group_streams,
    list_sessions,
    resolve_dual_log_dir,
    resolve_stem,
)
from .overlay import build_overlay, build_sys_tool_overlay
from .project_map import build_project_map
from .render import (
    render_expand_full,
    render_msgs,
    render_reqs,
    render_reqs_merged,
    render_search,
    render_sessions,
    render_turn_detail,
    render_turns,
)
from .search import find_matches
from .timeline import (
    AmbiguousRequestNumberError,
    UnknownRequestNumberError,
    UnknownTurnNumberError,
    build_turn_requests,
    build_turn_rows,
    full_turn,
    load_timeline,
    resolve_req_range,
    turn_openers,
)
from .usage import build_request_times_by_flow, build_usage_by_flow

# ORCHESTRATOR


def main(argv: list) -> int:
    args = _parse_args(argv)
    dual_log_dir = resolve_dual_log_dir()
    if not dual_log_dir.exists():
        print(f"dual_log directory not found: {dual_log_dir}", file=sys.stderr)
        return 2
    if args.command == "sessions":
        return _run_sessions(dual_log_dir, args)
    if args.command == "search":
        return _run_search(dual_log_dir, args)
    if args.command == "reqs":
        return _run_reqs(dual_log_dir, args)
    if args.command == "msgs":
        return _run_msgs(dual_log_dir, args)
    if args.command == "turns":
        return _run_turns(dual_log_dir, args)
    return _run_expand(dual_log_dir, args)


# FUNCTIONS


def _parse_args(argv: list) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.dual_log_cli",
        description="Read-only inspector for the proxy dual_log quartet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sessions = sub.add_parser("sessions", help="list all sessions, newest first")
    sessions.add_argument("context", nargs="?", default="", metavar="CONTEXT",
                          help="only sessions whose context contains this text, e.g. websearch")
    sessions.add_argument("--since", default="", metavar="YYYY-MM-DD",
                          help="only sessions started on or after this day (inclusive)")
    sessions.add_argument("--until", default="", metavar="YYYY-MM-DD",
                          help="only sessions started on or before this day (inclusive)")
    msgs = sub.add_parser(
        "msgs",
        help="one classifier line per msg of a session",
        description=(
            "Prints the session as request groups: a `── REQ n  HH:MM:SS ──` separator — "
            "`── REQ n  HH:MM:SS  CR c  CC c ──` when the owning request's prompt-cache usage "
            "resolves against CC's own transcript, unresolved ones staying plain — then the "
            "`[idx] role type chars` line of every msg that request added. Nothing else — no "
            "totals, no previews. A multi-block msg shows its block count in place of the type, "
            "followed by one indented sub-line per block (its own type/tool-name and chars, "
            "right-aligned to the same column). A msg or block the proxy stripped from or "
            "injected into carries an extra `−N +M → Wc` tail after its chars (chars removed, "
            "chars added, resulting wire size), plus ` by REQ n` when a LATER request performed "
            "the transform than the one whose separator the msg sits under; an untouched line "
            "stays exactly as before. FROM and TO are inclusive msg indices; omit both "
            "for the whole session, or give FROM alone to run from there to the last msg; a "
            "partially shown group keeps its separator. --req F [T] selects the same output by "
            "REQ number instead of msg index (T defaults to F) — the exact numbers the REQ "
            "separators already print — and is mutually exclusive with the FROM/TO positionals."
        ),
    )
    # "from" is a Python keyword, so the code-side name has to differ from the user-facing one
    msgs.add_argument("session", help="session stem or unambiguous substring")
    msgs.add_argument("from_msg", nargs="?", type=int, default=None, metavar="FROM",
                      help="first msg index (inclusive, default 0)")
    msgs.add_argument("to_msg", nargs="?", type=int, default=None, metavar="TO",
                      help="last msg index (inclusive, default the session's last msg)")
    msgs.add_argument("--req", nargs="+", type=int, default=None, metavar="F [T]",
                      help="REQ number range instead of msg indices, T defaults to F; "
                           "mutually exclusive with FROM/TO")
    turns = sub.add_parser(
        "turns",
        help="one line per turn: duration split into model time and tool wall time",
        description=(
            "Prints one line per turn of a session, in order — a turn is what happens between "
            "two prompts the human (or, for a worker, the orchestrator via `worker-cli send`) "
            "typed: the model runs many requests, each followed by tool execution, until it "
            "answers with text and goes idle. Each line carries the turn number, the local clock "
            "of its first request, total duration, model time (summed stream time per request), "
            "tool time (summed gap between one request's stream end and the next request's send — "
            "the turn's last request contributes none), request count, summed output tokens, and "
            "a one-line preview of the prompt that opened the turn. The duration/model/tool/token "
            "columns print \"?\" for a turn whose requests do not all resolve against CC's own "
            "transcript (the same join `msgs`' CR/CC separator uses) — the clock and request "
            "count still print, since they need no transcript join at all. Give a turn number N "
            "(as printed by the bare listing) to see one line per REQUEST of that turn instead: "
            "REQ number/clock, model seconds, tool seconds (next request's send minus this "
            "stream end; the turn's own last request shows none), output tokens, and the "
            "tool_use names of that request's own reply (e.g. `Bash`, or nothing for a "
            "text-only reply) — each column resolves independently, \"?\" only where it does not."
        ),
    )
    turns.add_argument("session", help="session stem or unambiguous substring")
    turns.add_argument("turn", nargs="?", type=int, default=None, metavar="N",
                       help="show one line per request of turn N instead of the bare per-turn listing")
    expand = sub.add_parser(
        "expand",
        help="full content of one msg, or of a window around it",
        description=(
            "Dumps the complete content of every block of every selected msg, as CC sent it. A "
            "block the proxy transformed is followed by `── stripped by REQ n ──` / `── injected "
            "by REQ n ──` sections showing what it removed and what it put there instead; an "
            "untouched block shows content only. --before/--after widen the window around the "
            "anchor and default to 0, so a bare call prints exactly the anchor msg. --only selects "
            "msgs by role and/or ANY block type; a selected msg always shows ALL of its blocks."
        ),
    )
    expand.add_argument("session", help="session stem or unambiguous substring")
    expand.add_argument("msg", type=int, help="anchor msg index")
    expand.add_argument("--before", type=int, default=0,
                        help="msgs before the anchor (0 and up, default 0)")
    expand.add_argument("--after", type=int, default=0,
                        help="msgs after the anchor (0 and up, default 0)")
    expand.add_argument("--only", default="", metavar="CLASSIFIER",
                        help=f"keep only msgs matching {ONLY_FORMS}")
    search = sub.add_parser("search", help="find a term across the deduplicated timelines")
    search.add_argument("term", help="literal term to look for (no regex)")
    search.add_argument("scope", nargs="?", default="", metavar="SCOPE",
                        help="only sessions whose context OR stem contains this text; omit to search all")
    search.add_argument("--since", default="", metavar="YYYY-MM-DD",
                        help="only sessions started on or after this day (inclusive)")
    search.add_argument("--until", default="", metavar="YYYY-MM-DD",
                        help="only sessions started on or before this day (inclusive)")
    search.add_argument("--only", default="", metavar="CLASSIFIER",
                        help=f"restrict hits to msgs matching {ONLY_FORMS}")
    search.add_argument("--case-sensitive", action="store_true", help="match case exactly (default: ignore case)")
    reqs = sub.add_parser(
        "reqs",
        help="one REQ number + time per line, per session",
        description=(
            "Prints, per session, a `session <stem>` line followed by one `REQ n   HH:MM:SS` line "
            "per request — the exact numbers and timestamps `msgs`' own separators print, in the "
            "same order (re-fires collapsed, a restart handled exactly the way `msgs` handles it). "
            "No other columns, no counts, no CR/CC. --gap MINUTES replaces the full per-session "
            "listing with only the REQs bracketing a consecutive gap of at least that many whole "
            "minutes — the after-REQ of each qualifying gap carries `  +Nm`; a REQ that is both the "
            "end of one qualifying gap and the start of the next prints once; a session with no "
            "qualifying gap prints only its `session` header line, so the reader sees it was "
            "checked. Omitting --gap reproduces the plain listing exactly. --merged combines every "
            "session in scope into ONE chronological REQ chain instead of one listing per session — "
            "the prompt cache hangs on the shared system/tools prefix every worker of a project "
            "sends, so a request from ANY session in scope keeps it warm for every other; a "
            "`merged <N> sessions` header replaces the per-session `session <stem>` lines, and each "
            "REQ line carries `  <tag>` (its context after the last `/` — a worker's name, or a "
            "main session's project). --merged --gap evaluates the SAME bracketing rule over the "
            "merged chain, so a within-session gap another session's request happens to fall "
            "inside no longer qualifies, and a gap that only exists ACROSS sessions does. "
            "--rebuild keeps only REQs where CC > CR (the request's own cache write outweighed "
            "what it read back); --drop keeps only REQs n where CR(n) < CR(n-1) + CC(n-1), i.e. "
            "part of the prefix the PREVIOUS request had cached was NOT read again by n — the "
            "previous request is the previous one in the same session, or in the merged chain when "
            "--merged is given; REQ 1 of a chain never qualifies for --drop (no predecessor). "
            "Every line --rebuild/--drop prints carries a `  CR c  CC c` tail; --drop also appends "
            "`  −N` (the shortfall, CR(n-1)+CC(n-1) − CR(n)). Both combine with each other (AND), "
            "with --gap (filtering exactly the lines --gap would print, before-line included), and "
            "with --merged; a REQ whose usage does not resolve is skipped under either flag."
        ),
    )
    reqs.add_argument("scope", nargs="?", default="", metavar="SCOPE",
                      help="only sessions whose context OR stem contains this text; omit to search all")
    reqs.add_argument("--since", default="", metavar="YYYY-MM-DD",
                      help="only sessions started on or after this day (inclusive)")
    reqs.add_argument("--until", default="", metavar="YYYY-MM-DD",
                      help="only sessions started on or before this day (inclusive)")
    reqs_family = reqs.add_mutually_exclusive_group()
    reqs_family.add_argument("--main", action="store_true", help="only main sessions (context starts with opus/)")
    reqs_family.add_argument("--worker", action="store_true", help="only worker sessions (context starts with worker/)")
    reqs.add_argument("--gap", type=int, default=None, metavar="MINUTES",
                      help="show only the REQs bracketing a consecutive gap of at least this many minutes")
    reqs.add_argument("--merged", action="store_true",
                      help="merge every session in scope into one chronological REQ chain, each line tagged by session")
    reqs.add_argument("--rebuild", action="store_true",
                      help="only REQs where CC > CR; every printed line carries a CR/CC tail")
    reqs.add_argument("--drop", action="store_true",
                      help="only REQs whose predecessor's cached prefix was not fully read back; carries a CR/CC + shortfall tail")
    return parser.parse_args(argv)


# A day flag must be exactly YYYY-MM-DD — strptime rejects both bad shapes and impossible dates
def _valid_day(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


# Exit code 2 plus a stderr line for a malformed day flag; 0 when both are fine
def _reject_bad_days(args: argparse.Namespace) -> int:
    for flag, value in (("--since", args.since), ("--until", args.until)):
        if value and not _valid_day(value):
            print(f"{flag}: {value!r} is not a valid date, expected YYYY-MM-DD", file=sys.stderr)
            return 2
    return 0


# sessions — inventory built from the _forwarded streams only, optionally date-bounded
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


# Resolve a session argument to a loaded timeline, or (None, exit_code) on a bad argument
def _load_for(dual_log_dir, session_arg: str) -> tuple:
    try:
        stem = resolve_stem(dual_log_dir, session_arg)
    except (AmbiguousSessionError, UnknownSessionError) as exc:
        print(str(exc), file=sys.stderr)
        return None, 2
    session = build_session(stem, group_streams(dual_log_dir)[stem], build_project_map())
    return load_timeline(session), 0


# search — scoped like `sessions`, then the same last-request reconstruction per session, so every
# match is deduplicated. A session whose timeline cannot be loaded is skipped, not fatal: one
# truncated log must not hide the matches in the other sixty.
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
        except Exception:
            skipped += 1
            continue
        hits = find_matches(data["payload"], args.term, args.case_sensitive, wanted)
        if hits:
            results.append((session, hits))
    sys.stdout.write(render_search(args.term, args.case_sensitive, results, skipped))
    return 0


# reqs — scoped like `search`, same per-session last-request reconstruction (skip-on-unloadable,
# not fatal), plus --main/--worker narrowing to sessions whose context starts with "opus/" or
# "worker/". No matcher, no hit filtering — every session that loads contributes its own REQ list,
# optionally reduced to only the REQs bracketing a qualifying --gap, optionally merged across
# every session in scope into one chronological chain (--merged) — session SELECTION is identical
# either way, only which render function turns `results` into text differs. --rebuild/--drop
# additionally need each contributing session's own CR/CC map (`usage.build_usage_by_flow`, the
# SAME per-request join `msgs` already resolves) — built only when either flag is set, so a plain
# `reqs` run never pays for the transcript-store join at all.
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
    for session in sessions:
        try:
            data = load_timeline(session)
        except Exception:
            skipped += 1
            continue
        results.append((session, data["boundaries"]))
    usage_by_stem = None
    if args.rebuild or args.drop:
        usage_by_stem = {
            session["stem"]: build_usage_by_flow(session, boundaries)
            for session, boundaries in results
        }
    if args.merged:
        sys.stdout.write(render_reqs_merged(results, skipped, args.gap, usage_by_stem, args.rebuild, args.drop))
    else:
        sys.stdout.write(render_reqs(results, skipped, args.gap, usage_by_stem, args.rebuild, args.drop))
    return 0


# msgs — one classifier line per msg, optionally bounded to an inclusive FROM..TO index range, or
# to an inclusive REQ number range (--req F [T], mutually exclusive with FROM/TO) translated into
# the equivalent msg-index range before falling into the exact same rendering path.
def _run_msgs(dual_log_dir, args: argparse.Namespace) -> int:
    data, code = _load_for(dual_log_dir, args.session)
    if data is None:
        return code
    last = len(data["turns"]) - 1
    if last < 0:
        print("session carries no msgs", file=sys.stderr)
        return 2
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
            start, end = resolve_req_range(data["boundaries"], req_from, req_to, last)
        except (UnknownRequestNumberError, AmbiguousRequestNumberError) as exc:
            print(str(exc), file=sys.stderr)
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
    usage_by_flow = build_usage_by_flow(data["session"], data["boundaries"])
    overlay = build_overlay(data["session"], data["family"], data["boundaries"])
    sys_tool_overlay = build_sys_tool_overlay(data["session"], data["family"], data["boundaries"])
    sys.stdout.write(render_msgs(data, start, end, usage_by_flow, overlay, sys_tool_overlay))
    return 0


# turns — a single session, like msgs/expand (no scope, no date window): the transcript join
# (usage.build_request_times_by_flow, the SAME per-request join `msgs`' CR/CC resolves, joined by
# requestId rather than by cache figures) feeds timeline.build_turn_rows, which does the turn
# grouping and duration arithmetic; render_turns only lays the rows out. `turns <session> N`
# (2026-09-09) routes the SAME loaded data + times_by_flow through timeline.build_turn_requests
# instead, for one line per request of turn N — UnknownTurnNumberError (raised for N outside
# 1..total, the SAME range `turn_openers` itself defines) is caught and its own message printed,
# mirroring `msgs --req`'s UnknownRequestNumberError handling above.
def _run_turns(dual_log_dir, args: argparse.Namespace) -> int:
    data, code = _load_for(dual_log_dir, args.session)
    if data is None:
        return code
    if not data["turns"]:
        print("session carries no msgs", file=sys.stderr)
        return 2
    if not turn_openers(data["turns"]):
        print("session carries no turn-opening msgs", file=sys.stderr)
        return 2
    times_by_flow = build_request_times_by_flow(data["session"], data["boundaries"])
    if args.turn is None:
        rows = build_turn_rows(data["turns"], data["boundaries"], times_by_flow)
        sys.stdout.write(render_turns(rows))
        return 0
    try:
        detail_rows = build_turn_requests(data["turns"], data["boundaries"], times_by_flow, args.turn)
    except UnknownTurnNumberError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    sys.stdout.write(render_turn_detail(detail_rows))
    return 0


# expand — the full content of the anchor msg, widened by --before/--after, optionally filtered
def _run_expand(dual_log_dir, args: argparse.Namespace) -> int:
    data, code = _load_for(dual_log_dir, args.session)
    if data is None:
        return code
    msgs = data["turns"]
    if args.msg < 0 or args.msg >= len(msgs):
        print(f"msg {args.msg} out of range (0..{len(msgs) - 1})", file=sys.stderr)
        return 2
    try:
        wanted = parse_only(args.only)
    except BadClassifierError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.before < 0 or args.after < 0:
        print("--before and --after must be 0 or greater", file=sys.stderr)
        return 2
    start, end = _window(args.msg, args.before, args.after, len(msgs))
    dumped = [
        (msg, full_turn(data["payload"], msg["index"]))
        for msg in msgs[start:end + 1]
        if matches_only(msg["role"], [b["type"] for b in msg["blocks"]], wanted)
    ]
    # msgs also builds this overlay now (for its own delta tail); sessions/search still never
    # read the _stripped/_injected streams, so their output cannot move with either one
    overlay = build_overlay(data["session"], data["family"], data["boundaries"])
    sys.stdout.write(render_expand_full(data, args.msg, start, end, args.only, dumped, overlay))
    return 0


# Clamp an anchor-centred window to the msg list
def _window(anchor: int, before: int, after: int, total: int) -> tuple:
    return max(0, anchor - before), min(total - 1, anchor + after)


if __name__ == "__main__":
    # Piped into `head`/`less`, the reader closes the pipe early. The EPIPE can surface at the
    # write itself OR at the interpreter's shutdown flush, and only the first is catchable here —
    # so stdout is flushed INSIDE the guard, and on failure its fd is redirected to /dev/null so
    # the shutdown flush has nothing left that can fail. Without the redirect Python prints
    # "Exception ignored while flushing sys.stdout" after main() has already returned.
    exit_code = 0
    try:
        exit_code = main(sys.argv[1:])
        sys.stdout.flush()
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        exit_code = 0
    sys.exit(exit_code)
