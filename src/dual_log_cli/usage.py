# INFRASTRUCTURE
import json
from pathlib import Path

from .discovery import stem_identity
from .project_map import build_project_index, project_label
from .reader import iter_jsonl, local_datetime

_PROJECTS_ROOT = Path("~/.claude/projects").expanduser()

# FUNCTIONS


# {flow_id: (request_id, status_code)} for every line of one session's _response stream
def _flow_status_ids(response_path: Path) -> dict:
    result = {}
    for entry in iter_jsonl(response_path):
        flow_id = entry.get("flow_id")
        if not flow_id:
            continue
        result[flow_id] = (entry.get("request_id", ""), entry.get("status_code"))
    return result


# Epoch seconds of an ISO timestamp, tolerant of the dual log's two shapes ("...998Z" and
# "...998+00:00Z" — the latter from addon.py appending "Z" to an isoformat() that already carries
# an offset). None on anything unparseable, which the caller reads as "don't filter by time".
# 2026-09-04: delegates to `reader.local_datetime` (the one shared UTC-aware parse this package
# now uses everywhere) rather than its own inline parsing — `.timestamp()` on an AWARE datetime is
# timezone-independent (correct regardless of which zone the datetime is expressed in), so this
# still returns the exact same epoch value as before; only the duplicate parsing logic is gone.
# Audited for a UTC-vs-local bug during that same-day work and found already correct: the ORIGINAL
# inline version explicitly appended "+00:00" whenever the cleaned string carried no offset of its
# own, so the "...998Z"-only case (the common one) was already parsed as AWARE UTC, never as a
# naive-assumed-local datetime.
def _epoch_from_iso(timestamp: str):
    dt = local_datetime(timestamp)
    return dt.timestamp() if dt else None


# The project directories a session's stem could possibly have a transcript in — derived from the
# stem alone, never a store-wide scan. A worker stem's sid8 resolves to its project's cwd (the
# same md5(project_path)[:8] hash `discovery.project_for_stem` resolves for `sessions`' PROJECT
# column), and the worker's OWN cwd is that project's cwd plus the worktree layout every worker runs under
# (".claude/worktrees/<name>"). A main stem's label is matched against every known cwd's label —
# plural on purpose, since two different projects can share a basename. Empty when the stem does
# not parse or its cwd/label matches no known directory.
def _candidate_dirs(stem: str, index: dict) -> list:
    identity = stem_identity(stem)
    if identity is None:
        return []
    cwd_to_dir = index["cwd_to_dir"]
    if identity[0] == "worker":
        _, sid, name = identity
        cwd = index["sid_to_cwd"].get(sid)
        if not cwd:
            return []
        worktree_cwd = f"{cwd.rstrip('/')}/.claude/worktrees/{name}"
        directory = cwd_to_dir.get(worktree_cwd)
        return [directory] if directory else []
    _, _head, label = identity
    return [directory for cwd, directory in cwd_to_dir.items() if project_label(cwd) == label]


# The first file (name order) under `directories`, with mtime at or after `since_epoch`, whose
# content contains the literal fragment `"requestId":"<id>"` — WITH the key, never a bare id (a
# tool_result can quote one, which a bare-id search would wrongly treat as that record's own).
# Stops at the first match rather than hunting for or rejecting a second one: a full-store sweep
# of the corpus on disk found zero sessions where the same request id appears in two transcripts.
# None when no candidate file matches or a candidate cannot be read.
def _find_transcript(request_id: str, directories: list, since_epoch=None) -> Path:
    fragment = f'"requestId":"{request_id}"'
    candidates = []
    for directory in directories:
        try:
            entries = sorted(directory.iterdir())
        except Exception:
            continue
        for path in entries:
            if path.suffix != ".jsonl":
                continue
            if since_epoch is not None:
                try:
                    if path.stat().st_mtime < since_epoch:
                        continue
                except OSError:
                    continue
            candidates.append(path)
    for path in candidates:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if fragment in content:
            return path
    return None


# {request_id: (cache_read_input_tokens, cache_creation_input_tokens)} from one transcript's
# assistant records. One API request produces several streaming assistant records with identical
# input-side usage, so only the first record per requestId is kept.
def _transcript_usage(transcript_path: Path) -> dict:
    usage = {}
    try:
        with open(transcript_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "assistant":
                    continue
                request_id = entry.get("requestId")
                if not request_id or request_id in usage:
                    continue
                message_usage = entry.get("message", {}).get("usage", {}) or {}
                cache_read = message_usage.get("cache_read_input_tokens")
                cache_creation = message_usage.get("cache_creation_input_tokens")
                if cache_read is None or cache_creation is None:
                    continue
                usage[request_id] = (cache_read, cache_creation)
    except Exception:
        return {}
    return usage


# The shared three-hop preamble both `build_usage_by_flow` and `build_request_times_by_flow`
# (2026-09-08) need before they can each read their OWN kind of record out of the same transcript:
# `_response` -> {flow_id: (request_id, status)}, the first non-haiku boundary's request id as
# anchor, the stem-derived candidate directories, and the one transcript file the anchor's literal
# `"requestId":"<id>"` fragment is found in. Returns (transcript_path, flow_status) — `flow_status`
# is `{}` only when the `_response` stream itself could not be read at all (every other failure
# still returns whatever `flow_status` WAS resolved, since a caller needing only the status map,
# not the transcript, should not lose it for a resolution failure of the LATER hops); the caller
# reads `transcript_path is None` as "degrade to {}", same threshold every failure inside here
# already used before this was split out.
def _resolve_session_transcript(session: dict, boundaries: list, projects_root: Path = None) -> tuple:
    if not boundaries:
        return None, {}
    response_path = session.get("streams", {}).get("response")
    if response_path is None:
        return None, {}
    try:
        flow_status = _flow_status_ids(response_path)
    except Exception:
        return None, {}
    anchor_request_id = None
    for boundary in boundaries:
        request_id, _status = flow_status.get(boundary.get("flow_id", ""), ("", None))
        if request_id:
            anchor_request_id = request_id
            break
    if not anchor_request_id:
        return None, flow_status
    root = Path(projects_root) if projects_root else _PROJECTS_ROOT
    index = build_project_index(root)
    directories = _candidate_dirs(session.get("stem", ""), index)
    if not directories:
        return None, flow_status
    since_epoch = _epoch_from_iso(boundaries[0].get("timestamp", ""))
    transcript_path = _find_transcript(anchor_request_id, directories, since_epoch)
    return transcript_path, flow_status


# {flow_id: (cache_read_input_tokens, cache_creation_input_tokens)} for one session — what
# render._req_separator looks its CR/CC figures up by, keyed on the group owner's flow_id from
# timeline.request_markers.
#
# Degrades to {} (every separator renders value-less, never a placeholder) when the _response
# stream is missing, no boundary's flow_id resolves to a request id, the stem does not resolve to
# a known project directory, no candidate file in it matches, or the matched transcript yields no
# usable usage lines. A flow whose _response status is not 200 is dropped even when its request id
# would otherwise resolve — an errored request carries no meaningful cache figures.
def build_usage_by_flow(session: dict, boundaries: list, projects_root: Path = None) -> dict:
    transcript_path, flow_status = _resolve_session_transcript(session, boundaries, projects_root)
    if transcript_path is None:
        return {}
    usage_by_request_id = _transcript_usage(transcript_path)
    if not usage_by_request_id:
        return {}
    usage_by_flow = {}
    for flow_id, (request_id, status) in flow_status.items():
        if status != 200 or not request_id:
            continue
        usage = usage_by_request_id.get(request_id)
        if usage is not None:
            usage_by_flow[flow_id] = usage
    return usage_by_flow


# {request_id: [stream_end_iso, output_tokens]} from one transcript's assistant records — what
# `build_request_times_by_flow` (`turns`, 2026-09-08) joins against, the SAME transcript
# `build_usage_by_flow` reads, parsed for different fields. CC writes an assistant record at
# STREAM END (verified: a trivial tool's own `tool_result` record follows by ~0.1s — never at
# first byte, unlike `_response`'s own `responseheaders`-time write, see `src/proxy/addon.py`
# lines 141-161), and one API request produces several streaming records sharing one requestId —
# `timestamp` is therefore OVERWRITTEN on every sighting (ending on the LAST record's, the actual
# stream end), while `output_tokens` is kept from the FIRST sighting only (observed identical
# across every record of the same requestId in the corpus this was checked against, matching the
# reference probe's own dedup rule exactly). `[ts, tokens]` stays a list, not a tuple, precisely so
# the timestamp slot can be mutated in place across repeat sightings.
def _transcript_stream_ends(transcript_path: Path) -> dict:
    ends = {}
    try:
        with open(transcript_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "assistant":
                    continue
                request_id = entry.get("requestId")
                if not request_id:
                    continue
                timestamp = entry.get("timestamp")
                if request_id not in ends:
                    message_usage = entry.get("message", {}).get("usage", {}) or {}
                    ends[request_id] = [timestamp, message_usage.get("output_tokens")]
                else:
                    ends[request_id][0] = timestamp
    except Exception:
        return {}
    return ends


# {flow_id: (stream_end_iso, output_tokens)} for one session — what `timeline.build_turn_rows`
# (`turns`, 2026-09-08) sums per turn. Same join, same degrade-to-{} conditions and same 200-status
# filter as `build_usage_by_flow` (an errored request carries no completed stream either) — only
# the transcript-record fields read differ. A flow whose end timestamp or output_tokens did not
# resolve is dropped entirely rather than included with a `None` half, so a caller never has to
# special-case a half-resolved pair.
def build_request_times_by_flow(session: dict, boundaries: list, projects_root: Path = None) -> dict:
    transcript_path, flow_status = _resolve_session_transcript(session, boundaries, projects_root)
    if transcript_path is None:
        return {}
    ends_by_request_id = _transcript_stream_ends(transcript_path)
    if not ends_by_request_id:
        return {}
    times_by_flow = {}
    for flow_id, (request_id, status) in flow_status.items():
        if status != 200 or not request_id:
            continue
        ends = ends_by_request_id.get(request_id)
        if ends is not None and ends[0] is not None and ends[1] is not None:
            times_by_flow[flow_id] = (ends[0], ends[1])
    return times_by_flow
