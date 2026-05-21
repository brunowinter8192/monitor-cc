# INFRASTRUCTURE
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"

# PreToolUse block format: "PreToolUse:<Tool> hook error: [python3 <path>]: BLOCKED: <msg>"
_BLOCK_RE = re.compile(
    r'PreToolUse:\w+ hook error: \[python3 ([^\]]+)\]: BLOCKED: ([^\n]+)'
)

# Friction: ≥ this many blocks from same (hook, project, branch) within FRICTION_WINDOW_MIN
FRICTION_THRESHOLD = 3
FRICTION_WINDOW_MIN = 30


# ORCHESTRATOR

# Collect hook-block events from ~/.claude/projects, aggregate, write MD report to output path
def analyze_blocks_workflow() -> None:
    args = _parse_args()
    since_dt = _parse_since(args.since)
    events = _collect_events(since_dt, args.project, args.hook)
    report = _build_report(events, since_dt, args.project, args.hook)
    output_path = _resolve_output(args.output)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(report)
    print(output_path)


# FUNCTIONS

# Parse CLI arguments
def _parse_args():
    p = argparse.ArgumentParser(description="Analyse CC hook-block events across sessions")
    p.add_argument("--since", default=None, help="YYYY-MM-DD (default: 7 days ago)")
    p.add_argument("--project", default=None, help="Project filter (case-insensitive substring)")
    p.add_argument("--hook", default=None, help="Hook name filter (case-insensitive substring)")
    p.add_argument("--output", default=None, help="Output path (default: dev/hook_analysis/reports/<ts>.md)")
    return p.parse_args()

# Parse --since string or return default 7 days ago
def _parse_since(since_str: str | None) -> datetime:
    if since_str:
        return datetime.strptime(since_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - timedelta(days=7)

# Resolve --output path or generate timestamped default
def _resolve_output(output: str | None) -> str:
    if output:
        return output
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return f"dev/hook_analysis/reports/{ts}.md"

# Walk all JSONL files in ~/.claude/projects, extract matching block events
def _collect_events(since_dt: datetime, project_filter: str | None, hook_filter: str | None) -> list:
    events = []
    cutoff = since_dt - timedelta(hours=1)  # 1h buffer for mtime imprecision
    for jsonl_path in sorted(PROJECTS_DIR.glob("*/*.jsonl")):
        try:
            mtime = datetime.fromtimestamp(jsonl_path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            mtime = None  # can't stat → don't skip
        if mtime is not None and mtime < cutoff:
            continue
        events.extend(_parse_jsonl(jsonl_path, since_dt, project_filter, hook_filter))
    return events

# Parse one JSONL file and return block events with trigger commands
def _parse_jsonl(path: Path, since_dt: datetime, project_filter, hook_filter) -> list:
    events = []
    try:
        lines = path.read_text(errors='replace').splitlines()
    except OSError as e:
        print(f"Warning: could not read {path}: {e}", file=sys.stderr)
        return events

    # Pass 1: build uuid→entry index for parentUuid lookup
    uuid_map: dict = {}
    for line in lines:
        if '"uuid"' not in line:
            continue
        try:
            obj = json.loads(line)
            uid = obj.get("uuid")
            if uid:
                uuid_map[uid] = obj
        except json.JSONDecodeError:
            continue

    # Pass 2: extract block events
    for line in lines:
        if "BLOCKED" not in line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        ev = _extract_event(obj, since_dt, project_filter, hook_filter, uuid_map)
        if ev:
            events.append(ev)
    return events

# Extract a block event dict from one JSONL entry; return None if not a match
def _extract_event(obj: dict, since_dt: datetime, project_filter, hook_filter, uuid_map: dict) -> dict | None:
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
    project = _project_from_cwd(cwd)
    session_type = "worker" if ".claude/worktrees/" in cwd else "main"

    if project_filter and project_filter.lower() not in project.lower():
        return None

    content = obj.get("message", {}).get("content", [])
    if not isinstance(content, list):
        return None

    for c in content:
        if not isinstance(c, dict) or c.get("type") != "tool_result":
            continue
        raw = c.get("content") or ""
        text = (
            " ".join(x.get("text", "") for x in raw if isinstance(x, dict))
            if isinstance(raw, list)
            else raw
        )
        m = _BLOCK_RE.search(text)
        if not m:
            continue
        hook_name = os.path.basename(m.group(1)).replace(".py", "")
        if hook_filter and hook_filter.lower() not in hook_name.lower():
            continue

        trigger_cmd = _find_trigger_cmd(obj, uuid_map)
        return {
            "timestamp": ts,
            "date": ts.strftime("%Y-%m-%d"),
            "hook_name": hook_name,
            "project": project,
            "session_type": session_type,
            "branch": obj.get("gitBranch", ""),
            "blocked_msg": m.group(2).strip()[:80],
            "trigger_cmd": trigger_cmd,
            "trigger_pattern": _pattern_key(trigger_cmd),
        }
    return None

# Find the tool_use command that preceded this block via parentUuid lookup
def _find_trigger_cmd(block_entry: dict, uuid_map: dict) -> str:
    parent_uuid = block_entry.get("parentUuid")
    if not parent_uuid:
        return ""
    parent = uuid_map.get(parent_uuid)
    if not parent:
        return ""
    content = parent.get("message", {}).get("content", [])
    if not isinstance(content, list):
        return ""
    for c in content:
        if not isinstance(c, dict) or c.get("type") != "tool_use":
            continue
        inp = c.get("input", {})
        cmd = inp.get("command") or inp.get("file_path") or ""
        return cmd
    return ""

# Derive project name from cwd (strips worktree suffix if present)
def _project_from_cwd(cwd: str) -> str:
    if ".claude/worktrees/" in cwd:
        cwd = cwd.split("/.claude/worktrees/")[0]
    return os.path.basename(cwd) if cwd else "unknown"

# Normalize trigger command to a stable pattern key for clustering
def _pattern_key(cmd: str) -> str:
    if not cmd:
        return "(unknown)"
    # Take first non-empty line, strip leading variable assignments (VAR=val)
    first_line = cmd.split('\n')[0].strip()
    first_line = re.sub(r'^[A-Z_]+=\S+\s*', '', first_line).strip()
    # Truncate to 70 chars for display
    return first_line[:70] or "(empty)"

# Detect friction clusters: (hook, project, branch) groups with ≥ threshold blocks in window
def _find_friction_clusters(events: list) -> list:
    groups: dict = defaultdict(list)
    for ev in events:
        key = (ev["hook_name"], ev["project"], ev["branch"])
        groups[key].append(ev["timestamp"])

    clusters = []
    for (hook, proj, branch), timestamps in groups.items():
        timestamps_sorted = sorted(timestamps)
        # Sliding window: find any consecutive sub-sequence within FRICTION_WINDOW_MIN
        for i in range(len(timestamps_sorted)):
            window_end = timestamps_sorted[i] + timedelta(minutes=FRICTION_WINDOW_MIN)
            in_window = [t for t in timestamps_sorted[i:] if t <= window_end]
            if len(in_window) >= FRICTION_THRESHOLD:
                clusters.append({
                    "hook": hook, "project": proj, "branch": branch,
                    "count": len(in_window),
                    "window_start": timestamps_sorted[i].strftime("%Y-%m-%d %H:%M"),
                    "window_end": in_window[-1].strftime("%H:%M"),
                })
                break  # one cluster report per group
    return sorted(clusters, key=lambda x: -x["count"])

# Build the full MD report string from aggregated events
def _build_report(events: list, since_dt: datetime, project_filter, hook_filter) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    since_str = since_dt.strftime("%Y-%m-%d")

    lines = [
        "# Hook Block Analysis",
        f"Generated: {now}  ",
        f"Period: {since_str} → today  ",
        f"Total blocks: {len(events)}  ",
    ]
    if project_filter:
        lines.append(f"Project filter: `{project_filter}`  ")
    if hook_filter:
        lines.append(f"Hook filter: `{hook_filter}`  ")
    lines.append("")

    if not events:
        lines.append("_No hook blocks found in the specified period._")
        return "\n".join(lines) + "\n"

    # --- Summary by hook ---
    hook_counts: dict = defaultdict(lambda: {"total": 0, "main": 0, "worker": 0})
    for ev in events:
        d = hook_counts[ev["hook_name"]]
        d["total"] += 1
        d[ev["session_type"]] += 1

    lines += [
        "## Summary by Hook",
        "",
        "| Hook | Total | Main | Worker |",
        "|---|---|---|---|",
    ]
    for hook_name, counts in sorted(hook_counts.items(), key=lambda x: -x[1]["total"]):
        lines.append(f"| {hook_name} | {counts['total']} | {counts['main']} | {counts['worker']} |")

    # --- Friction candidates ---
    friction = _find_friction_clusters(events)
    if friction:
        lines += [
            "",
            f"## Friction Candidates (≥{FRICTION_THRESHOLD} blocks in {FRICTION_WINDOW_MIN}min, same hook+branch)",
            "",
            "| Hook | Branch | Project | Count | Window |",
            "|---|---|---|---|---|",
        ]
        for fc in friction:
            lines.append(
                f"| {fc['hook']} | {fc['branch']} | {fc['project']} | "
                f"{fc['count']} | {fc['window_start']}–{fc['window_end']} |"
            )

    # --- Top trigger patterns per hook ---
    hook_patterns: dict = defaultdict(lambda: defaultdict(lambda: {"count": 0, "session_types": set()}))
    for ev in events:
        d = hook_patterns[ev["hook_name"]][ev["trigger_pattern"]]
        d["count"] += 1
        d["session_types"].add(ev["session_type"])

    lines += ["", "## Top Trigger Patterns by Hook", ""]
    for hook_name in sorted(hook_counts.keys(), key=lambda h: -hook_counts[h]["total"]):
        patterns = hook_patterns[hook_name]
        top = sorted(patterns.items(), key=lambda x: -x[1]["count"])[:5]
        lines.append(f"### {hook_name}")
        lines += ["", "| Pattern | Count | Session Types |", "|---|---|---|"]
        for pat, info in top:
            st = ", ".join(sorted(info["session_types"]))
            lines.append(f"| `{pat[:68]}` | {info['count']} | {st} |")
        lines.append("")

    # --- By project × hook ---
    proj_hook: dict = defaultdict(lambda: {"total": 0, "main": 0, "worker": 0})
    for ev in events:
        d = proj_hook[(ev["project"], ev["hook_name"])]
        d["total"] += 1
        d[ev["session_type"]] += 1

    lines += [
        "## By Project × Hook",
        "",
        "| Project | Hook | Total | Main | Worker |",
        "|---|---|---|---|---|",
    ]
    for (proj, hook_name), counts in sorted(proj_hook.items(), key=lambda x: (-x[1]["total"], x[0])):
        lines.append(f"| {proj} | {hook_name} | {counts['total']} | {counts['main']} | {counts['worker']} |")

    # --- Timeline by date ---
    date_counts: dict = defaultdict(lambda: defaultdict(int))
    for ev in events:
        date_counts[ev["date"]][ev["hook_name"]] += 1

    lines += [
        "",
        "## Timeline",
        "",
        "| Date | Hook | Count |",
        "|---|---|---|",
    ]
    for date in sorted(date_counts.keys()):
        for hook_name, count in sorted(date_counts[date].items(), key=lambda x: -x[1]):
            lines.append(f"| {date} | {hook_name} | {count} |")

    # --- Raw events (newest first, max 50) ---
    lines += [
        "",
        "## Events (newest first, max 50)",
        "",
        "| Timestamp | Hook | Project | Type | Branch | Trigger | Message |",
        "|---|---|---|---|---|---|---|",
    ]
    for ev in sorted(events, key=lambda x: x["timestamp"], reverse=True)[:50]:
        ts = ev["timestamp"].strftime("%Y-%m-%d %H:%M")
        msg = ev["blocked_msg"].replace("|", "\\|")
        pat = ev["trigger_pattern"][:40].replace("|", "\\|")
        lines.append(
            f"| {ts} | {ev['hook_name']} | {ev['project']} | {ev['session_type']} "
            f"| {ev['branch']} | `{pat}` | {msg} |"
        )

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    analyze_blocks_workflow()
