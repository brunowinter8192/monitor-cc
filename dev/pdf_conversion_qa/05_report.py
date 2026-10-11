# INFRASTRUCTURE
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from dev.pdf_conversion_qa.config import (
    CHEAP_CANDIDATES,
    CSV_DIR,
    JSON_DIR,
    MD_DIR,
    MINERU_CANDIDATES,
    RUN_RESULTS_FILE,
    WHOLE_RESULTS_FILE,
)

REPORT_FILE = MD_DIR / "05_report.md"
SUMMARY_JSON = JSON_DIR / "05_report.json"
CALIBRATION_PREFIX = "TelekomPib"
CLASS_COLUMNS = ("A", "B", "C", "F", "G", "H", "I")
CANDIDATE_ORDER = tuple(MINERU_CANDIDATES) + CHEAP_CANDIDATES
SHORT_FAILURE_LENGTH = 70
PARTIAL_CANDIDATES = ("C2",)
LOW_RECALL = 0.5
TOP_PEAKS = 3


# ORCHESTRATOR
def report_workflow() -> None:
    rows = read_jsonl(RUN_RESULTS_FILE)
    metrics = read_csv(CSV_DIR / "04_metrics.csv")
    whole_rows = read_jsonl(WHOLE_RESULTS_FILE) if WHOLE_RESULTS_FILE.exists() else []
    whole_metrics = read_csv(CSV_DIR / "04_metrics_whole.csv")
    floors = startup_floors(rows)
    sections = [
        "# PDF conversion QA - M1 measurements\n",
        section_scope(rows, whole_rows),
        section_startup(rows, floors),
        section_results(rows, floors),
        section_failures(rows),
        section_quality(metrics, rows, False),
        section_quality(metrics, rows, True),
        section_silent_loss(metrics),
        section_cleanup(metrics),
        section_peaks(rows),
        section_group_speed(rows),
        section_stability(rows),
        section_cheap_timing(rows),
        section_whole(whole_rows, whole_metrics),
    ]
    MD_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(sections))
    SUMMARY_JSON.write_text(json.dumps({"startup_floors": floors}, indent=1))
    print(f"report written: {REPORT_FILE.name}, {len(rows)} window rows, {len(whole_rows)} whole rows")


# FUNCTIONS
def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def read_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open() as handle:
        return list(csv.DictReader(handle))


def md_table(headers: list[str], body: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join("" if cell is None else str(cell) for cell in row) + " |" for row in body]
    return "\n".join(lines) + "\n"


def number(value, digits: int = 2):
    return None if value is None else round(value, digits)


def to_float(value: str):
    return float(value) if value not in ("", None) else None


def sample_rows(rows: list[dict], candidate: str) -> list[dict]:
    return [r for r in rows if r["candidate"] == candidate and r["rep"] == 1]


def startup_floors(rows: list[dict]) -> dict:
    floors = {}
    for candidate in CANDIDATE_ORDER:
        walls = [r["wall_s"] for r in rows if r["candidate"] == candidate and r["window_id"].startswith(CALIBRATION_PREFIX) and r["status"] == "ok"]
        floors[candidate] = statistics.median(walls) if len(walls) >= 3 else None
    return floors


def section_scope(rows: list[dict], whole_rows: list[dict]) -> str:
    windows = {r["window_id"] for r in rows}
    pages = sum(next(r["n_pages"] for r in rows if r["window_id"] == w) for w in windows)
    counts = Counter(r["candidate"] for r in rows)
    return (
        "## Scope\n\n"
        f"{len(windows)} windows, {pages} pages. Result rows per candidate: "
        + ", ".join(f"{c} {counts[c]}" for c in CANDIDATE_ORDER if counts[c])
        + f". Whole-document rows: {len(whole_rows)}.\n"
    )


def section_startup(rows: list[dict], floors: dict) -> str:
    body = []
    for candidate in CANDIDATE_ORDER:
        walls = [r["wall_s"] for r in rows if r["candidate"] == candidate and r["window_id"].startswith(CALIBRATION_PREFIX)]
        if walls:
            body.append([candidate, len(walls), walls, number(floors[candidate])])
    return "## Startup floor (1-page PDF, 3 runs)\n\n" + md_table(["candidate", "runs", "wall_s each", "median_s"], body)


def section_results(rows: list[dict], floors: dict) -> str:
    body = []
    for candidate in CANDIDATE_ORDER:
        sample = sample_rows(rows, candidate)
        if not sample:
            continue
        ok = [r for r in sample if r["status"] == "ok"]
        pages_ok = sum(r["n_pages"] for r in ok)
        wall_ok = sum(r["wall_s"] for r in ok)
        floor = floors[candidate] or 0.0
        net = sum(max(r["wall_s"] - floor, 0.0) for r in ok)
        peaks = [r["peak_footprint_gb"] for r in ok]
        avail = [r["min_available_gb"] for r in sample if r["min_available_gb"] is not None]
        body.append([
            candidate, f"{len(ok)}/{len(sample)}", f"{100 * len(ok) / len(sample):.0f}%",
            number(wall_ok / pages_ok, 3) if pages_ok else None,
            number(net / pages_ok, 3) if pages_ok else None,
            number(statistics.median(r["wall_s"] / r["n_pages"] for r in ok), 3) if ok else None,
            number(statistics.median(peaks)) if peaks else None,
            number(max(peaks)) if peaks else None,
            number(min(avail)) if avail else None,
        ])
    headers = ["candidate", "ok", "success", "s/page pooled", "s/page minus startup", "s/page median window", "peak GB median", "peak GB max", "min available GB"]
    return "## Results per candidate (one run per window, rep 1, ok windows for speed)\n\n" + md_table(headers, body)


def section_failures(rows: list[dict]) -> str:
    failed = [r for r in rows if r["status"] == "fail"]
    reasons = defaultdict(Counter)
    for r in failed:
        reasons[r["candidate"]][(r["failure_reason"] or "")[:SHORT_FAILURE_LENGTH]] += 1
    body = [[c, reason, count] for c in CANDIDATE_ORDER for reason, count in reasons[c].most_common()]
    detail = [[r["candidate"], r["window_id"], r["rep"], r["n_pages"], r["wall_s"], r["peak_footprint_gb"], (r["failure_reason"] or "")[:SHORT_FAILURE_LENGTH]] for r in failed]
    return (
        "## Failures by reason (all reps)\n\n" + (md_table(["candidate", "reason", "rows"], body) if body else "none\n")
        + "\n### Failed rows\n\n" + (md_table(["candidate", "window", "rep", "pages", "wall_s", "peak_GB", "reason"], detail) if detail else "none\n")
    )


def pooled(metric_rows: list[dict], matched: str, ref: str):
    denominator = sum(float(r[ref]) for r in metric_rows)
    return number(sum(float(r[matched]) for r in metric_rows) / denominator, 4) if denominator else None


def quality_row(candidate: str, metric_rows: list[dict]) -> list:
    return [
        candidate, len(metric_rows),
        pooled(metric_rows, "matched_chars", "ref_chars"),
        pooled(metric_rows, "matched_special", "ref_special"),
        pooled(metric_rows, "matched_umlaut", "ref_umlaut"),
        pooled(metric_rows, "out_chars", "ref_chars"),
        int(sum(float(r["ref_special"]) for r in metric_rows)),
        int(sum(float(r["ref_umlaut"]) for r in metric_rows)),
    ]


def common_windows(metrics: list[dict], formula: bool) -> set:
    per_candidate = []
    for candidate in (c for c in CANDIDATE_ORDER if c not in PARTIAL_CANDIDATES):
        ids = {r["window_id"] for r in metrics if r["candidate"] == candidate and r["rep"] == "1" and (r["indicative"] == "True") == formula}
        if ids:
            per_candidate.append(ids)
    return set.intersection(*per_candidate) if per_candidate else set()


def section_quality(metrics: list[dict], rows: list[dict], formula: bool) -> str:
    common = common_windows(metrics, formula)
    body_all, body_common = [], []
    for candidate in CANDIDATE_ORDER:
        selected = [r for r in metrics if r["candidate"] == candidate and r["rep"] == "1" and (r["indicative"] == "True") == formula]
        if selected:
            body_all.append(quality_row(candidate, selected))
            if candidate not in PARTIAL_CANDIDATES:
                body_common.append(quality_row(candidate, [r for r in selected if r["window_id"] in common]))
    headers = ["candidate", "windows", "recall", "recall special", "recall umlaut", "out/ref length", "ref special chars", "ref umlauts"]
    title = "formula windows (indicative only)" if formula else "text windows"
    return (
        f"## Character recall vs pdftotext layer, {title}\n\n"
        "Pooled (sum matched / sum reference) over ok windows of each candidate.\n\n" + md_table(headers, body_all)
        + f"\nSame, restricted to the {len(common)} windows measured by every candidate except C2 (C2 ran only on the panel).\n\n" + md_table(headers, body_common)
    )


def section_silent_loss(metrics: list[dict]) -> str:
    body = []
    for candidate in CANDIDATE_ORDER:
        low = [r for r in metrics if r["candidate"] == candidate and r["rep"] == "1" and to_float(r["recall"]) is not None and to_float(r["recall"]) < LOW_RECALL]
        if any(r["candidate"] == candidate for r in metrics):
            body.append([candidate, len(low), "; ".join(f"{r['window_id'][:28]} {to_float(r['recall']):.2f}" for r in low)])
    return f"## Status ok but recall below {LOW_RECALL} (silent content loss, rep 1, includes formula windows)\n\n" + md_table(["candidate", "windows", "which"], body)


def section_peaks(rows: list[dict]) -> str:
    body = []
    for candidate in MINERU_CANDIDATES:
        top = sorted((r for r in rows if r["candidate"] == candidate), key=lambda r: -r["peak_footprint_gb"])[:TOP_PEAKS]
        body += [[candidate, r["window_id"][:40], r["n_pages"], r["peak_footprint_gb"], r["min_available_gb"], r["wall_s"]] for r in top]
    return "## Highest process-tree peaks of the MinerU candidates\n\n" + md_table(["candidate", "window", "pages", "peak GB", "min available GB", "wall_s"], body)


def section_cleanup(metrics: list[dict]) -> str:
    body = []
    for candidate in CANDIDATE_ORDER:
        selected = [r for r in metrics if r["candidate"] == candidate and r["rep"] == "1"]
        if not selected:
            continue
        pages = sum(int(r["n_pages"]) for r in selected)
        totals = [int(sum(float(r[c]) for r in selected)) for c in CLASS_COLUMNS]
        j_total = int(sum(float(r["J_long_lines"]) + float(r["J_long_blocks"]) for r in selected))
        i_big = int(sum(float(r["I_over_2000"]) for r in selected))
        fffd = int(sum(float(r["A_replacement_char"]) for r in selected))
        body.append([candidate, pages] + totals + [fffd, j_total, i_big])
    headers = ["candidate", "pages"] + list(CLASS_COLUMNS) + ["A: U+FFFD", "J (lines+blocks >1000)", "I >2000"]
    return "## Cleanup class counts (SKILL regexes, totals over ok windows, rep 1)\n\n" + md_table(headers, body)


def section_group_speed(rows: list[dict]) -> str:
    groups = sorted({r["group"] for r in rows})
    body = []
    for candidate in CANDIDATE_ORDER:
        sample = [r for r in sample_rows(rows, candidate) if r["status"] == "ok"]
        if not sample:
            continue
        cells = []
        for group in groups:
            selected = [r for r in sample if r["group"] == group]
            cells.append(number(sum(r["wall_s"] for r in selected) / sum(r["n_pages"] for r in selected), 3) if selected else None)
        body.append([candidate] + cells)
    return "## Pooled wall seconds per page by window group (ok windows)\n\n" + md_table(["candidate"] + groups, body)


def section_stability(rows: list[dict]) -> str:
    grouped = defaultdict(list)
    for r in rows:
        if r["candidate"] in MINERU_CANDIDATES:
            grouped[(r["candidate"], r["window_id"])].append(r)
    body = []
    for (candidate, window), items in sorted(grouped.items()):
        if len(items) < 2 or window.startswith(CALIBRATION_PREFIX):
            continue
        items.sort(key=lambda r: r["rep"])
        body.append([
            candidate, window, len(items), "/".join(r["status"] for r in items),
            "/".join(str(r["wall_s"]) for r in items),
            "/".join(str(r["peak_footprint_gb"]) for r in items),
            len({r["md_sha256_16"] for r in items if r["md_sha256_16"]}),
        ])
    return "## Stability panel (MinerU candidates, repeated windows)\n\n" + (md_table(["candidate", "window", "runs", "status", "wall_s", "peak GB", "distinct md hashes"], body) if body else "none\n") + hash_comparison(rows)


def hash_comparison(rows: list[dict]) -> str:
    by_key = {(r["candidate"], r["window_id"], r["rep"]): r for r in rows}
    body = []
    for (candidate, window, rep), r in sorted(by_key.items()):
        other = by_key.get(("C1", window, rep))
        if candidate == "C2" and other is not None:
            body.append([window, rep, other["status"], r["status"], other["md_sha256_16"], r["md_sha256_16"], "identical" if other["md_sha256_16"] == r["md_sha256_16"] and r["md_sha256_16"] else "different"])
    return "\n### C1 vs C2 output hash\n\n" + (md_table(["window", "rep", "C1", "C2", "C1 sha", "C2 sha", "md"], body) if body else "none\n")


def section_cheap_timing(rows: list[dict]) -> str:
    body = []
    for candidate in CHEAP_CANDIDATES:
        per_rep = []
        for rep in (1, 2, 3):
            selected = [r for r in rows if r["candidate"] == candidate and r["rep"] == rep and r["status"] == "ok"]
            if selected:
                per_rep.append(sum(r["wall_s"] for r in selected) / sum(r["n_pages"] for r in selected))
        if per_rep:
            body.append([candidate, " / ".join(f"{v:.4f}" for v in per_rep), number(statistics.median(per_rep), 4), number(max(per_rep) / min(per_rep), 3)])
    return "## Timing of cheap candidates, n=3 (pooled s/page per full pass)\n\n" + md_table(["candidate", "pass 1 / 2 / 3", "median", "max/min"], body)


def section_whole(whole_rows: list[dict], whole_metrics: list[dict]) -> str:
    if not whole_rows:
        return "## Whole documents\n\nnot run\n"
    recall_by_key = {(m["candidate"], m["stem"]): m for m in whole_metrics}
    summary = []
    for candidate in CHEAP_CANDIDATES:
        selected = [r for r in whole_rows if r["candidate"] == candidate]
        ok = [r for r in selected if r["status"] == "ok"]
        if not selected:
            continue
        pages = sum(r["n_pages"] for r in ok)
        wall = sum(r["wall_s"] for r in ok)
        metrics = [recall_by_key[(candidate, r["window_id"])] for r in ok if (candidate, r["window_id"]) in recall_by_key]
        summary.append([
            candidate, f"{len(ok)}/{len(selected)}", pages, number(wall, 1), number(pages / wall, 2) if wall else None,
            number(max((r["peak_footprint_gb"] for r in ok), default=0)), number(min((r["min_available_gb"] for r in ok if r["min_available_gb"] is not None), default=0)),
            pooled(metrics, "matched_chars", "ref_chars") if metrics else None,
        ])
    detail = []
    for r in sorted(whole_rows, key=lambda x: (x["window_id"], CANDIDATE_ORDER.index(x["candidate"]))):
        metric = recall_by_key.get((r["candidate"], r["window_id"]), {})
        detail.append([
            r["window_id"][:34], r["n_pages"], r["candidate"], r["status"], r["wall_s"], r["pages_per_s"], r["peak_footprint_gb"],
            r["worker"].get("pages_out"), to_float(metric.get("recall")), (r["failure_reason"] or "")[:SHORT_FAILURE_LENGTH],
        ])
    return (
        "## Whole documents (21 wise2627 PDFs, one run per candidate)\n\n"
        + md_table(["candidate", "ok", "pages", "wall_s", "pages/s", "peak GB max", "min available GB", "recall (5 sampled pages/doc)"], summary)
        + "\n### Per document\n\n"
        + md_table(["document", "pages", "candidate", "status", "wall_s", "pages/s", "peak GB", "pages_out", "recall", "failure"], detail)
    )


if __name__ == "__main__":
    sys.exit(report_workflow())
