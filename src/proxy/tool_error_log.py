# INFRASTRUCTURE
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

# Global log: all tool_use_errors across projects/sessions, co-located with proxy JSONLs
LOG_FILE = Path(__file__).resolve().parent.parent / 'logs' / 'tool_use_errors.jsonl'

# Strip <tool_use_error>…</tool_use_error> wrapper from error text
_TUE_RE = re.compile(r'<tool_use_error>(.*?)</tool_use_error>', re.DOTALL)

# Match "exit code 128", "exited with non-zero code 1", "exit_code: 2", etc.
_EXIT_CODE_RE = re.compile(
    r'exit(?:ed with(?: non-zero)? code|[ _]code[: ]+)\s*(\d+)', re.IGNORECASE
)


# FUNCTIONS

# Append one tool_use_error entry; O_APPEND — POSIX-atomic for writes < PIPE_BUF (~65 KB)
def write(ts: str, session_id: str, project: str, worker, tool_name: str,
          command_preview, error_summary: str, exit_code) -> None:
    entry = {
        "ts": ts,
        "session_id": session_id,
        "project": project,
        "worker": worker,
        "tool_name": tool_name,
        "command_preview": command_preview,
        "error_summary": error_summary,
        "exit_code": exit_code,
    }
    line = json.dumps(entry) + "\n"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(line)


# Return all entries from the global log
def read_all() -> list[dict]:
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    result = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return result


# Return entries from start of today (local midnight, converted to UTC for comparison)
def read_today() -> list[dict]:
    now_local = datetime.now().astimezone()
    today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    return [e for e in read_all() if datetime.fromisoformat(e["ts"]) >= today_start]


# Return entries filtered by optional criteria (all criteria are AND-combined)
def read_filtered(by_tool=None, by_project=None, by_summary_substring=None) -> list[dict]:
    entries = read_all()
    if by_tool:
        entries = [e for e in entries if e.get("tool_name") == by_tool]
    if by_project:
        entries = [e for e in entries if e.get("project") == by_project]
    if by_summary_substring:
        sub = by_summary_substring.lower()
        entries = [e for e in entries if sub in (e.get("error_summary") or "").lower()]
    return entries


# Extract clean error summary — strip <tool_use_error> wrapper, return first line, max 200 chars
def _extract_error_summary(text: str) -> str:
    m = _TUE_RE.search(text)
    if m:
        text = m.group(1).strip()
    return text.split('\n')[0][:200]


# Extract exit code from error text; None if no match
def _extract_exit_code(text: str):
    m = _EXIT_CODE_RE.search(text)
    return int(m.group(1)) if m else None


# Get text from a raw API tool_result block (content is string or list-of-text-blocks)
def _get_block_text(blk: dict) -> str:
    content = blk.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for sub in content:
            if isinstance(sub, dict) and sub.get("type") == "text":
                parts.append(sub.get("text", ""))
        return "\n".join(parts)
    return ""


# Build {tool_use_id → (name, input_dict)} map from raw API messages (assistant role only)
def _build_tu_id_map(messages: list) -> dict:
    id_map = {}
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for blk in content:
            if blk.get("type") == "tool_use":
                bid = blk.get("id", "")
                if bid:
                    id_map[bid] = (blk.get("name", "?"), blk.get("input") or {})
    return id_map


# Extract command preview from tool_use input dict; max 200 chars
def _get_command_preview(tool_input) -> str:
    if not isinstance(tool_input, dict):
        return None
    cmd = (tool_input.get("command") or tool_input.get("file_path")
           or tool_input.get("pattern") or json.dumps(tool_input))
    return str(cmd)[:200]


# Scan modified_payload for tool_result errors; called from addon.py after _write_entry(entry)
# Wraps all logic in try/except — error logging failure must NEVER break the request flow
def log_tool_errors(modified_payload: dict, entry: dict) -> None:
    try:
        messages = modified_payload.get("messages", [])
        if not messages:
            return

        ts = entry.get("timestamp", datetime.now(timezone.utc).isoformat() + "Z")
        log_id = os.environ.get("PROXY_LOG_ID", "")
        session_id = log_id
        project = os.environ.get("PROXY_PROJECT_PATH", "")
        worker = None
        if log_id.startswith("worker_"):
            parts = log_id.split("_")
            if len(parts) >= 4:
                worker = "_".join(parts[2:-1])

        # Only process new messages in this REQ (first_diff_index slicing — prevents
        # re-processing the same error from previous REQs that carry it in cumulative history)
        diff = entry.get("diff_from_prev") or {}
        first_diff = diff.get("first_diff_index", 0)
        if first_diff < 0:
            return
        new_messages = messages[first_diff:]

        # Build id-map from ALL messages (tool_use may appear before first_diff)
        tu_map = _build_tu_id_map(messages)

        for msg in new_messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for blk in content:
                if blk.get("type") != "tool_result":
                    continue
                is_err = blk.get("is_error", False)
                text = _get_block_text(blk)
                has_tag = "<tool_use_error>" in text
                if not is_err and not has_tag:
                    continue
                tool_use_id = blk.get("tool_use_id", "")
                tool_name, tool_input = tu_map.get(tool_use_id, ("?", {}))
                command_preview = _get_command_preview(tool_input)
                error_summary = _extract_error_summary(text)
                exit_code = _extract_exit_code(text) if tool_name == "Bash" else None
                write(ts, session_id, project, worker, tool_name, command_preview, error_summary, exit_code)
    except Exception:
        pass
