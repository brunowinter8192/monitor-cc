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


def resolve_dual_log_dir() -> Path:
    env_root = os.environ.get("MONITOR_CC_ROOT")
    if env_root:
        return Path(env_root) / "src" / "logs" / "dual_log"
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    direct = repo_root / "src" / "logs" / "dual_log"
    if direct.exists():
        return direct
    if len(here.parents) > 5:
        from_worktree = here.parents[5] / "src" / "logs" / "dual_log"
        if from_worktree.exists():
            return from_worktree
    return direct


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


def group_streams(dual_log_dir: Path) -> dict:
    stems: dict = {}
    for entry in sorted(dual_log_dir.glob("*.jsonl")):
        match = _STEM_RE.match(entry.name)
        if not match:
            continue
        stems.setdefault(match.group("stem"), {})[match.group("stream")] = entry
    return stems


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


def _main_family(families: dict) -> str:
    ranked = [(n, f) for f, n in families.items() if f != "haiku"]
    if not ranked:
        return "haiku" if families else ""
    return max(ranked)[1]


def list_sessions(dual_log_dir: Path, project_index: dict = None) -> list:
    if project_index is None:
        project_index = build_project_index()
    sessions = [build_session(stem, streams, project_index)
                for stem, streams in group_streams(dual_log_dir).items()]
    sessions.sort(key=lambda s: (s["start"], s["stem"]), reverse=True)
    return sessions


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


def _matches_project_or_stem(session: dict, needle: str) -> bool:
    return (needle in session.get("project", "").lower()
            or needle in session.get("stem", "").lower())


def filter_by_family(sessions: list, main: bool = False, worker: bool = False) -> list:
    if main:
        return [s for s in sessions if _stem_family(s.get("stem", "")) == "main"]
    if worker:
        return [s for s in sessions if _stem_family(s.get("stem", "")) == "worker"]
    return sessions


def _stem_family(stem: str) -> str:
    identity = stem_identity(stem)
    return identity[0] if identity else ""


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
