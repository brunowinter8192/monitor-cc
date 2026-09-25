# INFRASTRUCTURE
import json
from pathlib import Path

from src.dual_log_cli.diagnostics import report_skip
from src.dual_log_cli.discovery import stem_identity
from src.dual_log_cli.project_map import build_project_index, project_label
from src.dual_log_cli.reader import iter_jsonl, local_datetime

_PROJECTS_ROOT = Path("~/.claude/projects").expanduser()

# FUNCTIONS


def flow_status_ids(response_path: Path) -> dict:
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
        except OSError as exc:
            report_skip("usage", str(directory), f"{type(exc).__name__}: {exc}")
            continue
        for path in entries:
            if path.suffix != ".jsonl":
                continue
            if since_epoch is not None:
                try:
                    if path.stat().st_mtime < since_epoch:
                        continue
                except OSError as exc:
                    report_skip("usage", str(path), f"{type(exc).__name__}: {exc}")
                    continue
            candidates.append(path)
    for path in candidates:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            report_skip("usage", str(path), f"{type(exc).__name__}: {exc}")
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
                    report_skip("usage", str(transcript_path), "JSONDecodeError: malformed line skipped")
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
    except OSError as exc:
        report_skip("usage", str(transcript_path), f"{type(exc).__name__}: {exc}")
        return {}
    return usage


def resolve_transcript(session: dict, boundaries: list, projects_root: Path = None) -> tuple:
    if not boundaries:
        return None, {}, "no requests"
    response_path = session.get("streams", {}).get("response")
    if response_path is None:
        return None, {}, "no _response stream"
    try:
        flow_status = flow_status_ids(response_path)
    except OSError as exc:
        return None, {}, f"_response unreadable: {type(exc).__name__}: {exc}"
    anchor_request_id = None
    for boundary in boundaries:
        request_id, _status = flow_status.get(boundary.get("flow_id", ""), ("", None))
        if request_id:
            anchor_request_id = request_id
            break
    if not anchor_request_id:
        return None, flow_status, "no request id in _response for any request"
    root = Path(projects_root) if projects_root else _PROJECTS_ROOT
    index = build_project_index(root)
    directories = _candidate_dirs(session.get("stem", ""), index)
    if not directories:
        return None, flow_status, "no project directory resolved for the stem"
    since_epoch = _epoch_from_iso(boundaries[0].get("timestamp", ""))
    transcript_path = _find_transcript(anchor_request_id, directories, since_epoch)
    if transcript_path is None:
        return None, flow_status, f"no transcript contains request {anchor_request_id}"
    return transcript_path, flow_status, None


def build_usage_by_flow(session: dict, boundaries: list, projects_root: Path = None) -> dict:
    transcript_path, flow_status, _reason = resolve_transcript(session, boundaries, projects_root)
    return usage_from_transcript(transcript_path, flow_status)


def usage_from_transcript(transcript_path: Path, flow_status: dict) -> dict:
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
