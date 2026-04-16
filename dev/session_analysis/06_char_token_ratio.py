#!/usr/bin/env python3
"""Correlates per-request char counts (system/tools/messages) with actual API token usage (CR, CC, D).

Single mode: reads one proxy JSONL log + optional session JSONL.
Batch mode (--batch DIR): scans all opus proxy logs, auto-pairs with session JSONLs by time overlap.
All scripts assume CWD = Monitor_CC/ (project root).
"""
# INFRASTRUCTURE
import argparse
import gzip
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

SESSION_DIR = (
    Path.home() / ".claude" / "projects"
    / "-Users-brunowinter2000-Documents-ai-Monitor-CC"
)

# ORCHESTRATOR

def main():
    args = parse_args()
    if args.batch:
        print(run_batch(Path(args.batch)))
    else:
        if not args.proxy_log:
            sys.exit("error: proxy_log required unless --batch is used")
        proxy_path = Path(args.proxy_log)
        session_path = Path(args.session_jsonl).expanduser() if args.session_jsonl else None
        proxy_rows = load_proxy_rows(proxy_path)
        session_rows = load_session_rows(session_path) if session_path else None
        print(build_table(proxy_rows, session_rows, proxy_path, session_path))

# FUNCTIONS

# Parse CLI arguments — proxy_log positional is optional when --batch is used
def parse_args():
    parser = argparse.ArgumentParser(
        description="Correlate proxy log char counts with session JSONL token usage (CR/CC/D)"
    )
    parser.add_argument(
        "proxy_log", nargs="?",
        help="Proxy JSONL log file (api_requests_*.jsonl) — omit when using --batch",
    )
    parser.add_argument(
        "--session-jsonl",
        help="Session JSONL file for CR/CC/D pairing (optional, single mode only)",
    )
    parser.add_argument(
        "--batch", metavar="DIR",
        help="Scan all api_requests_opus_monitor_cc_*.jsonl in DIR, auto-pair with session JSONLs",
    )
    return parser.parse_args()


# Run batch analysis across all proxy logs in proxy_dir — returns formatted output string
def run_batch(proxy_dir):
    proxy_logs = sorted(proxy_dir.glob("api_requests_opus_monitor_cc_*.jsonl"))
    if not proxy_logs:
        return f"No api_requests_opus_monitor_cc_*.jsonl found in {proxy_dir}"

    print(f"[batch] {len(proxy_logs)} proxy logs found, pairing with sessions...", file=sys.stderr)
    session_map = pair_sessions(proxy_logs)
    paired_count = sum(1 for p in proxy_logs if p in session_map)
    print(f"[batch] {paired_count}/{len(proxy_logs)} logs paired", file=sys.stderr)

    all_rows = []
    for proxy_path in proxy_logs:
        session_path = session_map.get(proxy_path)
        session_id = extract_session_id(proxy_path)
        proxy_rows = load_proxy_rows(proxy_path)
        session_rows = load_session_rows(session_path) if session_path else None
        for row in proxy_rows:
            entry = dict(row)
            entry["session_id"] = session_id
            entry["session_token"] = None
            if session_rows and row["req_n"] <= len(session_rows):
                entry["session_token"] = session_rows[row["req_n"] - 1]
            all_rows.append(entry)

    table = build_batch_table(all_rows)
    summary = compute_summary(all_rows, len(proxy_logs), paired_count)
    return table + "\n\n" + summary


# Match each proxy log to the best-overlapping session JSONL by time range
def pair_sessions(proxy_logs):
    session_ranges = {}
    if SESSION_DIR.exists():
        session_files = list(SESSION_DIR.glob("*.jsonl"))
        print(f"[batch] scanning {len(session_files)} session files for time ranges...", file=sys.stderr)
        for sp in session_files:
            r = extract_time_range_session(sp)
            if r:
                session_ranges[sp] = r

    result = {}
    for proxy_path in proxy_logs:
        pr = extract_time_range_proxy(proxy_path)
        if not pr:
            continue
        p_start, p_end = pr
        best = None
        best_overlap = -1.0
        for sp, (s_start, s_end) in session_ranges.items():
            if p_start <= s_end and p_end >= s_start:
                overlap = min(p_end, s_end) - max(p_start, s_start)
                if overlap > best_overlap:
                    best = sp
                    best_overlap = overlap
        if best is not None:
            result[proxy_path] = best
    return result


# Extract short numeric ID from proxy log filename (last underscore segment)
def extract_session_id(proxy_path):
    parts = proxy_path.stem.split("_")
    return parts[-1] if parts else proxy_path.stem


# Extract (first_ts_float, last_ts_float) from proxy log timestamps
def extract_time_range_proxy(proxy_path):
    first_ts = None
    last_ts = None
    try:
        with _open_jsonl(proxy_path) as f:
            for line in f:
                ts = _fast_extract_ts(line)
                if ts is not None:
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts
    except Exception:
        return None
    if first_ts is None:
        return None
    return first_ts, last_ts


# Extract (first_ts_float, last_ts_float) from session JSONL timestamps
def extract_time_range_session(session_path):
    first_ts = None
    last_ts = None
    try:
        with open(session_path, encoding="utf-8") as f:
            for line in f:
                ts = _fast_extract_ts(line)
                if ts is not None:
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts
    except Exception:
        return None
    if first_ts is None:
        return None
    return first_ts, last_ts


# Fast timestamp extraction without full JSON parse — looks for "timestamp":"..." pattern
def _fast_extract_ts(line):
    idx = line.find('"timestamp"')
    if idx == -1:
        return None
    colon = line.find(":", idx)
    if colon == -1:
        return None
    q1 = line.find('"', colon)
    if q1 == -1:
        return None
    q2 = line.find('"', q1 + 1)
    if q2 == -1:
        return None
    ts_str = line[q1 + 1:q2]
    return _parse_ts(ts_str)


# Parse ISO timestamp string to float Unix seconds
def _parse_ts(ts_str):
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


# Open proxy JSONL — supports gzip and plain text
def _open_jsonl(path):
    p = Path(path)
    if p.suffix == ".gz" or p.name.endswith(".jsonl.gz"):
        return gzip.open(p, "rt", encoding="utf-8")
    return open(p, encoding="utf-8")


# Extract total chars from raw_payload system blocks (text fields only)
def _system_chars(raw_payload):
    total = 0
    for block in raw_payload.get("system", []) or []:
        if isinstance(block, dict):
            total += len(block.get("text", ""))
    return total


# Extract total chars from raw_payload tools (json.dumps of each tool)
def _tools_chars(raw_payload):
    total = 0
    for tool in raw_payload.get("tools", []) or []:
        total += len(json.dumps(tool, ensure_ascii=False))
    return total


# Extract total chars from raw_payload messages (text content fields)
def _msgs_chars(raw_payload):
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


# Load all non-haiku, non-sent_meta proxy entries — returns list of row dicts
def load_proxy_rows(proxy_path):
    rows = []
    prev_msgs_chars = None
    prev_sys_chars = None
    prev_tools_chars = None
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
            req_n += 1
            rp = entry.get("raw_payload", {})
            sc = _system_chars(rp)
            tc = _tools_chars(rp)
            mc = _msgs_chars(rp)
            msgs_count = len(rp.get("messages", []) or [])
            delta = mc - prev_msgs_chars if prev_msgs_chars is not None else None
            sys_stable = (sc == prev_sys_chars) if prev_sys_chars is not None else None
            tools_stable = (tc == prev_tools_chars) if prev_tools_chars is not None else None
            rows.append({
                "req_n": req_n,
                "model": model,
                "sys_chars": sc,
                "tools_chars": tc,
                "msgs_chars": mc,
                "msgs_count": msgs_count,
                "delta_msgs_chars": delta,
                "sys_stable": sys_stable,
                "tools_stable": tools_stable,
            })
            prev_msgs_chars = mc
            prev_sys_chars = sc
            prev_tools_chars = tc
    return rows


# Load deduplicated session JSONL opus api_calls — returns list of (cr, cc, d, out) tuples
def load_session_rows(session_path):
    events = []
    pending_key = None
    pending_out = 0
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
                if pending_key is not None:
                    events.append((*pending_key, pending_out))
                    pending_key = None
                    pending_out = 0
                continue
            usage = entry.get("message", {}).get("usage", {})
            if not usage:
                continue
            cr = usage.get("cache_read_input_tokens", 0) or 0
            cc = usage.get("cache_creation_input_tokens", 0) or 0
            d = usage.get("input_tokens", 0) or 0
            out = usage.get("output_tokens", 0) or 0
            key = (cr, cc, d)
            if key == pending_key:
                if out > pending_out:
                    pending_out = out
            else:
                if pending_key is not None:
                    events.append((*pending_key, pending_out))
                pending_key = key
                pending_out = out
    if pending_key is not None:
        events.append((*pending_key, pending_out))
    return events


# Format chars/CC_token ratio — show "—" when CC is zero or data unavailable
def _ratio_str(chars, cc):
    if cc and cc > 0:
        return f"{chars / cc:.1f}"
    return "—"


# Build markdown table for single proxy log
def build_table(proxy_rows, session_rows, proxy_path, session_path):
    has_session = session_rows is not None
    session_label = str(session_path) if session_path else "not provided"

    lines = [
        "# Char-Token Ratio Analysis",
        f"# Proxy log: {proxy_path}",
        f"# Session JSONL: {session_label}",
        "",
    ]

    if has_session:
        lines.append(
            "| REQ# | Model | sys_chars | tools_chars | msgs_chars | msgs_count |"
            " Δmsgs_chars | CR | CC | D | chars/CC_tok |"
        )
        lines.append(
            "|------|-------|----------:|------------:|-----------:|-----------:|"
            "-------------:|---:|---:|--:|-------------:|"
        )
    else:
        lines.append(
            "| REQ# | Model | sys_chars | tools_chars | msgs_chars | msgs_count | Δmsgs_chars |"
        )
        lines.append(
            "|------|-------|----------:|------------:|-----------:|-----------:|-------------:|"
        )

    for row in proxy_rows:
        n = row["req_n"]
        model_short = row["model"].split("/")[-1] if "/" in row["model"] else row["model"]
        if len(model_short) > 24:
            model_short = model_short[:21] + "..."
        delta_str = f"{row['delta_msgs_chars']:+,}" if row["delta_msgs_chars"] is not None else "—"

        if has_session:
            if n <= len(session_rows):
                cr, cc, d, _out = session_rows[n - 1]
                total_chars = row["sys_chars"] + row["tools_chars"] + row["msgs_chars"]
                ratio = _ratio_str(total_chars, cc)
                lines.append(
                    f"| {n} | {model_short} |"
                    f" {row['sys_chars']:,} | {row['tools_chars']:,} |"
                    f" {row['msgs_chars']:,} | {row['msgs_count']:,} |"
                    f" {delta_str} |"
                    f" {cr:,} | {cc:,} | {d:,} |"
                    f" {ratio} |"
                )
            else:
                lines.append(
                    f"| {n} | {model_short} |"
                    f" {row['sys_chars']:,} | {row['tools_chars']:,} |"
                    f" {row['msgs_chars']:,} | {row['msgs_count']:,} |"
                    f" {delta_str} |"
                    f" — | — | — | — |"
                )
        else:
            lines.append(
                f"| {n} | {model_short} |"
                f" {row['sys_chars']:,} | {row['tools_chars']:,} |"
                f" {row['msgs_chars']:,} | {row['msgs_count']:,} |"
                f" {delta_str} |"
            )

    return "\n".join(lines)


# Build combined markdown table for batch mode — includes Session column
def build_batch_table(all_rows):
    has_tokens = any(r.get("session_token") is not None for r in all_rows)

    lines = ["# Char-Token Ratio Analysis — Batch Mode", ""]

    if has_tokens:
        lines.append(
            "| Session | REQ# | Model | sys_chars | tools_chars | msgs_chars |"
            " msgs_count | Δmsgs_chars | CR | CC | D | chars/CC_tok |"
        )
        lines.append(
            "|---------|------|-------|----------:|------------:|-----------:|"
            "-----------:|-------------:|---:|---:|--:|-------------:|"
        )
    else:
        lines.append(
            "| Session | REQ# | Model | sys_chars | tools_chars |"
            " msgs_chars | msgs_count | Δmsgs_chars |"
        )
        lines.append(
            "|---------|------|-------|----------:|------------:|"
            "-----------:|-----------:|-------------:|"
        )

    for row in all_rows:
        n = row["req_n"]
        sid = row["session_id"]
        model_short = row["model"].split("/")[-1] if "/" in row["model"] else row["model"]
        if len(model_short) > 20:
            model_short = model_short[:17] + "..."
        delta_str = f"{row['delta_msgs_chars']:+,}" if row["delta_msgs_chars"] is not None else "—"
        tok = row.get("session_token")

        if has_tokens:
            if tok is not None:
                cr, cc, d, _out = tok
                total_chars = row["sys_chars"] + row["tools_chars"] + row["msgs_chars"]
                ratio = _ratio_str(total_chars, cc)
                lines.append(
                    f"| {sid} | {n} | {model_short} |"
                    f" {row['sys_chars']:,} | {row['tools_chars']:,} |"
                    f" {row['msgs_chars']:,} | {row['msgs_count']:,} |"
                    f" {delta_str} |"
                    f" {cr:,} | {cc:,} | {d:,} |"
                    f" {ratio} |"
                )
            else:
                lines.append(
                    f"| {sid} | {n} | {model_short} |"
                    f" {row['sys_chars']:,} | {row['tools_chars']:,} |"
                    f" {row['msgs_chars']:,} | {row['msgs_count']:,} |"
                    f" {delta_str} |"
                    f" — | — | — | — |"
                )
        else:
            lines.append(
                f"| {sid} | {n} | {model_short} |"
                f" {row['sys_chars']:,} | {row['tools_chars']:,} |"
                f" {row['msgs_chars']:,} | {row['msgs_count']:,} |"
                f" {delta_str} |"
            )

    return "\n".join(lines)


# Compute summary statistics from all batch rows
def compute_summary(all_rows, total_sessions, paired_count):
    total_requests = len(all_rows)
    paired_requests = sum(1 for r in all_rows if r.get("session_token") is not None)

    # Overall chars/CC_tok ratios for all requests with CC > 0
    overall_ratios = []
    for row in all_rows:
        tok = row.get("session_token")
        if tok is None:
            continue
        _cr, cc, _d, _out = tok
        if cc > 0:
            total_chars = row["sys_chars"] + row["tools_chars"] + row["msgs_chars"]
            overall_ratios.append(total_chars / cc)

    # Message delta ratio: REQ#2+ where sys+tools unchanged, CC > 0, delta_msgs_chars > 0
    msg_ratios = []
    for row in all_rows:
        if row["req_n"] < 2:
            continue
        if not row.get("sys_stable") or not row.get("tools_stable"):
            continue
        delta = row.get("delta_msgs_chars")
        if delta is None or delta <= 0:
            continue
        tok = row.get("session_token")
        if tok is None:
            continue
        _cr, cc, _d, _out = tok
        if cc > 0:
            msg_ratios.append(delta / cc)

    # System+Tools prefix ratio: from REQ#1 rows where CR=0 (full rebuild)
    prefix_ratios = []
    for row in all_rows:
        if row["req_n"] != 1:
            continue
        tok = row.get("session_token")
        if tok is None:
            continue
        cr, cc, _d, _out = tok
        if cr == 0 and cc > 0:
            prefix_chars = row["sys_chars"] + row["tools_chars"]
            prefix_ratios.append(prefix_chars / cc)

    lines = ["## Summary", ""]
    lines.append(f"- **Total requests analyzed:** {total_requests:,}")
    lines.append(f"- **Sessions paired:** {paired_count} / {total_sessions}")
    lines.append(f"- **Requests with token data:** {paired_requests:,} / {total_requests:,}")
    lines.append("")

    if overall_ratios:
        med = statistics.median(overall_ratios)
        mean = statistics.mean(overall_ratios)
        stdev = statistics.stdev(overall_ratios) if len(overall_ratios) > 1 else 0.0
        lines.append(f"- **Overall chars/CC_tok** (all requests with CC > 0, n={len(overall_ratios)}):")
        lines.append(f"  - Median: {med:.2f}")
        lines.append(f"  - Mean: {mean:.2f} (stddev: {stdev:.2f})")
    else:
        lines.append("- **Overall chars/CC_tok:** no data (no paired requests with CC > 0)")

    lines.append("")

    if prefix_ratios:
        med_p = statistics.median(prefix_ratios)
        lines.append(
            f"- **System+Tools prefix chars/CC_tok** (REQ#1 full rebuilds where CR=0, n={len(prefix_ratios)}):"
        )
        lines.append(f"  - Median: {med_p:.2f}")
        lines.append(
            "  - Note: REQ#1 CC includes messages too — this ratio is an upper bound on the prefix ratio"
        )
    else:
        lines.append("- **System+Tools prefix chars/CC_tok:** no REQ#1 full-rebuild data")

    lines.append("")

    if msg_ratios:
        med_m = statistics.median(msg_ratios)
        mean_m = statistics.mean(msg_ratios)
        stdev_m = statistics.stdev(msg_ratios) if len(msg_ratios) > 1 else 0.0
        lines.append(
            f"- **Message delta chars/CC_tok** (REQ#2+ stable prefix, n={len(msg_ratios)}):"
        )
        lines.append(f"  - Median: {med_m:.2f}")
        lines.append(f"  - Mean: {mean_m:.2f} (stddev: {stdev_m:.2f})")
        lines.append(
            "  - Derived via: Δmsgs_chars / CC for requests where sys+tools unchanged and CC > 0"
        )
    else:
        lines.append("- **Message delta chars/CC_tok:** no qualifying REQ#2+ data")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
