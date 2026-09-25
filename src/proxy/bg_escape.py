# INFRASTRUCTURE
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.proxy.proxy_error_log import log_proxy_error, proxy_monitor_root
from src.proxy.rules_config import is_main_session
from src.proxy.strip_bg_launch_ack import _is_bg_launch_ack, _ACK_ID_RE

_TMUX_TIMEOUT_SECS = 2
_WORKER_PREFIX = "worker:"

_escaped_task_ids: set = set()


# ORCHESTRATOR

def _trigger_bg_escape(stripped_msg_removed: dict, worker_context: str, project_path: str) -> None:
    ack_chunks = _iter_ack_chunks(stripped_msg_removed)
    _escape_ack_chunks(ack_chunks, worker_context, project_path)


# FUNCTIONS

def _iter_ack_chunks(stripped_msg_removed: dict):
    for chunks in stripped_msg_removed.values():
        for chunk in chunks:
            if isinstance(chunk, str) and _is_bg_launch_ack(chunk):
                yield chunk


def _escape_ack_chunks(ack_chunks, worker_context: str, project_path: str) -> None:
    session_cache = {}
    for chunk in ack_chunks:
        _escape_ack_chunk(chunk, worker_context, project_path, session_cache)


def _escape_ack_chunk(chunk: str, worker_context: str, project_path: str, session_cache: dict) -> None:
    task_id = _extract_task_id(chunk)
    if not task_id:
        _log_bg_escape_event("skipped", worker_context, "", "", reason="no_task_id")
        return
    if task_id in _escaped_task_ids:
        _log_bg_escape_event("skipped", worker_context, task_id, "", reason="already_escaped")
        return
    tmux_session = _cached_tmux_session(session_cache, worker_context, project_path)
    if not tmux_session:
        reason = "main_context" if is_main_session(worker_context) else "no_tmux_session"
        _log_bg_escape_event("skipped", worker_context, task_id, "", reason=reason)
        return
    _escaped_task_ids.add(task_id)
    sent = _send_escape_key(tmux_session)
    _log_bg_escape_event("fired", worker_context, task_id, tmux_session, send_result=sent)


def _cached_tmux_session(session_cache: dict, worker_context: str, project_path: str) -> str:
    if 'tmux_session' not in session_cache:
        session_cache['tmux_session'] = _derive_tmux_session_name(worker_context, project_path) or ""
    return session_cache['tmux_session']

def _extract_task_id(ack_text: str) -> str:
    match = _ACK_ID_RE.search(ack_text)
    return match.group(1).strip() if match else ''


def _derive_tmux_session_name(worker_context: str, project_path: str) -> str:
    if is_main_session(worker_context):
        return ''
    worker_name = worker_context[len(_WORKER_PREFIX):]
    if not worker_name or not project_path:
        return ''
    basename = os.path.basename(project_path.rstrip('/'))
    if not basename:
        return ''
    return f'worker-{basename}-{worker_name}'


def _send_escape_key(tmux_session: str) -> bool:
    try:
        alive = subprocess.run(
            ["tmux", "has-session", "-t", tmux_session],
            capture_output=True, timeout=_TMUX_TIMEOUT_SECS,
        )
        if alive.returncode != 0:
            return False
        sent = subprocess.run(
            ["tmux", "send-keys", "-t", tmux_session, "Escape"],
            capture_output=True, timeout=_TMUX_TIMEOUT_SECS,
        )
        return sent.returncode == 0
    except Exception:
        return False


def _log_bg_escape_event(event: str, worker_context: str, task_id: str, tmux_session: str, reason: str = "", send_result: bool = None) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "worker_context": worker_context,
        "task_id": task_id,
        "tmux_session": tmux_session,
    }
    if reason:
        entry["reason"] = reason
    if send_result is not None:
        entry["send_result"] = send_result
    try:
        log_file = _resolve_bg_escape_log_file()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        log_proxy_error("bg_escape.event_log", e)


def _resolve_bg_escape_log_file() -> Path:
    return proxy_monitor_root() / "src" / "logs" / "bg_escape_events.jsonl"
