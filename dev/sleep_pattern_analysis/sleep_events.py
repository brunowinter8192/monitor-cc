# INFRASTRUCTURE
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
TARGET_HOOK = "block_chained_sleep"

_BLOCK_RE = re.compile(r'PreToolUse:\w+ hook error: \[python3 ([^\]]+)\]: BLOCKED: ([^\n]+)')
_content  = lambda obj: [c for c in (obj.get("message", {}).get("content") or []) if isinstance(c, dict)]


# FUNCTIONS

def _collect_events(since_dt: datetime) -> list:
    events = []
    cutoff = since_dt - timedelta(hours=1)
    for path in sorted(PROJECTS_DIR.glob("*/*.jsonl")):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            continue
        events.extend(_parse_jsonl(path, since_dt))
    return events


def _parse_jsonl(path: Path, since_dt: datetime) -> list:
    events = []
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError as e:
        print(f"Warning: {path}: {e}", file=sys.stderr)
        return events

    tu_map: dict = {}
    uuid_map: dict = {}
    for line in lines:
        if '"tool_use"' not in line and '"uuid"' not in line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        uid = obj.get("uuid")
        if uid:
            uuid_map[uid] = obj
        for mc in _content(obj):
            if mc.get("type") == "tool_use":
                tid = mc.get("id")
                if tid and tid not in tu_map:
                    inp = mc.get("input", {})
                    tu_map[tid] = inp.get("command") or ""

    for line in lines:
        if "BLOCKED" not in line or TARGET_HOOK not in line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        ev = _extract_event(obj, since_dt, uuid_map, tu_map, path)
        if ev:
            events.append(ev)
    return events


def _extract_event(obj: dict, since_dt: datetime, uuid_map: dict, tu_map: dict, path: Path) -> dict | None:
    if obj.get("type") != "user":
        return None
    ts_str = obj.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts < since_dt:
        return None
    cwd = obj.get("cwd", "")
    project = os.path.basename(cwd.split("/.claude/worktrees/")[0]) if cwd else "unknown"

    for c in _content(obj):
        if c.get("type") != "tool_result":
            continue
        raw = c.get("content") or ""
        text = (" ".join(x.get("text", "") for x in raw if isinstance(x, dict))
                if isinstance(raw, list) else raw)
        m = _BLOCK_RE.search(text)
        if not m or TARGET_HOOK not in m.group(1):
            continue

        tid = c.get("tool_use_id", "")
        cmd = tu_map.get(tid, "")
        if not cmd:
            parent = obj.get("parentUuid", "")
            if parent and parent in uuid_map:
                for mc in _content(uuid_map[parent]):
                    if mc.get("type") == "tool_use":
                        cmd = mc.get("input", {}).get("command") or ""
                        break
        return {"timestamp": ts, "project": project, "cmd": cmd}
    return None
