# INFRASTRUCTURE
import gzip
import json
import sys
from pathlib import Path

SESSION_DIR = (
    Path.home() / ".claude" / "projects"
    / "-Users-brunowinter2000-Documents-ai-Monitor-CC"
)
PROXY_LOG_DIR = Path("src/logs")

# FUNCTIONS

def find_latest_proxy_log() -> Path:
    logs = list(PROXY_LOG_DIR.glob("api_requests_opus_monitor_cc_*.jsonl"))
    if not logs:
        raise FileNotFoundError(f"No opus proxy logs found in {PROXY_LOG_DIR}")
    return max(logs, key=lambda p: p.stat().st_mtime)


def find_latest_session_jsonl() -> Path:
    candidates = [
        p for p in SESSION_DIR.glob("*.jsonl")
        if "agent" not in p.name
    ]
    if not candidates:
        raise FileNotFoundError(f"No session JSONLs found in {SESSION_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _open_jsonl(path: Path):
    if path.suffix == ".gz" or path.name.endswith(".jsonl.gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def _system_chars(raw_payload: dict) -> int:
    total = 0
    for block in raw_payload.get("system", []) or []:
        if isinstance(block, dict):
            total += len(block.get("text", ""))
    return total


def _tools_chars(raw_payload: dict) -> int:
    total = 0
    for tool in raw_payload.get("tools", []) or []:
        total += len(json.dumps(tool, ensure_ascii=False))
    return total


def _msgs_chars(raw_payload: dict) -> int:
    total = 0
    for msg in raw_payload.get("messages", []) or []:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += len(block.get("text", ""))
    return total


def load_proxy_rows(proxy_path: Path) -> list:
    rows = []
    prev_msgs_chars = None
    req_n = 0
    with _open_jsonl(proxy_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "raw_payload" not in entry:
                continue
            model = entry.get("model", "")
            if "haiku" in model.lower():
                continue
            if "opus" not in model.lower():
                continue
            req_n += 1
            rp = entry.get("raw_payload", {})
            sc = _system_chars(rp)
            tc = _tools_chars(rp)
            mc = _msgs_chars(rp)
            msgs_count = len(rp.get("messages", []) or [])
            delta = mc - prev_msgs_chars if prev_msgs_chars is not None else None
            rows.append({
                "req_n": req_n,
                "model": model,
                "sys_chars": sc,
                "tools_chars": tc,
                "msgs_chars": mc,
                "msgs_count": msgs_count,
                "delta_msgs_chars": delta,
                "raw_payload": rp,
                "timestamp": entry.get("timestamp", ""),
            })
            prev_msgs_chars = mc
    return rows


def _parse_assistant_usage(entry):
    msg = entry.get("message", {})
    usage = msg.get("usage", {})
    if not usage:
        return None
    cr = usage.get("cache_read_input_tokens", 0) or 0
    cc = usage.get("cache_creation_input_tokens", 0) or 0
    d = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    content = msg.get("content", [])
    has_thinking = any(
        isinstance(b, dict) and b.get("type") == "thinking"
        for b in content
    )
    return (cr, cc, d), out, has_thinking


def _flush_pending(events, pending_key, pending_out, pending_has_thinking):
    if pending_key is not None:
        cr, cc, d = pending_key
        events.append({"cr": cr, "cc": cc, "d": d, "out": pending_out, "has_thinking": pending_has_thinking})


def load_session_events(session_path: Path) -> list:
    events = []
    pending_key = None
    pending_out = 0
    pending_has_thinking = False
    with open(session_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "assistant":
                _flush_pending(events, pending_key, pending_out, pending_has_thinking)
                pending_key = None
                pending_out = 0
                pending_has_thinking = False
                continue
            parsed = _parse_assistant_usage(entry)
            if parsed is None:
                continue
            key, out, has_thinking = parsed
            if key == pending_key:
                if out > pending_out:
                    pending_out = out
                if has_thinking:
                    pending_has_thinking = True
            else:
                _flush_pending(events, pending_key, pending_out, pending_has_thinking)
                pending_key = key
                pending_out = out
                pending_has_thinking = has_thinking
    _flush_pending(events, pending_key, pending_out, pending_has_thinking)
    return events


def pair_rows(proxy_rows: list, session_events: list) -> list:
    paired = []
    for row in proxy_rows:
        n = row["req_n"]
        tok = None
        if n <= len(session_events):
            tok = session_events[n - 1]
        paired.append({**row, "token": tok})
    return paired
