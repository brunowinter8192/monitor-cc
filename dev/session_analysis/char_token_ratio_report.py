# INFRASTRUCTURE
import statistics
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path("dev/session_analysis/04_reports")
ANCHOR_CHARS = 154_550
ANCHOR_TOKENS = 41_975
ANCHOR_RATIO = ANCHOR_CHARS / ANCHOR_TOKENS  # 3.68 chars/token

# FUNCTIONS

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


def _build_sources_and_accounting_lines(paired, msg_ratios, proxy_path, session_path, ts_header):
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

    return [
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


def _build_ratio_sections_lines(prefix_ratio, prefix_info, msg_ratios):
    lines = ["## Prefix-Ratio (REQ#1 backsolve)"]
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

    lines.append("## Message-Delta Ratio (REQ#≥2, no-thinking, Δmsg>0, CC>0)")
    lines.append("Formula: Δmsg_chars / CC  [chars/token]")
    lines.append("")
    ratio_vals = [r["ratio"] for r in msg_ratios]
    lines.append(_stats_block(ratio_vals))
    lines.append("")
    return lines


def _build_tiktoken_drift_lines(tiktoken_drift):
    lines = ["## tiktoken Drift (cl100k_base vs actual input tokens)"]
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
    return lines


def _build_raw_data_lines(paired, prefix_ratio):
    lines = [
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
    return lines


def build_report(paired, msg_ratios, prefix_ratio, prefix_info, tiktoken_drift, proxy_path, session_path) -> str:
    now = datetime.now()
    ts_header = now.strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.extend(_build_sources_and_accounting_lines(paired, msg_ratios, proxy_path, session_path, ts_header))
    lines.extend(_build_ratio_sections_lines(prefix_ratio, prefix_info, msg_ratios))
    lines.extend(_build_tiktoken_drift_lines(tiktoken_drift))
    lines.extend(_build_raw_data_lines(paired, prefix_ratio))
    return "\n".join(lines)


def write_report(report: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"{ts}_token_ratios_live.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path
