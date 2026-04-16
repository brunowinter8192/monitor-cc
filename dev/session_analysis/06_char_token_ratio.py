#!/usr/bin/env python3
"""Single-session Opus 4.7 char-to-token ratio analysis.

Ratios computed (chars/token, consistent with anchor 3.68 chars/token):
  A) msg-ratio: Δmsg_chars / CC for clean requests (REQ#>=2, no-thinking, Δmsg>0)
  B) prefix-ratio: (sys+tools+msgs chars) / (CC+CR) backsolve from REQ#1 if clean

Filters: Opus only, no-thinking response, streaming dedup.
Auto-detects latest proxy log + session JSONL.
All scripts assume CWD = Monitor_CC/ (project root).
"""
# INFRASTRUCTURE
import gzip
import json
import statistics
from datetime import datetime
from pathlib import Path

import tiktoken

REPORTS_DIR = Path("dev/session_analysis/04_reports")
SESSION_DIR = (
    Path.home() / ".claude" / "projects"
    / "-Users-brunowinter2000-Documents-ai-Monitor-CC"
)
PROXY_LOG_DIR = Path("src/logs")
ANCHOR_CHARS = 154_550
ANCHOR_TOKENS = 41_975
ANCHOR_RATIO = ANCHOR_CHARS / ANCHOR_TOKENS  # 3.68 chars/token

# ORCHESTRATOR

def main():
    proxy_path = find_latest_proxy_log()
    session_path = find_latest_session_jsonl()
    print(f"Proxy log:    {proxy_path}")
    print(f"Session JSONL: {session_path}")

    proxy_rows = load_proxy_rows(proxy_path)
    session_events = load_session_events(session_path)
    paired = pair_rows(proxy_rows, session_events)

    msg_ratios, prefix_ratio, prefix_info = compute_ratios(paired)
    tiktoken_drift = compute_tiktoken_drift(proxy_path, paired)

    report = build_report(paired, msg_ratios, prefix_ratio, prefix_info, tiktoken_drift, proxy_path, session_path)
    report_path = write_report(report)
    print(report)
    print(f"\nReport written to: {report_path}")

# FUNCTIONS

# Find newest api_requests_opus_monitor_cc_*.jsonl by mtime
def find_latest_proxy_log() -> Path:
    logs = list(PROXY_LOG_DIR.glob("api_requests_opus_monitor_cc_*.jsonl"))
    if not logs:
        raise FileNotFoundError(f"No opus proxy logs found in {PROXY_LOG_DIR}")
    return max(logs, key=lambda p: p.stat().st_mtime)


# Find newest non-agent session JSONL in SESSION_DIR by mtime
def find_latest_session_jsonl() -> Path:
    candidates = [
        p for p in SESSION_DIR.glob("*.jsonl")
        if "agent" not in p.name
    ]
    if not candidates:
        raise FileNotFoundError(f"No session JSONLs found in {SESSION_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


# Open proxy JSONL — supports gzip and plain text
def _open_jsonl(path: Path):
    if path.suffix == ".gz" or path.name.endswith(".jsonl.gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


# Extract total chars from raw_payload system blocks (text fields only)
def _system_chars(raw_payload: dict) -> int:
    total = 0
    for block in raw_payload.get("system", []) or []:
        if isinstance(block, dict):
            total += len(block.get("text", ""))
    return total


# Extract total chars from raw_payload tools (json.dumps of each tool)
def _tools_chars(raw_payload: dict) -> int:
    total = 0
    for tool in raw_payload.get("tools", []) or []:
        total += len(json.dumps(tool, ensure_ascii=False))
    return total


# Extract total chars from raw_payload messages (text content fields)
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


# Load Opus-only proxy rows — returns list of row dicts (haiku filtered out)
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


# Load deduplicated session events — returns list of dicts with (cr, cc, d, out, has_thinking)
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
                if pending_key is not None:
                    cr, cc, d = pending_key
                    events.append({"cr": cr, "cc": cc, "d": d, "out": pending_out, "has_thinking": pending_has_thinking})
                    pending_key = None
                    pending_out = 0
                    pending_has_thinking = False
                continue
            msg = entry.get("message", {})
            usage = msg.get("usage", {})
            if not usage:
                continue
            cr = usage.get("cache_read_input_tokens", 0) or 0
            cc = usage.get("cache_creation_input_tokens", 0) or 0
            d = usage.get("input_tokens", 0) or 0
            out = usage.get("output_tokens", 0) or 0
            content = msg.get("content", [])
            has_thinking = any(
                isinstance(b, dict) and b.get("type") == "thinking"
                for b in content
            )
            key = (cr, cc, d)
            if key == pending_key:
                if out > pending_out:
                    pending_out = out
                if has_thinking:
                    pending_has_thinking = True
            else:
                if pending_key is not None:
                    pcr, pcc, pd = pending_key
                    events.append({"cr": pcr, "cc": pcc, "d": pd, "out": pending_out, "has_thinking": pending_has_thinking})
                pending_key = key
                pending_out = out
                pending_has_thinking = has_thinking
    if pending_key is not None:
        cr, cc, d = pending_key
        events.append({"cr": cr, "cc": cc, "d": d, "out": pending_out, "has_thinking": pending_has_thinking})
    return events


# Join proxy rows with session events by positional index
def pair_rows(proxy_rows: list, session_events: list) -> list:
    paired = []
    for row in proxy_rows:
        n = row["req_n"]
        tok = None
        if n <= len(session_events):
            tok = session_events[n - 1]
        paired.append({**row, "token": tok})
    return paired


# Compute msg-ratio list and prefix-ratio from paired rows — returns (msg_ratios, prefix_ratio, prefix_info)
def compute_ratios(paired: list) -> tuple:
    msg_ratios = []
    prefix_ratio = None
    prefix_info = {}

    for row in paired:
        tok = row.get("token")
        if tok is None:
            continue
        cr = tok["cr"]
        cc = tok["cc"]
        has_thinking = tok["has_thinking"]
        delta = row.get("delta_msgs_chars")
        req_n = row["req_n"]

        # Prefix-ratio from REQ#1 backsolve (clean only)
        if req_n == 1 and not has_thinking and (cc + cr) > 0:
            total_chars = row["sys_chars"] + row["tools_chars"] + row["msgs_chars"]
            prefix_ratio = total_chars / (cc + cr)
            prefix_info = {
                "req_n": req_n,
                "total_chars": total_chars,
                "total_tokens": cc + cr,
                "cr": cr,
                "cc": cc,
            }

        # msg-ratio for REQ#>=2: clean, positive delta, CC>0
        if req_n >= 2 and not has_thinking and delta is not None and delta > 0 and cc > 0:
            msg_ratios.append({"ratio": delta / cc, "row": row, "tok": tok})

    return msg_ratios, prefix_ratio, prefix_info


# Compute tiktoken cl100k_base estimates and per-request drift vs actual CC
def compute_tiktoken_drift(proxy_path: Path, paired: list) -> list:
    enc = tiktoken.get_encoding("cl100k_base")
    drift_rows = []
    for row in paired:
        tok = row.get("token")
        if tok is None or tok["cc"] == 0:
            continue
        rp = row.get("raw_payload", {})
        # Build text corpus: system + tools + messages
        parts = []
        for block in rp.get("system", []) or []:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
        for tool in rp.get("tools", []) or []:
            parts.append(json.dumps(tool, ensure_ascii=False))
        for msg in rp.get("messages", []) or []:
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for b in content:
                    if isinstance(b, dict):
                        parts.append(b.get("text", ""))
        full_text = "\n".join(parts)
        tiktoken_est = len(enc.encode(full_text))
        actual_total = tok["cr"] + tok["cc"] + tok["d"]
        drift_pct = (tiktoken_est - actual_total) / actual_total * 100 if actual_total > 0 else 0.0
        drift_rows.append({
            "req_n": row["req_n"],
            "tiktoken_est": tiktoken_est,
            "actual_total": actual_total,
            "cr": tok["cr"],
            "cc": tok["cc"],
            "d": tok["d"],
            "drift_pct": drift_pct,
            "has_thinking": tok["has_thinking"],
        })
    return drift_rows


# Build stats block string for a list of ratio values
def _stats_block(vals: list) -> str:
    if not vals:
        return "- N: 0\n- (no qualifying requests)"
    med = statistics.median(vals)
    mean = statistics.mean(vals)
    stddev = statistics.stdev(vals) if len(vals) > 1 else 0.0
    lo, hi = min(vals), max(vals)
    return (
        f"- N: {len(vals)}\n"
        f"- Median: {med:.3f} chars/token\n"
        f"- Mean:   {mean:.3f} (stddev: {stddev:.3f})\n"
        f"- Range:  {lo:.3f} — {hi:.3f}"
    )


# Build full markdown report
def build_report(paired, msg_ratios, prefix_ratio, prefix_info, tiktoken_drift, proxy_path, session_path) -> str:
    now = datetime.now()
    ts_header = now.strftime("%Y-%m-%d %H:%M")

    # Discard accounting
    total_req = len(paired)
    with_token = sum(1 for r in paired if r["token"] is not None)
    discarded_no_token = total_req - with_token
    discarded_thinking = sum(
        1 for r in paired
        if r["token"] is not None and r["token"]["has_thinking"]
    )
    discarded_no_delta = sum(
        1 for r in paired
        if r["token"] is not None
        and not r["token"]["has_thinking"]
        and r["req_n"] >= 2
        and (r.get("delta_msgs_chars") or 0) <= 0
    )
    clean_count = len(msg_ratios)

    lines = [
        f"# Token Ratio Analysis (Live Session) — {ts_header}",
        "",
        "## Sources",
        f"- Proxy log: `{proxy_path.name}`",
        f"- Session JSONL: `{session_path.name}`",
        "- Pairing: positional index (REQ#N → Nth deduplicated assistant event)",
        "- Model filter: Opus only (Haiku excluded)",
        "",
        "## Request Accounting",
        f"- Total Opus requests: {total_req}",
        f"- With token data: {with_token}",
        f"- Discarded (no token data): {discarded_no_token}",
        f"- Discarded (has thinking in response): {discarded_thinking}",
        f"- Discarded (REQ#≥2 but Δmsg≤0): {discarded_no_delta}",
        f"- Clean requests used for msg-ratio: {clean_count}",
        "",
        "## Anchor",
        f"- Known: {ANCHOR_CHARS:,} chars → {ANCHOR_TOKENS:,} tokens = **{ANCHOR_RATIO:.4f} chars/token**",
        "",
    ]

    # prefix-ratio section
    lines.append("## Prefix-Ratio (REQ#1 backsolve)")
    if prefix_ratio is not None:
        pi = prefix_info
        lines += [
            f"- REQ#{pi['req_n']}: {pi['total_chars']:,} chars / {pi['total_tokens']:,} tokens (CR:{pi['cr']:,} + CC:{pi['cc']:,})",
            f"- **Prefix-ratio: {prefix_ratio:.4f} chars/token**",
            f"- Δ vs anchor: {prefix_ratio - ANCHOR_RATIO:+.4f} chars/token",
        ]
    else:
        lines.append("- REQ#1 not clean (has thinking) — no prefix-ratio derived")
    lines.append("")

    # msg-ratio section
    lines.append("## Message-Delta Ratio (REQ#≥2, no-thinking, Δmsg>0, CC>0)")
    lines.append("Formula: Δmsg_chars / CC  [chars/token]")
    lines.append("")
    ratio_vals = [r["ratio"] for r in msg_ratios]
    lines.append(_stats_block(ratio_vals))
    lines.append("")

    # tiktoken comparison
    lines.append("## tiktoken Drift (cl100k_base vs actual input tokens)")
    if tiktoken_drift:
        drift_vals = [r["drift_pct"] for r in tiktoken_drift]
        med_drift = statistics.median(drift_vals)
        mean_drift = statistics.mean(drift_vals)
        lines += [
            f"- N requests: {len(tiktoken_drift)}",
            f"- Median drift: {med_drift:+.1f}%",
            f"- Mean drift:   {mean_drift:+.1f}%  (positive = tiktoken overcounts)",
            f"- Range: {min(drift_vals):+.1f}% — {max(drift_vals):+.1f}%",
            "",
            "| REQ# | tiktoken_est | actual_in | drift% | thinking |",
            "|-----:|-------------:|----------:|-------:|:--------:|",
        ]
        for dr in tiktoken_drift:
            thinking_mark = "✓" if dr["has_thinking"] else ""
            lines.append(
                f"| {dr['req_n']} |"
                f" {dr['tiktoken_est']:,} |"
                f" {dr['actual_total']:,} |"
                f" {dr['drift_pct']:+.1f}% |"
                f" {thinking_mark} |"
            )
    else:
        lines.append("- No requests with CC>0 found")
    lines.append("")

    # Raw data table
    lines += [
        "## Raw Data",
        "| REQ# | sys_chars | tools_chars | msgs_chars | Δmsg | CR | CC | D | thinking | ratio (c/tok) |",
        "|-----:|----------:|------------:|-----------:|-----:|---:|---:|--:|:--------:|--------------:|",
    ]
    for row in paired:
        tok = row.get("token")
        delta = row.get("delta_msgs_chars")
        delta_str = f"{delta:+,}" if delta is not None else "—"
        if tok is None:
            lines.append(
                f"| {row['req_n']} |"
                f" {row['sys_chars']:,} | {row['tools_chars']:,} |"
                f" {row['msgs_chars']:,} | {delta_str} |"
                f" — | — | — | — | — |"
            )
        else:
            cr, cc, d = tok["cr"], tok["cc"], tok["d"]
            thinking_mark = "✓" if tok["has_thinking"] else ""
            is_clean = not tok["has_thinking"] and row["req_n"] >= 2 and delta is not None and delta > 0 and cc > 0
            if is_clean:
                ratio_str = f"{delta / cc:.3f}"
            elif row["req_n"] == 1 and prefix_ratio is not None:
                ratio_str = f"{prefix_ratio:.3f}*"
            else:
                ratio_str = "—"
            lines.append(
                f"| {row['req_n']} |"
                f" {row['sys_chars']:,} | {row['tools_chars']:,} |"
                f" {row['msgs_chars']:,} | {delta_str} |"
                f" {cr:,} | {cc:,} | {d:,} |"
                f" {thinking_mark} | {ratio_str} |"
            )
    lines.append("")
    lines.append("_\\* prefix-ratio (total chars / total tokens, not delta)_")

    return "\n".join(lines)


# Write report to 04_reports/ with timestamp filename — returns path
def write_report(report: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"{ts}_token_ratios_live.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


if __name__ == "__main__":
    main()
