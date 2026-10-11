# INFRASTRUCTURE
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from dev.pdf_conversion_qa.config import (
    CHEAP_CANDIDATES,
    MINERU_BIN,
    MINERU_CANDIDATES,
    MINERU_ENV,
    PATCH_DIR,
    RUNS_DIR,
    TESSDATA_DIR,
    VENV_PYTHON,
    WINDOW_TIMEOUT_BASE_S,
    WINDOW_TIMEOUT_PER_PAGE_S,
    WHOLE_TIMEOUT_S,
)
from dev.pdf_conversion_qa.runner import mineru_lock, run_monitored, teardown_fast_api

ROOT_PACKAGE_DIR = Path(__file__).resolve().parents[2]
LOG_TAIL_BYTES = 60000
CHEAP_WINDOW_TIMEOUT_S = 900
MINERU_SAMPLE_INTERVAL_S = 1.0
MINERU_FOOTPRINT_INTERVAL_S = 3.0
CHEAP_SAMPLE_INTERVAL_S = 0.2
CHEAP_FOOTPRINT_INTERVAL_S = 0.2
FAILURE_PATTERNS = (
    ("detokenizer_unicode_decode", re.compile(r"UnicodeDecodeError")),
    ("import_error", re.compile(r"ImportError|ModuleNotFoundError")),
    ("hf_network_unreachable", re.compile(r"ProxyError|huggingface_hub.*(Connect|Offline)|LocalEntryNotFoundError")),
    ("connection_refused", re.compile(r"All connection attempts failed|Connection refused")),
    ("out_of_memory", re.compile(r"out of memory|OutOfMemory|MemoryError", re.IGNORECASE)),
)
RESULT_PREFIX = "QA_WORKER_RESULT "


# FUNCTIONS
def run_window(candidate: str, window: dict, rep: int, scope: str) -> dict:
    run_dir = RUNS_DIR / scope / candidate / window["window_id"] / f"rep{rep}"
    run_dir.mkdir(parents=True, exist_ok=True)
    pdf = Path(window["slice_pdf"]) if scope == "windows" else Path(window["source_pdf"])
    n_pages = window["n_pages"]
    if candidate in MINERU_CANDIDATES:
        measured = run_mineru(candidate, window, pdf, run_dir, n_pages)
    else:
        measured = run_cheap(candidate, window, pdf, run_dir, n_pages, scope)
    return build_row(candidate, window, rep, scope, run_dir, n_pages, measured)


def run_mineru(candidate: str, window: dict, pdf: Path, run_dir: Path, n_pages: int) -> dict:
    spec = MINERU_CANDIDATES[candidate]
    marker = run_dir / "patch_marker.txt"
    marker.unlink(missing_ok=True)
    shutil.rmtree(run_dir / "out", ignore_errors=True)
    (run_dir / "trace.jsonl").unlink(missing_ok=True)
    cmd = [str(MINERU_BIN), "-p", str(pdf.parent), "-o", str(run_dir / "out"), "-b", spec["backend"], "-f", spec["formula"]]
    env = mineru_env(spec["patch"], marker)
    timeout_s = WINDOW_TIMEOUT_BASE_S + WINDOW_TIMEOUT_PER_PAGE_S * n_pages
    with mineru_lock(window["window_id"]):
        measured = run_monitored(cmd, env, run_dir, run_dir / "run.log", run_dir / "trace.jsonl", timeout_s, MINERU_SAMPLE_INTERVAL_S, MINERU_FOOTPRINT_INTERVAL_S)
        measured["fast_api_survivors"] = teardown_fast_api()
    measured["md_path"] = locate_md(run_dir / "out", pdf.stem)
    measured["patch_marker_hits"] = len(marker.read_text().split()) if marker.exists() else 0
    measured["worker"] = {}
    measured["hf_offline"] = True
    return measured


def mineru_env(patched: bool, marker: Path) -> dict:
    env = os.environ.copy()
    env.update(MINERU_ENV)
    if patched:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(PATCH_DIR) + (os.pathsep + existing if existing else "")
        env["QA_DETOKENIZER_PATCH"] = "1"
        env["QA_PATCH_MARKER"] = str(marker)
    return env


def run_cheap(candidate: str, window: dict, pdf: Path, run_dir: Path, n_pages: int, scope: str) -> dict:
    out_md = run_dir / "out.md"
    offsets = run_dir / "offsets.json"
    for stale in (out_md, offsets):
        stale.unlink(missing_ok=True)
    cmd = [
        str(VENV_PYTHON), str(Path(__file__).parent / "cheap_worker.py"),
        "--candidate", candidate, "--pdf", str(pdf), "--out-md", str(out_md),
        "--offsets-json", str(offsets), "--tessdata", str(TESSDATA_DIR),
    ]
    env = os.environ.copy()
    env["TESSDATA_PREFIX"] = str(TESSDATA_DIR)
    env["PYTHONPATH"] = str(ROOT_PACKAGE_DIR)
    timeout_s = CHEAP_WINDOW_TIMEOUT_S if scope == "windows" else WHOLE_TIMEOUT_S
    measured = run_monitored(cmd, env, run_dir, run_dir / "run.log", run_dir / "trace.jsonl", timeout_s, CHEAP_SAMPLE_INTERVAL_S, CHEAP_FOOTPRINT_INTERVAL_S)
    measured["md_path"] = str(out_md) if out_md.exists() else None
    measured["patch_marker_hits"] = 0
    measured["worker"] = parse_worker_result(run_dir / "run.log")
    return measured


def parse_worker_result(log_path: Path) -> dict:
    for line in reversed(read_tail(log_path).splitlines()):
        if line.startswith(RESULT_PREFIX):
            return json.loads(line[len(RESULT_PREFIX):])
    return {}


def locate_md(out_dir: Path, stem: str) -> str | None:
    matches = sorted(out_dir.glob(f"**/{stem}.md"))
    return str(matches[0]) if matches else None


def read_tail(path: Path) -> str:
    if not path.exists():
        return ""
    size = path.stat().st_size
    with path.open("rb") as handle:
        handle.seek(max(0, size - LOG_TAIL_BYTES))
        raw = handle.read()
    return raw.decode("utf-8", errors="replace").replace("\r", "\n")


def classify_failure(measured: dict, run_dir: Path) -> str | None:
    if measured["abort_reason"]:
        return "memory_guard: " + measured["abort_reason"]
    if measured["timed_out"]:
        return "timeout"
    md_path = measured["md_path"]
    if md_path is not None and Path(md_path).stat().st_size > 0:
        return None
    tail = read_tail(run_dir / "run.log")
    for label, pattern in FAILURE_PATTERNS:
        if pattern.search(tail):
            return label
    last_line = next((line.strip() for line in reversed(tail.splitlines()) if line.strip()), "")
    return ("empty_md" if md_path is not None else "no_md") + (f": {last_line[:160]}" if last_line else "")


def log_flags(run_dir: Path) -> dict:
    tail = read_tail(run_dir / "run.log")
    return {"log_has_unicode_error": "UnicodeDecodeError" in tail, "log_has_traceback": "Traceback" in tail}


def md_digest(md_path: str | None) -> tuple[int | None, str | None]:
    if md_path is None:
        return None, None
    data = Path(md_path).read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()[:16]


def build_row(candidate: str, window: dict, rep: int, scope: str, run_dir: Path, n_pages: int, measured: dict) -> dict:
    failure = classify_failure(measured, run_dir)
    md_bytes, md_sha = md_digest(measured["md_path"] if failure is None else measured["md_path"])
    return {
        "scope": scope,
        "candidate": candidate,
        "window_id": window["window_id"],
        "group": window.get("group"),
        "rep": rep,
        "n_pages": n_pages,
        "status": "ok" if failure is None else "fail",
        "failure_reason": failure,
        "wall_s": measured["wall_s"],
        "wall_s_per_page": round(measured["wall_s"] / n_pages, 3),
        "pages_per_s": round(n_pages / measured["wall_s"], 3) if measured["wall_s"] > 0 else None,
        "exit_code": measured["exit_code"],
        "timed_out": measured["timed_out"],
        "peak_footprint_gb": measured["peak_footprint_gb"],
        "min_available_gb": measured["min_available_gb"],
        "start_available_gb": measured["start_available_gb"],
        "load_avg_1m_at_start": measured["load_avg_1m_at_start"],
        "started_at": measured["started_at"],
        "md_path": measured["md_path"],
        "md_bytes": md_bytes,
        "md_sha256_16": md_sha,
        "patch_marker_hits": measured["patch_marker_hits"],
        "fast_api_survivors": measured.get("fast_api_survivors"),
        "hf_offline": measured.get("hf_offline", False),
        "worker": measured["worker"],
        **log_flags(run_dir),
    }
