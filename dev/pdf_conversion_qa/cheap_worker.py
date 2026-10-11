# INFRASTRUCTURE
import argparse
import json
import resource
import sys
import time
from pathlib import Path

RESULT_PREFIX = "QA_WORKER_RESULT "
LITEPARSE_OCR_LANGUAGE = "deu"
PYMUPDF_OCR_LANGUAGE = "deu+eng"


# ORCHESTRATOR
def cheap_worker_workflow() -> None:
    args = parse_args()
    t_start = time.monotonic()
    converter = load_converter(args.candidate, args.tessdata)
    t_loaded = time.monotonic()
    page_texts = converter(args.pdf)
    t_done = time.monotonic()
    write_outputs(page_texts, Path(args.out_md), Path(args.offsets_json))
    print(RESULT_PREFIX + json.dumps({
        "import_s": round(t_loaded - t_start, 3),
        "convert_s": round(t_done - t_loaded, 3),
        "pages_out": len(page_texts),
        "chars_out": sum(len(text) for text in page_texts),
        **peak_rss_bytes(),
    }))


# FUNCTIONS
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, choices=["C4a", "C4b", "C5a", "C5b"])
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--offsets-json", required=True)
    parser.add_argument("--tessdata", required=True)
    return parser.parse_args()


def load_converter(candidate: str, tessdata: str):
    if candidate == "C4a":
        return pymupdf4llm_legacy()
    if candidate == "C4b":
        return pymupdf4llm_layout()
    if candidate == "C5a":
        return liteparse_converter(ocr_enabled=False, tessdata=tessdata)
    return liteparse_converter(ocr_enabled=True, tessdata=tessdata)


def pymupdf4llm_legacy():
    import pymupdf4llm

    pymupdf4llm.use_layout(False)

    def convert(pdf: str) -> list[str]:
        chunks = pymupdf4llm.to_markdown(pdf, page_chunks=True)
        return [chunk["text"] for chunk in chunks]

    return convert


def pymupdf4llm_layout():
    import pymupdf4llm

    def convert(pdf: str) -> list[str]:
        chunks = pymupdf4llm.to_markdown(pdf, page_chunks=True, use_ocr=True, ocr_language=PYMUPDF_OCR_LANGUAGE)
        return [chunk["text"] for chunk in chunks]

    return convert


def liteparse_converter(ocr_enabled: bool, tessdata: str):
    from liteparse import LiteParse

    if ocr_enabled:
        parser = LiteParse(ocr_enabled=True, ocr_language=LITEPARSE_OCR_LANGUAGE, tessdata_path=tessdata, quiet=True, output_format="markdown")
    else:
        parser = LiteParse(ocr_enabled=False, quiet=True, output_format="markdown")

    def convert(pdf: str) -> list[str]:
        result = parser.parse(pdf)
        return [page.markdown or "" for page in result.pages]

    return convert


def peak_rss_bytes() -> dict:
    return {
        "maxrss_self_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "maxrss_children_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    }


def write_outputs(page_texts: list[str], out_md: Path, offsets_json: Path) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    offsets = []
    position = 0
    parts = []
    for text in page_texts:
        chunk = text if text.endswith("\n") else text + "\n"
        offsets.append([position, position + len(chunk)])
        parts.append(chunk)
        position += len(chunk)
    out_md.write_text("".join(parts))
    offsets_json.write_text(json.dumps(offsets))


if __name__ == "__main__":
    sys.exit(cheap_worker_workflow())
