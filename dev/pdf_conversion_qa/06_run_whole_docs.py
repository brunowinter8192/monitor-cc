# INFRASTRUCTURE
import json
import sys

from dev.pdf_conversion_qa.candidates import run_window
from dev.pdf_conversion_qa.config import CHEAP_CANDIDATES, REFERENCE_SUMMARY_FILE, WHOLE_RESULTS_FILE, WISE_DIR

REP = 1


# ORCHESTRATOR
def run_whole_docs_workflow() -> None:
    documents = load_documents()
    existing = load_results()
    for document in documents:
        for candidate in CHEAP_CANDIDATES:
            if (candidate, document["window_id"]) in existing:
                continue
            row = run_window(candidate, document, REP, "whole")
            append_result(row)
            print(f"{candidate} {document['window_id']} {row['status']} {row['wall_s']}s {row['pages_per_s']}p/s peak={row['peak_footprint_gb']}GB {row['failure_reason'] or ''}", flush=True)


# FUNCTIONS
def load_documents() -> list[dict]:
    summaries = {s["stem"]: s for s in json.loads(REFERENCE_SUMMARY_FILE.read_text())["whole"]}
    return [
        {
            "window_id": pdf.stem,
            "group": "whole",
            "source_pdf": str(pdf),
            "n_pages": summaries[pdf.stem]["n_pages_reference"],
        }
        for pdf in sorted(WISE_DIR.glob("*.pdf"))
    ]


def load_results() -> set[tuple[str, str]]:
    if not WHOLE_RESULTS_FILE.exists():
        return set()
    rows = [json.loads(line) for line in WHOLE_RESULTS_FILE.read_text().splitlines() if line.strip()]
    return {(row["candidate"], row["window_id"]) for row in rows}


def append_result(row: dict) -> None:
    WHOLE_RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with WHOLE_RESULTS_FILE.open("a") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    sys.exit(run_whole_docs_workflow())
