# INFRASTRUCTURE
import json
import re
import subprocess
import sys
from pathlib import Path

import pymupdf

from dev.pdf_conversion_qa.config import MANIFEST_FILE, SAMPLES_DIR, TRADING_DIR, WISE_DIR

SHORT_PDF_MAX_PAGES = 12
MEDIUM_WINDOWS = {
    "BasnerMcGuireNoiseAndSleepReview2018": (18, 27),
    "Din5008Onlinematerialien": (5, 14),
    "PiesHielscherBeckmannMoralCommitments_2009": (10, 19),
    "PrakashPotoskiVoluntaryEnvironmentalPrograms_2007": (5, 14),
}
BOOK_STEMS = (
    "CoenenbergKostenrechnungKostenanalyse_2016",
    "DeitelIntroPythonDataScience_2020",
    "EwertWagenhoferRohlfingBastianInterneUnternehmensrechnung_2023",
    "GrundeiZaumseilAufsichtsratCorporateGovernance_2012",
    "KuepperControlling_2024",
    "ShefrinBehavioralRiskManagement_2016",
    "WelgeEulerichCorporateGovernanceManagement_2021",
    "WhoEnvironmentalNoiseGuidelinesEurope2018",
    "WhoNightNoiseGuidelinesEurope2009",
)
BOOK_WINDOW_PAGES = 6
BOOK_EARLY_START = 21
KUEPPER_EARLY_START = 3
FORMULA_WINDOWS = {
    "KeKellyXiu2019PredictingReturnsTextData": (40, 48),
    "EfronMorris1975SteinEstimatorDataAnalysis": (1, 10),
    "Tetlock2007GivingContentInvestorSentiment": (1, 8),
}
PANEL_WINDOWS = {
    ("CoenenbergKostenrechnungKostenanalyse_2016", "mid"),
    ("KeKellyXiu2019PredictingReturnsTextData", "formula"),
    ("WelgeEulerichCorporateGovernanceManagement_2021", "early"),
}
EWERT_STEM = "EwertWagenhoferRohlfingBastianInterneUnternehmensrechnung_2023"
EWERT_CRASH_ITEM = 6249
EWERT_TOTAL_ITEMS = 10028
CRASH_WINDOW_PAGES = 8
THREE_BYTE_RANGE = (0x0800, 0x10000)


# ORCHESTRATOR
def build_sample_workflow() -> None:
    specs = build_window_specs()
    crash_info = locate_ewert_crash_windows()
    specs.extend(crash_info["windows"])
    manifest = [slice_window(spec) for spec in specs]
    write_manifest(manifest, crash_info["diagnostics"])
    print(f"windows: {len(manifest)}  pages: {sum(m['n_pages'] for m in manifest)}")


# FUNCTIONS
def source_path(stem: str) -> Path:
    candidate = WISE_DIR / f"{stem}.pdf"
    return candidate if candidate.exists() else TRADING_DIR / f"{stem}.pdf"


def page_count(stem: str) -> int:
    with pymupdf.open(source_path(stem)) as doc:
        return doc.page_count


def build_window_specs() -> list[dict]:
    specs: list[dict] = []
    for pdf in sorted(WISE_DIR.glob("*.pdf")):
        stem = pdf.stem
        total = page_count(stem)
        if stem in BOOK_STEMS:
            specs.extend(book_specs(stem, total))
        elif stem in MEDIUM_WINDOWS:
            first, last = MEDIUM_WINDOWS[stem]
            specs.append(make_spec(stem, first, last, "medium", False, ""))
        elif total <= SHORT_PDF_MAX_PAGES:
            specs.append(make_spec(stem, 1, total, "short", False, ""))
        else:
            raise SystemExit(f"unclassified pdf: {stem} ({total} pages)")
    for stem, (first, last) in FORMULA_WINDOWS.items():
        panel = (stem, "formula") in PANEL_WINDOWS
        specs.append(make_spec(stem, first, last, "formula", panel, ""))
    return specs


def book_specs(stem: str, total: int) -> list[dict]:
    early_first = KUEPPER_EARLY_START if stem.startswith("Kuepper") else BOOK_EARLY_START
    mid_first = total // 2
    early = make_spec(stem, early_first, early_first + BOOK_WINDOW_PAGES - 1, "book_early", (stem, "early") in PANEL_WINDOWS, "")
    mid = make_spec(stem, mid_first, mid_first + BOOK_WINDOW_PAGES - 1, "book_mid", (stem, "mid") in PANEL_WINDOWS, "")
    return [early] if stem == EWERT_STEM else [early, mid]


def make_spec(stem: str, first: int, last: int, group: str, panel: bool, note: str) -> dict:
    short = re.split(r"[_]", stem)[0][:34]
    return {
        "window_id": f"{short}_p{first:04d}-{last:04d}",
        "stem": stem,
        "first_page": first,
        "last_page": last,
        "group": group,
        "panel": panel,
        "note": note,
    }


def locate_ewert_crash_windows() -> dict:
    pdf = source_path(EWERT_STEM)
    blocks = blocks_per_page(pdf)
    three_byte = three_byte_chars_per_page(pdf)
    center = page_at_item_fraction(blocks, EWERT_CRASH_ITEM / EWERT_TOTAL_ITEMS)
    first_a = max(1, center - CRASH_WINDOW_PAGES // 2)
    last_a = min(len(blocks), first_a + CRASH_WINDOW_PAGES - 1)
    first_b = densest_window_start(three_byte, CRASH_WINDOW_PAGES, avoid=(first_a, last_a))
    window_a = make_spec(EWERT_STEM, first_a, last_a, "ewert_crash_item_fraction", False, f"estimated page {center} from item fraction")
    window_b = make_spec(EWERT_STEM, first_b, first_b + CRASH_WINDOW_PAGES - 1, "ewert_crash_dense_chars", False, "densest 3-byte UTF-8 window")
    diagnostics = {
        "ewert_pages": len(blocks),
        "ewert_target_fraction": round(EWERT_CRASH_ITEM / EWERT_TOTAL_ITEMS, 4),
        "ewert_estimated_page": center,
        "ewert_dense_window_start": first_b,
        "ewert_top_dense_pages": sorted(range(1, len(three_byte) + 1), key=lambda p: -three_byte[p - 1])[:8],
    }
    return {"windows": [window_a, window_b], "diagnostics": diagnostics}


def blocks_per_page(pdf: Path) -> list[int]:
    result = subprocess.run(["pdftotext", "-bbox-layout", str(pdf), "-"], capture_output=True, text=True, check=True)
    pages = result.stdout.split("<page ")[1:]
    return [page.count("<block ") for page in pages]


def three_byte_chars_per_page(pdf: Path) -> list[int]:
    result = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True)
    low, high = THREE_BYTE_RANGE
    pages = result.stdout.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return [sum(1 for ch in page if low <= ord(ch) < high) for page in pages]


def page_at_item_fraction(blocks: list[int], fraction: float) -> int:
    total = sum(blocks)
    running = 0
    for index, count in enumerate(blocks, start=1):
        running += count
        if running / total >= fraction:
            return index
    return len(blocks)


def densest_window_start(counts: list[int], width: int, avoid: tuple[int, int]) -> int:
    best_start = 1
    best_score = -1
    for start in range(1, len(counts) - width + 2):
        end = start + width - 1
        if start <= avoid[1] and end >= avoid[0]:
            continue
        score = sum(counts[start - 1:end])
        if score > best_score:
            best_start, best_score = start, score
    return best_start


def slice_window(spec: dict) -> dict:
    window_dir = SAMPLES_DIR / spec["window_id"]
    window_dir.mkdir(parents=True, exist_ok=True)
    target = window_dir / f"{spec['window_id']}.pdf"
    source = source_path(spec["stem"])
    with pymupdf.open(source) as doc:
        total = doc.page_count
        source_encryption = doc.metadata.get("encryption")
        keep = list(range(spec["first_page"] - 1, spec["last_page"]))
        doc.select(keep)
        doc.save(str(target), garbage=2, deflate=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
    with pymupdf.open(target) as sliced:
        slice_pages = sliced.page_count
        slice_encryption = sliced.metadata.get("encryption")
    return {
        **spec,
        "source_pdf": str(source),
        "source_pages_total": total,
        "n_pages": slice_pages,
        "source_encryption": source_encryption,
        "slice_encryption": slice_encryption,
        "slice_pdf": str(target),
        "slice_bytes": target.stat().st_size,
    }


def write_manifest(manifest: list[dict], diagnostics: dict) -> None:
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps({"diagnostics": diagnostics, "windows": manifest}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(build_sample_workflow())
