# INFRASTRUCTURE
import json
from pathlib import Path

from .discovery import stem_identity
from .project_map import build_project_index, project_label
from .reader import iter_jsonl, local_datetime

_PROJECTS_ROOT = Path("~/.claude/projects").expanduser()

# FUNCTIONS


def _flow_status_ids(response_path: Path) -> dict:
    result = {}
    for entry in iter_jsonl(response_path):
        flow_id = entry.get("flow_id")
        if not flow_id:
            continue
        result[flow_id] = (entry.get("request_id", ""), entry.get("status_code"))
    return result


def _epoch_from_iso(timestamp: str):
    dt = local_datetime(timestamp)
    return dt.timestamp() if dt else None


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
