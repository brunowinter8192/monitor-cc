#!/usr/bin/env python3
"""Correlates per-request char counts (system/tools/messages) with actual API token usage (CR, CC, D).

Two meaningful ratios are computed:
  A) Full-rebuild ratio: total_chars / CC for requests where CR=0 (cold cache or first request)
  B) Message-delta ratio: Δmsgs_chars / CC for requests where CR>0, CC>0, and Δmsgs>0

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

REPORTS_DIR = Path("dev/session_analysis/04_reports")
SESSION_DIR = (
    Path.home() / ".claude" / "projects"
    / "-Users-brunowinter2000-Documents-ai-Monitor-CC"
)

# ORCHESTRATOR

def main():
    args = parse_args()
    if args.batch:
        report = run_batch(Path(args.batch))
        report_path = write_report(report)
        print(report)
        print(f"\nReport written to: {report_path}")
    else:
        if not args.proxy_log:
            sys.exit("error: proxy_log required unless --batch is used")
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


# Run batch analysis across all proxy logs in proxy_dir — returns formatted report string
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

    now = datetime.now()
    ts_header = now.strftime("%Y-%m-%d %H:%M")
    table = build_batch_table(all_rows)
    summary = compute_summary(all_rows, len(proxy_logs), paired_count, ts_header)
    return summary + "\n\n" + table


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


# Build full markdown report string for single-mode
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


# Format chars/CC_token ratio — show "—" when CC is zero or data unavailable
def _ratio_str(chars, cc):
    if cc and cc > 0:
        return f"{chars / cc:.1f}"
    return "—"


# Build markdown table for single proxy log (no ratio analysis — raw view)
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

    lines = ["## Raw Data (all sessions)", ""]

    if has_tokens:
        lines.append(
            "| Session | REQ# | sys_chars | tools_chars | msgs_chars |"
            " Δmsgs_chars | CR | CC | D | ratio_type | ratio |"
        )
        lines.append(
            "|---------|-----:|----------:|------------:|-----------:|"
            "-------------:|---:|---:|--:|:----------:|------:|"
        )
    else:
        lines.append(
            "| Session | REQ# | sys_chars | tools_chars | msgs_chars | msgs_count | Δmsgs_chars |"
        )
        lines.append(
            "|---------|-----:|----------:|------------:|-----------:|-----------:|-------------:|"
        )

    for row in all_rows:
        n = row["req_n"]
        sid = row["session_id"]
        delta_str = f"{row['delta_msgs_chars']:+,}" if row["delta_msgs_chars"] is not None else "—"
        tok = row.get("session_token")

        if has_tokens:
            if tok is not None:
                cr, cc, d, _out = tok
                total_chars = row["sys_chars"] + row["tools_chars"] + row["msgs_chars"]
                delta = row.get("delta_msgs_chars")
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
                    f"| {sid} | {n} |"
                    f" {row['sys_chars']:,} | {row['tools_chars']:,} |"
                    f" {row['msgs_chars']:,} |"
                    f" {delta_str} |"
                    f" {cr:,} | {cc:,} | {d:,} |"
                    f" {ratio_type} | {ratio_val} |"
                )
            else:
                lines.append(
                    f"| {sid} | {n} |"
                    f" {row['sys_chars']:,} | {row['tools_chars']:,} |"
                    f" {row['msgs_chars']:,} |"
                    f" {delta_str} |"
                    f" — | — | — | — | — |"
                )
        else:
            lines.append(
                f"| {sid} | {n} |"
                f" {row['sys_chars']:,} | {row['tools_chars']:,} |"
                f" {row['msgs_chars']:,} | {row['msgs_count']:,} |"
                f" {delta_str} |"
            )

    return "\n".join(lines)


# Compute summary statistics for batch mode — two correct ratios only (no misleading overall)
def compute_summary(all_rows, total_sessions, paired_count, ts_header):
    total_requests = len(all_rows)
    paired_requests = sum(1 for r in all_rows if r.get("session_token") is not None)

    # Full-rebuild ratio: CR=0, CC>0 — maps total chars to CC
    rebuild_ratios = []
    for row in all_rows:
        tok = row.get("session_token")
        if tok is None:
            continue
        cr, cc, _d, _out = tok
        if cr == 0 and cc > 0:
            total_chars = row["sys_chars"] + row["tools_chars"] + row["msgs_chars"]
            rebuild_ratios.append(total_chars / cc)

    # Message-delta ratio: CR>0, CC>0, positive delta — maps Δmsgs to CC
    delta_ratios = []
    for row in all_rows:
        tok = row.get("session_token")
        if tok is None:
            continue
        cr, cc, _d, _out = tok
        if cr <= 0 or cc <= 0:
            continue
        delta = row.get("delta_msgs_chars")
        if delta is None or delta <= 0:
            continue
        delta_ratios.append(delta / cc)

    lines = [
        f"# Token Ratio Analysis — Batch Mode — {ts_header}",
        "",
        "## Method",
        f"- Proxy logs scanned: {total_sessions}",
        f"- Sessions paired: {paired_count} / {total_sessions} (by timestamp overlap)",
        "- Filters: Opus/Sonnet only (Haiku skipped), streaming chunks deduplicated",
        "",
        f"## Coverage",
        f"- Total requests analyzed: {total_requests:,}",
        f"- Requests with token data: {paired_requests:,} / {total_requests:,}",
        "",
        "## Full-Rebuild Ratio (CR=0 requests)",
        "Maps total payload chars to CC tokens — entire cold-cache or post-eviction requests.",
        "",
    ]

    if rebuild_ratios:
        med = statistics.median(rebuild_ratios)
        mean = statistics.mean(rebuild_ratios)
        stdev = statistics.stdev(rebuild_ratios) if len(rebuild_ratios) > 1 else 0.0
        lo, hi = min(rebuild_ratios), max(rebuild_ratios)
        lines += [
            f"- N data points: {len(rebuild_ratios)}",
            f"- Median: {med:.2f} chars/token",
            f"- Mean: {mean:.2f} (stddev: {stdev:.2f})",
            f"- Range: {lo:.2f} — {hi:.2f}",
        ]
    else:
        lines += ["- N data points: 0", "- (no qualifying CR=0 requests with token data)"]

    lines += [
        "",
        "## Message-Delta Ratio (CR>0, CC>0, Δchars>0)",
        "Maps incremental message chars to CC tokens — measures chars/token for message content.",
        "",
    ]

    if delta_ratios:
        med = statistics.median(delta_ratios)
        mean = statistics.mean(delta_ratios)
        stdev = statistics.stdev(delta_ratios) if len(delta_ratios) > 1 else 0.0
        lo, hi = min(delta_ratios), max(delta_ratios)
        lines += [
            f"- N data points: {len(delta_ratios)}",
            f"- Median: {med:.2f} chars/token",
            f"- Mean: {mean:.2f} (stddev: {stdev:.2f})",
            f"- Range: {lo:.2f} — {hi:.2f}",
        ]
    else:
        lines += ["- N data points: 0", "- (no qualifying CR>0/CC>0/Δ>0 requests)"]

    lines += [
        "",
        "## Known Prefix Size",
        "- System+Tools: ~154,550 chars → ~41,975 tokens = 3.68 chars/token",
        "",
    ]

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
