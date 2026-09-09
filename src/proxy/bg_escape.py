# INFRASTRUCTURE
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .strip_bg_launch_ack import _is_bg_launch_ack, _ACK_ID_RE

_TMUX_TIMEOUT_SECS = 2
_WORKER_PREFIX = "worker:"

_escaped_task_ids: set = set()


# ORCHESTRATOR

def _trigger_bg_escape(stripped_msg_removed: dict, worker_context: str, project_path: str) -> None:
    tmux_session = None
    for chunks in stripped_msg_removed.values():
        for chunk in chunks:
            if not isinstance(chunk, str) or not _is_bg_launch_ack(chunk):
                continue
            task_id = _extract_task_id(chunk)
            if not task_id:
                _log_bg_escape_event("skipped", worker_context, "", "", reason="no_task_id")
                continue
            if task_id in _escaped_task_ids:
                _log_bg_escape_event("skipped", worker_context, task_id, "", reason="already_escaped")
                continue
            if tmux_session is None:
                tmux_session = _derive_tmux_session_name(worker_context, project_path) or ""
            if not tmux_session:
                reason = "main_context" if not worker_context.startswith(_WORKER_PREFIX) else "no_tmux_session"
                _log_bg_escape_event("skipped", worker_context, task_id, "", reason=reason)
                continue
            _escaped_task_ids.add(task_id)
            sent = _send_escape_key(tmux_session)
            _log_bg_escape_event("fired", worker_context, task_id, tmux_session, send_result=sent)


# FUNCTIONS

def _extract_task_id(ack_text: str) -> str:
    match = _ACK_ID_RE.search(ack_text)
    return match.group(1).strip() if match else ''


def _derive_tmux_session_name(worker_context: str, project_path: str) -> str:
    if not worker_context.startswith(_WORKER_PREFIX):
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
        "ts": datetime.now(timezone.utc).isoformat() + "Z",
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
        print(f"[bg_escape] event log write failed: {e}", file=sys.stderr)


def _resolve_bg_escape_log_file() -> Path:
    root = os.environ.get("MONITOR_CC_ROOT")
    if root:
        return Path(root) / "src" / "logs" / "bg_escape_events.jsonl"
    return Path("/tmp") / "bg_escape_events.jsonl"
