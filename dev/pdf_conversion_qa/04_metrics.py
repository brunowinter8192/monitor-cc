# INFRASTRUCTURE
import csv
import json
import sys
from pathlib import Path

from dev.pdf_conversion_qa.cleanup_classes import cleanup_class_counts
from dev.pdf_conversion_qa.config import (
    CHEAP_CANDIDATES,
    CSV_DIR,
    MANIFEST_FILE,
    REFERENCE_DIR,
    REFERENCE_SUMMARY_FILE,
    RUN_RESULTS_FILE,
    WHOLE_RESULTS_FILE,
)
from dev.pdf_conversion_qa.text_metrics import output_for_pages, ratio_or_none, recall_counts

WINDOW_METRICS_FILE = CSV_DIR / "04_metrics.csv"
WHOLE_METRICS_FILE = CSV_DIR / "04_metrics_whole.csv"
FORMULA_GROUP = "formula"


# ORCHESTRATOR
def metrics_workflow() -> None:
    groups = {window["window_id"]: window["group"] for window in json.loads(MANIFEST_FILE.read_text())["windows"]}
    eligible = {s["window_id"]: s["eligible_pages"] for s in json.loads(REFERENCE_SUMMARY_FILE.read_text())["windows"]}
    window_rows = [window_metrics(row, groups[row["window_id"]], eligible[row["window_id"]]) for row in read_jsonl(RUN_RESULTS_FILE) if row["status"] == "ok"]
    write_csv(WINDOW_METRICS_FILE, window_rows)
    whole_rows = [whole_metrics(row) for row in read_jsonl(WHOLE_RESULTS_FILE) if row["status"] == "ok"] if WHOLE_RESULTS_FILE.exists() else []
    write_csv(WHOLE_METRICS_FILE, whole_rows)
    print(f"window metric rows={len(window_rows)} whole metric rows={len(whole_rows)}")


# FUNCTIONS
def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def window_metrics(row: dict, group: str, eligible_pages: list[int]) -> dict:
    md_text = Path(row["md_path"]).read_text(errors="replace")
    reference_pages = json.loads((REFERENCE_DIR / "windows" / f"{row['window_id']}.json").read_text())
    reference_text = "\n".join(reference_pages[str(page)] for page in eligible_pages)
    output_text, alignment = output_for_pages(row, md_text, eligible_pages)
    return {
        "candidate": row["candidate"],
        "window_id": row["window_id"],
        "group": group,
        "rep": row["rep"],
        "n_pages": row["n_pages"],
        "indicative": group == FORMULA_GROUP,
        "page_alignment": alignment,
        **recall_columns(recall_counts(reference_text, output_text)),
        **cleanup_class_counts(md_text),
    }


def recall_columns(counts: dict) -> dict:
    return {
        **counts,
        "recall": ratio_or_none(counts["matched_chars"], counts["ref_chars"]),
        "length_ratio": ratio_or_none(counts["out_chars"], counts["ref_chars"]),
        "recall_special": ratio_or_none(counts["matched_special"], counts["ref_special"]),
        "recall_umlaut": ratio_or_none(counts["matched_umlaut"], counts["ref_umlaut"]),
    }


def whole_metrics(row: dict) -> dict:
    md_text = Path(row["md_path"]).read_text(errors="replace")
    offsets = json.loads(Path(row["md_path"]).with_name("offsets.json").read_text())
    sampled = json.loads((REFERENCE_DIR / "whole" / f"{row['window_id']}.json").read_text())
    usable = {page: text for page, text in sampled.items() if int(page) <= len(offsets)}
    reference_text = "\n".join(usable.values())
    output_text = "\n".join(md_text[offsets[int(page) - 1][0]:offsets[int(page) - 1][1]] for page in usable)
    return {
        "candidate": row["candidate"],
        "stem": row["window_id"],
        "n_pages": row["n_pages"],
        "sampled_pages": len(usable),
        "offsets_pages": len(offsets),
        **recall_columns(recall_counts(reference_text, output_text)),
        **cleanup_class_counts(md_text),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    sys.exit(metrics_workflow())
