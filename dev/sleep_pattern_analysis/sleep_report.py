# INFRASTRUCTURE
from collections import defaultdict
from datetime import datetime

from classify import add_classification


# FUNCTIONS

def _build_report(records: list, events: list, since_dt: datetime) -> str:
    lines, shell_recs = _report_header(records, events, since_dt)
    if not shell_recs:
        return "\n".join(lines) + "\n"

    before_counts = _build_cmd_before_section(lines, shell_recs)
    _build_cmd_after_section(lines, shell_recs)
    _build_loop_canonical_section(lines, shell_recs)
    _build_duration_section(lines, shell_recs)

    lines += ["## Classification", ""]
    add_classification(lines, before_counts)

    return "\n".join(lines) + "\n"


def _report_header(records: list, events: list, since_dt: datetime) -> tuple:
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
    return lines, shell_recs


def _build_cmd_before_section(lines: list, shell_recs: list) -> dict:
    before_counts: dict = defaultdict(list)
    for r in shell_recs:
        before_counts[r["cmd_before"]].append(r)
    top_before = sorted(before_counts.items(), key=lambda x: -len(x[1]))[:25]

    lines += ["## cmd_before Histogram (top 25)", "",
              "| Rank | Token | Count | % | Example commands |",
              "|---|---|---|---|---|"]
    for rank, (tok, recs) in enumerate(top_before, 1):
        pct = 100 * len(recs) / len(shell_recs)
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
    return before_counts


def _build_cmd_after_section(lines: list, shell_recs: list) -> None:
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


def _build_loop_canonical_section(lines: list, shell_recs: list) -> None:
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


def _build_duration_section(lines: list, shell_recs: list) -> None:
    n = len(shell_recs)
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
