# INFRASTRUCTURE
import json
import sys
from pathlib import Path

from dev.pdf_conversion_qa.config import (
    MANIFEST_FILE,
    REFERENCE_DIR,
    REFERENCE_SUMMARY_FILE,
    WHOLE_SAMPLE_PAGES,
    WISE_DIR,
)
from dev.pdf_conversion_qa.text_metrics import page_profile, pdftotext_pages


# ORCHESTRATOR
def extract_reference_workflow() -> None:
    windows = json.loads(MANIFEST_FILE.read_text())["windows"]
    window_summaries = [extract_window(window) for window in windows]
    whole_summaries = [extract_whole(pdf) for pdf in sorted(WISE_DIR.glob("*.pdf"))]
    write_summary(window_summaries, whole_summaries)
    print(summary_line(window_summaries, whole_summaries))


# FUNCTIONS
def extract_window(window: dict) -> dict:
    pages = pdftotext_pages(Path(window["slice_pdf"]))
    profiles = [page_profile(text) for text in pages]
    write_reference(REFERENCE_DIR / "windows" / f"{window['window_id']}.json", {str(i + 1): text for i, text in enumerate(pages)})
    return {
        "window_id": window["window_id"],
        "n_pages_manifest": window["n_pages"],
        "n_pages_reference": len(pages),
        "profiles": profiles,
        "eligible_pages": [i + 1 for i, profile in enumerate(profiles) if profile["eligible"]],
    }


def extract_whole(pdf: Path) -> dict:
    pages = pdftotext_pages(pdf)
    profiles = [page_profile(text) for text in pages]
    eligible = [i + 1 for i, profile in enumerate(profiles) if profile["eligible"]]
    sampled = evenly_spaced(eligible, WHOLE_SAMPLE_PAGES)
    write_reference(REFERENCE_DIR / "whole" / f"{pdf.stem}.json", {str(page): pages[page - 1] for page in sampled})
    return {
        "stem": pdf.stem,
        "n_pages_reference": len(pages),
        "n_eligible_pages": len(eligible),
        "sampled_pages": sampled,
    }


def evenly_spaced(items: list[int], count: int) -> list[int]:
    if len(items) <= count:
        return items
    return [items[round(index * (len(items) - 1) / (count - 1))] for index in range(count)]


def write_reference(path: Path, pages: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pages, ensure_ascii=False))


def write_summary(window_summaries: list[dict], whole_summaries: list[dict]) -> None:
    REFERENCE_SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE_SUMMARY_FILE.write_text(json.dumps({"windows": window_summaries, "whole": whole_summaries}, ensure_ascii=False))


def summary_line(window_summaries: list[dict], whole_summaries: list[dict]) -> str:
    pages = sum(s["n_pages_reference"] for s in window_summaries)
    eligible = sum(len(s["eligible_pages"]) for s in window_summaries)
    mismatched = [s["window_id"] for s in window_summaries if s["n_pages_manifest"] != s["n_pages_reference"]]
    whole_pages = sum(s["n_pages_reference"] for s in whole_summaries)
    return f"windows pages={pages} eligible={eligible} page_count_mismatch={mismatched} whole_docs={len(whole_summaries)} whole_pages={whole_pages}"


if __name__ == "__main__":
    sys.exit(extract_reference_workflow())
