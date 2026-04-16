#!/usr/bin/env python3
"""Correlates per-request char counts (system/tools/messages) with actual API token usage (CR, CC, D).

Two meaningful ratios are computed:
  A) Full-rebuild ratio: total_chars / CC for requests where CR=0 (cold cache or first request)
  B) Message-delta ratio: Δmsgs_chars / CC for requests where CR>0, CC>0, and Δmsgs>0

Reads a proxy JSONL log and optionally a session JSONL for pairing.
All scripts assume CWD = Monitor_CC/ (project root).
"""
# INFRASTRUCTURE
import argparse
import gzip
import json
import statistics
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path("dev/session_analysis/04_reports")

# ORCHESTRATOR

def main():
    args = parse_args()
    proxy_path = Path(args.proxy_log)
    session_path = Path(args.session_jsonl).expanduser() if args.session_jsonl else None

    proxy_rows = load_proxy_rows(proxy_path)
    session_rows = load_session_rows(session_path) if session_path else None

    paired = pair_rows(proxy_rows, session_rows)

    rebuild_ratios, delta_ratios = compute_ratios(paired)

    report = build_report(paired, rebuild_ratios, delta_ratios, proxy_path, session_path)

    report_path = write_report(report)
    print(report)
    print(f"\nReport written to: {report_path}")

# FUNCTIONS

# Parse CLI arguments
def parse_args():
    parser = argparse.ArgumentParser(
        description="Correlate proxy log char counts with session JSONL token usage (CR/CC/D)"
    )
    parser.add_argument("proxy_log", help="Proxy JSONL log file (api_requests_*.jsonl)")
    parser.add_argument(
        "--session-jsonl",
        help="Session JSONL file for CR/CC/D pairing (optional)",
    )
    return parser.parse_args()


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
            rows.append({
                "req_n": req_n,
                "model": model,
                "sys_chars": sc,
                "tools_chars": tc,
                "msgs_chars": mc,
                "msgs_count": msgs_count,
                "delta_msgs_chars": delta,
            })
            prev_msgs_chars = mc
    return rows


# Load deduplicated session JSONL opus api_calls — returns list of (cr, cc, d, out) tuples
# Dedup: consecutive assistant events with same (CR, CC, D) → keep highest Out
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


# Join proxy rows with session rows by positional index — returns list of combined dicts
def pair_rows(proxy_rows, session_rows):
    paired = []
    for row in proxy_rows:
        n = row["req_n"]
        token_data = None
        if session_rows is not None and n <= len(session_rows):
            cr, cc, d, out = session_rows[n - 1]
            token_data = {"cr": cr, "cc": cc, "d": d, "out": out}
        paired.append({**row, **(token_data or {})})
    return paired


# Compute full-rebuild and message-delta ratio lists from paired rows
def compute_ratios(paired):
    rebuild_ratios = []
    delta_ratios = []
    for row in paired:
        cr = row.get("cr")
        cc = row.get("cc")
        if cr is None or cc is None or cc == 0:
            continue
        total_chars = row["sys_chars"] + row["tools_chars"] + row["msgs_chars"]
        # Full-rebuild: CR=0 (entire payload was cache-created)
        if cr == 0:
            rebuild_ratios.append((total_chars / cc, row))
        # Delta: CR>0, CC>0, and there is a positive message delta
        delta = row.get("delta_msgs_chars")
        if cr > 0 and delta is not None and delta > 0:
            delta_ratios.append((delta / cc, row))
    return rebuild_ratios, delta_ratios


# Format stats block for a list of (ratio, row) tuples
def _stats_block(ratios):
    if not ratios:
        return "- N data points: 0\n- (no qualifying requests)"
    vals = [r for r, _ in ratios]
    med = statistics.median(vals)
    mean = statistics.mean(vals)
    stddev = statistics.stdev(vals) if len(vals) > 1 else 0.0
    lo, hi = min(vals), max(vals)
    return (
        f"- N data points: {len(vals)}\n"
        f"- Median: {med:.2f} chars/token\n"
        f"- Mean: {mean:.2f} (stddev: {stddev:.2f})\n"
        f"- Range: {lo:.2f} — {hi:.2f}"
    )


# Build full markdown report string
def build_report(paired, rebuild_ratios, delta_ratios, proxy_path, session_path):
    now = datetime.now()
    ts_header = now.strftime("%Y-%m-%d %H:%M")
    session_label = str(session_path) if session_path else "not provided"

    lines = [
        f"# Token Ratio Analysis — {ts_header}",
        "",
        "## Method",
        f"- Proxy log: {proxy_path}",
        f"- Session JSONL: {session_label}",
        "- Pairing: positional index (REQ#N → Nth deduplicated assistant event)",
        "- Filters: Opus/Sonnet only (Haiku skipped), streaming chunks deduplicated",
        "",
        "## Full-Rebuild Ratio (CR=0 requests)",
        "Maps total payload chars to CC tokens — measures chars/token for entire cold-cache requests.",
        "",
        _stats_block(rebuild_ratios),
        "",
        "## Message-Delta Ratio (CR>0, CC>0, Δchars>0)",
        "Maps incremental message chars to CC tokens — measures chars/token for message content specifically.",
        "",
        _stats_block(delta_ratios),
        "",
        "## Known Prefix Size",
        "- System+Tools: ~154,550 chars → ~41,975 tokens = 3.68 chars/token",
        "",
    ]

    # Raw data table — top 20 by CC (descending), only rows with token data
    tokened = [r for r in paired if "cc" in r]
    top20 = sorted(tokened, key=lambda r: r["cc"], reverse=True)[:20]

    lines += [
        "## Raw Data (top 20 by CC)",
        "| REQ# | sys_chars | tools_chars | msgs_chars | Δmsgs | CR | CC | D | ratio_type | ratio |",
        "|-----:|----------:|------------:|-----------:|------:|---:|---:|--:|:----------:|------:|",
    ]
    for row in top20:
        cr, cc, d = row["cr"], row["cc"], row["d"]
        total_chars = row["sys_chars"] + row["tools_chars"] + row["msgs_chars"]
        delta = row.get("delta_msgs_chars")
        delta_str = f"{delta:+,}" if delta is not None else "—"

        if cr == 0 and cc > 0:
            ratio_type = "full-rebuild"
            ratio_val = f"{total_chars / cc:.2f}"
        elif cr > 0 and cc > 0 and delta and delta > 0:
            ratio_type = "delta"
            ratio_val = f"{delta / cc:.2f}"
        else:
            ratio_type = "—"
            ratio_val = "—"

        lines.append(
            f"| {row['req_n']} |"
            f" {row['sys_chars']:,} |"
            f" {row['tools_chars']:,} |"
            f" {row['msgs_chars']:,} |"
            f" {delta_str} |"
            f" {cr:,} | {cc:,} | {d:,} |"
            f" {ratio_type} | {ratio_val} |"
        )

    return "\n".join(lines)


# Write report to 04_reports/ with timestamp filename — returns path
def write_report(report):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"{ts}_token_ratios.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


if __name__ == "__main__":
    main()
