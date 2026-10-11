# INFRASTRUCTURE
import json
import sys
from collections import Counter
from pathlib import Path

from dev.pdf_conversion_qa.config import CANDIDATE_ORDER_ALL, MANIFEST_FILE, MD_DIR, REFERENCE_DIR, REFERENCE_SUMMARY_FILE, RUN_RESULTS_FILE
from dev.pdf_conversion_qa.text_metrics import SPECIAL_CHARS, UMLAUT_CHARS, normalize, output_for_pages

REPORT_FILE = MD_DIR / "07_char_diagnosis.md"
TOP_LOST = 8
FORMULA_GROUP = "formula"
PARTIAL_CANDIDATE = "C2"


# ORCHESTRATOR
def char_diagnosis_workflow() -> None:
    groups = {w["window_id"]: w["group"] for w in json.loads(MANIFEST_FILE.read_text())["windows"]}
    eligible = {s["window_id"]: s["eligible_pages"] for s in json.loads(REFERENCE_SUMMARY_FILE.read_text())["windows"]}
    rows = [json.loads(line) for line in RUN_RESULTS_FILE.read_text().splitlines() if line.strip()]
    selected = [r for r in rows if r["rep"] == 1 and r["status"] == "ok" and groups[r["window_id"]] != FORMULA_GROUP]
    counters = {candidate: count_chars(candidate, selected, eligible) for candidate in CANDIDATE_ORDER_ALL if candidate != PARTIAL_CANDIDATE}
    MD_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(render(counters, reference_counter(selected, eligible)))
    print(f"written {REPORT_FILE.name}")


# FUNCTIONS
def count_chars(candidate: str, rows: list[dict], eligible: dict) -> Counter:
    total = Counter()
    for row in (r for r in rows if r["candidate"] == candidate):
        md_text = Path(row["md_path"]).read_text(errors="replace")
        text, _ = output_for_pages(row, md_text, eligible[row["window_id"]])
        total.update(normalize(text))
    return total


def reference_counter(rows: list[dict], eligible: dict) -> Counter:
    windows = sorted({r["window_id"] for r in rows if r["candidate"] == "C4a"})
    total = Counter()
    for window in windows:
        pages = json.loads((REFERENCE_DIR / "windows" / f"{window}.json").read_text())
        total.update(normalize("\n".join(pages[str(p)] for p in eligible[window])))
    return total


def render(counters: dict, reference: Counter) -> str:
    chars = SPECIAL_CHARS + UMLAUT_CHARS
    header = "| char | reference | " + " | ".join(counters) + " |\n|" + "---|" * (len(counters) + 2) + "\n"
    body = "".join(f"| {ch} | {reference[ch]} | " + " | ".join(str(counters[c][ch]) for c in counters) + " |\n" for ch in chars)
    lost = "".join(f"- {c}: " + ", ".join(f"{ch!r} {reference[ch] - counters[c][ch]}" for ch, _ in top_lost(reference, counters[c])) + "\n" for c in counters)
    return (
        "# Character diagnosis (text windows, rep 1, eligible pages)\n\n"
        "## Count of special characters and umlauts in the output versus the reference\n\n" + header + body
        + "\n## Most lost characters (reference count minus output count)\n\n" + lost
    )


def top_lost(reference: Counter, output: Counter) -> list[tuple[str, int]]:
    deficits = {ch: reference[ch] - output[ch] for ch in reference if reference[ch] > output[ch]}
    return sorted(deficits.items(), key=lambda item: -item[1])[:TOP_LOST]


if __name__ == "__main__":
    sys.exit(char_diagnosis_workflow())
