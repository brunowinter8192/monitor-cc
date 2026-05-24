"""Sleep pattern analyzer for block_chained_sleep hook events.

Walks ~/.claude/projects/*/*.jsonl for the last 30 days, correlates each
block_chained_sleep event to its trigger Bash command via tool_use_id, parses
every `sleep N` in that command for context (cmd_before, cmd_after, chain_op,
in_loop, is_canonical), and produces a classification report.

Usage (from project root):
    ./venv/bin/python dev/sleep_pattern_analysis/analyze.py [--since YYYY-MM-DD] [--out PATH]
"""

# INFRASTRUCTURE
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# From classify.py: token classification + add_classification()
from classify import add_classification

PROJECTS_DIR = Path.home() / ".claude" / "projects"
DEFAULT_DAYS = 30
TARGET_HOOK = "block_chained_sleep"

_BLOCK_RE = re.compile(r'PreToolUse:\w+ hook error: \[python3 ([^\]]+)\]: BLOCKED: ([^\n]+)')
_SLEEP_RE = re.compile(r'\bsleep\s+(\d+(?:\.\d+)?)\b')
_OP_RE    = re.compile(r'(&&|\|\||;|\n)')
_LOOP_RE  = re.compile(r'\b(while|for|until)\b')
_content  = lambda obj: [c for c in (obj.get("message", {}).get("content") or []) if isinstance(c, dict)]


# ORCHESTRATOR


def analyze_sleep_patterns_workflow():
    args = _parse_args()
    since_dt = (
        datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if args.since
        else datetime.now(timezone.utc) - timedelta(days=DEFAULT_DAYS)
    )
    events = _collect_events(since_dt)
    records = _parse_all_sleeps(events)
    report = _build_report(records, events, since_dt)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(out)


# FUNCTIONS


def _parse_args():
    p = argparse.ArgumentParser(description="Analyze block_chained_sleep events")
    p.add_argument("--since", default=None, help="YYYY-MM-DD (default: 30d ago)")
    p.add_argument("--out", default="dev/sleep_pattern_analysis/01_reports/sleep_audit_2026-05-24.md")
    return p.parse_args()


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

    # Pass 1: build tool_use_id → command map + uuid → entry map
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

    # Pass 2: find block events for target hook
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

        # Resolve trigger command: exact tool_use_id first, then parent fallback
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


def _parse_all_sleeps(events: list) -> list:
    records = []
    for ev in events:
        if not ev["cmd"]:
            continue
        for rec in _sleep_contexts(ev["cmd"]):
            rec["timestamp"] = ev["timestamp"]
            rec["project"]   = ev["project"]
            rec["cmd_snippet"] = ev["cmd"][:200].replace("\n", " ")
            records.append(rec)
    return records


def _sleep_contexts(cmd: str) -> list:
    # Pre-detect heredoc spans: list of (start, end) byte ranges that are heredoc bodies
    heredoc_spans = _heredoc_spans(cmd)

    results = []
    for m in _SLEEP_RE.finditer(cmd):
        duration = float(m.group(1))
        pos    = m.start()
        before = cmd[:pos]
        after  = cmd[m.end():]

        # Flag sleeps that land inside a heredoc body (hook FP — regex scanner too broad)
        in_heredoc = any(s <= pos < e for s, e in heredoc_spans)

        # chain_op and cmd_before
        ops = list(_OP_RE.finditer(before))
        if ops:
            last_op  = ops[-1]
            chain_op = last_op.group(1)
            seg_after_op = before[last_op.end():]
            # If nothing between last operator and sleep, cmd_before is the segment
            # ending at the operator (e.g. "cmd2\n sleep" → cmd_before = "cmd2")
            if seg_after_op.strip():
                segment = seg_after_op
            elif len(ops) >= 2:
                segment = before[ops[-2].end(): last_op.start()]
            else:
                segment = before[: last_op.start()]
        else:
            chain_op = "start"
            segment  = before

        cmd_before = _first_token(segment)

        # cmd_after: first token after the operator following sleep
        op_after = re.match(r"\s*(&&|\|\||;|\n)\s*", after)
        rest      = after[op_after.end():] if op_after else after
        cmd_after = _first_token(rest)

        is_canonical = bool(re.match(r"\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*$", cmd.strip()))
        in_loop      = bool(_LOOP_RE.search(before[-200:]))

        results.append({
            "duration":     int(duration) if duration == int(duration) else duration,
            "cmd_before":   cmd_before,
            "cmd_after":    cmd_after,
            "chain_op":     chain_op,
            "in_loop":      in_loop,
            "is_canonical": is_canonical,
            "in_heredoc":   in_heredoc,
        })
    return results


def _heredoc_spans(cmd: str) -> list:
    """Return list of (start, end) for heredoc body regions in cmd."""
    spans = []
    for hm in re.finditer(r"<<['\"]?(\w+)['\"]?\n", cmd):
        delim = hm.group(1)
        body_start = hm.end()
        end_pat = re.compile(r"^" + re.escape(delim) + r"\s*$", re.MULTILINE)
        em = end_pat.search(cmd, body_start)
        if em:
            spans.append((body_start, em.start()))
    return spans


def _first_token(text: str) -> str:
    text = text.strip()
    if not text:
        return "(empty)"
    # Strip variable assignments (VAR=val ...)
    text = re.sub(r"^[A-Z_][A-Z_0-9]*=\S*\s*", "", text).strip()
    if not text:
        return "(assignment)"
    first = text.split()[0]
    first = first.lstrip("$(")          # strip subshell prefixes
    if first.startswith("./"):
        first = first[2:]
    if "/" in first:
        first = os.path.basename(first)  # normalize paths to basename
    return first or "(empty)"


def _build_report(records: list, events: list, since_dt: datetime) -> str:
    now_str   = datetime.now().strftime("%Y-%m-%d %H:%M")
    since_str = since_dt.strftime("%Y-%m-%d")
    dates     = [ev["timestamp"] for ev in events]
    date_min  = min(dates).strftime("%Y-%m-%d") if dates else "—"
    date_max  = max(dates).strftime("%Y-%m-%d") if dates else "—"

    heredoc_n = sum(1 for r in records if r.get("in_heredoc"))
    shell_recs = [r for r in records if not r.get("in_heredoc")]

    lines = [
        "# Sleep Pattern Audit — block_chained_sleep",
        f"Generated: {now_str}  ",
        f"Period analysed: {since_str} → today  ",
        f"Actual date range in data: {date_min} – {date_max}  ",
        f"Total blocked events: {len(events)}  ",
        f"Total sleep occurrences parsed: {len(records)} "
        f"({heredoc_n} inside heredoc bodies — hook FP, excluded from histograms)  ",
        f"Shell-level sleep occurrences (used for histograms): {len(shell_recs)}  ",
        "",
    ]

    if not shell_recs:
        lines.append("_No shell-level sleep data._")
        return "\n".join(lines) + "\n"

    # cmd_before histogram — shell sleeps only
    before_counts: dict = defaultdict(list)
    for r in shell_recs:
        before_counts[r["cmd_before"]].append(r)
    top_before = sorted(before_counts.items(), key=lambda x: -len(x[1]))[:25]

    lines += ["## cmd_before Histogram (top 25)", "",
              "| Rank | Token | Count | % | Example commands |",
              "|---|---|---|---|---|"]
    for rank, (tok, recs) in enumerate(top_before, 1):
        pct = 100 * len(recs) / len(shell_recs)
        # pick up to 3 unique snippets
        seen: set = set()
        examples = []
        for r in recs:
            snip = r["cmd_snippet"][:120].replace("|", "\\|")
            if snip not in seen:
                seen.add(snip)
                examples.append(f"`{snip}`")
            if len(examples) == 3:
                break
        ex_str = " / ".join(examples)
        lines.append(f"| {rank} | `{tok}` | {len(recs)} | {pct:.1f}% | {ex_str} |")
    lines.append("")

    # cmd_after histogram
    after_counts: dict = defaultdict(int)
    for r in shell_recs:
        after_counts[r["cmd_after"]] += 1
    top_after = sorted(after_counts.items(), key=lambda x: -x[1])[:15]
    lines += ["## cmd_after Histogram (top 15)", "",
              "| Rank | Token | Count | % |",
              "|---|---|---|---|"]
    for rank, (tok, cnt) in enumerate(top_after, 1):
        lines.append(f"| {rank} | `{tok}` | {cnt} | {100*cnt/len(shell_recs):.1f}% |")
    lines.append("")

    # In-loop vs naked
    in_loop_n   = sum(1 for r in shell_recs if r["in_loop"])
    canonical_n = sum(1 for r in shell_recs if r["is_canonical"])
    n = len(shell_recs)
    lines += [
        "## In-loop vs Naked vs Canonical",
        "",
        f"- In-loop (`while`/`for`/`until` body): **{in_loop_n}** ({100*in_loop_n/n:.1f}%)",
        f"- Canonical (`sleep N && echo done` standalone): **{canonical_n}** ({100*canonical_n/n:.1f}%)",
        f"- Naked (neither): **{n - in_loop_n - canonical_n}**",
        "",
    ]

    # Duration distribution
    buckets = {"1s": 0, "2–5s": 0, "6–15s": 0, "16–60s": 0, "60s+": 0}
    bucket_ex: dict = defaultdict(list)
    for r in shell_recs:
        d = r["duration"]
        if d <= 1:    bkt = "1s"
        elif d <= 5:  bkt = "2–5s"
        elif d <= 15: bkt = "6–15s"
        elif d <= 60: bkt = "16–60s"
        else:         bkt = "60s+"
        buckets[bkt] += 1
        if len(bucket_ex[bkt]) < 2:
            bucket_ex[bkt].append(r["cmd_snippet"][:100])
    lines += ["## Sleep Duration Distribution", "",
              "| Bucket | Count | % | Example |",
              "|---|---|---|---|"]
    for bkt, cnt in buckets.items():
        pct = 100 * cnt / n
        ex = bucket_ex[bkt][0][:80].replace("|", "\\|") if bucket_ex[bkt] else "—"
        lines.append(f"| {bkt} | {cnt} | {pct:.1f}% | `{ex}` |")
    lines.append("")

    # Classification
    lines += ["## Classification", ""]
    add_classification(lines, before_counts)

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    analyze_sleep_patterns_workflow()
