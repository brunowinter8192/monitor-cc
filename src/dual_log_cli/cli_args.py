# INFRASTRUCTURE
import argparse

from .classifier import ONLY_FORMS

_REQS_DESCRIPTION = (
    "Prints, per session, a `session <stem>` line, then every REQ grouped under its own "
    "turn separator (`── turn n  HH:MM:SS  SPAN  <preview> ──` — a turn is what happens "
    "between two prompts the human/orchestrator typed, SPAN is that turn's last REQ send "
    "minus its first, no transcript join, only send times a session already has) — turn "
    "grouping is ALWAYS on; a session with no turn opener at all prints its REQ lines with "
    "no separators. Every `REQ n   HH:MM:SS` line carries `  CR c  CC c` (prompt-cache "
    "usage, joined via the same transcript-store lookup `msgs` uses), `CR ?  CC ?` when "
    "the flow does not resolve. Every other flag is a pure filter or selector over this "
    "SAME fixed form, and they all combine (AND). --turn N narrows FIRST, keeping only "
    "turn N of each session in scope (its separator plus its own REQ lines) — a session "
    "missing that turn prints only its `session` header line. --gap MINUTES then keeps "
    "only the REQs bracketing a consecutive gap of at least that many whole minutes "
    "(same session unless --merged, in which case chronological neighbors across every "
    "session in scope); a turn's separator prints only when at least one of its OWN REQ "
    "lines survives — the separator's own clock/span/preview are always that turn's WHOLE "
    "figures, never recomputed from whichever REQs a filter happened to keep. --rebuild "
    "keeps only REQs where CC > CR (the request's own cache write outweighed what it read "
    "back); --drop keeps only REQs n where CR(n) < CR(n-1) + CC(n-1), i.e. part of the "
    "prefix the PREVIOUS request had cached was NOT read again by n — the previous request "
    "is always the SAME session's own previous one, --merged or not; REQ 1 of a session "
    "never qualifies for --drop (no predecessor). A REQ whose usage (or, for --drop, its "
    "predecessor's) does not resolve fails --rebuild/--drop outright. --merged combines "
    "every session in scope into ONE chronological REQ chain instead of one listing per "
    "session — the prompt cache hangs on the shared system/tools prefix every worker of a "
    "project sends, so a request from ANY session in scope keeps it warm for every other; "
    "a `merged <N> sessions` header replaces the per-session `session <stem>` lines, and "
    "every REQ line AND every turn separator carries `  <tag>` (a worker's name, or a main "
    "session's project label, read off the stem) — turn numbers stay per session."
)

# FUNCTIONS


def _parse_args(argv: list, epilog: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.dual_log_cli",
        description="Read-only inspector for the proxy dual_log quartet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    _add_sessions_subparser(sub)
    _add_msgs_subparser(sub)
    _add_expand_subparser(sub)
    _add_search_subparser(sub)
    _add_reqs_subparser(sub)
    return parser.parse_args(argv)


def _add_sessions_subparser(sub) -> None:
    sessions = sub.add_parser("sessions", help="list all sessions, newest first")
    sessions.add_argument("context", nargs="?", default="", metavar="PROJECT",
                          help="only sessions whose real project path OR stem contains this text, "
                               "e.g. trading or a full path")
    sessions.add_argument("--since", default="", metavar="YYYY-MM-DD",
                          help="only sessions started on or after this day (inclusive)")
    sessions.add_argument("--until", default="", metavar="YYYY-MM-DD",
                          help="only sessions started on or before this day (inclusive)")


def _add_msgs_subparser(sub) -> None:
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
    msgs.add_argument("session", help="session stem or unambiguous substring")
    msgs.add_argument("from_msg", nargs="?", type=int, default=None, metavar="FROM",
                      help="first msg index (inclusive, default 0)")
    msgs.add_argument("to_msg", nargs="?", type=int, default=None, metavar="TO",
                      help="last msg index (inclusive, default the session's last msg)")
    msgs.add_argument("--req", nargs="+", type=int, default=None, metavar="F [T]",
                      help="REQ number range instead of msg indices, T defaults to F; "
                           "mutually exclusive with FROM/TO")


def _add_expand_subparser(sub) -> None:
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


def _add_search_subparser(sub) -> None:
    search = sub.add_parser("search", help="find a term across the deduplicated timelines")
    search.add_argument("term", help="literal term to look for (no regex)")
    search.add_argument("scope", nargs="?", default="", metavar="SCOPE",
                        help="only sessions whose real project path OR stem contains this text; omit to search all")
    search.add_argument("--since", default="", metavar="YYYY-MM-DD",
                        help="only sessions started on or after this day (inclusive)")
    search.add_argument("--until", default="", metavar="YYYY-MM-DD",
                        help="only sessions started on or before this day (inclusive)")
    search.add_argument("--only", default="", metavar="CLASSIFIER",
                        help=f"restrict hits to msgs matching {ONLY_FORMS}")
    search.add_argument("--case-sensitive", action="store_true", help="match case exactly (default: ignore case)")


def _add_reqs_subparser(sub) -> None:
    reqs = sub.add_parser(
        "reqs",
        help="one fixed REQ listing, turn-grouped, every flag a filter over it",
        description=_REQS_DESCRIPTION,
    )
    reqs.add_argument("scope", nargs="?", default="", metavar="SCOPE",
                      help="only sessions whose real project path OR stem contains this text; omit to search all")
    reqs.add_argument("--since", default="", metavar="YYYY-MM-DD",
                      help="only sessions started on or after this day (inclusive)")
    reqs.add_argument("--until", default="", metavar="YYYY-MM-DD",
                      help="only sessions started on or before this day (inclusive)")
    reqs_family = reqs.add_mutually_exclusive_group()
    reqs_family.add_argument("--main", action="store_true", help="only main sessions (stem identifies as opus)")
    reqs_family.add_argument("--worker", action="store_true", help="only worker sessions (stem identifies as worker)")
    reqs.add_argument("--turn", type=int, default=None, metavar="N",
                      help="keep only turn N of each session (its separator plus its own REQ lines)")
    reqs.add_argument("--gap", type=int, default=None, metavar="MINUTES",
                      help="keep only the REQs bracketing a consecutive gap of at least this many minutes")
    reqs.add_argument("--merged", action="store_true",
                      help="merge every session in scope into one chronological REQ chain, each line/separator tagged by session")
    reqs.add_argument("--rebuild", action="store_true",
                      help="keep only REQs where CC > CR")
    reqs.add_argument("--drop", action="store_true",
                      help="keep only REQs whose predecessor's cached prefix was not fully read back")
