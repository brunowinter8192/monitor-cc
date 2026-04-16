#!/usr/bin/env python3
"""Correlates per-request char counts (system/tools/messages) with actual API token usage (CR, CC, D).

Reads a proxy JSONL log and optionally a session JSONL for pairing.
All scripts assume CWD = Monitor_CC/ (project root).
"""
# INFRASTRUCTURE
import argparse
import gzip
import json
from pathlib import Path

# ORCHESTRATOR

def main():
    args = parse_args()
    proxy_path = Path(args.proxy_log)
    session_path = Path(args.session_jsonl).expanduser() if args.session_jsonl else None

    proxy_rows = load_proxy_rows(proxy_path)
    session_rows = load_session_rows(session_path) if session_path else None

    print(build_table(proxy_rows, session_rows, proxy_path, session_path))

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
    if p.suffix == ".gz" or (p.name.endswith(".jsonl.gz")):
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
                continue  # skip sent_meta entries
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


# Format chars/CC_token ratio — show "—" when CC is zero or no session data
def _ratio_str(chars, cc):
    if cc and cc > 0:
        return f"{chars / cc:.1f}"
    return "—"


# Build markdown table from proxy rows and optional session rows
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
        # Truncate model name for table readability
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


if __name__ == "__main__":
    main()
