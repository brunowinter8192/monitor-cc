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

# Parse one JSONL file and return block events matching filters
def _parse_jsonl(path: Path, since_dt: datetime, project_filter, hook_filter) -> list:
    events = []
    try:
        with open(path) as f:
            for line in f:
                if "BLOCKED" not in line:   # fast skip before JSON parse
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ev = _extract_event(obj, since_dt, project_filter, hook_filter)
                if ev:
                    events.append(ev)
    except OSError as e:
        print(f"Warning: could not read {path}: {e}", file=sys.stderr)
    return events

# Extract a block event dict from one JSONL entry; return None if not a match
def _extract_event(obj: dict, since_dt: datetime, project_filter, hook_filter) -> dict | None:
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
        return {
            "timestamp": ts,
            "date": ts.strftime("%Y-%m-%d"),
            "hook_name": hook_name,
            "project": project,
            "session_type": session_type,
            "branch": obj.get("gitBranch", ""),
            "blocked_msg": m.group(2).strip()[:80],
        }
    return None

# Derive project name from cwd (strips worktree suffix if present)
def _project_from_cwd(cwd: str) -> str:
    if ".claude/worktrees/" in cwd:
        cwd = cwd.split("/.claude/worktrees/")[0]
    return os.path.basename(cwd) if cwd else "unknown"

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

    # --- By project × hook ---
    proj_hook: dict = defaultdict(lambda: {"total": 0, "main": 0, "worker": 0})
    for ev in events:
        d = proj_hook[(ev["project"], ev["hook_name"])]
        d["total"] += 1
        d[ev["session_type"]] += 1

    lines += [
        "",
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
        "| Timestamp | Hook | Project | Type | Branch | Message |",
        "|---|---|---|---|---|---|",
    ]
    for ev in sorted(events, key=lambda x: x["timestamp"], reverse=True)[:50]:
        ts = ev["timestamp"].strftime("%Y-%m-%d %H:%M")
        msg = ev["blocked_msg"].replace("|", "\\|")
        lines.append(
            f"| {ts} | {ev['hook_name']} | {ev['project']} | {ev['session_type']} | {ev['branch']} | {msg} |"
        )

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    analyze_blocks_workflow()
