# INFRASTRUCTURE
import os
import re
from pathlib import Path

from .project_map import build_project_index, project_label
from .reader import infer_family, iter_jsonl, local_datetime

STREAM_SUFFIXES = ("original", "forwarded", "stripped", "injected", "response", "errors")

_STEM_RE = re.compile(r"^(?P<stem>.+)_(?P<stream>" + "|".join(STREAM_SUFFIXES) + r")\.jsonl$")
_STEM_PREFIX = "api_requests_"
_TRAILING_EPOCH_RE = re.compile(r"_\d+$")
_WORKER_BODY_RE = re.compile(r"^(?P<sid>[0-9a-f]{6,})_(?P<name>.+)$")


class AmbiguousSessionError(Exception):
    pass


class UnknownSessionError(Exception):
    pass


# FUNCTIONS


# Resolve the dual_log directory. MONITOR_CC_ROOT wins; otherwise the repo root derived from
# this file, falling back to the MAIN repo when running inside .claude/worktrees/<name>/
# (the log directory is gitignored and exists only in the main checkout).
def resolve_dual_log_dir() -> Path:
    env_root = os.environ.get("MONITOR_CC_ROOT")
    if env_root:
        return Path(env_root) / "src" / "logs" / "dual_log"
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    direct = repo_root / "src" / "logs" / "dual_log"
    if direct.exists():
        return direct
    # <main>/.claude/worktrees/<name>/src/dual_log_cli/discovery.py → parents[5] == <main>
    if len(here.parents) > 5:
        from_worktree = here.parents[5] / "src" / "logs" / "dual_log"
        if from_worktree.exists():
            return from_worktree
    return direct


# Parse a stem into its raw identity: ("worker", sid8, name) or ("main", family_head, label).
# None when a "worker_" body does not match the expected shape, or a non-worker body carries no
# "_" at all. The one place every stem-derived value in this package (the real project PATH via
# `project_for_stem`, the sid8-stripped `display_stem`, `usage.py`'s transcript-directory lookup,
# `filter_by_family`'s opus/worker split) starts from — never re-parsed a second way.
def stem_identity(stem: str):
    body = stem[len(_STEM_PREFIX):] if stem.startswith(_STEM_PREFIX) else stem
    body = _TRAILING_EPOCH_RE.sub("", body)
    if body.startswith("worker_"):
        match = _WORKER_BODY_RE.match(body[len("worker_"):])
        if not match:
            return None
        return ("worker", match.group("sid"), match.group("name"))
    head, _, tail = body.partition("_")
    if not tail:
        return None
    return ("main", head, tail)


# The REAL project directory a session ran in, as CC's own transcript records it (`sessions`'
# PROJECT column, `expand`'s project header, 2026-09-10 — replaces the old `worker/<label>/<name>`
# CONTEXT rendering entirely). A worker stem carries only md5(project_path)[:8] (its `sid8`);
# `project_index["sid_to_cwd"]` (`project_map.build_project_index`) resolves that to the PROJECT's
# own cwd — NOT the worker's own worktree cwd, which is that path plus
# ".claude/worktrees/<name>" (see `usage.py`'s `_candidate_dirs`, the same sid8→cwd lookup used to
# find a worker's transcript). A main stem carries only the readable LABEL
# (`project_map.project_label`'s own spelling, e.g. "monitor_cc"); resolving it to a path means
# scanning every known cwd for the one whose label matches — ambiguous when two different projects
# share a basename, in which case the alphabetically first cwd wins (arbitrary but deterministic,
# not otherwise observed in the corpus). Falls back to the sid8 (worker, unresolved) or the label
# (main, unresolved) — the row still carries what IS known rather than an empty column — and to
# the raw stem when `stem_identity` cannot parse it at all.
def project_for_stem(stem: str, project_index: dict = None) -> str:
    identity = stem_identity(stem)
    if identity is None:
        return stem
    index = project_index or {}
    if identity[0] == "worker":
        _, sid, _name = identity
        return index.get("sid_to_cwd", {}).get(sid) or sid
    _, _head, label = identity
    for cwd in sorted(index.get("cwd_to_dir", {})):
        if project_label(cwd) == label:
            return cwd
    return label


# The stem as `sessions`/`resolve_stem` DISPLAY it: a worker's sid8 segment removed
# (`api_requests_worker_1dda1c81_reldist-power_1788726467` ->
# `api_requests_worker_reldist-power_1788726467`), a main stem unchanged. Display-only — the
# on-disk file names (and every OTHER function in this package that reads a stem) never change;
# this exists purely so a name copied out of the `sessions` table resolves via `resolve_stem`. The
# epoch suffix is preserved by re-extracting it from the stem directly (`stem_identity`'s own
# `name` never carries it, having already stripped it to compute the identity) rather than
# reconstructing the whole stem from parts.
def display_stem(stem: str) -> str:
    identity = stem_identity(stem)
    if identity is None or identity[0] != "worker":
        return stem
    _, _sid, name = identity
    has_prefix = stem.startswith(_STEM_PREFIX)
    body = stem[len(_STEM_PREFIX):] if has_prefix else stem
    epoch_match = _TRAILING_EPOCH_RE.search(body)
    epoch = epoch_match.group(0) if epoch_match else ""
    return f"{_STEM_PREFIX if has_prefix else ''}worker_{name}{epoch}"


# Group every *.jsonl in the directory by session stem → {stream: Path}
def group_streams(dual_log_dir: Path) -> dict:
    stems: dict = {}
    for entry in sorted(dual_log_dir.glob("*.jsonl")):
        match = _STEM_RE.match(entry.name)
        if not match:
            continue
        stems.setdefault(match.group("stem"), {})[match.group("stream")] = entry
    return stems


# Build the inventory row for one stem. Reads _forwarded only — it is line-for-line aligned
# with _original (verified: identical line count and per-line model/message_count) and two
# orders of magnitude smaller.
#
# A zero-tool non-haiku line (the sidecar `timeline._is_sidecar` also excludes — a recurring
# "security monitor" review call, not a conversation turn) is skipped from `requests`,
# `requests_main` and `last_message_count` the same way, so this inventory's request count means
# the same thing `timeline.request_boundaries` counts. Its timestamp still extends `start`/`end`,
# since those describe the file's real wall-clock span, unrelated to what counts as a request.
def build_session(stem: str, streams: dict, project_index: dict = None) -> dict:
    total_bytes = sum(p.stat().st_size for p in streams.values())
    requests = 0
    start_ts = ""
    end_ts = ""
    families: dict = {}
    last_message_count = 0
    forwarded = streams.get("forwarded")
    if forwarded is not None:
        for entry in iter_jsonl(forwarded):
            if entry.get("type") != "forwarded_delta":
                continue
            timestamp = entry.get("timestamp", "")
            if not start_ts:
                start_ts = timestamp
            end_ts = timestamp
            family = infer_family(entry.get("model", ""))
            counts = entry.get("counts", {}) or {}
            if family != "haiku" and counts.get("tools", 0) == 0:
                continue
            requests += 1
            families[family] = families.get(family, 0) + 1
            if family != "haiku":
                last_message_count = counts.get("messages", 0)
    main_family = _main_family(families)
    return {
        "stem": stem,
        "display_stem": display_stem(stem),
        "project": project_for_stem(stem, project_index),
        "start": start_ts,
        "end": end_ts,
        "requests": requests,
        "requests_main": families.get(main_family, 0),
        "family": main_family,
        "messages": last_message_count,
        "bytes": total_bytes,
        "streams": streams,
    }


# The conversation family of a session — the non-haiku family with the most requests
def _main_family(families: dict) -> str:
    ranked = [(n, f) for f, n in families.items() if f != "haiku"]
    if not ranked:
        return "haiku" if families else ""
    return max(ranked)[1]


# All sessions in the directory, newest first. The project index is built once and shared across
# every session rather than per stem — it costs one scan of CC's transcript store.
def list_sessions(dual_log_dir: Path, project_index: dict = None) -> list:
    if project_index is None:
        project_index = build_project_index()
    sessions = [build_session(stem, streams, project_index)
                for stem, streams in group_streams(dual_log_dir).items()]
    sessions.sort(key=lambda s: (s["start"], s["stem"]), reverse=True)
    return sessions


# Keep the sessions matching every active criterion (AND). `context` (from `sessions <CONTEXT>`)
# and `scope` (from `search <SCOPE>`/`reqs <SCOPE>`) are functionally identical selectors now
# (2026-09-10: both used to differ — `context` matched only the rendered `worker/<label>/<name>`
# string, `scope` also fell back to the stem — but that string is gone, and the PROJECT path it
# has been replaced with is exactly what both commands' filter term is meant to catch, whether the
# session is a worker or a main one) — kept as two separate parameters only because `sessions` and
# `search`/`reqs` keep their own CLI wording, never both set on the same call. Each is a
# case-insensitive substring matched against the session's PROJECT path OR its stem, so `trading`,
# `ai/trading`, or a full path all work, and a name copied from the SESSION column still matches
# via the stem. Plus an inclusive [since, until] window on the start day.
#
# Days are compared on the LOCAL calendar day of the start timestamp (2026-09-04: was the RAW
# UTC YYYY-MM-DD prefix, lexicographic order over that being equal to UTC calendar order — but
# --since/--until are days the CALLER means in their OWN local time, so a session started 23:30
# local on the 3rd, whose UTC instant can fall on the 4th, was silently listed under the 4th; see
# `reader.local_datetime`, the one shared conversion point). A session with no start timestamp, or
# one that fails to parse, cannot be placed on a calendar, so an active DATE filter drops it; a
# context or scope filter alone still keeps it, because both of its match targets are known either
# way.
def filter_sessions(sessions: list, context: str = "", scope: str = "",
                    since: str = "", until: str = "") -> list:
    if not context and not scope and not since and not until:
        return sessions
    needle = context.lower()
    scope_needle = scope.lower()
    kept = []
    for session in sessions:
        if needle and not _matches_project_or_stem(session, needle):
            continue
        if scope_needle and not _matches_project_or_stem(session, scope_needle):
            continue
        if since or until:
            dt = local_datetime(session.get("start") or "")
            if dt is None:
                continue
            day = dt.strftime("%Y-%m-%d")
            if since and day < since:
                continue
            if until and day > until:
                continue
        kept.append(session)
    return kept


# True when the lowercased needle appears in the session's real PROJECT path or in its stem
def _matches_project_or_stem(session: dict, needle: str) -> bool:
    return (needle in session.get("project", "").lower()
            or needle in session.get("stem", "").lower())


# Keep only sessions whose STEM identifies as "opus" (main) or "worker" — the --main/--worker
# filter `reqs` uses (2026-09-10: reads the stem via `stem_identity` directly now, since the
# `worker/`/`opus/` CONTEXT prefix this used to check no longer exists). Mutually exclusive at the
# CLI level (an argparse group), so at most one of the two is ever True here; neither set returns
# `sessions` unchanged.
def filter_by_family(sessions: list, main: bool = False, worker: bool = False) -> list:
    if main:
        return [s for s in sessions if _stem_family(s.get("stem", "")) == "main"]
    if worker:
        return [s for s in sessions if _stem_family(s.get("stem", "")) == "worker"]
    return sessions


# "main"/"worker"/"" from stem_identity's own first element — "" (never a stem_identity result)
# for an unparseable stem, so it matches neither --main nor --worker rather than raising.
def _stem_family(stem: str) -> str:
    identity = stem_identity(stem)
    return identity[0] if identity else ""


# Resolve a stem or unambiguous substring to exactly one session stem. The query may be a
# substring of the FULL on-disk stem OR of its DISPLAYED form (`display_stem`, sid8 stripped for a
# worker) — 2026-09-10, so a name copied straight out of the `sessions` table's SESSION column
# resolves here without the reader having to guess the hidden sid8 back in. Ambiguity is judged
# over the UNION of both match sets — a query could in principle match one stem's raw form and a
# DIFFERENT stem's displayed form, which is exactly the kind of collision this function exists to
# refuse rather than silently pick one.
def resolve_stem(dual_log_dir: Path, query: str) -> str:
    stems = sorted(group_streams(dual_log_dir))
    if query in stems:
        return query
    matches = [s for s in stems if query in s or query in display_stem(s)]
    if not matches:
        raise UnknownSessionError(f"no session matches {query!r} in {dual_log_dir}")
    if len(matches) > 1:
        listing = "\n  ".join(matches)
        raise AmbiguousSessionError(f"{query!r} matches {len(matches)} sessions:\n  {listing}")
    return matches[0]
