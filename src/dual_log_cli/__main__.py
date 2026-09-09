"""dual_log_cli — read-only inspector for src/logs/dual_log/.

Commands:
    sessions                 list every session (start, real project path, display stem), newest
                             first — a worker's stem is shown with its sid8 segment stripped
    sessions <project>       keep only sessions whose real project path OR stem contains that text
                             (substring, any case, e.g. "trading" or a full path)
    sessions --since D --until D   bound that listing by start day, inclusive, YYYY-MM-DD
    search <term> [scope]    find a term across the deduplicated timelines, each match reported once
                             scope matches a session's real project path OR stem; omit it to search all
                             --only restricts hits to one classifier (role, type, or role/type)
    reqs [scope]             per session: every REQ grouped under its turn separator
                             ("── turn n  HH:MM:SS  SPAN  <preview> ──", SPAN = that turn's last
                             send minus its first), each REQ line carrying "  CR c  CC c" (prompt-
                             cache usage, "CR ?  CC ?" when it does not resolve) — a session with
                             no turn opener at all prints its REQ lines with no separators; scope
                             matches project path OR stem like search; --main/--worker (mutually
                             exclusive) keep only main or worker sessions
    reqs [scope] --turn N    keep only turn N of each session in scope (its separator plus its own
                             REQ lines); a session missing that turn prints only its "session" line
    reqs [scope] --gap M     keep only the REQs bracketing a gap of >= M minutes between
                             consecutive requests (same session unless --merged); a turn's
                             separator prints only when at least one of its own REQs survives
    reqs [scope] --merged    merge every session in scope into ONE chronological REQ chain (the
                             prompt cache is shared across a project's workers) instead of one
                             listing per session; every REQ line and every turn separator carries
                             the session's own tag; turn numbers stay per session; --gap pairs
                             chronological neighbors across every session in the merged chain
    reqs [scope] --rebuild   keep only REQs where CC > CR (this request's own cache write
                             outweighed what it read back)
    reqs [scope] --drop      keep only REQs n where CR(n) < CR(n-1) + CC(n-1) — part of the prefix
                             the PREVIOUS request (same session, even under --merged) had cached
                             was not read again; REQ 1 of a session never qualifies (no
                             predecessor). --rebuild/--drop/--gap/--turn all combine (AND), --turn
                             narrowing first, then the rest filtering within it
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
    expand <s> <msg>         full content of that msg, plus what the proxy stripped/injected there
    expand <s> <msg> [--before N] [--after N] [--only X]   full content of the window around it

Usage (from project root, or via bin/duallog once symlinked into PATH):
    ./venv/bin/python -m src.dual_log_cli sessions
    ./venv/bin/python -m src.dual_log_cli search "worker-cli merge" gh_cli_1787939513
    ./venv/bin/python -m src.dual_log_cli search Reißleine websearch --since 2026-08-28
    ./venv/bin/python -m src.dual_log_cli reqs websearch --main
    ./venv/bin/python -m src.dual_log_cli reqs websearch --turn 2
    ./venv/bin/python -m src.dual_log_cli reqs websearch --gap 30
    ./venv/bin/python -m src.dual_log_cli reqs websearch --merged --gap 30
    ./venv/bin/python -m src.dual_log_cli reqs websearch --merged --rebuild
    ./venv/bin/python -m src.dual_log_cli reqs websearch --drop
    ./venv/bin/python -m src.dual_log_cli msgs websearch_1787924727
    ./venv/bin/python -m src.dual_log_cli msgs websearch_1787924727 700 740
    ./venv/bin/python -m src.dual_log_cli msgs websearch_1787924727 --req 259
    ./venv/bin/python -m src.dual_log_cli msgs websearch_1787924727 --req 259 261
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

from .cli_args import _parse_args as _build_args
from .commands import _run_expand, _run_msgs, _run_reqs, _run_search, _run_sessions
from .discovery import resolve_dual_log_dir

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
    return _run_expand(dual_log_dir, args)


# FUNCTIONS


def _parse_args(argv: list) -> argparse.Namespace:
    return _build_args(argv, __doc__)


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
