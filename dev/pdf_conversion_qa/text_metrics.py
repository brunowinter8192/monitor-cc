# INFRASTRUCTURE
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path

SPECIAL_CHARS = "§„“”–—€"
UMLAUT_CHARS = "äöüÄÖÜß"
MIN_REFERENCE_CHARS = 200
MAX_REPLACEMENT_RATIO = 0.01
REPLACEMENT_CHAR = "�"
WHITESPACE_RE = re.compile(r"\s+")


# FUNCTIONS
def normalize(text: str) -> str:
    return WHITESPACE_RE.sub("", unicodedata.normalize("NFKC", text))


def pdftotext_pages(pdf: Path, first_page: int | None = None, last_page: int | None = None) -> list[str]:
    cmd = ["pdftotext"]
    if first_page is not None:
        cmd += ["-f", str(first_page), "-l", str(last_page)]
    result = subprocess.run(cmd + [str(pdf), "-"], capture_output=True, check=True)
    pages = result.stdout.decode("utf-8", errors="replace").split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages


def page_profile(text: str) -> dict:
    normalized = normalize(text)
    replacement = normalized.count(REPLACEMENT_CHAR)
    ratio = replacement / len(normalized) if normalized else 0.0
    return {
        "chars": len(normalized),
        "replacement_ratio": round(ratio, 5),
        "eligible": len(normalized) >= MIN_REFERENCE_CHARS and ratio < MAX_REPLACEMENT_RATIO,
    }


def recall_counts(reference_text: str, output_text: str) -> dict:
    reference = Counter(normalize(reference_text))
    output = Counter(normalize(output_text))
    return {
        "ref_chars": sum(reference.values()),
        "out_chars": sum(output.values()),
        "matched_chars": overlap(reference, output, None),
        "ref_special": overlap(reference, reference, SPECIAL_CHARS),
        "matched_special": overlap(reference, output, SPECIAL_CHARS),
        "ref_umlaut": overlap(reference, reference, UMLAUT_CHARS),
        "matched_umlaut": overlap(reference, output, UMLAUT_CHARS),
    }


def overlap(reference: Counter, output: Counter, subset: str | None) -> int:
    chars = reference.keys() if subset is None else [ch for ch in subset if ch in reference]
    return sum(min(reference[ch], output.get(ch, 0)) for ch in chars)


def ratio_or_none(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None
